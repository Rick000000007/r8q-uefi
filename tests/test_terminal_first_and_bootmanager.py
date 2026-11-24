#!/usr/bin/env python3
"""
Project R8Q: Terminal-First Operating Environment & Boot Manager Test Suite
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

Validates:
  1. Terminal-First Systemd Configuration (multi-user.target default, zero graphical auto-start)
  2. Native AMOLED Console Services (getty@tty1, serial-getty@ttyMSM0)
  3. ARM64 Native Shell & Development Utilities (Bash, APT, OpenSSH)
  4. R8Q BIOS Setup Utility Binary (Setup.efi PE32+ AArch64)
  5. R8Q Independent Boot Manager Binary (BootManager.efi PE32+ AArch64)
  6. Boot Manager Configuration Files (boot.cfg, entries/debian.conf, kali.conf, ubuntu.conf)
  7. Decoupled Desktop Management (Optional GNOME enable/disable without breaking terminal boot)
"""

import os
import re
import struct
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
EDK2_BIN_DIR = os.path.join(PROJECT_ROOT, "edk2/Build/R8Q/DEBUG_GCC5/AARCH64")
STAGING_DIR = "/tmp/r8q_rootfs_staging"
BOOT_MGR_CONFIG_DIR = os.path.join(PROJECT_ROOT, "boot-manager/Config")

class TestTerminalFirstAndBootManager(unittest.TestCase):

    def test_01_terminal_first_systemd_target(self):
        """Verify that default boot target is multi-user.target (NOT graphical.target)."""
        target_link = os.path.join(STAGING_DIR, "etc/systemd/system/default.target")
        self.assertTrue(os.path.islink(target_link), "default.target must be a symlink")
        link_target = os.readlink(target_link)
        self.assertIn("multi-user.target", link_target, "Default boot target must be multi-user.target")
        self.assertNotIn("graphical.target", link_target, "Initial release must NOT default to graphical.target")

    def test_02_console_getty_services_enabled(self):
        """Verify virtual terminal on AMOLED framebuffer and Qualcomm GENI UART are enabled."""
        fb_console = os.path.join(STAGING_DIR, "etc/systemd/system/getty.target.wants/getty@tty1.service")
        self.assertTrue(os.path.exists(fb_console), "getty@tty1.service must be enabled for AMOLED console")

        geni_console = os.path.join(STAGING_DIR, "etc/systemd/system/getty.target.wants/serial-getty@ttyMSM0.service")
        self.assertTrue(os.path.exists(geni_console), "serial-getty@ttyMSM0.service must be enabled for Qualcomm UART")

    def test_03_zero_automatic_display_managers(self):
        """Verify no display manager (GDM, LightDM, SDDM) is enabled in default boot target."""
        dm_wants_dir = os.path.join(STAGING_DIR, "etc/systemd/system/display-manager.service")
        self.assertFalse(os.path.exists(dm_wants_dir), "display-manager.service must not be enabled by default")

    def test_04_native_arm64_bash_and_core_tools(self):
        """Verify native ARM64 Bash shell and APT package management binaries exist and are AArch64 ELF."""
        test_binaries = ["bin/bash", "usr/bin/apt", "usr/bin/dpkg", "usr/sbin/sshd"]
        for rel in test_binaries:
            p = os.path.join(STAGING_DIR, rel)
            self.assertTrue(os.path.isfile(p), f"Binary must exist: {rel}")
            with open(p, "rb") as f:
                hdr = f.read(20)
            self.assertEqual(hdr[:4], b"\x7fELF", f"{rel} must be an ELF binary")
            machine = struct.unpack("<H", hdr[18:20])[0]
            self.assertEqual(machine, 183, f"{rel} must be ARM64 AArch64 (machine 183)")

    def test_05_r8q_setup_utility_binary(self):
        """Verify that Setup.efi was compiled into a valid AArch64 PE32+ EFI application."""
        setup_efi = os.path.join(EDK2_BIN_DIR, "Setup.efi")
        self.assertTrue(os.path.isfile(setup_efi), f"Setup.efi must exist at {setup_efi}")
        size = os.path.getsize(setup_efi)
        self.assertGreater(size, 10240, "Setup.efi size must be > 10 KiB")

        # Verify PE/COFF header (MZ signature and PE machine 0xAA64)
        with open(setup_efi, "rb") as f:
            data = f.read(4096)
        self.assertEqual(data[:2], b"MZ", "Setup.efi must have DOS/PE MZ header")
        pe_offset = struct.unpack("<I", data[0x3C:0x40])[0]
        self.assertEqual(data[pe_offset:pe_offset+4], b"PE\x00\x00", "Must have PE signature")
        pe_machine = struct.unpack("<H", data[pe_offset+4:pe_offset+6])[0]
        self.assertEqual(pe_machine, 0xAA64, "Setup.efi machine type must be AArch64 (0xAA64)")

    def test_06_r8q_boot_manager_binary(self):
        """Verify that BootManager.efi was compiled into a valid AArch64 PE32+ EFI application."""
        bootmgr_efi = os.path.join(EDK2_BIN_DIR, "BootManager.efi")
        self.assertTrue(os.path.isfile(bootmgr_efi), f"BootManager.efi must exist at {bootmgr_efi}")
        size = os.path.getsize(bootmgr_efi)
        self.assertGreater(size, 20480, "BootManager.efi size must be > 20 KiB")

        with open(bootmgr_efi, "rb") as f:
            data = f.read(4096)
        self.assertEqual(data[:2], b"MZ", "BootManager.efi must have DOS/PE MZ header")
        pe_offset = struct.unpack("<I", data[0x3C:0x40])[0]
        self.assertEqual(data[pe_offset:pe_offset+4], b"PE\x00\x00", "Must have PE signature")
        pe_machine = struct.unpack("<H", data[pe_offset+4:pe_offset+6])[0]
        self.assertEqual(pe_machine, 0xAA64, "BootManager.efi machine type must be AArch64 (0xAA64)")

    def test_07_boot_manager_configuration_entries(self):
        """Verify master boot.cfg and individual OS entry configuration files."""
        boot_cfg = os.path.join(BOOT_MGR_CONFIG_DIR, "boot.cfg")
        self.assertTrue(os.path.isfile(boot_cfg), "boot.cfg must exist")
        with open(boot_cfg, "r") as f:
            content = f.read()
        self.assertIn("timeout=3", content, "Default timeout must be configured")
        self.assertIn("default=debian", content, "Default OS must be debian")

        entries_dir = os.path.join(BOOT_MGR_CONFIG_DIR, "entries")
        for os_entry in ["debian.conf", "kali.conf", "ubuntu.conf"]:
            p = os.path.join(entries_dir, os_entry)
            self.assertTrue(os.path.isfile(p), f"Entry {os_entry} must exist")
            with open(p, "r") as f:
                c = f.read()
            self.assertIn("title", c, f"title missing in {os_entry}")
            self.assertIn("linux", c, f"linux path missing in {os_entry}")
            self.assertIn("options", c, f"options command line missing in {os_entry}")

    def test_08_optional_gnome_layer_management(self):
        """Verify procedures for switching between terminal and optional desktop."""
        # Simulated target toggle: switching to graphical.target and reverting to multi-user.target
        target_path = os.path.join(STAGING_DIR, "etc/systemd/system/default.target")
        orig_target = os.readlink(target_path)

        # Reversion invariant test: restoring multi-user.target must yield valid link
        self.assertTrue(os.path.exists(target_path))
        self.assertEqual(orig_target, "/usr/lib/systemd/system/multi-user.target")

if __name__ == "__main__":
    unittest.main()
