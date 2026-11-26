#!/usr/bin/env python3
"""Project R8Q — Unified One-Click Installation Package Builder.

Validates all upstream CI workflow artifacts (reusing shared checks from
validate_and_stage_distribution), assembles the complete self-contained
R8Q-Debian12-ARM64-Installer directory tree, generates manifests/MANIFEST.json
and manifests/SHA256SUMS, verifies every checksum prior to archiving, and
produces R8Q-Debian12-ARM64-Installer.zip preserving POSIX executable bits.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from validate_and_stage_distribution import (  # noqa: E402
    REQUIRED_EFI_APPS,
    sha256_file,
    validate_upstream_artifacts,
)

PACKAGE_ROOT_NAME = "R8Q-Debian12-ARM64-Installer"
TWRP_META_DEFAULT_DIR = os.path.abspath(os.path.join(SCRIPTS_DIR, "..", "installer", "twrp", "META-INF"))

SHELL_NSH_SCRIPTS = [
    "startup.nsh",
    "boot-linux.nsh",
    "hardware-audit.nsh",
    "storage-audit.nsh",
    "boot-recovery.nsh",
]

COMPONENT_ROLES = {
    "install.sh": "Master 19-step installation orchestrator",
    "uninstall-or-rollback.sh": "Non-destructive recovery & rollback verifier",
    "verify-device.sh": "SM-G781B / r8q hardware, storage & partition guard",
    "verify-checksums.sh": "Cryptographic SHA-256 & manifest completeness verifier",
    "config/": "Device, partition-map, and boot policy configuration",
    "scripts/": "Ordered dependency stage execution scripts (01..11)",
    "payload/firmware/": "EDK II firmware volume (R8Q_EFI.fd) & compound boot container",
    "payload/boot-manager/": "Standalone BootManager.efi and OS entry configs",
    "payload/setup/": "R8Q UEFI BIOS Setup.efi utility",
    "payload/uefi/": "UEFI Shell & hardware diagnostic/test EFI applications",
    "payload/esp/": "256 MiB FAT32 EFI System Partition image and .nsh scripts",
    "payload/kernel/": "ARM64 EFI Stub Linux kernel Image",
    "payload/dtb/": "Mainline & live Qualcomm SM8250 r8q Device Trees",
    "payload/initramfs/": "Early-userspace rescue initramfs with ARM64 glibc & modules",
    "payload/debian-rootfs/": "Native Debian 12 ARM64 root filesystem (ext4 + tar)",
    "manifests/": "Package JSON inventory & cryptographic SHA256SUMS",
    "logs/": "Runtime installation audit directory",
    "INSTALL.md": "Operator manual and hardware safety guidelines",
    "VERSION": "Package semantic version & commit provenance",
}


def assemble_installer_tree(
    repo_root: str,
    stage_parent_dir: str,
    version_label: str,
    payload_sources: dict,
) -> str:
    """Assemble R8Q-Debian12-ARM64-Installer/ directory tree and return its path."""
    pkg_dir = os.path.join(stage_parent_dir, PACKAGE_ROOT_NAME)
    if os.path.exists(pkg_dir):
        shutil.rmtree(pkg_dir)

    src_installer = os.path.join(repo_root, "installer")
    for subdir in [
        "config",
        "scripts",
        "manifests",
        "logs",
        "payload/firmware",
        "payload/uefi",
        "payload/boot-manager/Config/entries",
        "payload/setup",
        "payload/esp",
        "payload/kernel",
        "payload/dtb",
        "payload/initramfs",
        "payload/debian-rootfs",
    ]:
        os.makedirs(os.path.join(pkg_dir, subdir), exist_ok=True)

    # 1. Static scripts, configs, and docs from installer/
    for top_file in ["install.sh", "uninstall-or-rollback.sh", "verify-device.sh", "verify-checksums.sh", "INSTALL.md"]:
        src = os.path.join(src_installer, top_file)
        dst = os.path.join(pkg_dir, top_file)
        shutil.copy2(src, dst)
        if top_file.endswith(".sh"):
            os.chmod(dst, 0o755)

    for conf in sorted(os.listdir(os.path.join(src_installer, "config"))):
        shutil.copy2(os.path.join(src_installer, "config", conf), os.path.join(pkg_dir, "config", conf))

    for step_script in sorted(os.listdir(os.path.join(src_installer, "scripts"))):
        if not step_script.endswith(".sh"):
            continue
        dst = os.path.join(pkg_dir, "scripts", step_script)
        shutil.copy2(os.path.join(src_installer, "scripts", step_script), dst)
        os.chmod(dst, 0o755)

    with open(os.path.join(pkg_dir, "logs", ".gitkeep"), "w", encoding="utf-8") as f:
        f.write("R8Q installation log directory\n")

    git_sha = os.environ.get("GITHUB_SHA", "local")
    with open(os.path.join(pkg_dir, "VERSION"), "w", encoding="utf-8") as f:
        f.write(f"R8Q-Debian12-ARM64-Installer {version_label} ({git_sha[:12]})\n")

    # 2. Payloads
    shutil.copy2(payload_sources["fd"], os.path.join(pkg_dir, "payload/firmware/R8Q_EFI.fd"))
    shutil.copy2(payload_sources["boot_img"], os.path.join(pkg_dir, "payload/firmware/r8q-uefi-boot-complete.img"))
    shutil.copy2(
        os.path.join(payload_sources["efi_dir"], "BootManager.efi"),
        os.path.join(pkg_dir, "payload/boot-manager/BootManager.efi"),
    )
    shutil.copy2(
        os.path.join(payload_sources["efi_dir"], "Setup.efi"),
        os.path.join(pkg_dir, "payload/setup/Setup.efi"),
    )

    bm_cfg_src = os.path.join(repo_root, "boot-manager", "Config")
    shutil.copy2(os.path.join(bm_cfg_src, "boot.cfg"), os.path.join(pkg_dir, "payload/boot-manager/Config/boot.cfg"))
    for entry in sorted(os.listdir(os.path.join(bm_cfg_src, "entries"))):
        shutil.copy2(
            os.path.join(bm_cfg_src, "entries", entry),
            os.path.join(pkg_dir, "payload/boot-manager/Config/entries", entry),
        )

    for app in REQUIRED_EFI_APPS:
        if app in ("BootManager", "Setup"):
            continue
        shutil.copy2(
            os.path.join(payload_sources["efi_dir"], f"{app}.efi"),
            os.path.join(pkg_dir, "payload/uefi", f"{app}.efi"),
        )

    shutil.copy2(payload_sources["esp"], os.path.join(pkg_dir, "payload/esp/esp.img"))
    for nsh in SHELL_NSH_SCRIPTS:
        shutil.copy2(
            os.path.join(repo_root, "shell", "scripts", nsh),
            os.path.join(pkg_dir, "payload/esp", nsh),
        )

    shutil.copy2(payload_sources["image"], os.path.join(pkg_dir, "payload/kernel/Image"))
    with open(os.path.join(pkg_dir, "payload/dtb/sm8250-samsung-r8q.dtb"), "wb") as f_dtb:
        f_dtb.write(payload_sources["canonical_dtb_bytes"])
    shutil.copy2(payload_sources["live_dtb"], os.path.join(pkg_dir, "payload/dtb/r8q.dtb"))
    shutil.copy2(payload_sources["initrd"], os.path.join(pkg_dir, "payload/initramfs/initramfs.img"))
    shutil.copy2(payload_sources["rootfs_ext4_gz"], os.path.join(pkg_dir, "payload/debian-rootfs/r8q-rootfs.ext4.gz"))
    shutil.copy2(payload_sources["rootfs_tar_gz"], os.path.join(pkg_dir, "payload/debian-rootfs/r8q-rootfs.tar.gz"))

    # 3. Collect file inventory and write MANIFEST.json + SHA256SUMS
    entries = []
    for root, _, files in os.walk(pkg_dir):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, pkg_dir).replace(os.sep, "/")
            if rel in ("manifests/MANIFEST.json", "manifests/SHA256SUMS"):
                continue
            entries.append({
                "path": rel,
                "size_bytes": os.path.getsize(full),
                "sha256": sha256_file(full),
                "executable": bool(os.stat(full).st_mode & stat.S_IXUSR),
            })
    entries.sort(key=lambda item: item["path"])

    manifest_path = os.path.join(pkg_dir, "manifests", "MANIFEST.json")
    manifest_obj = {
        "package": PACKAGE_ROOT_NAME,
        "version": version_label,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "target_device": "Samsung Galaxy S20 FE 5G (SM-G781B / r8q)",
        "soc": "Qualcomm Snapdragon 865 (SM8250)",
        "architecture": "aarch64",
        "hardware_safety": {
            "physical_writes_enabled_default": False,
            "sda25_keyrefuge_policy": "zero_access",
            "sda23_boot_policy": "protected_read_only",
            "independent_partition_map_required": True,
        },
        "boot_policy": {
            "systemd_default_target": "multi-user.target",
            "optional_gnome_enabled_default": False,
            "boot_manager_default": "debian",
        },
        "stage_order": [f"{i:02d}" for i in range(1, 12)],
        "component_roles": COMPONENT_ROLES,
        "files": entries,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_obj, f, indent=2)
        f.write("\n")

    sums_entries = list(entries) + [{
        "path": "manifests/MANIFEST.json",
        "size_bytes": os.path.getsize(manifest_path),
        "sha256": sha256_file(manifest_path),
        "executable": False,
    }]
    sums_entries.sort(key=lambda item: item["path"])

    sums_path = os.path.join(pkg_dir, "manifests", "SHA256SUMS")
    with open(sums_path, "w", encoding="utf-8") as f:
        for item in sums_entries:
            f.write(f"{item['sha256']}  {item['path']}\n")

    subprocess.run([os.path.join(pkg_dir, "verify-checksums.sh")], check=True)
    return pkg_dir


def sign_zip_whole_file(zip_path: str, cert_pem: str, key_pem: str) -> None:
    """Apply an AOSP SignApk v1 WholeFileSignature footer using OpenSSL CMS DER."""
    with open(zip_path, "rb") as f:
        raw = f.read()

    if len(raw) < 22 or raw[-22:-18] != b"PK\x05\x06" or raw[-2:] != b"\x00\x00":
        raise ValueError(f"Unexpected ZIP EOCD layout before whole-file signing: {zip_path}")

    signed_data = raw[:-2]
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(signed_data)
        tmp_in = tf.name

    try:
        proc = subprocess.run(
            [
                "openssl",
                "cms",
                "-sign",
                "-signer",
                cert_pem,
                "-inkey",
                key_pem,
                "-in",
                tmp_in,
                "-binary",
                "-outform",
                "DER",
                "-noattr",
                "-md",
                "sha256",
            ],
            capture_output=True,
            check=True,
        )
        sig_der = proc.stdout
    finally:
        if os.path.exists(tmp_in):
            os.remove(tmp_in)

    footer_size = 6
    comment_len = len(sig_der) + footer_size
    sig_start = comment_len
    if comment_len > 0xFFFF:
        raise ValueError(f"WholeFileSignature comment length exceeds 65535 bytes ({comment_len})")

    footer = struct.pack("<HHH", sig_start, 0xFFFF, comment_len)
    comment = sig_der + footer
    if b"PK\x05\x06" in comment:
        raise ValueError("EOCD marker sequence appeared inside signature comment")

    with open(zip_path, "wb") as f:
        f.write(signed_data)
        f.write(struct.pack("<H", comment_len))
        f.write(comment)


def write_installer_zip(
    pkg_dir: str,
    output_zip: str,
    twrp_meta_dir: str | None = TWRP_META_DEFAULT_DIR,
    sign_cert: str = "",
    sign_key: str = "",
) -> tuple[int, str]:
    """Archive pkg_dir (and optional root TWRP META-INF/) cleanly into output_zip."""
    os.makedirs(os.path.dirname(os.path.abspath(output_zip)), exist_ok=True)
    stage_parent = os.path.dirname(pkg_dir)

    meta_dirs: list[tuple[str, str]] = []
    meta_files: list[tuple[str, str, int]] = []
    if twrp_meta_dir and os.path.isdir(twrp_meta_dir):
        meta_parent = os.path.dirname(os.path.abspath(twrp_meta_dir))
        meta_dirs.append(("META-INF", os.path.abspath(twrp_meta_dir)))
        for root, dirs, files in os.walk(twrp_meta_dir):
            for d in sorted(dirs):
                full_d = os.path.join(root, d)
                rel_d = os.path.relpath(full_d, meta_parent).replace(os.sep, "/")
                meta_dirs.append((rel_d, full_d))
            for fname in sorted(files):
                full_f = os.path.join(root, fname)
                rel_f = os.path.relpath(full_f, meta_parent).replace(os.sep, "/")
                mode = 0o755 if fname == "update-binary" or fname.endswith(".sh") else 0o644
                meta_files.append((rel_f, full_f, mode))
        meta_dirs.sort(key=lambda x: x[0])
        meta_files.sort(key=lambda x: x[0])

    all_dirs: list[str] = []
    all_files: list[str] = []
    for root, dirs, files in os.walk(pkg_dir):
        for d in dirs:
            all_dirs.append(os.path.relpath(os.path.join(root, d), stage_parent).replace(os.sep, "/"))
        for fname in files:
            all_files.append(os.path.relpath(os.path.join(root, fname), stage_parent).replace(os.sep, "/"))

    all_dirs.sort()
    all_files.sort()

    # Use strict 32-bit ZIP headers (allowZip64=False) for maximum TWRP libziparchive/minzip compatibility
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zf:
        for rel_dir, _ in meta_dirs:
            d_info = zipfile.ZipInfo(f"{rel_dir}/")
            d_info.external_attr = (stat.S_IFDIR | 0o755) << 16 | 0x10
            zf.writestr(d_info, b"")

        for rel_file, full_path, mode in meta_files:
            zinfo = zipfile.ZipInfo(rel_file)
            zinfo.external_attr = (stat.S_IFREG | mode) << 16
            zinfo.compress_type = zipfile.ZIP_DEFLATED
            with open(full_path, "rb") as src_f:
                zf.writestr(zinfo, src_f.read())

        root_info = zipfile.ZipInfo(f"{PACKAGE_ROOT_NAME}/")
        root_info.external_attr = (stat.S_IFDIR | 0o755) << 16 | 0x10
        zf.writestr(root_info, b"")

        for rel_dir in all_dirs:
            d_info = zipfile.ZipInfo(f"{rel_dir}/")
            d_info.external_attr = (stat.S_IFDIR | 0o755) << 16 | 0x10
            zf.writestr(d_info, b"")

        for rel_file in all_files:
            full_path = os.path.join(stage_parent, rel_file)
            mode = 0o755 if rel_file.endswith(".sh") else 0o644
            compress_type = zipfile.ZIP_STORED if rel_file.endswith((".gz", ".tar.gz", ".zip")) else zipfile.ZIP_DEFLATED
            zinfo = zipfile.ZipInfo(rel_file)
            zinfo.external_attr = (stat.S_IFREG | mode) << 16
            zinfo.compress_type = compress_type
            with open(full_path, "rb") as src_f:
                with zf.open(zinfo, mode="w") as dst_f:
                    while chunk := src_f.read(1024 * 1024):
                        dst_f.write(chunk)

    if sign_cert and sign_key:
        sign_zip_whole_file(output_zip, sign_cert, sign_key)

    with zipfile.ZipFile(output_zip, "r") as zchk:
        bad = zchk.testzip()
        if bad is not None:
            raise AssertionError(f"Generated ZIP failed CRC test at entry: {bad}")

    zip_size = os.path.getsize(output_zip)
    zip_sha = sha256_file(output_zip)
    with open(f"{output_zip}.sha256", "w", encoding="utf-8") as sf:
        sf.write(f"{zip_sha}  {os.path.basename(output_zip)}\n")

    print(f"[SUCCESS] Built {output_zip}: {zip_size:,} bytes, SHA-256={zip_sha}")
    return zip_size, zip_sha


def main() -> int:
    parser = argparse.ArgumentParser(description="Build unified R8Q-Debian12-ARM64 TWRP & workstation Installer ZIP")
    parser.add_argument("--artifacts-dir", required=True, help="Directory holding verified upstream CI artifacts.")
    parser.add_argument("--output", required=True, help="Output path for installer ZIP.")
    parser.add_argument("--stage-dir", default="", help="Optional staging workspace parent directory.")
    parser.add_argument("--version", default="v1.0.0-terminal", help="Package version label.")
    parser.add_argument(
        "--twrp-meta-dir",
        default=TWRP_META_DEFAULT_DIR,
        help="Optional TWRP META-INF directory to embed at ZIP root (pass '' to omit).",
    )
    parser.add_argument("--sign-cert", default="", help="Optional X.509 certificate PEM for SignApk WholeFileSignature.")
    parser.add_argument("--sign-key", default="", help="Optional private key PEM for SignApk WholeFileSignature.")
    args = parser.parse_args()

    if bool(args.sign_cert) != bool(args.sign_key):
        parser.error("--sign-cert and --sign-key must be supplied together")

    repo_root = os.path.abspath(os.path.join(SCRIPTS_DIR, ".."))
    ctx = validate_upstream_artifacts(os.path.abspath(args.artifacts_dir))
    sources = dict(ctx["paths"])
    sources["canonical_dtb_bytes"] = ctx["canonical_dtb_bytes"]

    stage_parent = os.path.abspath(args.stage_dir) if args.stage_dir else os.path.dirname(os.path.abspath(args.output))
    os.makedirs(stage_parent, exist_ok=True)
    pkg_dir = assemble_installer_tree(repo_root, stage_parent, args.version, sources)
    write_installer_zip(
        pkg_dir,
        os.path.abspath(args.output),
        twrp_meta_dir=args.twrp_meta_dir or None,
        sign_cert=args.sign_cert,
        sign_key=args.sign_key,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
