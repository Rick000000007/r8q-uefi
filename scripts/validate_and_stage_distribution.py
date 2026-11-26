#!/usr/bin/env python3
"""Project R8Q — Distribution Validation & Consolidated Staging Utility.

Validates all upstream CI workflow artifacts (presence, SHA-256 manifests,
deep binary/container structural integrity, and cross-artifact provenance),
assembles a complete self-contained release distribution tree, generates
BUILD-INVENTORY.{json,md} and SHA256SUMS.dist manifests, and verifies every
staged output before uploading the consolidated CI distribution bundle.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile

PAGE_SIZE = 4096
FIRMWARE_EXPECTED_SIZE = 4194304
ESP_EXPECTED_SIZE = 268435456
MAX_SDA24_CAPACITY = 82694144
ROOTFS_TAR_MIN_SIZE = 30 * 1024 * 1024
INITRAMFS_MIN_CPIO_BYTES = 1024 * 1024

REQUIRED_ARTIFACTS = [
    "r8q-uefi-firmware-volume",
    "r8q-boot-manager-and-setup",
    "r8q-kernel-and-dtb",
    "r8q-initramfs",
    "r8q-debian12-rootfs",
    "r8q-debian12-rootfs-meta",
    "r8q-esp",
    "r8q-complete-boot-img",
    "r8q-full-system-distribution",
    "r8q-recovery-installer-zip",
]

REQUIRED_EFI_APPS = [
    "Setup",
    "BootManager",
    "Shell",
    "LinuxBoot",
    "sysinfo",
    "cpuinfo",
    "memmap",
    "diagnostics",
    "storage",
    "display",
    "battery",
    "thermal",
    "fdtinfo",
    "firmware",
    "CoreTest",
    "StorageTest",
    "ShellTest",
]

REQUIRED_DOCS = [
    "README.md",
    "INSTALLATION.md",
    "INSTALLATION-USB.md",
    "INSTALLER-AUDIT.md",
    "BOOT-ARCHITECTURE.md",
    "HARDWARE-COMPATIBILITY.md",
    "PARTITION-LAYOUT.md",
    "RECOVERY.md",
    "TROUBLESHOOTING.md",
    "BUILD-MANIFEST.md",
]


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_sha256_manifest(manifest_path: str) -> dict[str, str]:
    """Parse standard sha256sum output lines into {relative_path: hex_digest}."""
    entries: dict[str, str] = {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2 or len(parts[0]) != 64:
                raise ValueError(f"Malformed checksum line {line_no} in {manifest_path}: {raw!r}")
            digest = parts[0].lower()
            target = parts[1].lstrip("*").strip()
            entries[target] = digest
    if not entries:
        raise ValueError(f"Empty checksum manifest: {manifest_path}")
    return entries


def verify_manifest_entries(base_dir: str, manifest_path: str) -> dict[str, str]:
    """Verify every digest entry inside a manifest file relative to base_dir."""
    entries = parse_sha256_manifest(manifest_path)
    for rel_path, expected in entries.items():
        full_path = os.path.join(base_dir, rel_path)
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"Manifest {manifest_path} references missing file: {full_path}")
        actual = sha256_file(full_path)
        if actual != expected:
            raise AssertionError(
                f"SHA-256 mismatch in {manifest_path} for {rel_path}: expected {expected}, got {actual}"
            )
    return entries


def verify_pe32plus_aarch64(path: str) -> None:
    """Validate MZ + PE32+ AArch64 (0xAA64) header on UEFI EFI binaries."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 0x100 or data[:2] != b"MZ":
        raise AssertionError(f"{path}: invalid or missing MZ signature")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 6 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\x00\x00":
        raise AssertionError(f"{path}: invalid PE signature at 0x{pe_offset:x}")
    machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
    if machine != 0xAA64:
        raise AssertionError(f"{path}: expected AArch64 machine 0xAA64, got 0x{machine:04X}")


def validate_fdt_bytes(data: bytes, label: str) -> None:
    """Validate FDT v17 magic, version, and total length."""
    if len(data) < 40:
        raise AssertionError(f"{label}: DTB too short ({len(data)} bytes)")
    magic, totalsize, _, _, _, version = struct.unpack_from(">6I", data, 0)
    if magic != 0xD00DFEED:
        raise AssertionError(f"{label}: invalid FDT magic 0x{magic:08X}")
    if version != 17:
        raise AssertionError(f"{label}: expected FDT version 17, got {version}")
    if totalsize != len(data):
        raise AssertionError(f"{label}: FDT totalsize ({totalsize}) != buffer length ({len(data)})")


def parse_cpio_newc_names(cpio_bytes: bytes) -> set[str]:
    """Parse ASCII newc (070701) CPIO archive member paths."""
    names: set[str] = set()
    pos = 0
    total = len(cpio_bytes)
    while pos + 110 <= total:
        magic = cpio_bytes[pos : pos + 6]
        if magic != b"070701":
            raise AssertionError(f"Invalid CPIO newc magic at offset {pos}: {magic!r}")
        filesize = int(cpio_bytes[pos + 54 : pos + 62], 16)
        namesize = int(cpio_bytes[pos + 94 : pos + 102], 16)
        name_start = pos + 110
        name_end = name_start + namesize
        if name_end > total:
            raise AssertionError("Truncated CPIO filename header")
        raw_name = cpio_bytes[name_start : name_end - 1].decode("utf-8", errors="replace")
        if raw_name == "TRAILER!!!":
            break
        names.add(raw_name.lstrip("./") or ".")
        data_start = align_up(name_end, 4)
        pos = align_up(data_start + filesize, 4)
    if not names:
        raise AssertionError("CPIO archive contained zero entries")
    return names


def mcopy_read(esp_path: str, fat_path: str) -> bytes:
    """Extract a single file from FAT32 ESP partition via mtools mcopy."""
    return subprocess.check_output(["mcopy", "-i", f"{esp_path}@@1M", fat_path, "-"])


def validate_esp(esp_path: str, efi_hashes: dict[str, str], kernel_sha: str, initrd_sha: str, r8q_dtb_sha: str) -> None:
    """Validate GPT/FAT32 ESP geometry and exact SHA-256 provenance of embedded payloads."""
    esp_size = os.path.getsize(esp_path)
    if esp_size != ESP_EXPECTED_SIZE:
        raise AssertionError(f"ESP size {esp_size} != {ESP_EXPECTED_SIZE}")

    with open(esp_path, "rb") as f:
        hdr = f.read(1024)
    if hdr[510:512] != b"\x55\xaa":
        raise AssertionError("ESP missing MBR 0x55AA signature")
    if hdr[512:520] != b"EFI PART":
        raise AssertionError("ESP missing GPT 'EFI PART' header")

    bare = subprocess.check_output(
        ["mdir", "-b", "-i", f"{esp_path}@@1M", "::", "::/EFI/BOOT", "::/EFI/R8Q", "::/EFI/R8Q/Config"],
        text=True,
    )
    bare_lower = {line.strip().lower() for line in bare.splitlines() if line.strip()}
    required_paths = [
        "::/efi/boot/bootaa64.efi",
        "::/efi/r8q/bootmanager.efi",
        "::/efi/r8q/setup.efi",
        "::/efi/r8q/shell.efi",
        "::/efi/r8q/linuxboot.efi",
        "::/efi/r8q/image",
        "::/efi/r8q/initramfs.img",
        "::/efi/r8q/r8q.dtb",
        "::/efi/r8q/config/boot.cfg",
        "::/startup.nsh",
    ]
    for req in required_paths:
        if req not in bare_lower:
            raise AssertionError(f"ESP missing required FAT32 path: {req}")

    expected_esp_payloads = {
        "::EFI/BOOT/BOOTAA64.EFI": efi_hashes["BootManager.efi"],
        "::EFI/R8Q/BootManager.efi": efi_hashes["BootManager.efi"],
        "::EFI/R8Q/Setup.efi": efi_hashes["Setup.efi"],
        "::EFI/R8Q/Shell.efi": efi_hashes["Shell.efi"],
        "::EFI/R8Q/LinuxBoot.efi": efi_hashes["LinuxBoot.efi"],
        "::EFI/R8Q/Image": kernel_sha,
        "::EFI/R8Q/initramfs.img": initrd_sha,
        "::EFI/R8Q/r8q.dtb": r8q_dtb_sha,
    }
    for fat_path, expected_sha in expected_esp_payloads.items():
        actual_sha = sha256_bytes(mcopy_read(esp_path, fat_path))
        if actual_sha != expected_sha:
            raise AssertionError(
                f"Stale or mismatched ESP payload {fat_path}: expected {expected_sha}, got {actual_sha}"
            )
    if not mcopy_read(esp_path, "::startup.nsh").strip():
        raise AssertionError("ESP ::startup.nsh is empty")


def validate_compound_boot_img(
    boot_img_path: str, fd_sha: str, fd_size: int, kernel_sha: str, kernel_size: int, initrd_sha: str, initrd_size: int
) -> bytes:
    """Parse Android Boot Image v2 container and verify exact payload provenance."""
    with open(boot_img_path, "rb") as f:
        data = f.read()
    size = len(data)
    if size > MAX_SDA24_CAPACITY:
        raise AssertionError(f"Compound boot image ({size} B) exceeds sda24 limit ({MAX_SDA24_CAPACITY} B)")

    unpacked = struct.unpack_from("<8s9II16s512s32s1024sIQIIQ", data, 0)
    magic = unpacked[0]
    compound_kernel_size = unpacked[1]
    ramdisk_size = unpacked[3]
    page_size = unpacked[8]
    header_version = unpacked[9]
    header_size = unpacked[18]
    dtb_size = unpacked[19]

    if magic != b"ANDROID!":
        raise AssertionError(f"Compound boot image missing ANDROID! magic: {magic!r}")
    if header_version != 2 or header_size != 1660 or page_size != PAGE_SIZE:
        raise AssertionError(
            f"Unexpected boot header geometry: version={header_version}, header_size={header_size}, page={page_size}"
        )

    kernel_offset = page_size
    ramdisk_offset = align_up(kernel_offset + compound_kernel_size, page_size)
    dtb_offset = align_up(ramdisk_offset + ramdisk_size, page_size)
    expected_total = align_up(dtb_offset + dtb_size, page_size)
    if size != expected_total:
        raise AssertionError(f"Boot image size {size} != aligned layout size {expected_total}")

    expected_compound_kernel = 64 + fd_size + kernel_size
    if compound_kernel_size != expected_compound_kernel:
        raise AssertionError(
            f"Compound kernel size {compound_kernel_size} != 64 + {fd_size} + {kernel_size}"
        )

    compound_kernel = data[kernel_offset : kernel_offset + compound_kernel_size]
    if struct.unpack_from("<I", compound_kernel, 0)[0] != 0x14000010:
        raise AssertionError("Compound kernel missing branch-forward wrapper instruction")
    if compound_kernel[0x38:0x3C] != b"ARM\x64":
        raise AssertionError("Compound kernel wrapper missing ARM64 magic")

    embedded_fd = compound_kernel[64 : 64 + fd_size]
    embedded_kernel = compound_kernel[64 + fd_size :]
    embedded_ramdisk = data[ramdisk_offset : ramdisk_offset + ramdisk_size]
    embedded_dtb = data[dtb_offset : dtb_offset + dtb_size]

    if sha256_bytes(embedded_fd) != fd_sha:
        raise AssertionError("Embedded R8Q_EFI.fd in compound boot image does not match current firmware artifact")
    if sha256_bytes(embedded_kernel) != kernel_sha:
        raise AssertionError("Embedded Linux Image in compound boot image does not match current kernel artifact")
    if ramdisk_size != initrd_size or sha256_bytes(embedded_ramdisk) != initrd_sha:
        raise AssertionError("Embedded initramfs in compound boot image does not match current initramfs artifact")

    validate_fdt_bytes(embedded_dtb, "compound-boot-img DTB")
    with tempfile.NamedTemporaryFile(suffix=".dtb") as tmp:
        tmp.write(embedded_dtb)
        tmp.flush()
        initrd_end_out = subprocess.check_output(
            ["fdtget", "-t", "x", tmp.name, "/chosen", "linux,initrd-end"], text=True
        ).strip().split()
        expected_end = 0xA4400000 + initrd_size
        if not initrd_end_out or int(initrd_end_out[-1], 16) != expected_end:
            raise AssertionError(
                f"Embedded DTB /chosen linux,initrd-end {initrd_end_out} != 0x{expected_end:x}"
            )
    return embedded_dtb


def validate_recovery_zip(rec_zip_path: str, boot_img_sha: str, boot_img_size: int) -> None:
    """Validate recovery ZIP integrity, sda25 safety guard, and matching boot image payload."""
    with zipfile.ZipFile(rec_zip_path, "r") as z:
        bad = z.testzip()
        if bad is not None:
            raise AssertionError(f"Corrupted recovery ZIP entry: {bad}")
        names = set(z.namelist())
        required = {
            "META-INF/com/google/android/update-binary",
            "META-INF/com/google/android/updater-script",
            "META-INF/com/android/metadata",
            "r8q-uefi-boot-complete.img",
            "r8q-uefi-boot-complete.img.sha256",
        }
        missing = required - names
        if missing:
            raise AssertionError(f"Recovery ZIP missing required entries: {sorted(missing)}")

        updater = z.read("META-INF/com/google/android/update-binary").decode("utf-8", errors="ignore")
        if "sda25" not in updater or "CRITICAL SECURITY HAZARD" not in updater:
            raise AssertionError("Recovery ZIP update-binary missing sda25 Keyrefuge guard")

        embedded_boot = z.read("r8q-uefi-boot-complete.img")
        if len(embedded_boot) != boot_img_size or sha256_bytes(embedded_boot) != boot_img_sha:
            raise AssertionError("Recovery ZIP boot image does not match current CI compound boot image")

        embedded_sha = z.read("r8q-uefi-boot-complete.img.sha256").decode("utf-8").strip().split()[0].lower()
        if embedded_sha != boot_img_sha:
            raise AssertionError(f"Recovery ZIP internal .sha256 ({embedded_sha}) != {boot_img_sha}")


def validate_full_system_tarball(
    tar_path: str, expected_member_hashes: dict[str, str], staged_dtb_output: str
) -> None:
    """Stream full-system tarball, check required docs & hashes, and extract canonical DTB."""
    found_members: set[str] = set()
    extracted_dtb = False

    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar:
            norm = member.name.lstrip("./")
            found_members.add(norm)
            if not member.isfile():
                continue
            if norm in expected_member_hashes or norm == "R8Q-Debian12-Full-System/kernel/sm8250-samsung-r8q.dtb":
                f_obj = tar.extractfile(member)
                if f_obj is None:
                    raise AssertionError(f"Unable to read tarball member: {norm}")
                h = hashlib.sha256()
                dtb_chunks = [] if norm == "R8Q-Debian12-Full-System/kernel/sm8250-samsung-r8q.dtb" else None
                while chunk := f_obj.read(65536):
                    h.update(chunk)
                    if dtb_chunks is not None:
                        dtb_chunks.append(chunk)
                digest = h.hexdigest()
                if norm in expected_member_hashes and digest != expected_member_hashes[norm]:
                    raise AssertionError(
                        f"Tarball member {norm} SHA-256 ({digest}) != current CI artifact ({expected_member_hashes[norm]})"
                    )
                if dtb_chunks is not None:
                    with open(staged_dtb_output, "wb") as out_f:
                        out_f.write(b"".join(dtb_chunks))
                    extracted_dtb = True
            elif norm.startswith("R8Q-Debian12-Full-System/") and member.size == 0:
                raise AssertionError(f"Zero-byte member in Full System tarball: {norm}")

    required_docs = [
        "R8Q-Debian12-Full-System/README.md",
        "R8Q-Debian12-Full-System/INSTALLATION.md",
        "R8Q-Debian12-Full-System/INSTALLATION-USB.md",
        "R8Q-Debian12-Full-System/INSTALLER-AUDIT.md",
        "R8Q-Debian12-Full-System/BOOT-ARCHITECTURE.md",
        "R8Q-Debian12-Full-System/HARDWARE-COMPATIBILITY.md",
        "R8Q-Debian12-Full-System/PARTITION-LAYOUT.md",
        "R8Q-Debian12-Full-System/RECOVERY.md",
        "R8Q-Debian12-Full-System/TROUBLESHOOTING.md",
        "R8Q-Debian12-Full-System/SHA256SUMS-RECOVERY-ZIP.txt",
    ]
    for req in list(expected_member_hashes.keys()) + required_docs:
        if req not in found_members:
            raise AssertionError(f"Full System tarball missing required member: {req}")
    if not extracted_dtb:
        raise AssertionError("Failed to extract canonical DTB from Full System tarball")


def write_inventory_reports(
    dist_dir: str,
    release_version: str,
    checks: list[str],
    dist_entries: list[tuple[str, int, str]],
) -> None:
    """Write BUILD-INVENTORY.json and BUILD-INVENTORY.md inside dist_dir."""
    generated_at = datetime.now(timezone.utc).isoformat()
    inventory = {
        "project": "Project R8Q UEFI + Native Debian 12 ARM64",
        "device": "Samsung Galaxy S20 FE 5G (SM-G781B / r8q)",
        "soc": "Qualcomm Snapdragon 865 (SM8250)",
        "release_version_candidate": release_version,
        "generated_at_utc": generated_at,
        "git_sha": os.environ.get("GITHUB_SHA", "local"),
        "git_ref": os.environ.get("GITHUB_REF", "local"),
        "workflow": os.environ.get("GITHUB_WORKFLOW", "local"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_number": os.environ.get("GITHUB_RUN_NUMBER", "local"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME", "local"),
        "upstream_artifacts_verified": REQUIRED_ARTIFACTS,
        "validation_checks_passed": checks,
        "artifacts": [
            {"path": rel, "size_bytes": size, "sha256": digest}
            for rel, size, digest in dist_entries
        ],
    }

    with open(os.path.join(dist_dir, "BUILD-INVENTORY.json"), "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2)
        f.write("\n")

    lines = [
        "# Project R8Q — Consolidated Distribution Inventory & Verification Report",
        "",
        f"- **Commit SHA:** `{inventory['git_sha']}`",
        f"- **Workflow / Run:** `{inventory['workflow']}` (Run ID `{inventory['run_id']}`, `#{inventory['run_number']}`, event `{inventory['event_name']}`)",
        f"- **Release Candidate Tag:** `{release_version}`",
        f"- **Generated (UTC):** `{generated_at}`",
        f"- **Upstream Artifacts Verified:** `{len(REQUIRED_ARTIFACTS)}` / `{len(REQUIRED_ARTIFACTS)}`",
        "",
        "## Integrity & Cross-Artifact Provenance Checks Passed",
        "",
    ]
    lines.extend(f"- [PASS] {item}" for item in checks)
    lines.extend([
        "",
        "## Staged Distribution Inventory",
        "",
        "| Relative Path | Size (Bytes) | SHA-256 Digest |",
        "|---|---:|---|",
    ])
    for rel, size, digest in dist_entries:
        lines.append(f"| `{rel}` | {size:,} | `{digest}` |")
    lines.append("")

    with open(os.path.join(dist_dir, "BUILD-INVENTORY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_validation_and_staging(repo_root: str, artifacts_dir: str, dist_dir: str, release_version: str) -> None:
    checks: list[str] = []

    # 1. Verify all 10 mandatory artifact directories exist and contain zero 0-byte files
    for art_name in REQUIRED_ARTIFACTS:
        art_path = os.path.join(artifacts_dir, art_name)
        if not os.path.isdir(art_path):
            raise FileNotFoundError(f"Missing mandatory upstream CI artifact directory: {art_path}")
        file_count = 0
        for root, _, files in os.walk(art_path):
            for fname in files:
                fpath = os.path.join(root, fname)
                if os.path.getsize(fpath) == 0:
                    raise AssertionError(f"Zero-byte file detected in artifact {art_name}: {fpath}")
                file_count += 1
        if file_count == 0:
            raise AssertionError(f"Empty upstream CI artifact directory: {art_path}")
    checks.append(f"All {len(REQUIRED_ARTIFACTS)} mandatory CI artifacts present and non-empty")

    # 2. Verify all upstream SHA-256 manifests
    verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-uefi-firmware-volume"),
        os.path.join(artifacts_dir, "r8q-uefi-firmware-volume", "R8Q_EFI.fd.sha256"),
    )
    efi_hashes = verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-boot-manager-and-setup"),
        os.path.join(artifacts_dir, "r8q-boot-manager-and-setup", "SHA256SUMS.txt"),
    )
    verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-kernel-and-dtb"),
        os.path.join(artifacts_dir, "r8q-kernel-and-dtb", "Image.sha256"),
    )
    verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-kernel-and-dtb"),
        os.path.join(artifacts_dir, "r8q-kernel-and-dtb", "dtb.sha256"),
    )
    verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-kernel-and-dtb"),
        os.path.join(artifacts_dir, "r8q-kernel-and-dtb", "r8q.dtb.sha256"),
    )
    verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-initramfs"),
        os.path.join(artifacts_dir, "r8q-initramfs", "initramfs.img.sha256"),
    )
    verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-debian12-rootfs"),
        os.path.join(artifacts_dir, "r8q-debian12-rootfs", "rootfs.sha256"),
    )
    verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-esp"),
        os.path.join(artifacts_dir, "r8q-esp", "esp.img.sha256"),
    )
    verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-complete-boot-img"),
        os.path.join(artifacts_dir, "r8q-complete-boot-img", "r8q-uefi-boot-complete.img.sha256"),
    )
    verify_manifest_entries(
        os.path.join(artifacts_dir, "r8q-recovery-installer-zip"),
        os.path.join(artifacts_dir, "r8q-recovery-installer-zip", "R8Q-Debian12-Recovery.zip.sha256"),
    )

    rootfs_sha_main = open(os.path.join(artifacts_dir, "r8q-debian12-rootfs", "rootfs.sha256"), encoding="utf-8").read().strip()
    rootfs_sha_meta = open(os.path.join(artifacts_dir, "r8q-debian12-rootfs-meta", "rootfs.sha256"), encoding="utf-8").read().strip()
    if rootfs_sha_main != rootfs_sha_meta:
        raise AssertionError("r8q-debian12-rootfs/rootfs.sha256 != r8q-debian12-rootfs-meta/rootfs.sha256")
    checks.append("Upstream SHA-256 sidecar manifests and rootfs metadata digest match passed")

    # Locate component files
    fd_path = os.path.join(artifacts_dir, "r8q-uefi-firmware-volume", "build", "R8Q_EFI.fd")
    efi_dir = os.path.join(artifacts_dir, "r8q-boot-manager-and-setup")
    image_path = os.path.join(artifacts_dir, "r8q-kernel-and-dtb", "build", "Image")
    mainline_dtb_path = os.path.join(artifacts_dir, "r8q-kernel-and-dtb", "build", "sm8250-samsung-r8q.dtb")
    live_dtb_path = os.path.join(artifacts_dir, "r8q-kernel-and-dtb", "build", "r8q.dtb")
    initrd_path = os.path.join(artifacts_dir, "r8q-initramfs", "build", "initramfs.img")
    rootfs_ext4_gz = os.path.join(artifacts_dir, "r8q-debian12-rootfs", "R8Q-DEBIAN12-RELEASE", "rootfs", "r8q-rootfs.ext4.gz")
    rootfs_tar_gz = os.path.join(artifacts_dir, "r8q-debian12-rootfs", "R8Q-DEBIAN12-RELEASE", "rootfs", "r8q-rootfs.tar.gz")
    esp_path = os.path.join(artifacts_dir, "r8q-esp", "build", "esp.img")
    boot_img_path = os.path.join(artifacts_dir, "r8q-complete-boot-img", "build", "r8q-uefi-boot-complete.img")
    rec_zip_path = os.path.join(artifacts_dir, "r8q-recovery-installer-zip", "build", "R8Q-Debian12-Recovery.zip")
    full_dist_dir = os.path.join(artifacts_dir, "r8q-full-system-distribution")
    full_tar_path = os.path.join(full_dist_dir, "R8Q-Debian12-Full-System.tar.gz")
    if not os.path.isfile(full_tar_path):
        full_tar_path = os.path.join(full_dist_dir, "R8Q-DEBIAN12-RELEASE", "R8Q-Debian12-Full-System.tar.gz")
    ci_manifest_path = os.path.join(full_dist_dir, "SHA256SUMS.ci")
    if not os.path.isfile(ci_manifest_path):
        ci_manifest_path = os.path.join(full_dist_dir, "R8Q-DEBIAN12-RELEASE", "SHA256SUMS.ci")

    # 3. Validate Firmware (R8Q_EFI.fd)
    fd_size = os.path.getsize(fd_path)
    if fd_size != FIRMWARE_EXPECTED_SIZE:
        raise AssertionError(f"R8Q_EFI.fd size {fd_size} != {FIRMWARE_EXPECTED_SIZE}")
    with open(fd_path, "rb") as f:
        fd_hdr = f.read(64)
    if fd_hdr[0x28:0x2C] != b"_FVH":
        raise AssertionError(f"R8Q_EFI.fd missing EDK II _FVH signature: {fd_hdr[0x28:0x2C]!r}")
    fd_sha = sha256_file(fd_path)
    checks.append(f"EDK II UEFI firmware validated (4,194,304 B, _FVH, sha256={fd_sha[:12]}...)")

    # 4. Validate all 17 UEFI Applications (BootManager, Setup, Shell, R8Q utilities)
    for app in REQUIRED_EFI_APPS:
        app_file = f"{app}.efi"
        if app_file not in efi_hashes:
            raise AssertionError(f"Missing {app_file} in SHA256SUMS.txt")
        verify_pe32plus_aarch64(os.path.join(efi_dir, app_file))
    checks.append(f"All {len(REQUIRED_EFI_APPS)} UEFI PE32+ AArch64 applications verified (incl. BootManager.efi & Setup.efi)")

    # 5. Validate Kernel & DTBs
    with open(image_path, "rb") as f:
        img_hdr = f.read(64)
    if img_hdr[:2] != b"MZ" or img_hdr[0x38:0x3C] != b"ARM\x64":
        raise AssertionError("Kernel Image missing EFI MZ or ARM64 magic")
    with open(mainline_dtb_path, "rb") as f:
        validate_fdt_bytes(f.read(), "sm8250-samsung-r8q.dtb")
    with open(live_dtb_path, "rb") as f:
        validate_fdt_bytes(f.read(), "r8q.dtb")
    kernel_sha = sha256_file(image_path)
    kernel_size = os.path.getsize(image_path)
    r8q_dtb_sha = sha256_file(live_dtb_path)
    checks.append("ARM64 EFI stub Linux Image and FDT v17 DTBs (sm8250-samsung-r8q.dtb & r8q.dtb) validated")

    # 6. Validate Initramfs (ARM64 glibc + modules)
    with gzip.open(initrd_path, "rb") as gz:
        cpio_bytes = gz.read()
    if len(cpio_bytes) < INITRAMFS_MIN_CPIO_BYTES:
        raise AssertionError(f"Initramfs uncompressed CPIO too small ({len(cpio_bytes)} B)")
    cpio_entries = parse_cpio_newc_names(cpio_bytes)
    for req_entry in [
        "init",
        "bin/busybox",
        "lib/ld-linux-aarch64.so.1",
        "lib/libc.so.6",
        "lib/modules/virtio_blk.ko",
        "lib/modules/ext4.ko",
        "lib/modules/jbd2.ko",
        "lib/modules/mbcache.ko",
        "lib/modules/crc16.ko",
    ]:
        if req_entry not in cpio_entries:
            raise AssertionError(f"Initramfs missing critical member: {req_entry}")
    initrd_sha = sha256_file(initrd_path)
    initrd_size = os.path.getsize(initrd_path)
    checks.append(f"Early-userspace initramfs validated ({initrd_size:,} B, ARM64 glibc + kernel modules)")

    # 7. Validate Debian 12 ARM64 Rootfs (.ext4.gz + .tar.gz)
    with gzip.open(rootfs_ext4_gz, "rb") as gz:
        ext4_hdr = gz.read(2048)
    if len(ext4_hdr) < 1024 + 0x3A or ext4_hdr[1024 + 0x38 : 1024 + 0x3A] != b"\x53\xef":
        raise AssertionError("Debian rootfs ext4 superblock missing 0xEF53 magic")
    tar_size = os.path.getsize(rootfs_tar_gz)
    if tar_size < ROOTFS_TAR_MIN_SIZE:
        raise AssertionError(f"Rootfs tarball unexpectedly small: {tar_size} B")
    with tarfile.open(rootfs_tar_gz, "r:gz") as tar:
        tar_names = {m.name.lstrip("./") for m in tar}
    for req_root in ["bin/bash", "usr/bin/apt", "etc/sudoers.d/r8q"]:
        if req_root not in tar_names:
            raise AssertionError(f"Rootfs tarball missing required member: {req_root}")
    rootfs_ext4_sha = sha256_file(rootfs_ext4_gz)
    checks.append("Debian 12 ARM64 rootfs ext4 superblock (0xEF53) and FHS tarball verified")

    # 8. Validate ESP & bit-for-bit provenance against upstream EFI/Kernel/Initramfs artifacts
    validate_esp(esp_path, efi_hashes, kernel_sha, initrd_sha, r8q_dtb_sha)
    esp_sha = sha256_file(esp_path)
    checks.append("256 MiB FAT32 ESP verified bit-for-bit against current-run BootManager/Setup/Shell/Kernel/Initramfs/DTB")

    # 9. Validate Compound Boot Image & cross-check embedded payloads against upstream artifacts
    boot_img_sha = sha256_file(boot_img_path)
    boot_img_size = os.path.getsize(boot_img_path)
    embedded_dtb = validate_compound_boot_img(
        boot_img_path, fd_sha, fd_size, kernel_sha, kernel_size, initrd_sha, initrd_size
    )
    embedded_dtb_sha = sha256_bytes(embedded_dtb)
    checks.append(
        f"Compound Boot Image v2 validated ({boot_img_size:,} B, sda24 safe, embedded FD/Image/Initramfs/DTB match current run)"
    )

    # 10. Validate Recovery Installer ZIP & boot image match
    validate_recovery_zip(rec_zip_path, boot_img_sha, boot_img_size)
    rec_zip_sha = sha256_file(rec_zip_path)
    checks.append("LineageOS Recovery ZIP verified (CRC OK, sda25 Keyrefuge guard, matching boot image digest)")

    # 11. Cross-verify SHA256SUMS.ci & Full System Tarball against all current-run digests
    ci_sums = parse_sha256_manifest(ci_manifest_path)
    expected_ci = {
        "firmware/R8Q_EFI.fd": fd_sha,
        "kernel/Image": kernel_sha,
        "kernel/sm8250-samsung-r8q.dtb": embedded_dtb_sha,
        "kernel/initramfs.img": initrd_sha,
        "rootfs/r8q-rootfs.ext4.gz": rootfs_ext4_sha,
        "boot/esp.img": esp_sha,
        "boot/r8q-uefi-boot-complete.img": boot_img_sha,
        "R8Q-Debian12-Recovery.zip": rec_zip_sha,
        "R8Q-Debian12-Full-System.tar.gz": sha256_file(full_tar_path),
    }
    for key, exp_digest in expected_ci.items():
        if key not in ci_sums or ci_sums[key] != exp_digest:
            raise AssertionError(
                f"SHA256SUMS.ci entry mismatch for {key}: expected {exp_digest}, got {ci_sums.get(key)}"
            )

    # Prepare clean distribution directory and validate Full System tarball members
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    for sub in ["boot", "efi", "firmware", "kernel", "rootfs"]:
        os.makedirs(os.path.join(dist_dir, sub), exist_ok=True)

    canonical_dtb_staged = os.path.join(dist_dir, "kernel", "sm8250-samsung-r8q.dtb")
    tar_member_expectations = {
        "R8Q-Debian12-Full-System/firmware/R8Q_EFI.fd": fd_sha,
        "R8Q-Debian12-Full-System/kernel/Image": kernel_sha,
        "R8Q-Debian12-Full-System/kernel/sm8250-samsung-r8q.dtb": embedded_dtb_sha,
        "R8Q-Debian12-Full-System/kernel/initramfs.img": initrd_sha,
        "R8Q-Debian12-Full-System/rootfs/r8q-rootfs.ext4.gz": rootfs_ext4_sha,
        "R8Q-Debian12-Full-System/boot/esp.img": esp_sha,
        "R8Q-Debian12-Full-System/boot/r8q-uefi-boot-complete.img": boot_img_sha,
        "R8Q-Debian12-Full-System/R8Q-Debian12-Recovery.zip": rec_zip_sha,
    }
    validate_full_system_tarball(full_tar_path, tar_member_expectations, canonical_dtb_staged)
    checks.append("Full System tarball & SHA256SUMS.ci verified bit-for-bit against all current-run payloads")

    # 12. Populate Complete Consolidated Distribution Directory
    rel_src_docs = os.path.join(repo_root, "R8Q-DEBIAN12-RELEASE")
    for doc_name in REQUIRED_DOCS:
        src_doc = os.path.join(rel_src_docs, doc_name)
        if not os.path.isfile(src_doc) or os.path.getsize(src_doc) == 0:
            raise FileNotFoundError(f"Missing or empty release documentation file: {src_doc}")
        shutil.copy2(src_doc, os.path.join(dist_dir, doc_name))

    shutil.copy2(fd_path, os.path.join(dist_dir, "firmware", "R8Q_EFI.fd"))
    shutil.copy2(
        os.path.join(artifacts_dir, "r8q-uefi-firmware-volume", "R8Q_EFI.fd.sha256"),
        os.path.join(dist_dir, "firmware", "R8Q_EFI.fd.sha256"),
    )
    for app in REQUIRED_EFI_APPS:
        shutil.copy2(os.path.join(efi_dir, f"{app}.efi"), os.path.join(dist_dir, "efi", f"{app}.efi"))
    shutil.copy2(os.path.join(efi_dir, "SHA256SUMS.txt"), os.path.join(dist_dir, "efi", "SHA256SUMS.txt"))
    shutil.copy2(image_path, os.path.join(dist_dir, "kernel", "Image"))
    shutil.copy2(live_dtb_path, os.path.join(dist_dir, "kernel", "r8q.dtb"))
    shutil.copy2(initrd_path, os.path.join(dist_dir, "kernel", "initramfs.img"))
    shutil.copy2(rootfs_ext4_gz, os.path.join(dist_dir, "rootfs", "r8q-rootfs.ext4.gz"))
    shutil.copy2(rootfs_tar_gz, os.path.join(dist_dir, "rootfs", "r8q-rootfs.tar.gz"))
    shutil.copy2(esp_path, os.path.join(dist_dir, "boot", "esp.img"))
    shutil.copy2(boot_img_path, os.path.join(dist_dir, "boot", "r8q-uefi-boot-complete.img"))
    shutil.copy2(rec_zip_path, os.path.join(dist_dir, "R8Q-Debian12-Recovery.zip"))
    shutil.copy2(full_tar_path, os.path.join(dist_dir, "R8Q-Debian12-Full-System.tar.gz"))
    shutil.copy2(ci_manifest_path, os.path.join(dist_dir, "SHA256SUMS.ci"))

    rec_manifest_lines = [
        f"{sha256_file(os.path.join(dist_dir, 'R8Q-Debian12-Recovery.zip'))}  R8Q-Debian12-Recovery.zip",
        f"{sha256_file(os.path.join(dist_dir, 'INSTALLATION-USB.md'))}  INSTALLATION-USB.md",
        f"{sha256_file(os.path.join(dist_dir, 'INSTALLER-AUDIT.md'))}  INSTALLER-AUDIT.md",
        f"{boot_img_sha}  r8q-uefi-boot-complete.img",
    ]
    with open(os.path.join(dist_dir, "SHA256SUMS-RECOVERY-ZIP.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(rec_manifest_lines) + "\n")

    # Collect initial staged inventory (excluding BUILD-INVENTORY.* / SHA256SUMS.dist) for report tables
    pre_entries: list[tuple[str, int, str]] = []
    for root, _, files in os.walk(dist_dir):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, dist_dir).replace(os.sep, "/")
            pre_entries.append((rel, os.path.getsize(full), sha256_file(full)))
    pre_entries.sort(key=lambda item: item[0])

    write_inventory_reports(dist_dir, release_version, checks, pre_entries)

    # Write final consolidated SHA256SUMS.dist covering every staged file including BUILD-INVENTORY.*
    all_entries: list[tuple[str, str]] = []
    for root, _, files in os.walk(dist_dir):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, dist_dir).replace(os.sep, "/")
            if rel == "SHA256SUMS.dist":
                continue
            all_entries.append((rel, sha256_file(full)))
    all_entries.sort(key=lambda item: item[0])

    dist_manifest_path = os.path.join(dist_dir, "SHA256SUMS.dist")
    with open(dist_manifest_path, "w", encoding="utf-8") as f:
        for rel, digest in all_entries:
            f.write(f"{digest}  {rel}\n")

    verify_manifest_entries(dist_dir, dist_manifest_path)
    verify_manifest_entries(dist_dir, os.path.join(dist_dir, "SHA256SUMS.ci"))
    print(f"[SUCCESS] Distribution validated & staged: {len(all_entries)} verified files in {dist_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate upstream R8Q CI artifacts and stage release distribution.")
    parser.add_argument("--artifacts-dir", required=True, help="Directory containing downloaded CI artifacts.")
    parser.add_argument("--dist-dir", required=True, help="Output directory for consolidated distribution bundle.")
    parser.add_argument("--release-version", default="v1.0.0-terminal", help="Target release version tag label.")
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    run_validation_and_staging(repo_root, os.path.abspath(args.artifacts_dir), os.path.abspath(args.dist_dir), args.release_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
