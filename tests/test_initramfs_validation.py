#!/usr/bin/env python3
"""
Project R8Q: Initramfs & Early-Userspace Validation Suite
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
Validates:
  1. Initramfs archive integrity (CPIO format, gzip compression, ARM64 ELF binaries)
  2. Early-userspace /init syntax and executable rights
  3. Storage discovery logic (PARTUUID, UUID, LABEL, loopback image, auto-probe)
  4. Non-destructive safety (zero UFS write commands, read-only defaults)
  5. Fallback emergency rescue shell behavior
"""

import gzip
import os
import re
import stat
import subprocess
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
INITRAMFS_IMG = os.path.join(BUILD_DIR, "initramfs.img")
BUILD_INITRAMFS_SH = os.path.join(SCRIPTS_DIR, "build_initramfs.sh")

class TestInitramfsValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Build fresh initramfs to validate
        result = subprocess.run([BUILD_INITRAMFS_SH], cwd=PROJECT_ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"build_initramfs.sh output: {result.stdout}")
            print(f"build_initramfs.sh error: {result.stderr}")
            raise RuntimeError("Failed to build initramfs for validation")

    def test_01_initramfs_archive_structure(self):
        """Verify initramfs.img is a valid gzip-compressed cpio archive."""
        self.assertTrue(os.path.isfile(INITRAMFS_IMG), "initramfs.img must exist")
        size = os.path.getsize(INITRAMFS_IMG)
        self.assertGreater(size, 500 * 1024, "initramfs.img should be at least 500 KiB")

        # Verify gzip magic number (0x1f, 0x8b)
        with open(INITRAMFS_IMG, "rb") as f:
            magic = f.read(2)
        self.assertEqual(magic, b"\x1f\x8b", "Must begin with gzip magic header 0x1f 0x8b")

        # Decompress and verify CPIO magic ("070701" for newc)
        with gzip.open(INITRAMFS_IMG, "rb") as gz:
            cpio_magic = gz.read(6)
        self.assertEqual(cpio_magic, b"070701", "CPIO header must match ASCII newc format (070701)")

    def test_02_archive_contents_and_applets(self):
        """Extract and verify all critical directories, binaries, and symlinks."""
        result = subprocess.run(
            ["sh", "-c", f"zcat {INITRAMFS_IMG} | cpio -t"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, "cpio table of contents extraction failed")
        entries = set(result.stdout.strip().split("\n"))

        required_entries = [
            "init",
            "bin/busybox",
            "bin/sh",
            "bin/switch_root",
            "bin/mount",
            "bin/umount",
            "bin/blkid",
            "bin/findfs",
            "bin/losetup",
            "bin/dmesg",
            "bin/df",
            "bin/ls",
            "dev",
            "proc",
            "sys",
            "newroot",
            "mnt/storage"
        ]

        for item in required_entries:
            self.assertIn(item, entries, f"Required entry missing from initramfs: {item}")

    def test_03_init_script_safety_and_policy(self):
        """Audit /init script for safety policies, zero-UFS-write policy, and syntax."""
        result = subprocess.run(
            ["sh", "-c", f"zcat {INITRAMFS_IMG} | cpio -i --to-stdout init"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, "Failed to extract init script from cpio")
        init_content = result.stdout

        # Verify bash syntax check
        check = subprocess.run(["sh", "-n"], input=init_content, text=True, capture_output=True)
        self.assertEqual(check.returncode, 0, f"/init syntax error: {check.stderr}")

        # Safety Check 1: Zero write commands to internal UFS /dev/block/sda* or /dev/sda*
        prohibited_write_patterns = [
            r"mkfs\.[a-z0-9]+\s+/dev/sda",
            r"mkfs\.[a-z0-9]+\s+/dev/block/sda",
            r"dd\s+if=.*of=/dev/sda",
            r"dd\s+if=.*of=/dev/block/sda",
            r"mount\s+-o\s+.*rw.*/dev/sda[0-9]+",
            r"mount\s+-o\s+.*rw.*/dev/block/sda[0-9]+"
        ]
        for pattern in prohibited_write_patterns:
            matches = re.findall(pattern, init_content)
            self.assertEqual(len(matches), 0, f"Prohibited write operation detected in /init: {matches}")

        # Safety Check 2: switch_root validation exists
        self.assertIn("switch_root /newroot", init_content, "/init must execute switch_root")
        self.assertIn("/newroot/lib/systemd/systemd", init_content, "systemd init check must be present")
        self.assertIn("/newroot/sbin/init", init_content, "standard /sbin/init check must be present")

        # Safety Check 3: Block device auto-probe support
        self.assertIn("r8q-rootfs", init_content, "Auto-probing for r8q-rootfs must be implemented")
        self.assertIn("losetup", init_content, "Loop device support for virtual images must be present")
        self.assertIn("cat /proc/partitions", init_content, "Rescue diagnostics must display partitions")

    def test_04_elf_architecture(self):
        """Extract busybox and verify it is pure ARM64 ELF."""
        result = subprocess.run(
            ["sh", "-c", f"zcat {INITRAMFS_IMG} | cpio -i --to-stdout bin/busybox"],
            capture_output=True
        )
        self.assertEqual(result.returncode, 0, "Failed to extract bin/busybox")
        elf_data = result.stdout

        # ELF magic: 0x7f, 'E', 'L', 'F'
        self.assertEqual(elf_data[:4], b"\x7fELF", "busybox must have ELF header")
        # Class: 2 = 64-bit
        self.assertEqual(elf_data[4], 2, "busybox must be 64-bit ELF")
        # Data: 1 = Little Endian
        self.assertEqual(elf_data[5], 1, "busybox must be Little Endian")
        # Machine: 183 (0xb7) = AArch64 (ARM64)
        machine = int.from_bytes(elf_data[18:20], byteorder="little")
        self.assertEqual(machine, 183, "busybox must target ARM64 / AArch64 architecture")

if __name__ == "__main__":
    unittest.main()
