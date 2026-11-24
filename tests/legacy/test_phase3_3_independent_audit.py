#!/usr/bin/env python3
"""
Project R8Q UEFI: Phase 3.3 Independent Engineering Audit Test Suite
Automated evidence verification for architectural defects, memory alignment,
relocation offset errors, devicetree compatibility, and release integrity.
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)
Baseline Commit: 4e62ec4
"""

import os
import sys
import struct
import unittest
import hashlib
import json
import subprocess

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
MANIFESTS_DIR = os.path.join(PROJECT_ROOT, "manifests")

class TestPhase33IndependentAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.uefi_fd = os.path.join(BUILD_DIR, "R8Q_EFI.fd")
        cls.complete_img = os.path.join(BUILD_DIR, "r8q-uefi-boot-complete.img")
        cls.kernel_img = os.path.join(BUILD_DIR, "Image")
        cls.dtb_img = os.path.join(BUILD_DIR, "r8q.dtb")
        cls.manifest = os.path.join(MANIFESTS_DIR, "phase3_2_manifest.json")

    def test_audit_01_prepi_relocation_offset_mismatch(self):
        """[P33-ARM64-BOOT-01] Detect relocation offset mismatch in PrePi ModuleEntryPoint."""
        with open(self.uefi_fd, "rb") as f:
            fd_data = f.read()

        # Find _ModuleEntryPoint offset via ARM64 header magic
        magic_idx = fd_data.find(b"ARM\x64")
        self.assertNotEqual(magic_idx, -1, "ARM64 header magic must exist in firmware")
        entry_offset = magic_idx - 0x38  # 0x13E0
        self.assertEqual(entry_offset, 0x13E0, "ModuleEntryPoint should be at offset 0x13E0 in FD")

        # In ModuleEntryPoint, verify adr x20, _ModuleEntryPoint vs FV base
        # adr x20, _ModuleEntryPoint calculates PC relative to entry, NOT FV base (offset 0)
        # Disassembly shows ldr x25, [literal pool] loading target 0x9E401488
        # But copy starts at entry_offset (0x13E0), placing entry at 0x9E400000 instead of 0x9E4013E0!
        target_literal_offset = entry_offset + 0xD0
        reloc_target = struct.unpack("<Q", fd_data[target_literal_offset:target_literal_offset+8])[0]
        self.assertEqual(reloc_target, 0x9E401488, "Literal pool specifies 0x9E401488")
        
        # Prove shift error: entry copied to 0x9E400000 places .Lalready_relocated at 0x9E4000A8, NOT 0x9E401488!
        actual_reloc_code_addr = 0x9E400000 + 0x00A8
        shift_discrepancy = reloc_target - actual_reloc_code_addr
        self.assertEqual(shift_discrepancy, 0x13E0, "Execution branch will jump 0x13E0 (5088 bytes) past relocated code!")

    def test_audit_02_kernel_image_absence_in_boot_image(self):
        """[P33-BOOTCHAIN-ARCH-01] Verify that native Linux kernel Image is missing from complete boot image."""
        with open(self.complete_img, "rb") as f:
            hdr = f.read(1660)

        fmt = "<8s9II16s512s32s1024sIQIIQ"
        fields = struct.unpack(fmt, hdr[:1660])
        kernel_size = fields[1]

        # The kernel slot in boot image v2 contains ONLY the 64B wrapper + 4MB FD
        self.assertEqual(kernel_size, 4194368, "Kernel segment contains only 4 MiB wrapper + FD")
        # Native kernel Image is 16.02 MiB and is entirely omitted
        actual_kernel_size = os.path.getsize(self.kernel_img)
        self.assertGreater(actual_kernel_size, 16 * 1024 * 1024, "Real kernel Image is > 16 MiB")
        self.assertNotEqual(kernel_size, actual_kernel_size + 4194368, "Image is not packed in boot image")

    def test_audit_03_upstream_mainline_dtb_availability(self):
        """[P33-DTB-BINDING-01] Verify upstream Linux 7.2 has native sm8250-samsung-r8q.dts."""
        upstream_dts = "/usr/src/linux/arch/arm64/boot/dts/qcom/sm8250-samsung-r8q.dts"
        self.assertTrue(os.path.isfile(upstream_dts), "Upstream sm8250-samsung-r8q.dts must exist in kernel source")
        with open(upstream_dts, "r") as f:
            content = f.read()
        self.assertIn('compatible = "samsung,r8q", "qcom,sm8250"', content)

    def test_audit_04_recovery_partition_backup_absence(self):
        """[P33-PARTITION-SAFETY-01] Verify that no physical sda24 backup image exists on disk."""
        backup_candidates = [
            "/root/r8q-uefi/sda24_recovery.img",
            "/root/r8q-uefi/build/sda24_recovery.img",
            "/root/sda24_recovery.img"
        ]
        for b in backup_candidates:
            self.assertFalse(os.path.exists(b), f"Recovery backup {b} should not exist yet (requires explicit dump)")

    def test_audit_05_rootfs_ssh_lockout_condition(self):
        """[P33-ROOTFS-SEC-01] Verify that rootfs denies password auth and has empty authorized_keys."""
        staging_dir = "/tmp/r8q_rootfs_staging"
        sshd_cfg = os.path.join(staging_dir, "etc/ssh/sshd_config")
        if os.path.exists(sshd_cfg):
            with open(sshd_cfg, "r") as f:
                cfg = f.read()
            self.assertIn("PasswordAuthentication no", cfg)
            
            # Check authorized_keys in root and r8q home
            root_keys = os.path.join(staging_dir, "root/.ssh/authorized_keys")
            r8q_keys = os.path.join(staging_dir, "home/r8q/.ssh/authorized_keys")
            self.assertFalse(os.path.exists(root_keys) and os.path.getsize(root_keys) > 0, "Root authorized_keys must be empty")
            self.assertFalse(os.path.exists(r8q_keys) and os.path.getsize(r8q_keys) > 0, "User r8q authorized_keys must be empty")

    def test_audit_06_rootfs_hardcoded_user_hash_and_nopasswd_sudo(self):
        """[P33-ROOTFS-SEC-02] Verify static user hash and passwordless sudo configuration."""
        staging_dir = "/tmp/r8q_rootfs_staging"
        shadow_file = os.path.join(staging_dir, "etc/shadow")
        sudoers_r8q = os.path.join(staging_dir, "etc/sudoers.d/r8q")
        if os.path.exists(shadow_file) and os.path.exists(sudoers_r8q):
            with open(shadow_file, "r") as f:
                shadow = f.read()
            self.assertIn("qemuR8Qsec", shadow, "User r8q uses static salt qemuR8Qsec")
            with open(sudoers_r8q, "r") as f:
                sudo = f.read()
            self.assertIn("NOPASSWD: ALL", sudo, "User r8q has unauthenticated sudo access")

    def test_audit_07_artifact_manifest_exact_checksums(self):
        """Verify all artifacts on disk match phase3_2_manifest.json bit-for-bit."""
        with open(self.manifest, "r") as f:
            manifest_data = json.load(f)
        manifest_map = {item["path"]: item["sha256"] for item in manifest_data["files"]}

        checked = 0
        for relpath in ["build/Image", "build/R8Q_EFI.fd", "build/r8q.dtb", "build/r8q-uefi-boot-complete.img", "build/esp.img", "build/initramfs.img", "build/r8q-rootfs.ext4"]:
            if os.path.exists(relpath):
                h = hashlib.sha256()
                with open(relpath, "rb") as f:
                    while chunk := f.read(65536):
                        h.update(chunk)
                self.assertEqual(h.hexdigest(), manifest_map[relpath], f"Checksum mismatch on {relpath}")
                checked += 1
        self.assertEqual(checked, 7, "All 7 core build artifacts must match manifest")

if __name__ == "__main__":
    unittest.main()
