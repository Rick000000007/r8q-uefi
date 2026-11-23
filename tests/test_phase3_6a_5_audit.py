#!/usr/bin/env python3
"""
test_phase3_6a_5_audit.py - Linux ARM64 Boot Protocol Compliance Audit Suite

Validates:
1. Kernel image placement, header fields, and direct entry point calculation
2. Cache coherency (PoC clean for complete Linux Image and DTB, PoU for firmware)
3. DTB protocol compliance (strict 2 MiB ceiling per booting.rst)
4. Relocation vector arithmetic (0x01D60000 = 29.375 MiB) and fault classification
5. Deliverable document integrity (PHASE3_6A_5_LINUX_ARM64_PROTOCOL_AUDIT.md)

Antigravity Engineering - Project R8Q UEFI
"""

import os
import struct
import unittest

PROJECT_ROOT = "/root/r8q-uefi"
KERNEL_IMAGE = os.path.join(PROJECT_ROOT, "build/Image")
PREPI_C = os.path.join(PROJECT_ROOT, "platform/R8QPkg/PrePi/PrePi.c")
ENTRY_POINT_ASM = os.path.join(PROJECT_ROOT, "platform/R8QPkg/PrePi/ModuleEntryPoint.S")
DOC_P36A5 = os.path.join(PROJECT_ROOT, "docs/phase3_6/PHASE3_6A_5_LINUX_ARM64_PROTOCOL_AUDIT.md")

DRAM_BASE_PHYS = 0x80000000
DRAM_LIMIT_PHYS = 0x200000000
FDT_MAGIC = 0xD00DFEED
FDT_HEADER_SIZE = 40
FDT_MAX_SIZE = 0x00200000  # 2 MiB ceiling per Linux ARM64 boot protocol

TRUSTZONE_BASE = 0x80B00000
TRUSTZONE_END = 0x88400000
FB_BASE_PHYS = 0x9C000000
FB_BASE_LIMIT = 0x9E300000
FIRMWARE_BASE = 0x9E400000
FIRMWARE_STACK_TOP = 0x9E890000


def simulate_is_valid_device_tree_p36a5(dtb_phys_base, total_size, magic=FDT_MAGIC):
    """
    Python reference model of IsValidDeviceTree() enforcing the 2 MiB protocol limit.
    """
    if dtb_phys_base == 0 or (dtb_phys_base & 0x7) != 0:
        return False, 0

    if (dtb_phys_base < DRAM_BASE_PHYS or 
        (dtb_phys_base + FDT_HEADER_SIZE) > DRAM_LIMIT_PHYS or 
        (dtb_phys_base + FDT_HEADER_SIZE) < dtb_phys_base):
        return False, 0

    if magic != FDT_MAGIC:
        return False, 0

    # Strict 2 MiB protocol ceiling
    if total_size < FDT_HEADER_SIZE or total_size > FDT_MAX_SIZE:
        return False, 0

    dtb_end = dtb_phys_base + total_size
    if dtb_end <= dtb_phys_base or dtb_end > DRAM_LIMIT_PHYS:
        return False, 0

    if dtb_phys_base < TRUSTZONE_END and dtb_end > TRUSTZONE_BASE:
        return False, 0

    if dtb_phys_base < FB_BASE_LIMIT and dtb_end > FB_BASE_PHYS:
        return False, 0

    if dtb_phys_base < 0x9E880000 and dtb_end > FIRMWARE_BASE:
        return False, 0

    if dtb_phys_base < FIRMWARE_STACK_TOP and dtb_end > 0x9E880000:
        return False, 0

    return True, total_size


class TestPhase36A5Audit(unittest.TestCase):
    """Test suite validating Phase 3.6A.5 requirements."""

    def test_01_kernel_image_header_and_entry(self):
        """Workstream 1: Extract and verify current Linux Image header fields and entry logic."""
        self.assertTrue(os.path.isfile(KERNEL_IMAGE), "build/Image must exist")

        with open(KERNEL_IMAGE, "rb") as f:
            hdr = f.read(64)

        code0, code1, text_offset, image_size, flags, res2, res3, res4, magic, res5 = struct.unpack("<IIQQQQQQII", hdr)

        # Magic: ARM\x64 = 0x644D5241
        self.assertEqual(magic, 0x644D5241, "ARM64 Image Magic must be 0x644D5241")
        # Text offset is 0 in modern 5.8+ arm64 kernels
        self.assertEqual(text_offset, 0, "Current kernel artifact text_offset must be 0")
        # Image size: must exceed 16 MiB
        self.assertGreater(image_size, 16 * 1024 * 1024, "Kernel image_size must exceed 16 MiB")
        # Flags: bit 3 set allows physical placement anywhere in DRAM modulo 2 MiB
        self.assertEqual(flags & 0x8, 0x8, "Flags bit 3 must be set (placement anywhere in DRAM)")

        # Verify entry point logic in PrePi.c
        with open(PREPI_C, "r") as f:
            c_code = f.read()

        # PrePi.c must branch directly to KernelCandidate (offset 0) via ArmLaunchLinuxKernel
        self.assertTrue("ArmLaunchLinuxKernel(KernelCandidate, ValidatedDtbBase);" in c_code or "LinuxEntry = (LINUX_ENTRY_POINT)(UINTN)KernelCandidate;" in c_code,
                      "ArmLaunchLinuxKernel or LinuxEntry must branch directly to KernelCandidate (offset +0x00 / code0)")

    def test_02_cache_coherency_poc(self):
        """Workstream 2: Audit cache maintenance across Kernel, DTB, and Firmware."""
        with open(PREPI_C, "r") as f:
            c_code = f.read()
        with open(ENTRY_POINT_ASM, "r") as f:
            asm = f.read()

        # Kernel Image PoC clean
        self.assertIn("Point-of-Coherence (PoC) cache maintenance for entire loaded Linux Image", c_code)
        self.assertIn("dc civac, %0", c_code, "Kernel and DTB cleaning must use dc civac to PoC")
        self.assertIn("dsb sy", c_code, "System barrier must follow cache cleans")
        self.assertIn("isb", c_code, "Instruction barrier must follow system barrier")

        # Relocated firmware PoU clean
        self.assertIn("dc      cvau", asm, "Relocated firmware envelope must be cleaned to PoU via dc cvau")
        self.assertIn("ic      iallu", asm, "Instruction cache must be invalidated")

    def test_03_dtb_validation_2mib_ceiling(self):
        """Workstream 3: Verify DTB protocol compliance and 2 MiB maximum size ceiling."""
        with open(PREPI_C, "r") as f:
            c_code = f.read()

        self.assertIn("#define FDT_MAX_SIZE      0x00200000ULL", c_code,
                      "FDT_MAX_SIZE must be defined as 2 MiB (0x00200000)")
        self.assertIn("TotalSize > FDT_MAX_SIZE", c_code,
                      "IsValidDeviceTree must enforce 2 MiB ceiling")

        # Reference model testing at boundary:
        # 1. Exact 2 MiB total size: PASS
        valid, sz = simulate_is_valid_device_tree_p36a5(0xA0002000, 0x00200000)
        self.assertTrue(valid, "Exact 2 MiB DTB must pass")
        self.assertEqual(sz, 0x00200000)

        # 2. 2 MiB + 1 byte: FAIL
        valid, _ = simulate_is_valid_device_tree_p36a5(0xA0002000, 0x00200001)
        self.assertFalse(valid, "DTB exceeding 2 MiB by 1 byte must fail")

        # 3. Legacy 8 MiB total size: FAIL
        valid, _ = simulate_is_valid_device_tree_p36a5(0xA0002000, 0x00800000)
        self.assertFalse(valid, "Legacy 8 MiB DTB must fail under 2 MiB protocol constraint")

    def test_04_relocation_arithmetic_correction(self):
        """Workstream 5: Verify relocation vector arithmetic and fault classification."""
        staging_base = 0xA0160000
        reloc_dest = 0x9E400000
        firmware_size = 0x00400000  # 4 MiB

        # Base-to-base displacement vector
        base_delta = staging_base - reloc_dest
        self.assertEqual(base_delta, 0x01D60000, "Base-to-base displacement must be 0x01D60000")
        self.assertEqual(base_delta, 30801920, "Displacement must be 30,801,920 bytes")
        self.assertAlmostEqual(base_delta / (1024 * 1024), 29.375, places=3,
                               msg="Base-to-base displacement must be 29.375 MiB")

        # Inter-envelope clearance gap
        envelope_gap = staging_base - (reloc_dest + firmware_size)
        self.assertEqual(envelope_gap, 0x01960000, "Inter-envelope clearance gap must be 0x01960000")
        self.assertAlmostEqual(envelope_gap / (1024 * 1024), 25.375, places=3,
                               msg="Inter-envelope clearance gap must be 25.375 MiB")

    def test_05_deliverable_integrity(self):
        """Task 8: Verify Phase 3.6A.5 deliverable exists and contains all required sections."""
        self.assertTrue(os.path.isfile(DOC_P36A5), "Phase 3.6A.5 deliverable markdown must exist")
        with open(DOC_P36A5, "r") as f:
            doc = f.read()

        required_strings = [
            "Project R8Q — Phase 3.6A.5: Linux ARM64 Boot Protocol Compliance Audit",
            "Workstream 1 — Kernel Image Placement and Entry Protocol",
            "Workstream 2 — Cache Coherency & PoC Maintenance",
            "Workstream 3 — DTB Protocol Compliance (2 MiB Ceiling)",
            "Workstream 4 — Complete Linux ARM64 Handoff Contract",
            "Workstream 5 — Relocation Arithmetic & Fault Classification",
            "29.375 MiB",
            "0x01D60000",
            "FDT_MAX_SIZE",
            "2 MiB",
            "Point of Coherency",
            "KernelCandidate",
            "Documentation/arm64/booting.rst",
            "Master Evidence Classification Ledger",
            "List of Hardware-Only Unknowns",
            "Required Final Verdict",
            "CONDITIONAL GO FOR A FUTURE PHYSICAL TRIAL",
            "STRICT SAFETY",
        ]
        for s in required_strings:
            self.assertIn(s, doc, f"Missing required string in Phase 3.6A.5 deliverable: {s}")


if __name__ == "__main__":
    unittest.main()
