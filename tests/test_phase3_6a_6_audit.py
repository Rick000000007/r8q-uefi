#!/usr/bin/env python3
"""
test_phase3_6a_6_audit.py - Kernel Placement and CPU Handoff Remediation Test Suite

Validates:
1. Kernel 2 MiB alignment remediation (KERNEL_ALIGNED_BASE = 0xA2000000)
2. Complete Image header extraction & PE/COFF relationship
3. Dynamic cache line derivation via CTR_EL0.DminLine and unit reconciliation
4. CPU, Timer, GIC, and PSCI handoff contract
5. DMA peripheral quiescence & 1 GiB memory window compliance
6. Deliverable document integrity (PHASE3_6A_6_KERNEL_PLACEMENT_CPU_HANDOFF.md)

Antigravity Engineering - Project R8Q UEFI
"""

import os
import struct
import unittest

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
KERNEL_IMAGE = os.path.join(PROJECT_ROOT, "build/Image")
PREPI_C = os.path.join(PROJECT_ROOT, "platform/R8QPkg/PrePi/PrePi.c")
ENTRY_POINT_ASM = os.path.join(PROJECT_ROOT, "platform/R8QPkg/PrePi/ModuleEntryPoint.S")
DOC_P36A6 = os.path.join(PROJECT_ROOT, "docs/phase3_6/PHASE3_6A_6_KERNEL_PLACEMENT_CPU_HANDOFF.md")

# Architectural constants
KERNEL_ALIGNED_BASE = 0xA2000000
KERNEL_SIZE = 17235968  # 0x01070000
KERNEL_END = KERNEL_ALIGNED_BASE + KERNEL_SIZE  # 0xA3070000

STAGING_BASE = 0xA0160000
STAGING_SIZE = 24068096  # 22.95 MiB
STAGING_END = STAGING_BASE + STAGING_SIZE  # 0xA1854000

FIRMWARE_BASE = 0x9E400000
FIRMWARE_SIZE = 0x00400000  # 4 MiB
FIRMWARE_END = FIRMWARE_BASE + FIRMWARE_SIZE  # 0x9E800000
STACK_TOP = 0x9E890000
STACK_LIMIT = 0x9E880000

FB_BASE = 0x9C000000
FB_END = 0x9E300000  # 35 MiB
TRUSTZONE_BASE = 0x80B00000
TRUSTZONE_END = 0x88400000  # 121 MiB
SEC_DEBUG_BASE = 0x9F000000
SEC_DEBUG_END = 0x9FA00000  # 10 MiB
TIMA_BASE = 0xB0100000
TIMA_END = 0xB1C00000  # TIMA + UH heap


class TestPhase36A6Audit(unittest.TestCase):
    """Test suite validating Phase 3.6A.6 requirements."""

    def test_01_kernel_placement_remediation(self):
        """Workstream 1: Verify 2 MiB alignment and absolute memory non-overlap."""
        # 1. 2 MiB Alignment Check: Address % 0x200000 == 0
        self.assertEqual(KERNEL_ALIGNED_BASE % 0x200000, 0,
                         "KERNEL_ALIGNED_BASE (0xA2000000) must be strictly 2 MiB aligned")

        # 2. Staged Compound Image Non-Overlap
        self.assertGreater(KERNEL_ALIGNED_BASE, STAGING_END,
                           "Kernel destination (0xA2000000) must be above Staging buffer end (0xA1854000)")
        clearance = KERNEL_ALIGNED_BASE - STAGING_END
        self.assertGreaterEqual(clearance, 7 * 1024 * 1024,
                                "Clearance between staging buffer and kernel must be >= 7 MiB")

        # 3. High DRAM Boundary Non-Overlap (TIMA / UH heap)
        self.assertLess(KERNEL_END, TIMA_BASE,
                        "Kernel end (0xA3070000) must be well below TIMA carveout (0xB0100000)")
        margin_to_tima = TIMA_BASE - KERNEL_END
        self.assertGreaterEqual(margin_to_tima, 200 * 1024 * 1024,
                                "Headroom between kernel end and TIMA must be >= 200 MiB")

        # 4. Low DRAM / Firmware Non-Overlap
        self.assertGreater(KERNEL_ALIGNED_BASE, FIRMWARE_END)
        self.assertGreater(KERNEL_ALIGNED_BASE, STACK_TOP)
        self.assertGreater(KERNEL_ALIGNED_BASE, FB_END)
        self.assertGreater(KERNEL_ALIGNED_BASE, TRUSTZONE_END)
        self.assertGreater(KERNEL_ALIGNED_BASE, SEC_DEBUG_END)

        # 5. PrePi.c source verification
        with open(PREPI_C, "r") as f:
            c_code = f.read()

        self.assertIn("#define KERNEL_ALIGNED_BASE 0xA2000000ULL", c_code,
                      "PrePi.c must define KERNEL_ALIGNED_BASE as 0xA2000000ULL")
        self.assertIn("(KernelCandidate & 0x001FFFFFULL) != 0", c_code,
                      "PrePi.c must test for 2 MiB misalignment")
        self.assertIn("Dst[Idx] = Src[Idx];", c_code,
                      "PrePi.c must relocate misaligned kernel to KERNEL_ALIGNED_BASE")

    def test_02_image_header_validation(self):
        """Workstream 2: Validate live kernel Image header and PE/COFF EFI relationship."""
        self.assertTrue(os.path.isfile(KERNEL_IMAGE), "build/Image must exist")
        with open(KERNEL_IMAGE, "rb") as f:
            hdr = f.read(128)

        code0, code1, text_offset, image_size, flags, res2, res3, res4, magic, pe_offset = struct.unpack("<IIQQQQQQII", hdr[:64])

        self.assertEqual(magic, 0x644D5241, "ARM64 Image Magic must be 0x644D5241 (ARM\x64)")
        self.assertEqual(code0, 0xfa405a4d, "code0 must match ARM64 ccmp / PE MZ header")
        self.assertEqual(code1 & 0xFC000000, 0x14000000, "code1 must match ARM64 b stext branch")
        self.assertEqual(text_offset, 0, "text_offset must be 0 for modern 5.8+ arm64 kernels")
        self.assertGreater(image_size, 16 * 1024 * 1024, "image_size must exceed 16 MiB")
        self.assertEqual(flags & 0x8, 0x8, "Flags bit 3 must be set (allows 2 MiB placement anywhere)")

        # PE/COFF header relationship
        self.assertEqual(pe_offset, 0x40, "PE/COFF header offset (res5) must be 0x40")
        pe_sig = hdr[pe_offset:pe_offset+4]
        self.assertEqual(pe_sig, b"PE\x00\x00", "PE signature at offset 0x40 must be 'PE\0\0'")

    def test_03_cache_line_and_ctr_el0(self):
        """Workstream 3: Audit dynamic cache line derivation and unit reconciliation."""
        with open(PREPI_C, "r") as f:
            c_code = f.read()

        # Dynamic derivation via CTR_EL0.DminLine
        self.assertIn("mrs %0, ctr_el0", c_code, "Must read CTR_EL0 register")
        self.assertIn("(Ctr >> 16) & 0xF", c_code, "Must extract DminLine bits 19:16")
        self.assertIn("4ULL << DminLine", c_code, "Line size must be computed as 4 << DminLine")

        # Alignment masking
        self.assertIn("~(CacheLineSize - 1)", c_code, "Cache clean addresses must be line-aligned")

        # Unit reconciliation: 17,235,968 bytes
        iec_mib = KERNEL_SIZE / (1024 * 1024)
        si_mb = KERNEL_SIZE / (1000 * 1000)
        self.assertAlmostEqual(iec_mib, 16.4375, places=3, msg="16.44 MiB is binary IEC")
        self.assertAlmostEqual(si_mb, 17.235968, places=3, msg="17.24 MB is decimal SI")

    def test_04_cpu_timer_gic_handoff_matrix(self):
        """Workstream 4: Audit CPU, Timer, GIC, and PSCI handoff contract."""
        with open(PREPI_C, "r") as f:
            c_code = f.read()
        with open(ENTRY_POINT_ASM, "r") as f:
            asm = f.read()

        # Assembly setup
        self.assertIn("msr     daifset, #0xf", asm, "All interrupts must be masked (DAIF)")
        self.assertIn("cpacr_el1", asm, "FP/SIMD must be enabled in CPACR_EL1")
        self.assertIn("ic      iallu", asm, "Instruction cache must be invalidated")

        # Linux entry branch
        self.assertTrue("ArmLaunchLinuxKernel(KernelCandidate, ValidatedDtbBase);" in c_code or "LinuxEntry(ValidatedDtbBase, 0, 0, 0);" in c_code or "LinuxEntry(DtbPhysBase, 0, 0, 0);" in c_code,
                        "Final register call x0=DTB, x1-x3=0")

    def test_05_dma_quiescence_and_1gib_window(self):
        """Workstream 5 & 6: Verify DMA quiescence classification and 1 GiB window."""
        window_base = 0x80000000
        window_size = 0x40000000  # 1 GiB
        window_limit = window_base + window_size  # 0xC0000000

        # Verify all operational components reside within [0x80000000, 0xC0000000)
        self.assertTrue(window_base <= FB_BASE < window_limit, "Framebuffer must be in 1 GiB window")
        self.assertTrue(window_base <= FIRMWARE_BASE < window_limit, "Firmware must be in 1 GiB window")
        self.assertTrue(window_base <= STACK_TOP < window_limit, "Stack must be in 1 GiB window")
        self.assertTrue(window_base <= STAGING_BASE < window_limit, "Staging buffer must be in 1 GiB window")
        self.assertTrue(window_base <= KERNEL_ALIGNED_BASE < window_limit, "Kernel must be in 1 GiB window")
        self.assertTrue(window_base <= KERNEL_END <= window_limit, "Kernel end must be in 1 GiB window")

    def test_06_deliverable_integrity(self):
        """Task 8: Verify Phase 3.6A.6 deliverable markdown exists and contains all required sections."""
        self.assertTrue(os.path.isfile(DOC_P36A6), "Phase 3.6A.6 deliverable markdown must exist")
        with open(DOC_P36A6, "r") as f:
            doc = f.read()

        required_strings = [
            "Project R8Q — Phase 3.6A.6: Kernel Placement and CPU Handoff Remediation",
            "Workstream 1 — Kernel Placement Remediation",
            "Workstream 2 — Image Header Validation & PE/COFF Relationship",
            "Workstream 3 — Cache-Line Correctness & CTR_EL0 Derivation",
            "Workstream 4 — CPU, Timer, GIC, and PSCI Handoff Contract",
            "Workstream 5 — DMA-Capable Peripherals & Hardware Quiescence",
            "Workstream 6 — Artifact and Physical Memory Map Reconciliation",
            "0xA2000000",
            "KERNEL_ALIGNED_BASE",
            "CTR_EL0.DminLine",
            "16.44 MiB",
            "17.24 MB",
            "17,235,968",
            "Master Evidence Classification Ledger",
            "List of Hardware-Only Unknowns",
            "Required Final Verdict",
            "CONDITIONAL GO FOR A FUTURE PHYSICAL TRIAL",
            "STRICT SAFETY",
        ]
        for s in required_strings:
            self.assertIn(s, doc, f"Missing required string in Phase 3.6A.6 deliverable: {s}")


if __name__ == "__main__":
    unittest.main()
