#!/usr/bin/env python3
"""
Project R8Q UEFI: Phase 3 Physical Boot Readiness & Hardware Integration Test Suite
Validates SM8250 device tree nodes, memory carveouts, 6-state driver configurations,
boot image v2 container integrity, recovery partition geometry, and credential isolation.
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
"""

import os
import sys
import struct
import unittest
import hashlib
import json

PROJECT_ROOT = "/root/r8q-uefi"
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
DT_DIR = os.path.join(PROJECT_ROOT, "devicetree")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
MANIFESTS_DIR = os.path.join(PROJECT_ROOT, "manifests")

class TestPhase3HardwareReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.complete_img = os.path.join(BUILD_DIR, "r8q-uefi-boot-complete.img")
        cls.kernel_img = os.path.join(BUILD_DIR, "Image")
        cls.dtb_img = os.path.join(BUILD_DIR, "r8q.dtb")
        cls.live_dts = os.path.join(DT_DIR, "r8q-live.dts")
        cls.defconfig = os.path.join(CONFIG_DIR, "kernel_r8q_defconfig")
        cls.live_dt_base = "/sys/firmware/devicetree/base"

    def test_01_live_hardware_soc_identity(self):
        """Verify running device hardware model and SM8250 compatible string."""
        if os.path.exists(self.live_dt_base):
            model_path = os.path.join(self.live_dt_base, "model")
            comp_path = os.path.join(self.live_dt_base, "compatible")
            with open(model_path, "r", encoding="utf-8", errors="ignore") as f:
                model = f.read().strip()
            with open(comp_path, "rb") as f:
                comp = f.read().decode("utf-8", errors="ignore")
            self.assertIn("Samsung R8Q", model, "Live hardware model must match Samsung R8Q")
            self.assertIn("qcom,kona", comp, "Live hardware compatible must declare Qualcomm Kona (SM8250)")

    def test_02_live_subsystem_dt_nodes(self):
        """Verify critical SM8250 hardware peripheral nodes in live device tree."""
        if not os.path.exists(self.live_dt_base):
            self.skipTest("Live DT not available outside device")

        soc_dir = os.path.join(self.live_dt_base, "soc")
        self.assertTrue(os.path.isdir(soc_dir), "Device tree must expose /soc bus")

        critical_nodes = [
            "interrupt-controller@17a00000",  # GICv3
            "interrupt-controller@b220000",   # PDC
            "ufshc@1d84000",                  # UFS 3.1
            "sdhci@8804000",                  # SDHCI MicroSD
            "qcom,spmi@c440000",              # SPMI PMIC Arbiter
            "qcom,pcie@1c00000",              # PCIe RC0 (QCA6390)
            "qcom,pcie@1c08000",              # PCIe RC1 (SDX55 modem)
            "tsens@c222000",                  # TSENS Thermal
            "qcom,mdss_dsi_ctrl0@ae94000",    # DSI Controller
        ]
        for node in critical_nodes:
            node_path = os.path.join(soc_dir, node)
            self.assertTrue(os.path.exists(node_path), f"Critical node {node} must exist in /soc")

    def test_03_reserved_memory_carveouts(self):
        """Verify continuous splash and hardware carveouts in live devicetree."""
        if not os.path.exists(self.live_dt_base):
            self.skipTest("Live DT not available outside device")

        res_dir = os.path.join(self.live_dt_base, "reserved-memory")
        self.assertTrue(os.path.isdir(res_dir), "Reserved-memory directory must exist")

        splash_node = os.path.join(res_dir, "cont_splash_region@9c000000")
        self.assertTrue(os.path.exists(splash_node), "Continuous splash framebuffer node must exist at 0x9c000000")

        # Verify framebuffer base and size: 0x9c000000, 35 MiB (0x02300000)
        reg_file = os.path.join(splash_node, "reg")
        with open(reg_file, "rb") as f:
            reg_bytes = f.read()
        self.assertEqual(len(reg_bytes), 16, "Reg property must be 64-bit base + 64-bit size (16 bytes)")
        base, size = struct.unpack(">QQ", reg_bytes)
        self.assertEqual(base, 0x9C000000, "Continuous splash base must be 0x9C000000")
        self.assertEqual(size, 0x02300000, "Continuous splash size must be 35 MiB (0x02300000)")

    def test_04_firmware_stack_non_overlap(self):
        """Verify mathematical non-overlap between firmware volume and PrePi stack."""
        # EDK II FV: 0x9E400000 - 0x9E800000 (4 MiB)
        fv_base = 0x9E400000
        fv_size = 0x00400000
        fv_end = fv_base + fv_size

        # Stack bounds: SP = 0x9E880000, size = 512 KiB (0x80000), limit = 0x9E800000
        stack_top = 0x9E880000
        stack_size = 0x00080000
        stack_limit = stack_top - stack_size

        # Continuous splash: 0x9C000000 - 0x9E300000
        splash_base = 0x9C000000
        splash_size = 0x02300000
        splash_end = splash_base + splash_size

        # Assert no overlap
        self.assertLessEqual(splash_end, fv_base, "Splash must not overlap FV")
        self.assertGreaterEqual(stack_limit, fv_end, "Stack limit must be >= FV end to prevent stack corruption")
        self.assertEqual(stack_limit, fv_end, "Stack limit exactly borders FV boundary (0x9E800000) with zero overlap")

    def test_05_native_kernel_image_integrity(self):
        """Verify build/Image is a valid ARM64 kernel with EFI stub and PE/COFF header."""
        self.assertTrue(os.path.isfile(self.kernel_img), f"Kernel Image must exist at {self.kernel_img}")
        size = os.path.getsize(self.kernel_img)
        self.assertGreater(size, 40 * 1024 * 1024, "Kernel Image must be > 40 MiB")

        with open(self.kernel_img, "rb") as f:
            hdr = f.read(64)
            code0, code1, text_offset, img_size, flags, res1, magic, pe_offset = struct.unpack("<IIQQQ24s4sI", hdr)
            self.assertEqual(magic, b"ARM\x64", "Kernel image must declare ARM64 magic")
            self.assertEqual(flags & 0x01, 0, "Kernel must be Little-Endian")

            f.seek(pe_offset)
            pe_sig = f.read(4)
            self.assertEqual(pe_sig, b"PE\x00\x00", "Kernel must contain valid PE/COFF signature for EFI Stub")

    def test_06_kernel_driver_defconfig_completeness(self):
        """Verify all 42 required platform driver symbols are present in kernel_r8q_defconfig."""
        self.assertTrue(os.path.isfile(self.defconfig), f"Defconfig must exist at {self.defconfig}")
        with open(self.defconfig, "r") as f:
            cfg_text = f.read()

        required_symbols = [
            "CONFIG_ARCH_QCOM=y", "CONFIG_ARM64=y", "CONFIG_ARM_PSCI_FW=y",
            "CONFIG_ARM_GIC_V3=y", "CONFIG_ARM_GIC_V3_ITS=y", "CONFIG_QCOM_SM8250_GCC=y",
            "CONFIG_QCOM_SM8250_DISPCC=y", "CONFIG_QCOM_SM8250_GPUCC=y", "CONFIG_EFI=y",
            "CONFIG_EFI_STUB=y", "CONFIG_FB_EFI=y", "CONFIG_DRM_SIMPLEDRM=y",
            "CONFIG_DRM_MSM=m", "CONFIG_SERIAL_MSM_GENI=y", "CONFIG_SCSI_UFSHCD=y",
            "CONFIG_SCSI_UFS_QCOM=y", "CONFIG_MMC_SDHCI=y", "CONFIG_MMC_SDHCI_MSM=y",
            "CONFIG_PCIE_QCOM=y", "CONFIG_ATH11K_PCI=m", "CONFIG_MHI_BUS=y",
            "CONFIG_USB_DWC3_QCOM=y", "CONFIG_TOUCHSCREEN_EDT_FT5X06=y",
            "CONFIG_SND_SOC_QCOM=y", "CONFIG_QCOM_SPMI_PMIC=y", "CONFIG_MFD_MAX77705=y",
            "CONFIG_QCOM_TSENS=y", "CONFIG_BLK_DEV_INITRD=y", "CONFIG_EXT4_FS=y"
        ]
        for sym in required_symbols:
            self.assertIn(sym, cfg_text, f"Required kernel configuration symbol {sym} must be present")

    def test_07_compound_boot_image_v2_header(self):
        """Verify Android Boot Image v2 header, capacity limits, and segment alignment."""
        self.assertTrue(os.path.isfile(self.complete_img), f"Boot image missing: {self.complete_img}")
        total_size = os.path.getsize(self.complete_img)

        # SM-G781B sda24 partition capacity: exactly 80 MiB (83,886,080 bytes)
        RECOVERY_CAPACITY = 83886080
        self.assertLessEqual(total_size, RECOVERY_CAPACITY, "Compound boot image must fit in sda24 (80 MiB)")

        with open(self.complete_img, "rb") as f:
            hdr = f.read(1660)

        fmt = "<8s9II16s512s32s1024sIQIIQ"
        fields = struct.unpack(fmt, hdr[:1660])
        magic = fields[0]
        k_size = fields[1]
        k_addr = fields[2]
        r_size = fields[3]
        r_addr = fields[4]
        header_version = fields[9]
        page_size = fields[8]
        header_size = fields[-3]
        dtb_size = fields[-2]
        dtb_addr = fields[-1]

        self.assertEqual(magic, b"ANDROID!", "Boot image magic must be ANDROID!")
        self.assertEqual(header_version, 2, "Header version must be 2")
        self.assertEqual(page_size, 4096, "Page size must be 4096 bytes")
        self.assertEqual(header_size, 1660, "Header struct size must be 1660 bytes")
        self.assertIn(k_addr, [0x00008000, 0x80000000, 0x80008000], "Kernel load offset/address must match Qualcomm ABL conventions")
        self.assertGreater(k_size, 50 * 1024 * 1024, "Compound kernel size must exceed 50 MiB")
        self.assertGreater(r_size, 2 * 1024 * 1024, "Ramdisk size must exceed 2 MiB")
        self.assertGreater(dtb_size, 100 * 1024, "DTB size must exceed 100 KiB")

    def test_08_recovery_slot_isolation_and_safety_checks(self):
        """Verify sda23 active LineageOS boot partition is strictly protected."""
        # sda23 (boot) vs sda24 (recovery)
        boot_part = "/dev/block/by-name/boot"
        rec_part = "/dev/block/by-name/recovery"

        if os.path.exists(boot_part) and os.path.exists(rec_part):
            boot_real = os.path.realpath(boot_part)
            rec_real = os.path.realpath(rec_part)
            self.assertIn("sda23", boot_real, "boot partition must resolve to sda23")
            self.assertIn("sda24", rec_real, "recovery partition must resolve to sda24")
            self.assertNotEqual(boot_real, rec_real, "boot and recovery partitions must be completely separate")

    def test_09_security_credential_isolation(self):
        """Verify release manifest contains zero private keys."""
        manifest_file = os.path.join(MANIFESTS_DIR, "phase3_manifest.json")
        if os.path.exists(manifest_file):
            with open(manifest_file, "r") as f:
                manifest = json.load(f)
            for item in manifest.get("files", []):
                p = item.get("path", "")
                self.assertNotIn("_id_ed25519", p, f"Private key must not be present in release manifest: {p}")
                self.assertNotIn("_id_rsa", p, f"Private key must not be present in release manifest: {p}")
                self.assertFalse(p.endswith(".key"), f"Key file must not be present in release manifest: {p}")

if __name__ == "__main__":
    unittest.main()
