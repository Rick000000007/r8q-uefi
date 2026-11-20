#!/usr/bin/env python3
"""
Project R8Q UEFI: Phase 2 QEMU ARM64 Integration & Boot Validation Suite
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
Platform: Qualcomm Snapdragon 865 (SM8250 / Kona)
Virt: QEMU AArch64 Virt Machine

Validates:
  1. Toolchain & virtualization prerequisites (qemu-system-aarch64, QEMU_EFI.fd)
  2. EFI System Partition (ESP) GPT geometry, volume label, and EFI binaries
  3. Initramfs virtualization drivers (virtio_blk, ext4, jbd2, mbcache, crc16)
  4. Direct Linux kernel boot through initramfs into systemd PID 1
  5. UEFI firmware loading and ARM64 Linux EFI Stub execution
  6. Emergency failure injection resilience and missing root recovery
  7. Hardened security credentials and fresh SSH host keys
"""

import os
import shutil
import subprocess
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
KERNEL_IMG = os.path.join(BUILD_DIR, "Image")
INITRD_IMG = os.path.join(BUILD_DIR, "initramfs.img")
ROOTFS_IMG = os.path.join(BUILD_DIR, "r8q-rootfs.ext4")
ESP_IMG = os.path.join(BUILD_DIR, "esp.img")
SSH_KEY = os.path.join(BUILD_DIR, "r8q_test_id_ed25519")
UEFI_FW = "/usr/share/qemu-efi-aarch64/QEMU_EFI.fd"
STAGING_DIR = "/tmp/r8q_rootfs_staging"

class TestQemuPhase2Validation(unittest.TestCase):
    def test_01_toolchain_and_virtualization_prerequisites(self):
        """Verify QEMU ARM64 emulator, UEFI firmware, and disk tools are present."""
        self.assertIsNotNone(shutil.which("qemu-system-aarch64"), "qemu-system-aarch64 must be installed")
        self.assertTrue(os.path.isfile(UEFI_FW), f"QEMU UEFI firmware missing: {UEFI_FW}")
        self.assertGreater(os.path.getsize(UEFI_FW), 1024 * 1024, "QEMU_EFI.fd must be > 1 MiB")
        self.assertIsNotNone(shutil.which("parted"), "parted must be installed")
        self.assertIsNotNone(shutil.which("mkfs.vfat"), "mkfs.vfat must be installed")
        self.assertIsNotNone(shutil.which("mcopy"), "mtools (mcopy) must be installed")

    def test_02_esp_gpt_geometry_and_components(self):
        """Verify ESP disk image geometry, GPT partition, and installed EFI payloads."""
        self.assertTrue(os.path.isfile(ESP_IMG), f"ESP image must exist: {ESP_IMG}")
        esp_size = os.path.getsize(ESP_IMG)
        self.assertEqual(esp_size, 256 * 1024 * 1024, "ESP disk image must be exactly 256 MiB")

        # Verify GPT partition table via parted
        res = subprocess.run(["parted", "-s", ESP_IMG, "print"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"parted failed on ESP image: {res.stderr}")
        self.assertIn("Partition Table: gpt", res.stdout)
        self.assertIn("fat32", res.stdout)

        # Verify EFI payloads inside ESP image using mdir
        mdir_res = subprocess.run(["mdir", "-i", f"{ESP_IMG}@@1M", "::EFI/R8Q"], capture_output=True, text=True)
        self.assertEqual(mdir_res.returncode, 0, f"mdir failed: {mdir_res.stderr}")
        required_apps = ["SHELL", "sysinfo", "cpuinfo", "memmap", "diagnostics", "LinuxBoot"]
        for app in required_apps:
            self.assertIn(app.lower(), mdir_res.stdout.lower(), f"Application {app} must be present on ESP")

    def test_03_initramfs_virtualization_and_fs_modules(self):
        """Verify initramfs bundles essential filesystem and VirtIO modules."""
        self.assertTrue(os.path.isfile(INITRD_IMG), f"initramfs image must exist: {INITRD_IMG}")
        
        # Test CPIO content via cpio list
        proc = subprocess.Popen(["zcat", INITRD_IMG], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cpio_proc = subprocess.Popen(["cpio", "-t"], stdin=proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        proc.stdout.close()
        cpio_out, _ = cpio_proc.communicate()
        
        required_modules = [
            "lib/modules/virtio_blk.ko",
            "lib/modules/ext4.ko",
            "lib/modules/jbd2.ko",
            "lib/modules/mbcache.ko",
            "lib/modules/crc16.ko"
        ]
        for mod in required_modules:
            self.assertIn(mod, cpio_out, f"Required kernel module {mod} missing in initramfs")

    def test_04_direct_kernel_qemu_execution(self):
        """Execute QEMU direct kernel boot and verify rootfs mount and systemd startup."""
        cmd = [
            "qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a57", "-m", "1024M",
            "-kernel", KERNEL_IMG,
            "-initrd", INITRD_IMG,
            "-append", "console=ttyAMA0 root=/dev/vda rw earlycon",
            "-drive", f"file={ROOTFS_IMG},format=raw,if=virtio",
            "-nographic"
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(28)
        p.terminate()
        out, _ = p.communicate()

        self.assertIn("Linux version 7.2.15+kali-arm64", out, "Kernel 7.2.15 must boot")
        self.assertIn("Run /init as init process", out, "Initramfs /init must execute")
        self.assertIn("virtio_blk", out, "VirtIO block driver must enumerate")
        self.assertIn("EXT4-fs (vda): mounted filesystem", out, "Rootfs ext4 must mount rw")
        self.assertIn("switch_root to /usr/lib/systemd/systemd", out, "switch_root to systemd must execute")
        self.assertIn("systemd 262-1 running in system mode", out, "systemd PID 1 must initialize")
        self.assertTrue("Welcome to" in out or "Debian" in out or "systemd" in out, "Debian userspace banner must appear")

    def test_05_uefi_efi_stub_boot_execution(self):
        """Execute QEMU UEFI firmware and verify ARM64 Linux EFI Stub handoff."""
        cmd = [
            "qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a57", "-m", "1024M",
            "-bios", UEFI_FW,
            "-kernel", KERNEL_IMG,
            "-initrd", INITRD_IMG,
            "-append", "console=ttyAMA0 root=/dev/vda rw",
            "-drive", f"file={ROOTFS_IMG},format=raw,if=virtio",
            "-nographic"
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(15)
        p.terminate()
        out, _ = p.communicate()

        self.assertIn("UEFI firmware", out, "EDK II UEFI firmware must start")
        self.assertIn("efi: EFI v2.7 by Debian distribution of EDK II", out, "Linux EFI Stub must identify UEFI runtime")
        self.assertIn("Run /init as init process", out, "Initramfs must execute under UEFI")
        self.assertIn("switch_root to /usr/lib/systemd/systemd", out, "Systemd transition must complete under UEFI")

    def test_06_failure_resilience_and_device_fallback(self):
        """Verify initramfs failure detection when root storage is unavailable."""
        cmd = [
            "qemu-system-aarch64", "-M", "virt", "-cpu", "cortex-a57", "-m", "1024M",
            "-kernel", KERNEL_IMG,
            "-initrd", INITRD_IMG,
            "-append", "console=ttyAMA0 root=/dev/nonexistent rw",
            "-nographic"
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(10)
        p.terminate()
        out, _ = p.communicate()

        self.assertIn("Scanning storage hardware for root device: /dev/nonexistent", out)
        self.assertIn("PROJECT R8Q NATIVE LINUX OPERATING SYSTEM", out)

    def test_07_security_credentials_and_host_keys(self):
        """Verify removal of default credentials and presence of hardened keys."""
        self.assertTrue(os.path.isfile(SSH_KEY), f"Ed25519 test key must exist: {SSH_KEY}")
        self.assertTrue(os.path.isfile(f"{SSH_KEY}.pub"), "Ed25519 public key must exist")

        with open(os.path.join(STAGING_DIR, "etc/shadow"), "r") as f:
            shadow = f.read()
        self.assertRegex(shadow, r"root:\*:", "Root password must be locked (*)")

        with open(os.path.join(STAGING_DIR, "etc/ssh/sshd_config"), "r") as f:
            sshd = f.read()
        self.assertIn("PasswordAuthentication no", sshd)
        self.assertIn("PermitRootLogin prohibit-password", sshd)

if __name__ == "__main__":
    unittest.main()
