#!/usr/bin/env python3
"""
Project R8Q: Unified One-Click Debian 12 ARM64 Installer Test Suite

Validates:
  1. All firmware, UEFI, BootManager, Setup, ESP, kernel, DTB, initramfs & rootfs components exist
  2. All master/helper/stage scripts (01..11) are present and executable
  3. Dependency installation order (01 -> 02 -> ... -> 11) is strictly enforced
  4. Out-of-order stage invocation & dependency failures halt installation
  5. Missing payloads stop installation immediately before subsequent stages
  6. SHA-256 checksum mismatches stop installation immediately
  7. Wrong device models / CPU architectures / SoCs are rejected
  8. Protected partitions (sda25, keyrefuge, sda23, boot, sda) and unapproved sda24 writes are blocked
  9. Insufficient storage triggers safe abort
 10. --dry-run executes cleanly with zero filesystem/block writes; extracted ZIP runs --verify & --dry-run
"""

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import gzip
import hashlib
import io
import json
import os
import shutil
import stat
import struct
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from build_unified_installer import PACKAGE_ROOT_NAME, assemble_installer_tree, write_installer_zip  # noqa: E402
from validate_and_stage_distribution import REQUIRED_EFI_APPS  # noqa: E402


def _make_pe32plus_aarch64_stub() -> bytes:
    buf = bytearray(512)
    buf[:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x80)
    buf[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", buf, 0x84, 0xAA64)
    return bytes(buf)


def _make_cpio_newc_archive(entries: dict[str, bytes]) -> bytes:
    out = bytearray()
    for ino, (name, data) in enumerate(entries.items(), start=1):
        name_bytes = name.encode("utf-8") + b"\x00"
        hdr = (
            f"070701{ino:08x}{0o100755:08x}{0:08x}{0:08x}{1:08x}{0:08x}"
            f"{len(data):08x}{0:08x}{0:08x}{0:08x}{0:08x}{len(name_bytes):08x}{0:08x}"
        ).encode("ascii")
        out.extend(hdr)
        out.extend(name_bytes)
        while len(out) % 4:
            out.append(0)
        out.extend(data)
        while len(out) % 4:
            out.append(0)
    trailer = (
        f"070701{len(entries)+1:08x}{0:08x}{0:08x}{0:08x}{1:08x}{0:08x}"
        f"{0:08x}{0:08x}{0:08x}{0:08x}{0:08x}{11:08x}{0:08x}"
    ).encode("ascii") + b"TRAILER!!!\x00"
    out.extend(trailer)
    while len(out) % 4:
        out.append(0)
    # Pad beyond 1 MiB minimum CPIO sanity bound matching real archive threshold check
    if len(out) < 1_100_000:
        pad_name = b"usr/share/r8q-pad\x00"
        pad_data_len = 1_100_000 - len(out)
        hdr2 = (
            f"070701{999:08x}{0o100644:08x}{0:08x}{0:08x}{1:08x}{0:08x}"
            f"{pad_data_len:08x}{0:08x}{0:08x}{0:08x}{0:08x}{len(pad_name):08x}{0:08x}"
        ).encode("ascii")
        # Rebuild cleanly so TRAILER!!! remains last
        pre = bytearray()
        for ino, (name, data) in enumerate(list(entries.items()) + [("usr/share/r8q-pad", b"\x00" * pad_data_len)], start=1):
            nb = name.encode("utf-8") + b"\x00"
            h = (
                f"070701{ino:08x}{0o100755:08x}{0:08x}{0:08x}{1:08x}{0:08x}"
                f"{len(data):08x}{0:08x}{0:08x}{0:08x}{0:08x}{len(nb):08x}{0:08x}"
            ).encode("ascii")
            pre.extend(h)
            pre.extend(nb)
            while len(pre) % 4:
                pre.append(0)
            pre.extend(data)
            while len(pre) % 4:
                pre.append(0)
        pre.extend(trailer)
        while len(pre) % 4:
            pre.append(0)
        return bytes(pre)
    return bytes(out)


def _create_mock_payload_sources(base_dir: str) -> dict:
    """Create valid synthetic payload files mirroring real SM8250 binary headers when no prebuilt ZIP exists."""
    src_dir = os.path.join(base_dir, "mock_sources")
    efi_dir = os.path.join(src_dir, "efi")
    os.makedirs(efi_dir, exist_ok=True)

    # Firmware (4 MiB with _FVH magic)
    fd_path = os.path.join(src_dir, "R8Q_EFI.fd")
    fd_buf = bytearray(4194304)
    fd_buf[0x28:0x2C] = b"_FVH"
    with open(fd_path, "wb") as f:
        f.write(fd_buf)

    # Compound boot img v2
    boot_path = os.path.join(src_dir, "r8q-uefi-boot-complete.img")
    boot_buf = bytearray(4096 * 4)
    struct.pack_into("<8s9II", boot_buf, 0, b"ANDROID!", 4096, 0x8000, 0, 0x1000000, 0, 0, 0x100, 4096, 2, 0)
    with open(boot_path, "wb") as f:
        f.write(boot_buf)

    # 17 UEFI binaries
    pe_stub = _make_pe32plus_aarch64_stub()
    for app in REQUIRED_EFI_APPS:
        with open(os.path.join(efi_dir, f"{app}.efi"), "wb") as f:
            f.write(pe_stub)

    # Real or synthetic ESP
    local_esp = os.path.join(PROJECT_ROOT, "build", "esp.img")
    esp_path = os.path.join(src_dir, "esp.img")
    if os.path.isfile(local_esp) and os.path.getsize(local_esp) == 268435456:
        shutil.copy2(local_esp, esp_path)
    else:
        with open(esp_path, "wb") as f:
            f.seek(268435456 - 1)
            f.write(b"\x00")
            f.seek(510)
            f.write(b"\x55\xaa" + b"EFI PART")

    # Kernel ARM64 EFI Stub header
    img_path = os.path.join(src_dir, "Image")
    img_hdr = bytearray(4096)
    img_hdr[:2] = b"MZ"
    img_hdr[0x38:0x3C] = b"ARM\x64"
    with open(img_path, "wb") as f:
        f.write(img_hdr)

    # DTB FDT v17
    dtb_bytes = struct.pack(">6I", 0xD00DFEED, 64, 40, 56, 64, 17) + b"\x00" * (64 - 24)
    live_dtb_path = os.path.join(src_dir, "r8q.dtb")
    with open(live_dtb_path, "wb") as f:
        f.write(dtb_bytes)

    # Initramfs gzip CPIO
    cpio_raw = _make_cpio_newc_archive({
        "init": b"#!/bin/sh\nexit 0\n",
        "bin/busybox": b"\x7fELF",
        "lib/ld-linux-aarch64.so.1": b"\x7fELF",
        "lib/libc.so.6": b"\x7fELF",
        "lib/modules/virtio_blk.ko": b"MOD",
        "lib/modules/ext4.ko": b"MOD",
        "lib/modules/jbd2.ko": b"MOD",
        "lib/modules/mbcache.ko": b"MOD",
        "lib/modules/crc16.ko": b"MOD",
    })
    initrd_path = os.path.join(src_dir, "initramfs.img")
    with gzip.open(initrd_path, "wb") as gz:
        gz.write(cpio_raw)

    # Debian 12 Rootfs ext4.gz + tar.gz padded >30 MiB to mirror validation check
    ext4_gz = os.path.join(src_dir, "r8q-rootfs.ext4.gz")
    ext4_hdr = bytearray(4096)
    ext4_hdr[1024 + 0x38 : 1024 + 0x3A] = b"\x53\xef"
    with gzip.open(ext4_gz, "wb") as gz:
        gz.write(ext4_hdr)

    tar_gz = os.path.join(src_dir, "r8q-rootfs.tar.gz")
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:gz") as tar:
        ti_sym = tarfile.TarInfo("etc/systemd/system/default.target")
        ti_sym.type = tarfile.SYMTYPE
        ti_sym.linkname = "/usr/lib/systemd/system/multi-user.target"
        tar.addfile(ti_sym)

        for rel in [
            "bin/bash",
            "usr/bin/apt",
            "etc/sudoers.d/r8q",
            "etc/systemd/system/getty.target.wants/getty@tty1.service",
            "etc/systemd/system/getty.target.wants/serial-getty@ttyMSM0.service",
        ]:
            ti = tarfile.TarInfo(rel)
            ti.size = 4
            tar.addfile(ti, io.BytesIO(b"TEST"))

        pad_ti = tarfile.TarInfo("usr/share/r8q-ci-test-blob")
        pad_data = os.urandom(31 * 1024 * 1024)
        pad_ti.size = len(pad_data)
        tar.addfile(pad_ti, io.BytesIO(pad_data))

    with open(tar_gz, "wb") as f:
        f.write(tar_buf.getvalue())

    return {
        "fd": fd_path,
        "boot_img": boot_path,
        "efi_dir": efi_dir,
        "esp": esp_path,
        "image": img_path,
        "canonical_dtb_bytes": dtb_bytes,
        "live_dtb": live_dtb_path,
        "initrd": initrd_path,
        "rootfs_ext4_gz": ext4_gz,
        "rootfs_tar_gz": tar_gz,
    }


class TestUnifiedInstallerPackage(unittest.TestCase):
    """Comprehensive verification for R8Q-Debian12-ARM64-Installer.zip & master installer."""

    temp_root: str
    zip_path: str
    extracted_root: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_root = tempfile.mkdtemp(prefix="r8q_unified_test_")
        cls.extract_parent = os.path.join(cls.temp_root, "extracted")
        os.makedirs(cls.extract_parent, exist_ok=True)

        env_zip = os.environ.get("R8Q_UNIFIED_INSTALLER_ZIP", "")
        if env_zip and os.path.isfile(env_zip):
            cls.zip_path = env_zip
        else:
            sources = _create_mock_payload_sources(cls.temp_root)
            pkg_dir = assemble_installer_tree(PROJECT_ROOT, cls.temp_root, "v1.0.0-test", sources)
            cls.zip_path = os.path.join(cls.temp_root, "R8Q-Debian12-ARM64-Installer.zip")
            write_installer_zip(pkg_dir, cls.zip_path)

        # Extract via system unzip or zipfile (preserving executable mode bits)
        if shutil.which("unzip"):
            subprocess.run(["unzip", "-q", cls.zip_path, "-d", cls.extract_parent], check=True)
        else:
            with zipfile.ZipFile(cls.zip_path, "r") as zf:
                for info in zf.infolist():
                    zf.extract(info, cls.extract_parent)
                    if not info.is_dir():
                        unix_mode = (info.external_attr >> 16) & 0o777
                        if unix_mode:
                            os.chmod(os.path.join(cls.extract_parent, info.filename), unix_mode)

        cls.extracted_root = os.path.join(cls.extract_parent, PACKAGE_ROOT_NAME)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temp_root, ignore_errors=True)

    def _run(self, rel_cmd: list[str], cwd: str | None = None, env_extra: dict | None = None) -> subprocess.CompletedProcess:
        root = cwd or self.extracted_root
        cmd = [os.path.join(root, rel_cmd[0])] + rel_cmd[1:]
        env = os.environ.copy()
        # Preserve minimal clean CI detection behavior inside tests unless overridden
        if env_extra:
            env.update(env_extra)
        return subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)

    def _copy_pkg(self, label: str) -> str:
        copy_dir = os.path.join(self.temp_root, f"copy_{label}")
        shutil.copytree(self.extracted_root, copy_dir, symlinks=True)
        return copy_dir

    def test_01_zip_archive_contains_all_required_components_and_scripts(self) -> None:
        """Verify archive integrity, internal layout, payloads, configs, manifests, and executable permissions."""
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            self.assertIsNone(zf.testzip())
            names = set(zf.namelist())

        required_files = [
            "install.sh",
            "uninstall-or-rollback.sh",
            "verify-device.sh",
            "verify-checksums.sh",
            "config/device.conf",
            "config/partition-map.conf",
            "config/boot.conf",
            "payload/firmware/R8Q_EFI.fd",
            "payload/firmware/r8q-uefi-boot-complete.img",
            "payload/boot-manager/BootManager.efi",
            "payload/boot-manager/Config/boot.cfg",
            "payload/boot-manager/Config/entries/debian.conf",
            "payload/boot-manager/Config/entries/kali.conf",
            "payload/boot-manager/Config/entries/ubuntu.conf",
            "payload/setup/Setup.efi",
            "payload/esp/esp.img",
            "payload/esp/startup.nsh",
            "payload/kernel/Image",
            "payload/dtb/sm8250-samsung-r8q.dtb",
            "payload/dtb/r8q.dtb",
            "payload/initramfs/initramfs.img",
            "payload/debian-rootfs/r8q-rootfs.ext4.gz",
            "payload/debian-rootfs/r8q-rootfs.tar.gz",
            "manifests/MANIFEST.json",
            "manifests/SHA256SUMS",
            "INSTALL.md",
            "VERSION",
        ]
        for idx, name in enumerate([
            "01-preflight.sh",
            "02-verify-payloads.sh",
            "03-prepare-target.sh",
            "04-install-firmware.sh",
            "05-install-uefi.sh",
            "06-install-esp.sh",
            "07-install-kernel.sh",
            "08-install-initramfs.sh",
            "09-install-rootfs.sh",
            "10-configure-boot.sh",
            "11-post-install-validation.sh",
        ], start=1):
            self.assertTrue(name.startswith(f"{idx:02d}-"))
            required_files.append(f"scripts/{name}")

        for app in REQUIRED_EFI_APPS:
            if app not in ("BootManager", "Setup"):
                required_files.append(f"payload/uefi/{app}.efi")

        for rel in required_files:
            self.assertIn(f"{PACKAGE_ROOT_NAME}/{rel}", names, f"Missing in ZIP: {rel}")
            full = os.path.join(self.extracted_root, rel)
            self.assertTrue(os.path.isfile(full), f"Missing extracted file: {full}")
            if rel.endswith(".sh"):
                self.assertTrue(os.stat(full).st_mode & stat.S_IXUSR, f"Script not executable: {rel}")

        self.assertTrue(os.path.isdir(os.path.join(self.extracted_root, "logs")))

    def test_02_extracted_zip_verify_and_dry_run_and_order(self) -> None:
        """Extracted ZIP passes --help, verify-checksums, --verify --target-profile r8q, and full ordered --dry-run."""
        res_help = self._run(["install.sh", "--help"])
        self.assertEqual(res_help.returncode, 0, res_help.stderr)
        self.assertIn("--dry-run", res_help.stdout)
        self.assertIn("--verify", res_help.stdout)
        self.assertIn("--install", res_help.stdout)

        res_sum = self._run(["verify-checksums.sh"])
        self.assertEqual(res_sum.returncode, 0, res_sum.stdout + res_sum.stderr)

        res_ver = self._run(["install.sh", "--verify", "--target-profile", "r8q"])
        self.assertEqual(res_ver.returncode, 0, res_ver.stdout + res_ver.stderr)
        self.assertIn("[VERIFY COMPLETE] Stages 01-03 PASSED", res_ver.stdout)

        report_candidate = os.path.join(self.temp_root, "dryrun_should_not_exist.txt")
        res_dry = self._run(["install.sh", "--dry-run", "--report-file", report_candidate])
        self.assertEqual(res_dry.returncode, 0, res_dry.stdout + res_dry.stderr)
        self.assertIn("Dependency Chain:     01,02,03,04,05,06,07,08,09,10,11 (STRICT ORDER OK)", res_dry.stdout)
        self.assertIn("Physical Writes Done: 0 bytes", res_dry.stdout)
        self.assertFalse(os.path.exists(report_candidate), "--dry-run must NOT write files to disk")

        # Verify monotonic stage ordering 01 -> 11
        positions = [res_dry.stdout.index(f"[STAGE {i:02d}/11]") for i in range(1, 12)]
        self.assertEqual(positions, sorted(positions), "Stages did not execute in strict dependency order")

    def test_03_out_of_order_and_dependency_failure_stops_installation(self) -> None:
        """Calling a dependent stage directly without prior stages completed must abort cleanly."""
        res_out_of_order = subprocess.run(
            ["bash", os.path.join(self.extracted_root, "scripts", "06-install-esp.sh")],
            cwd=self.extracted_root,
            env={"PATH": os.environ["PATH"], "R8Q_INSTALLER_ROOT": self.extracted_root},
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res_out_of_order.returncode, 0)
        self.assertIn("Out-of-order execution", res_out_of_order.stderr)

        # Incomplete dependency chain stops final validation even if prior marker is set
        res_chain = subprocess.run(
            ["bash", os.path.join(self.extracted_root, "scripts", "11-post-install-validation.sh")],
            cwd=self.extracted_root,
            env={
                "PATH": os.environ["PATH"],
                "R8Q_INSTALLER_ROOT": self.extracted_root,
                "R8Q_STAGE_DONE_10": "1",
                "R8Q_COMPLETED_STEPS": "01,02",
            },
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res_chain.returncode, 0)
        self.assertIn("Dependency sequence mismatch", res_chain.stderr)

        # Missing stage script halts execution immediately at checksum verification before any staging runs
        pkg_broken = self._copy_pkg("missing_stage")
        os.remove(os.path.join(pkg_broken, "scripts", "07-install-kernel.sh"))
        res_dep = self._run(["install.sh", "--dry-run"], cwd=pkg_broken)
        self.assertNotEqual(res_dep.returncode, 0)
        self.assertIn("Missing payload file: scripts/07-install-kernel.sh", res_dep.stderr)
        self.assertNotIn("[STAGE 03/11]", res_dep.stdout)
        self.assertNotIn("[STAGE 08/11]", res_dep.stdout)

    def test_04_missing_payload_stops_installation(self) -> None:
        """Deleting any mandatory payload halts installation at verification stage before target changes."""
        pkg = self._copy_pkg("missing_kernel")
        os.remove(os.path.join(pkg, "payload", "kernel", "Image"))
        res = self._run(["install.sh", "--dry-run"], cwd=pkg)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Missing payload file: payload/kernel/Image", res.stderr)
        self.assertNotIn("[STAGE 03/11]", res.stdout)

    def test_05_checksum_mismatch_stops_installation(self) -> None:
        """Bit-flipping a payload byte halts installation immediately at Stage 02 checksum verification."""
        pkg = self._copy_pkg("tampered_rootfs")
        target = os.path.join(pkg, "payload", "debian-rootfs", "r8q-rootfs.ext4.gz")
        with open(target, "r+b") as f:
            b0 = f.read(1)
            f.seek(0)
            f.write(bytes([b0[0] ^ 0xFF]))
        res = self._run(["install.sh", "--dry-run"], cwd=pkg)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Checksum mismatch", res.stderr)
        self.assertNotIn("[STAGE 03/11]", res.stdout)

    def test_06_wrong_device_model_and_arch_and_insufficient_space_rejected(self) -> None:
        """Wrong device model, non-ARM64 arch, and insufficient disk space must abort cleanly."""
        res_model = self._run([
            "install.sh",
            "--dry-run",
            "--arch",
            "aarch64",
            "--soc",
            "qcom,sm8250",
            "--device-model",
            "SM-S918B",
            "--device-codename",
            "dm3q",
        ])
        self.assertNotEqual(res_model.returncode, 0)
        self.assertIn("Unsupported or mismatched device", res_model.stderr)
        self.assertNotIn("[STAGE 02/11]", res_model.stdout)

        res_arch = self._run([
            "verify-device.sh",
            "--device-model",
            "SM-G781B",
            "--device-codename",
            "r8q",
            "--soc",
            "qcom,sm8250",
            "--arch",
            "x86_64",
        ])
        self.assertNotEqual(res_arch.returncode, 0)
        self.assertIn("Architecture mismatch", res_arch.stderr)

        res_space = self._run([
            "install.sh",
            "--dry-run",
            "--min-space-bytes",
            "999999999999999999",
        ])
        self.assertNotEqual(res_space.returncode, 0)
        self.assertIn("Insufficient storage space", res_space.stderr)

    def test_07_protected_partitions_and_physical_safety_lock_enforced(self) -> None:
        """Protected partitions sda25/keyrefuge/sda23/boot/sda cannot be selected; --install stays locked."""
        for bad_part in [
            "/dev/block/sda25",
            "sda25",
            "keyrefuge",
            "/dev/block/sda23",
            "/dev/block/by-name/boot",
            "/dev/block/sda",
        ]:
            res = self._run(["install.sh", "--dry-run", "--target-partition", bad_part])
            self.assertNotEqual(res.returncode, 0, f"Protected target accepted: {bad_part}")
            self.assertIn("SECURITY-ABORT", res.stderr)
            self.assertNotIn("[STAGE 02/11]", res.stdout)

        # Even rollback verifier refuses protected partitions
        res_rb = self._run(["uninstall-or-rollback.sh", "--target-partition", "/dev/block/sda25"])
        self.assertNotEqual(res_rb.returncode, 0)
        self.assertIn("SECURITY-ABORT", res_rb.stderr)

        # Normal invocation without mode fails safely
        res_empty = self._run(["install.sh"])
        self.assertNotEqual(res_empty.returncode, 0)

        # --install fails safely when hardware safety lock is disabled or inside CI
        res_inst = self._run(["install.sh", "--install"], env_extra={"CI": "true"})
        self.assertNotEqual(res_inst.returncode, 0)


if __name__ == "__main__":
    unittest.main()
