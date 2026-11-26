#!/usr/bin/env python3
"""
Project R8Q: TWRP Recovery Installer Compatibility & Sandbox Test Suite

Verifies R8Q-Debian12-ARM64-TWRP-Installer.zip in an isolated TWRP-mimicking
BusyBox ash environment (NO GNU bash and NO python3 in PATH), testing:
  1. ZIP32 (non-ZIP64) layout and root META-INF/com/google/android/{update-binary,updater-script}
  2. Real pipe OUTFD protocol (`ui_print` / `set_progress`) under BusyBox ash
  3. Recovery argument validation (API version, OUTFD, ZIP path)
  4. Package extraction to staging workspace and cleanup
  5. Complete 19-step / 11-stage dry-run execution via update-binary -> install.sh
  6. Tampered payload / wrong model / insufficient space / sda25 protection halt & exit codes
  7. AOSP SignApk v1 WholeFileSignature EOCD footer verification with ephemeral test key
"""

from __future__ import annotations

import gzip
import os
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

sys.dont_write_bytecode = True

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from build_unified_installer import (  # noqa: E402
    PACKAGE_ROOT_NAME,
    TWRP_META_DEFAULT_DIR,
    assemble_installer_tree,
    sign_zip_whole_file,
    write_installer_zip,
)
from validate_and_stage_distribution import REQUIRED_EFI_APPS  # noqa: E402


TWRP_APPLETS = [
    "[",
    "ash",
    "awk",
    "basename",
    "cat",
    "chmod",
    "cpio",
    "cut",
    "date",
    "dd",
    "df",
    "dirname",
    "grep",
    "gunzip",
    "gzip",
    "head",
    "hexdump",
    "id",
    "ls",
    "mkdir",
    "mktemp",
    "od",
    "printf",
    "readlink",
    "rm",
    "sed",
    "sh",
    "sha256sum",
    "sleep",
    "sort",
    "stat",
    "tail",
    "tar",
    "test",
    "tr",
    "uname",
    "unzip",
    "wc",
]


def _pe32plus_aa64_stub() -> bytes:
    buf = bytearray(512)
    buf[:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x80)
    buf[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", buf, 0x84, 0xAA64)
    return bytes(buf)


def _cpio_newc(entries: dict[str, bytes]) -> bytes:
    all_items = list(entries.items())
    # Pad archive past 1 MiB CPIO minimum threshold checked in 08-install-initramfs.sh
    all_items.append(("usr/share/r8q-pad", b"\x00" * 1_100_000))
    out = bytearray()
    for ino, (name, data) in enumerate(all_items, start=1):
        nb = name.encode("utf-8") + b"\x00"
        hdr = (
            f"070701{ino:08x}{0o100755:08x}{0:08x}{0:08x}{1:08x}{0:08x}"
            f"{len(data):08x}{0:08x}{0:08x}{0:08x}{0:08x}{len(nb):08x}{0:08x}"
        ).encode("ascii")
        out.extend(hdr)
        out.extend(nb)
        while len(out) % 4:
            out.append(0)
        out.extend(data)
        while len(out) % 4:
            out.append(0)
    out.extend(
        f"070701{len(all_items) + 1:08x}{0:08x}{0:08x}{0:08x}{1:08x}{0:08x}"
        f"{0:08x}{0:08x}{0:08x}{0:08x}{0:08x}{11:08x}{0:08x}".encode("ascii")
        + b"TRAILER!!!\x00"
    )
    while len(out) % 4:
        out.append(0)
    return bytes(out)


def _create_twrp_mock_sources(base_dir: str) -> dict[str, object]:
    src = os.path.join(base_dir, "mock_sources")
    efi_dir = os.path.join(src, "efi")
    os.makedirs(efi_dir, exist_ok=True)

    fd_path = os.path.join(src, "R8Q_EFI.fd")
    fd_buf = bytearray(4_194_304)
    fd_buf[0x28:0x2C] = b"_FVH"
    with open(fd_path, "wb") as f:
        f.write(fd_buf)

    boot_path = os.path.join(src, "r8q-uefi-boot-complete.img")
    boot_buf = bytearray(8192)
    boot_buf[:8] = b"ANDROID!"
    struct.pack_into("<I", boot_buf, 40, 2)
    with open(boot_path, "wb") as f:
        f.write(boot_buf)

    pe_stub = _pe32plus_aa64_stub()
    for app in REQUIRED_EFI_APPS:
        with open(os.path.join(efi_dir, f"{app}.efi"), "wb") as f:
            f.write(pe_stub)

    esp_path = os.path.join(src, "esp.img")
    with open(esp_path, "wb") as f:
        f.seek(268_435_456 - 1)
        f.write(b"\x00")
    with open(esp_path, "r+b") as f:
        f.seek(510)
        f.write(b"\x55\xaaEFI PART")

    img_path = os.path.join(src, "Image")
    img_buf = bytearray(8192)
    img_buf[:2] = b"MZ"
    img_buf[0x38:0x3C] = b"ARM\x64"
    with open(img_path, "wb") as f:
        f.write(img_buf)

    dtb_buf = bytearray(4096)
    struct.pack_into(">6I", dtb_buf, 0, 0xD00DFEED, len(dtb_buf), 0x40, 0x200, 0x30, 17)
    live_dtb = os.path.join(src, "r8q.dtb")
    with open(live_dtb, "wb") as f:
        f.write(dtb_buf)

    initrd_path = os.path.join(src, "initramfs.img")
    cpio_bytes = _cpio_newc({
        "init": b"#!/bin/busybox sh\n",
        "bin/busybox": b"\x7fELF",
        "lib/ld-linux-aarch64.so.1": b"\x7fELF",
        "lib/libc.so.6": b"\x7fELF",
        "lib/modules/virtio_blk.ko": b"\x7fELF",
        "lib/modules/ext4.ko": b"\x7fELF",
        "lib/modules/jbd2.ko": b"\x7fELF",
        "lib/modules/mbcache.ko": b"\x7fELF",
        "lib/modules/crc16.ko": b"\x7fELF",
    })
    with gzip.open(initrd_path, "wb") as gz:
        gz.write(cpio_bytes)

    ext4_gz = os.path.join(src, "r8q-rootfs.ext4.gz")
    ext4_hdr = bytearray(4096)
    ext4_hdr[1024 + 0x38:1024 + 0x3A] = b"\x53\xef"
    with gzip.open(ext4_gz, "wb") as gz:
        gz.write(ext4_hdr)

    tar_gz = os.path.join(src, "r8q-rootfs.tar.gz")
    with tarfile.open(tar_gz, "w:gz") as tar:
        for name, data in [
            ("bin/bash", b"\x7fELF" + b"\x00" * 16),
            ("usr/bin/apt", b"\x7fELF"),
            ("etc/sudoers.d/r8q", b"r8q ALL=(ALL) NOPASSWD:ALL\n"),
            ("etc/systemd/system/getty.target.wants/getty@tty1.service", b"[Unit]\n"),
            ("etc/systemd/system/getty.target.wants/serial-getty@ttyMSM0.service", b"[Unit]\n"),
            ("usr/share/r8q-test-blob", os.urandom(33 * 1024 * 1024)),
        ]:
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tar.addfile(ti, fileobj=gzip.io.BytesIO(data) if hasattr(gzip, "io") else __import__("io").BytesIO(data))
        sym = tarfile.TarInfo("etc/systemd/system/default.target")
        sym.type = tarfile.SYMTYPE
        sym.linkname = "/lib/systemd/system/multi-user.target"
        tar.addfile(sym)

    return {
        "fd": fd_path,
        "boot_img": boot_path,
        "efi_dir": efi_dir,
        "esp": esp_path,
        "image": img_path,
        "live_dtb": live_dtb,
        "initrd": initrd_path,
        "rootfs_ext4_gz": ext4_gz,
        "rootfs_tar_gz": tar_gz,
        "canonical_dtb_bytes": bytes(dtb_buf),
    }


def _create_twrp_busybox_sbin(sbin_dir: str) -> str:
    """Create a sterile recovery bin directory with BusyBox applets and zero bash/python3."""
    bb = shutil.which("busybox")
    if not bb:
        raise unittest.SkipTest("busybox binary is required for TWRP sterile recovery simulation")
    os.makedirs(sbin_dir, exist_ok=True)
    for applet in TWRP_APPLETS:
        dst = os.path.join(sbin_dir, applet)
        if not os.path.exists(dst):
            os.symlink(bb, dst)
    return sbin_dir


class TestTwrpInstallerCompatibility(unittest.TestCase):
    """Test TWRP recovery ZIP layout, update-binary protocol, BusyBox compatibility, and safety."""

    temp_root: str
    zip_path: str
    twrp_sbin: str
    stage_base: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_root = tempfile.mkdtemp(prefix="r8q_twrp_test_")
        cls.twrp_sbin = _create_twrp_busybox_sbin(os.path.join(cls.temp_root, "twrp_sbin"))
        cls.stage_base = os.path.join(cls.temp_root, "twrp_tmp")
        os.makedirs(cls.stage_base, exist_ok=True)

        env_zip = os.environ.get("R8Q_TWRP_INSTALLER_ZIP", "")
        if env_zip and os.path.isfile(env_zip):
            cls.zip_path = env_zip
        else:
            sources = _create_twrp_mock_sources(cls.temp_root)
            pkg_dir = assemble_installer_tree(PROJECT_ROOT, cls.temp_root, "v1.0.0-twrp-test", sources)
            cls.zip_path = os.path.join(cls.temp_root, "R8Q-Debian12-ARM64-TWRP-Installer.zip")
            write_installer_zip(pkg_dir, cls.zip_path, twrp_meta_dir=TWRP_META_DEFAULT_DIR)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temp_root, ignore_errors=True)

    def _run_twrp_update_binary(
        self,
        zip_path: str,
        api_ver: str = "3",
        extra_env: dict[str, str] | None = None,
        override_outfd: str | None = None,
        omit_zip_arg: bool = False,
    ) -> tuple[int, str, str, str]:
        """Simulate TeamWin twinstall.cpp Run_Update_Binary using pipe FD and BusyBox sh only."""
        with tempfile.TemporaryDirectory(prefix="ub_run_", dir=self.temp_root) as ub_dir:
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                ub_bytes = zf.read("META-INF/com/google/android/update-binary")
            ub_path = os.path.join(ub_dir, "update_binary")
            with open(ub_path, "wb") as f:
                f.write(ub_bytes)
            os.chmod(ub_path, 0o755)

            sh_bin = os.path.join(self.twrp_sbin, "sh")
            env = {
                "PATH": self.twrp_sbin,
                "R8Q_SH_BIN": sh_bin,
                "R8Q_UNZIP_BIN": os.path.join(self.twrp_sbin, "unzip"),
                "R8Q_STAGE_BASE": self.stage_base,
            }
            if extra_env:
                env.update(extra_env)

            # Confirm neither bash nor python3 resolves inside TWRP sterile PATH
            assert shutil.which("bash", path=env["PATH"]) is None
            assert shutil.which("python3", path=env["PATH"]) is None

            r_fd, w_fd = os.pipe()
            try:
                outfd_arg = override_outfd if override_outfd is not None else str(w_fd)
                cmd = [sh_bin, ub_path]
                if omit_zip_arg:
                    cmd.extend([api_ver, outfd_arg])
                else:
                    cmd.extend([api_ver, outfd_arg, zip_path])

                proc = subprocess.Popen(
                    cmd,
                    env=env,
                    pass_fds=(w_fd,),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                os.close(w_fd)
                w_fd = -1

                with os.fdopen(r_fd, "r", encoding="utf-8", errors="replace") as pf:
                    pipe_output = pf.read()
                r_fd = -1
                stdout_data, stderr_data = proc.communicate(timeout=300)
                return proc.returncode, pipe_output, stdout_data, stderr_data
            finally:
                if r_fd != -1:
                    os.close(r_fd)
                if w_fd != -1:
                    os.close(w_fd)

    def test_01_twrp_zip_format_root_metainf_and_permissions(self) -> None:
        """Verify ZIP root META-INF TWRP files, POSIX permissions, and strict non-ZIP64 EOCD."""
        with zipfile.ZipFile(self.zip_path, "r") as zf:
            self.assertIsNone(zf.testzip())
            infos = {i.filename: i for i in zf.infolist()}

        self.assertIn("META-INF/com/google/android/update-binary", infos)
        self.assertIn("META-INF/com/google/android/updater-script", infos)
        self.assertIn(f"{PACKAGE_ROOT_NAME}/install.sh", infos)
        self.assertIn(f"{PACKAGE_ROOT_NAME}/scripts/lib-common.sh", infos)

        ub_info = infos["META-INF/com/google/android/update-binary"]
        ub_mode = (ub_info.external_attr >> 16) & 0o777
        self.assertEqual(ub_mode, 0o755, "update-binary must have 0755 executable permissions")
        self.assertGreater(ub_info.file_size, 500)

        # Ensure standard 32-bit EOCD without ZIP64 locator/record for minzip & libziparchive compatibility
        with open(self.zip_path, "rb") as f:
            tail = f.read()[-65536:] if os.path.getsize(self.zip_path) > 65536 else f.read()
        self.assertIn(b"PK\x05\x06", tail)
        self.assertNotIn(b"PK\x06\x06", tail, "ZIP64 End of Central Directory must not be present")
        self.assertNotIn(b"PK\x06\x07", tail, "ZIP64 EOCD Locator must not be present")

    def test_02_twrp_update_binary_dry_run_pipe_protocol_under_busybox_only(self) -> None:
        """Execute update-binary -> install.sh in sterile BusyBox recovery PATH (no bash/python3)."""
        rc, pipe_out, stdout_data, stderr_data = self._run_twrp_update_binary(self.zip_path)
        self.assertEqual(rc, 0, f"stderr={stderr_data}\npipe={pipe_out}")

        lines = pipe_out.splitlines()
        ui_lines = [ln[9:] for ln in lines if ln.startswith("ui_print ")]
        prog_vals = [float(ln.split()[1]) for ln in lines if ln.startswith("set_progress ")]

        self.assertGreaterEqual(len(prog_vals), 12)
        self.assertEqual(prog_vals, sorted(prog_vals), "TWRP set_progress values must be monotonically increasing")
        self.assertGreaterEqual(prog_vals[0], 0.0)
        self.assertEqual(prog_vals[-1], 1.0)

        joined_ui = "\n".join(ui_lines)
        for expected_stage in range(1, 12):
            self.assertIn(f"[STAGE {expected_stage:02d}/11]", joined_ui)
        self.assertIn("Dependency Chain:     01,02,03,04,05,06,07,08,09,10,11 (STRICT ORDER OK)", joined_ui)
        self.assertIn("Physical Writes Done: 0 bytes", joined_ui)
        self.assertIn("SUCCESS: Project R8Q installer finished (--dry-run).", joined_ui)

        # Staging directory must clean itself up completely
        leftovers = os.listdir(self.stage_base)
        self.assertEqual(leftovers, [], f"Leftover staging directories remained: {leftovers}")

    def test_03_twrp_argument_validation_and_malformed_zip_rejection(self) -> None:
        """Validate update-binary rejects bad API version, bad OUTFD, missing ZIP, or missing install.sh."""
        rc_omit, _, _, _ = self._run_twrp_update_binary(self.zip_path, omit_zip_arg=True)
        self.assertEqual(rc_omit, 2)

        rc_api, _, _, _ = self._run_twrp_update_binary(self.zip_path, api_ver="0")
        self.assertEqual(rc_api, 2)

        rc_fd, _, _, _ = self._run_twrp_update_binary(self.zip_path, override_outfd="notafd")
        self.assertEqual(rc_fd, 2)

        rc_missing, pipe_m, _, _ = self._run_twrp_update_binary("/nonexistent/missing.zip")
        self.assertEqual(rc_missing, 3)
        self.assertIn("Installer ZIP package missing", pipe_m)

        # ZIP lacking R8Q-Debian12-ARM64-Installer/install.sh must fail cleanly
        bad_zip = os.path.join(self.temp_root, "missing_master.zip")
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("META-INF/com/google/android/update-binary", "#!/sbin/sh\n")
            zf.writestr("dummy.txt", "hello")
        rc_nomaster, pipe_nm, _, _ = self._run_twrp_update_binary(bad_zip)
        self.assertEqual(rc_nomaster, 5)
        self.assertIn("install.sh", pipe_nm)

    def test_04_twrp_error_propagation_tampered_payload_protected_partition_and_device(self) -> None:
        """Verify update-binary stops cleanly on tampered checksum, sda25 target, wrong model, and safety lock."""
        # 1. Protected partition sda25 must abort with exit 14 before Stage 02
        rc_p, pipe_p, _, _ = self._run_twrp_update_binary(
            self.zip_path,
            extra_env={"R8Q_TARGET_PARTITION": "/dev/block/sda25"},
        )
        self.assertEqual(rc_p, 14)
        self.assertIn("SECURITY-ABORT", pipe_p)
        self.assertIn("exit code 14", pipe_p)
        self.assertNotIn("[STAGE 02/11]", pipe_p)

        # 2. Wrong device model / codename must abort at Stage 01 with exit 11
        rc_m, pipe_m, _, _ = self._run_twrp_update_binary(
            self.zip_path,
            extra_env={"R8Q_DEVICE_MODEL": "SM-S918B", "R8Q_DEVICE_CODENAME": "dm3q"},
        )
        self.assertEqual(rc_m, 11)
        self.assertIn("Unsupported or mismatched device", pipe_m)
        self.assertNotIn("[STAGE 02/11]", pipe_m)

        # 3. Forced --install mode must halt at Stage 03 safety lock (exit 42 or CI exit 30)
        rc_inst, pipe_inst, _, _ = self._run_twrp_update_binary(
            self.zip_path,
            extra_env={"R8Q_INSTALL_MODE": "install"},
        )
        self.assertNotEqual(rc_inst, 0)
        self.assertIn("FAILED: Installation halted cleanly", pipe_inst)
        self.assertNotIn("[STAGE 04/11]", pipe_inst)

        # 4. Tampered ZIP payload
        tampered_zip = os.path.join(self.temp_root, "tampered_twrp.zip")
        with (
            zipfile.ZipFile(self.zip_path, "r") as zin,
            zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as zout,
        ):
            for item in zin.infolist():
                if item.is_dir():
                    zout.writestr(item, b"")
                    continue
                data = zin.read(item.filename)
                if item.filename == f"{PACKAGE_ROOT_NAME}/payload/kernel/Image":
                    data = bytes([data[0] ^ 0xFF]) + data[1:]
                info = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                info.external_attr = item.external_attr
                info.compress_type = zipfile.ZIP_STORED
                zout.writestr(info, data)
        rc_t, pipe_t, _, _ = self._run_twrp_update_binary(tampered_zip)
        self.assertNotEqual(rc_t, 0)
        self.assertIn("Checksum mismatch", pipe_t)
        self.assertNotIn("[STAGE 03/11]", pipe_t)

    def test_05_whole_file_signature_footer_format_matches_twrp_verifier(self) -> None:
        """Verify optional SignApk v1 WholeFileSignature footer layout matches twrpinstall/verifier.cpp."""
        if not shutil.which("openssl"):
            self.skipTest("openssl is required for WholeFileSignature verification test")

        with tempfile.TemporaryDirectory(prefix="twrp_sig_", dir=self.temp_root) as sig_dir:
            key_pem = os.path.join(sig_dir, "ephemeral_test.key.pem")
            cert_pem = os.path.join(sig_dir, "ephemeral_test.x509.pem")
            signed_zip = os.path.join(sig_dir, "signed_test.zip")

            # Generate ephemeral test-only RSA-2048 cert/key strictly in temporary directory
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-keyout",
                    key_pem,
                    "-out",
                    cert_pem,
                    "-days",
                    "1",
                    "-nodes",
                    "-subj",
                    "/CN=R8Q Ephemeral Test/",
                ],
                check=True,
                capture_output=True,
            )

            small_zip = os.path.join(sig_dir, "sample.zip")
            with zipfile.ZipFile(small_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zf:
                zf.writestr("META-INF/com/google/android/update-binary", "#!/sbin/sh\necho ok\n")
            shutil.copy2(small_zip, signed_zip)
            sign_zip_whole_file(signed_zip, cert_pem, key_pem)

            # Parse footer identically to twrpinstall/verifier.cpp
            with open(signed_zip, "rb") as f:
                data = f.read()
            footer = data[-6:]
            sig_start, magic, comment_len = struct.unpack("<HHH", footer)
            self.assertEqual(magic, 0xFFFF)
            self.assertGreater(sig_start, 6)
            self.assertLessEqual(sig_start, comment_len)

            eocd_size = comment_len + 22
            eocd = data[-eocd_size:]
            self.assertEqual(eocd[:4], b"PK\x05\x06")
            self.assertNotIn(b"PK\x05\x06", eocd[4:])

            # Verify CMS SignedData DER over bytes [0 .. signed_len)
            signed_len = len(data) - eocd_size + 22 - 2
            content_file = os.path.join(sig_dir, "signed_content.bin")
            sig_file = os.path.join(sig_dir, "sig.der")
            with open(content_file, "wb") as f:
                f.write(data[:signed_len])
            with open(sig_file, "wb") as f:
                f.write(data[-sig_start:-6])

            res = subprocess.run(
                [
                    "openssl",
                    "cms",
                    "-verify",
                    "-inform",
                    "DER",
                    "-in",
                    sig_file,
                    "-content",
                    content_file,
                    "-binary",
                    "-certfile",
                    cert_pem,
                    "-noverify",
                    "-out",
                    os.devnull,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            with zipfile.ZipFile(signed_zip, "r") as zchk:
                self.assertIsNone(zchk.testzip())


if __name__ == "__main__":
    unittest.main()
