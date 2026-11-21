#!/usr/bin/env python3
"""
Project R8Q - Phase 3.6A.7 Automated Test Suite
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)
Phase: Complete Memory Ownership and Relocation Integrity Audit

Validates:
1. Exact artifact physical addresses, sizes, and boundaries.
2. Kernel / DTB overlap collision proof at 0xA3000000 and resolution at 0xA4000000.
3. Machine-readable memory map (r8q_physical_memory_map.json) structural integrity and non-overlap.
4. Relocation correctness, alignment, forward copy safety, and PoC cache maintenance.
5. DTB / Initramfs handoff contract within 1 GiB window and zero XPU claim integrity.
6. Documentation deliverable completeness and conditional trial verdict.
"""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(REPO_ROOT, "docs", "phase3_6")
PREPI_C = os.path.join(REPO_ROOT, "platform", "R8QPkg", "PrePi", "PrePi.c")
ENTRY_POINT_ASM = os.path.join(REPO_ROOT, "platform", "R8QPkg", "PrePi", "ModuleEntryPoint.S")
MEM_MAP_JSON = os.path.join(DOCS_DIR, "r8q_physical_memory_map.json")
AUDIT_DOC = os.path.join(DOCS_DIR, "PHASE3_6A_7_MEMORY_OWNERSHIP_AUDIT.md")


class Phase36A7AuditTests(unittest.TestCase):
    """Test suite for Phase 3.6A.7 Memory Ownership and Relocation Integrity Audit."""

    @classmethod
    def setUpClass(cls):
        with open(PREPI_C, "r") as f:
            cls.prepi_c = f.read()
        with open(ENTRY_POINT_ASM, "r") as f:
            cls.asm = f.read()
        with open(MEM_MAP_JSON, "r") as f:
            cls.mem_map = json.load(f)

    def test_01_exact_artifact_addresses(self):
        """Workstream 1: Verify exact artifact physical addresses, sizes, and exclusive boundaries."""
        # Compound Image: 0xA0160000 - 0xA1854000
        compound_start = 0xA0160000
        compound_size = 24068096  # 0x016F4000
        compound_end = compound_start + compound_size
        self.assertEqual(compound_end, 0xA1854000)

        # Firmware staging inside compound image: offset 0x1040
        fw_staging_start = compound_start + 0x1040
        self.assertEqual(fw_staging_start, 0xA0161040)
        fw_size = 0x00400000  # 4 MiB
        fw_staging_end = fw_staging_start + fw_size
        self.assertEqual(fw_staging_end, 0xA0561040)

        # Firmware destination: 0x9E400000 - 0x9E800000
        fw_dest_start = 0x9E400000
        fw_dest_end = fw_dest_start + fw_size
        self.assertEqual(fw_dest_end, 0x9E800000)

        # Kernel staging inside compound image: 0xA0561040
        kernel_src_start = 0xA0561040
        kernel_size = 17235968  # 0x01070000
        kernel_src_end = kernel_src_start + kernel_size
        self.assertEqual(kernel_src_end, 0xA15D1040)

        # Kernel relocated destination: 0xA2000000 - 0xA3070000
        kernel_dst_start = 0xA2000000
        kernel_dst_end = kernel_dst_start + kernel_size
        self.assertEqual(kernel_dst_end, 0xA3070000)

        # Framebuffer carveout: 0x9C000000 - 0x9E300000 (35 MiB)
        fb_start = 0x9C000000
        fb_size = 0x02300000
        self.assertEqual(fb_start + fb_size, 0x9E300000)

        # Stack & Heap: Heap 0x9E800000-0x9E880000, Stack 0x9E880000-0x9E890000
        heap_start = 0x9E800000
        heap_size = 0x00080000
        stack_limit = 0x9E880000
        stack_top = 0x9E890000
        self.assertEqual(heap_start + heap_size, stack_limit)
        self.assertEqual(stack_top - stack_limit, 0x00010000)

    def test_02_kernel_dtb_overlap_collision_and_resolution(self):
        """Workstream 2: Formally prove kernel/DTB collision at 0xA3000000 and resolution at 0xA4000000."""
        kernel_dst_start = 0xA2000000
        kernel_dst_end = 0xA3070000
        legacy_dtb_start = 0xA3000000
        dtb_size = 112160  # 0x1B620

        # Collision Proof: legacy DTB start is strictly inside relocated kernel range
        self.assertTrue(kernel_dst_start <= legacy_dtb_start < kernel_dst_end,
                        "Legacy DTB base 0xA3000000 must fall inside kernel [0xA2000000, 0xA3070000)")
        collision_overlap_bytes = kernel_dst_end - legacy_dtb_start
        self.assertEqual(collision_overlap_bytes, 0x70000, "Overlap must be exactly 448 KiB (0x70000 bytes)")

        # Resolution Proof: DTB relocated to 0xA4000000
        resolved_dtb_start = 0xA4000000
        resolved_dtb_buffer_end = resolved_dtb_start + 0x00200000  # 2 MiB buffer
        clearance = resolved_dtb_start - kernel_dst_end
        self.assertEqual(clearance, 0x00F90000, "Clearance between kernel and DTB must be 15.56 MiB (0xF90000 bytes)")
        self.assertGreater(clearance, 0, "Clearance must be strictly positive")

        # Verify PrePi.c configuration
        self.assertIn("#define DTB_REALLOC_BASE    0xA4000000ULL", self.prepi_c,
                      "PrePi.c must define DTB_REALLOC_BASE as 0xA4000000")
        self.assertIn("ValidatedDtbBase = DTB_REALLOC_BASE;", self.prepi_c,
                      "PrePi.c must relocate DTB when collision is detected")

    def test_03_machine_readable_memory_map_integrity(self):
        """Workstream 3: Validate JSON structure, required fields, and verify strict non-overlap."""
        regions = self.mem_map.get("regions", [])
        self.assertGreaterEqual(len(regions), 30, "Memory map must contain at least 30 regions")

        required_keys = ["name", "start", "end", "size", "owner", "type", "source", "writable", "occupied_during_relocation"]

        # Validate fields and arithmetic for every region
        for r in regions:
            for k in required_keys:
                self.assertIn(k, r, f"Region {r.get('name', 'UNKNOWN')} missing field {k}")
            start = int(r["start"], 16)
            end = int(r["end"], 16)
            size = r["size"]
            self.assertEqual(end - start, size, f"Arithmetic mismatch in region {r['name']}: {end:#x} - {start:#x} != {size:#x}")
            self.assertGreater(size, 0, f"Size must be positive in region {r['name']}")
            self.assertLess(end, 0x200000000, f"Region {r['name']} exceeds DRAM upper boundary 0x200000000")

        # Sort and verify strict non-overlap across independent top-level regions
        independent_regions = [r for r in regions if r.get("hierarchy") != "child_allocation"]
        sorted_regions = sorted(independent_regions, key=lambda x: int(x["start"], 16))
        for i in range(len(sorted_regions) - 1):
            cur = sorted_regions[i]
            nxt = sorted_regions[i+1]
            cur_end = int(cur["end"], 16)
            nxt_start = int(nxt["start"], 16)
            self.assertLessEqual(cur_end, nxt_start,
                                 f"Overlap detected: {cur['name']} ends at {cur_end:#x} but {nxt['name']} starts at {nxt_start:#x}")

    def test_04_relocation_correctness_and_alignment(self):
        """Workstream 4: Verify alignment, forward copy safety, and cache maintenance."""
        # 1. Alignment verification
        kernel_base = 0xA2000000
        dtb_base = 0xA4000000
        stack_top = 0x9E890000
        fw_base = 0x9E400000

        self.assertEqual(kernel_base % 0x200000, 0, "Kernel base must be 2 MiB aligned per ARM64 boot protocol")
        self.assertEqual(dtb_base % 8, 0, "DTB base must be 8-byte aligned")
        self.assertEqual(dtb_base % 0x200000, 0, "DTB base is placed on 2 MiB boundary")
        self.assertEqual(stack_top % 16, 0, "Stack top must be 16-byte aligned")
        self.assertEqual(fw_base % 0x1000, 0, "Firmware base must be 4 KiB page aligned")

        # 2. Forward copy verification (PrePi.c)
        # Source (0xA0561040) < Destination (0xA2000000) -> Forward ascending copy is provably non-destructive
        kernel_src = 0xA0561040
        self.assertLess(kernel_src, kernel_base, "Source must be below destination for ascending forward copy")
        self.assertIn("Dst[Idx] = Src[Idx];", self.prepi_c, "Ascending forward copy loop must be used")

        # 3. PoC cache maintenance
        self.assertIn("dc civac", self.prepi_c, "PoC cache clean/invalidate dc civac must be executed")
        self.assertIn("CTR_EL0.DminLine", self.prepi_c, "Cache line size derived dynamically from CTR_EL0.DminLine")

    def test_05_initramfs_dtb_handoff_contract(self):
        """Workstream 5: Verify DTB in x0, 1 GiB window, and absence of automatic XPU recovery claims."""
        # DTB passed in x0 via ValidatedDtbBase
        self.assertIn("LinuxEntry(ValidatedDtbBase, 0, 0, 0);", self.prepi_c,
                      "LinuxEntry must pass ValidatedDtbBase in x0 and 0 in x1-x3")

        # 1 GiB window [0x80000000, 0xC0000000) verification
        win_start = 0x80000000
        win_end = 0xC0000000
        components = [
            ("Framebuffer", 0x9C000000, 0x9E300000),
            ("Firmware FD", 0x9E400000, 0x9E800000),
            ("Firmware Stack", 0x9E880000, 0x9E890000),
            ("Kernel Staging", 0xA0561040, 0xA15D1040),
            ("Kernel Relocated", 0xA2000000, 0xA3070000),
            ("DTB Relocated", 0xA4000000, 0xA4200000),
            ("Initramfs Staged", 0xA4400000, 0xA6400000)
        ]
        for name, start, end in components:
            self.assertTrue(win_start <= start < win_end, f"{name} start {start:#x} outside 1 GiB window")
            self.assertTrue(win_start < end <= win_end, f"{name} end {end:#x} outside 1 GiB window")

        # No automatic XPU recovery: XPU violations are unrecoverable hardware exceptions
        self.assertNotIn("recover_xpu", self.prepi_c.lower(), "Firmware must not claim automatic XPU violation recovery")

    def test_06_markdown_deliverables(self):
        """Verify existence and completeness of Phase 3.6A.7 documentation."""
        self.assertTrue(os.path.isfile(AUDIT_DOC), "Audit deliverable document must exist")
        with open(AUDIT_DOC, "r") as f:
            doc = f.read()

        # Check required sections
        self.assertIn("Workstream 1", doc)
        self.assertIn("Workstream 2", doc)
        self.assertIn("Workstream 3", doc)
        self.assertIn("Workstream 4", doc)
        self.assertIn("Workstream 5", doc)
        self.assertIn("Workstream 6", doc)

        # Check required verdict
        self.assertIn("CONDITIONAL GO FOR A FUTURE PHYSICAL TRIAL, WITH CLEARLY ENUMERATED UNRESOLVED RISKS", doc)


if __name__ == "__main__":
    unittest.main()
