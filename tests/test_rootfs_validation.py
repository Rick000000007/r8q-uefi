#!/usr/bin/env python3
"""
Project R8Q: Native ARM64 Linux Root Filesystem Validation Suite
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
Validates:
  1. ext4 disk image consistency, superblock label, and geometry
  2. FHS 3.0 directory hierarchy and standard permissions
  3. Essential GNU/Linux userspace tools, systemd init, and udev daemon
  4. ARM64 AArch64 ELF binary architecture verification
  5. Complete independence from Android userspace (no bionic, toybox, or Android linker)
  6. Configuration completeness (fstab, hostname, hosts, shadow, sudoers, udev, SSH)
"""

import os
import re
import subprocess
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
ROOTFS_EXT4 = os.path.join(BUILD_DIR, "r8q-rootfs.ext4")
ROOTFS_TAR = os.path.join(BUILD_DIR, "r8q-rootfs.tar.gz")
STAGING_DIR = "/tmp/r8q_rootfs_staging"

class TestNativeRootfsValidation(unittest.TestCase):
    def test_01_artifacts_exist_and_geometry(self):
        """Verify rootfs disk image and archive exist with correct geometry."""
        self.assertTrue(os.path.isfile(ROOTFS_EXT4), f"ext4 image must exist: {ROOTFS_EXT4}")
        self.assertTrue(os.path.isfile(ROOTFS_TAR), f"tarball must exist: {ROOTFS_TAR}")

        # Check raw ext4 image size (2048 MiB = 2,147,483,648 bytes)
        ext4_size = os.path.getsize(ROOTFS_EXT4)
        self.assertEqual(ext4_size, 2048 * 1024 * 1024, "ext4 image size must be exactly 2048 MiB")

        # Check compressed tarball size (between 30 MiB and 500 MiB)
        tar_size = os.path.getsize(ROOTFS_TAR)
        self.assertGreater(tar_size, 30 * 1024 * 1024, "tarball must be > 30 MiB")
        self.assertLess(tar_size, 500 * 1024 * 1024, "tarball must be < 500 MiB")

    def test_02_ext4_filesystem_integrity_and_label(self):
        """Check filesystem consistency with e2fsck and verify volume label."""
        cmd = ["e2fsck", "-f", "-n", ROOTFS_EXT4]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"e2fsck failed on rootfs image: {res.stderr}")
        self.assertIn("r8q-rootfs", res.stdout, "Volume label 'r8q-rootfs' must appear in e2fsck output")

        # Verify dumpe2fs superblock details
        dump_cmd = ["dumpe2fs", "-h", ROOTFS_EXT4]
        dump_res = subprocess.run(dump_cmd, capture_output=True, text=True)
        self.assertEqual(dump_res.returncode, 0, "dumpe2fs failed")
        self.assertIn("Filesystem volume name:   r8q-rootfs", dump_res.stdout)
        self.assertIn("Filesystem state:         clean", dump_res.stdout)

    def test_03_fhs_hierarchy_and_essential_binaries(self):
        """Verify FHS hierarchy and essential GNU utilities exist."""
        required_paths = [
            "bin/bash",
            "bin/sh",
            "bin/ls",
            "bin/cat",
            "bin/cp",
            "bin/mv",
            "bin/rm",
            "bin/mkdir",
            "sbin/e2fsck",
            "usr/bin/dpkg",
            "usr/bin/apt",
            "usr/bin/sudo",
            "usr/sbin/sshd",
            "etc/fstab",
            "etc/hostname",
            "etc/hosts",
            "etc/passwd",
            "etc/shadow",
            "etc/group",
            "etc/sudoers.d/r8q",
            "etc/udev/rules.d/90-sm8250-gpu.rules",
            "etc/udev/rules.d/91-sm8250-touch.rules",
            "etc/udev/rules.d/92-sm8250-power.rules",
            "etc/udev/rules.d/93-sm8250-modem.rules",
            "etc/udev/rules.d/94-sm8250-wifi.rules",
            "etc/ssh/sshd_config",
            "sbin/emergency_rescue.sh"
        ]

        for rel_path in required_paths:
            full_path = os.path.join(STAGING_DIR, rel_path)
            self.assertTrue(os.path.exists(full_path), f"Required file missing in rootfs: {rel_path}")

    def test_04_systemd_init_and_console_configuration(self):
        """Verify systemd init and target console services are present."""
        # Check systemd executable exists in lib or usr/lib
        systemd_path1 = os.path.join(STAGING_DIR, "lib/systemd/systemd")
        systemd_path2 = os.path.join(STAGING_DIR, "usr/lib/systemd/systemd")
        self.assertTrue(os.path.exists(systemd_path1) or os.path.exists(systemd_path2), "systemd init binary must exist")

        # Check default target symlink
        default_target = os.path.join(STAGING_DIR, "etc/systemd/system/default.target")
        self.assertTrue(os.path.islink(default_target), "default.target must be a symlink")

        # Check serial console service on ttyMSM0
        serial_service = os.path.join(STAGING_DIR, "etc/systemd/system/getty.target.wants/serial-getty@ttyMSM0.service")
        self.assertTrue(os.path.exists(serial_service), "serial-getty@ttyMSM0.service must be enabled")

    def test_05_arm64_elf_binary_architecture(self):
        """Verify that binaries in the rootfs are pure ARM64 / AArch64 ELF."""
        test_binaries = ["bin/bash", "usr/sbin/sshd", "usr/bin/dpkg", "sbin/e2fsck"]
        for rel in test_binaries:
            path = os.path.join(STAGING_DIR, rel)
            with open(path, "rb") as f:
                header = f.read(20)
            self.assertEqual(header[:4], b"\x7fELF", f"{rel} must be an ELF binary")
            self.assertEqual(header[4], 2, f"{rel} must be 64-bit (ELFCLASS64)")
            self.assertEqual(header[5], 1, f"{rel} must be Little Endian (ELFDATA2LSB)")
            machine = int.from_bytes(header[18:20], byteorder="little")
            self.assertEqual(machine, 183, f"{rel} must target ARM64 / AArch64 (0xb7 = 183)")

    def test_06_android_independence_and_no_bionic(self):
        """Verify rootfs is completely independent from Android userspace."""
        # 1. No Android linker
        self.assertFalse(os.path.exists(os.path.join(STAGING_DIR, "system/bin/linker64")), "Android linker64 must not exist")
        self.assertFalse(os.path.exists(os.path.join(STAGING_DIR, "system/bin/linker")), "Android linker must not exist")
        # 2. No Android init.rc
        self.assertFalse(os.path.exists(os.path.join(STAGING_DIR, "init.rc")), "Android init.rc must not exist")
        # 3. Dynamic linker check: /lib/ld-linux-aarch64.so.1 or /usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1
        has_gnu_linker = (
            os.path.exists(os.path.join(STAGING_DIR, "lib/ld-linux-aarch64.so.1")) or
            os.path.exists(os.path.join(STAGING_DIR, "usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1")) or
            os.path.exists(os.path.join(STAGING_DIR, "lib/aarch64-linux-gnu/ld-linux-aarch64.so.1"))
        )
        self.assertTrue(has_gnu_linker, "GNU ld-linux-aarch64 dynamic linker must be installed")

    def test_07_user_and_security_configuration(self):
        """Verify user accounts, shadow password hashes, and sudoers permissions."""
        with open(os.path.join(STAGING_DIR, "etc/passwd"), "r") as f:
            passwd_content = f.read()
        self.assertIn("root:x:0:0:root:/root:/bin/bash", passwd_content)
        self.assertIn("r8q:x:1000:1000:R8Q Linux User,,,:/home/r8q:/bin/bash", passwd_content)

        with open(os.path.join(STAGING_DIR, "etc/shadow"), "r") as f:
            shadow_content = f.read()
        # Verify root password is locked (*) to prevent unauthorized password logins
        self.assertRegex(shadow_content, r"root:\*:", "Root password must be locked (*)")
        # Verify r8q user has secure SHA-512 hash
        self.assertRegex(shadow_content, r"r8q:\$6\$", "r8q user password hash must be present")

        # Verify sudoers
        sudoers_file = os.path.join(STAGING_DIR, "etc/sudoers.d/r8q")
        self.assertTrue(os.path.exists(sudoers_file))
        mode = oct(os.stat(sudoers_file).st_mode & 0o777)
        self.assertEqual(mode, "0o440", "sudoers file must have 0440 permissions")

        # Verify hardened SSH daemon configuration
        sshd_config = os.path.join(STAGING_DIR, "etc/ssh/sshd_config")
        self.assertTrue(os.path.exists(sshd_config))
        with open(sshd_config, "r") as f:
            ssh_conf = f.read()
        self.assertIn("PasswordAuthentication no", ssh_conf)
        self.assertIn("PermitRootLogin prohibit-password", ssh_conf)
        self.assertIn("PubkeyAuthentication yes", ssh_conf)

        # Verify credential isolation
        if os.environ.get("PRODUCTION_BUILD", "1") == "1":
            # Production build: static test keys must be eradicated
            root_auth = os.path.join(STAGING_DIR, "root/.ssh/authorized_keys")
            if os.path.isfile(root_auth):
                with open(root_auth, "r") as f:
                    self.assertNotIn("r8q-automated-test-key", f.read())
        else:
            self.assertTrue(os.path.isfile(os.path.join(STAGING_DIR, "root/.ssh/authorized_keys")))
            self.assertTrue(os.path.isfile(os.path.join(STAGING_DIR, "home/r8q/.ssh/authorized_keys")))

if __name__ == "__main__":
    unittest.main()
