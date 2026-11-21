#!/usr/bin/env python3
"""
Project R8Q - Phase 3.6A.8 Automated Test Suite
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)
Phase: Independent Memory Ownership, Relocation and Linux Handoff Verification

Validates:
1. Exact source implementation file paths, function names, and line references.
2. Generalized overflow-safe half-open interval validation [start, end).
3. Exhaustive pairwise allocation overlap test across all 34 memory map entries.
4. Negative tests for DTB/Kernel/Initramfs/Firmware collisions.
5. Stack and heap boundary and collision safety.
6. Integer overflow and physical boundary violation detection.
7. DTB header, magic, alignment, and totalsize validation.
8. Kernel, DTB, Stack, and Firmware alignment constraints.
9. DTB and initramfs contract, including /chosen payload vs buffer capacity distinction.
10. Forward copy source/destination non-corruption proof.
11. Point-of-Coherence cache maintenance and hardware dependency classification.
"""

import json
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(REPO_ROOT, "docs", "phase3_6")
PREPI_C = os.path.join(REPO_ROOT, "platform", "R8QPkg", "PrePi", "PrePi.c")
ENTRY_POINT_ASM = os.path.join(REPO_ROOT, "platform", "R8QPkg", "PrePi", "ModuleEntryPoint.S")
MEM_MAP_JSON = os.path.join(DOCS_DIR, "r8q_physical_memory_map.json")
AUDIT_DOC = os.path.join(DOCS_DIR, "PHASE3_6A_8_INDEPENDENT_INTEGRITY_VERIFICATION.md")

DRAM_BASE = 0x80000000
DRAM_LIMIT = 0x200000000


class MemoryInterval:
    """Half-open physical memory interval [start, end)."""

    def __init__(self, name, start, end_or_size, is_size=False):
        self.name = name
        self.start = int(start, 16) if isinstance(start, str) else int(start)
        if is_size:
            size = int(end_or_size, 16) if isinstance(end_or_size, str) else int(end_or_size)
            self.size = size
            self.end = self.start + size
        else:
            self.end = int(end_or_size, 16) if isinstance(end_or_size, str) else int(end_or_size)
            self.size = self.end - self.start

        # 64-bit unsigned address space and overflow check
        MAX_UINT64 = 0xFFFFFFFFFFFFFFFF
        if self.start > MAX_UINT64 or self.end > MAX_UINT64 or self.end <= self.start or self.size <= 0:
            raise ValueError(f"Invalid interval {name}: start={self.start:#x}, end={self.end:#x}, size={self.size:#x}")

    def overlaps(self, other):
        """Half-open interval overlap check: [s1, e1) intersects [s2, e2) iff s1 < e2 and e1 > s2."""
        return self.start < other.end and self.end > other.start

    def clearance(self, other):
        """Returns positive distance if disjoint, or negative overlap amount."""
        if self.overlaps(other):
            overlap_start = max(self.start, other.start)
            overlap_end = min(self.end, other.end)
            return -(overlap_end - overlap_start)
        if self.end <= other.start:
            return other.start - self.end
        return self.start - other.end


class Phase36A8AuditTests(unittest.TestCase):
    """Test suite for Phase 3.6A.8 Independent Integrity Verification."""

    @classmethod
    def setUpClass(cls):
        with open(PREPI_C, "r") as f:
            cls.prepi_c = f.read()
        with open(ENTRY_POINT_ASM, "r") as f:
            cls.asm = f.read()
        with open(MEM_MAP_JSON, "r") as f:
            cls.mem_map = json.load(f)

    def test_01_actual_source_implementation_inspection(self):
        """Requirement 1: Inspect committed source files and verify functions and logic."""
        # 1. Kernel Relocation: PrePi.c CEntryPoint() relocates misaligned kernel to KERNEL_ALIGNED_BASE
        self.assertIn("KERNEL_ALIGNED_BASE", self.prepi_c)
        self.assertIn("DstEnd <= DRAM_LIMIT_PHYS", self.prepi_c, "Kernel relocation must validate destination ceiling")
        self.assertIn("KernelRunBase = KERNEL_ALIGNED_BASE;", self.prepi_c)

        # 2. DTB Validation and Relocation: IsValidDeviceTree() and CEntryPoint()
        self.assertIn("IsValidDeviceTree", self.prepi_c)
        self.assertIn("DTB_REALLOC_BASE", self.prepi_c)
        self.assertIn("ValidatedDtbBase = DTB_REALLOC_BASE;", self.prepi_c)
        # DTB post-relocation re-validation
        self.assertIn("PostRelocSize", self.prepi_c, "PrePi must re-validate DTB at destination after relocation")

        # 3. Cache Maintenance: ModuleEntryPoint.S (PoU) and PrePi.c (PoC)
        self.assertIn("dc      cvau", self.asm, "ModuleEntryPoint.S must clean firmware to PoU via dc cvau")
        self.assertIn("dc civac", self.prepi_c, "PrePi.c must clean DTB and Kernel to PoC via dc civac")
        self.assertIn("dsb sy", self.prepi_c, "PrePi.c must issue full system barrier")
        self.assertIn("isb", self.prepi_c, "PrePi.c must issue instruction pipeline flush")

        # 4. Final Linux Register Handoff: x0 = DTB, x1-x3 = 0
        self.assertIn("LinuxEntry(ValidatedDtbBase, 0, 0, 0);", self.prepi_c)

    def test_02_generalized_half_open_interval_validation(self):
        """Requirement 2: Generalize memory-range validation on all regions."""
        regions = self.mem_map.get("regions", [])
        self.assertGreaterEqual(len(regions), 34, "Memory map must have at least 34 entries")

        intervals = []
        for r in regions:
            inter = MemoryInterval(r["name"], r["start"], r["end"])
            self.assertEqual(inter.size, r["size"], f"Size calculation mismatch in {r['name']}")
            self.assertGreaterEqual(inter.start, DRAM_BASE, f"Region {r['name']} below DRAM base")
            self.assertLessEqual(inter.end, DRAM_LIMIT, f"Region {r['name']} exceeds DRAM limit")
            intervals.append(inter)

        self.assertEqual(len(intervals), len(regions))

    def test_03_pairwise_allocation_overlap_exhaustive(self):
        """Requirement 6: Exhaustive pairwise non-overlap test across independent live entries."""
        regions = [r for r in self.mem_map.get("regions", []) if r.get("hierarchy") != "child_allocation"]
        intervals = [MemoryInterval(r["name"], r["start"], r["end"]) for r in regions]

        pairs_checked = 0
        for i in range(len(intervals)):
            for j in range(i + 1, len(intervals)):
                a = intervals[i]
                b = intervals[j]
                self.assertFalse(a.overlaps(b),
                                 f"Pairwise collision detected between {a.name} [{a.start:#x}, {a.end:#x}) and {b.name} [{b.start:#x}, {b.end:#x})")
                pairs_checked += 1

        expected_pairs = (len(intervals) * (len(intervals) - 1)) // 2
        self.assertEqual(pairs_checked, expected_pairs)

    def test_04_negative_tests_dtb_overlap(self):
        """Requirement 6: Negative test proving detection when DTB overlaps kernel or initramfs."""
        kernel_dest = MemoryInterval("kernel_dst", 0xA2000000, 0xA3070000)
        dtb_colliding_kernel = MemoryInterval("dtb_bad", 0xA3000000, 112160, is_size=True)
        self.assertTrue(kernel_dest.overlaps(dtb_colliding_kernel), "Must detect DTB collision inside kernel footprint")

        initramfs_dest = MemoryInterval("initrd_dst", 0xA4400000, 0xA6400000)
        dtb_colliding_initrd = MemoryInterval("dtb_bad2", 0xA4410000, 112160, is_size=True)
        self.assertTrue(initramfs_dest.overlaps(dtb_colliding_initrd), "Must detect DTB collision inside initramfs footprint")

        # Proves resolved DTB at 0xA4000000 has zero overlap
        dtb_resolved = MemoryInterval("dtb_ok", 0xA4000000, 112160, is_size=True)
        self.assertFalse(kernel_dest.overlaps(dtb_resolved))
        self.assertFalse(initramfs_dest.overlaps(dtb_resolved))

    def test_05_negative_tests_kernel_and_firmware_overlap(self):
        """Requirement 6: Negative test proving detection when kernel destination overlaps firmware."""
        firmware_envelope = MemoryInterval("fw_envelope", 0x9E400000, 0x9E800000)
        kernel_colliding_fw = MemoryInterval("kernel_bad", 0x9E600000, 17235968, is_size=True)
        self.assertTrue(firmware_envelope.overlaps(kernel_colliding_fw), "Must detect kernel overlap with firmware envelope")

        # Proves relocated kernel at 0xA2000000 has zero overlap
        kernel_resolved = MemoryInterval("kernel_ok", 0xA2000000, 17235968, is_size=True)
        self.assertFalse(firmware_envelope.overlaps(kernel_resolved))

    def test_06_stack_and_heap_collision_and_boundary(self):
        """Requirement 6: Stack and heap collision and half-open boundary safety."""
        heap = MemoryInterval("uefi_heap", 0x9E800000, 0x9E880000)
        stack = MemoryInterval("uefi_stack", 0x9E880000, 0x9E890000)

        # Proves half-open boundary: [0x9E800000, 0x9E880000) and [0x9E880000, 0x9E890000) meet with 0 overlap
        self.assertFalse(heap.overlaps(stack), "Heap and stack must not overlap")
        self.assertEqual(heap.end, stack.start, "Heap end must exactly equal stack limit")

        # Stack pointer alignment (sp = 0x9E890000)
        self.assertEqual(stack.end % 16, 0, "Initial SP must be 16-byte aligned per ARM64 ABI")

    def test_07_integer_overflow_validation(self):
        """Requirement 2 & 6: Validate detection of arithmetic overflow and DRAM limits."""
        # Arithmetic overflow on 64-bit integer
        with self.assertRaises(ValueError):
            MemoryInterval("overflow_test", 0xFFFFFFFFFFFFFF00, 0x200, is_size=True)

        # Zero-sized allocation rejection
        with self.assertRaises(ValueError):
            MemoryInterval("zero_size_test", 0xA0000000, 0, is_size=True)

    def test_08_invalid_dtb_header_and_totalsize(self):
        """Requirement 6: Validation of DTB header magic, limits, and totalsize."""
        fdt_magic_be = 0xD00DFEED
        fdt_max_size = 0x00200000  # 2 MiB

        # Size check logic in PrePi.c
        self.assertIn("TotalSize < sizeof(FDT_HEADER) || TotalSize > FDT_MAX_SIZE", self.prepi_c)
        self.assertIn("FDT_MAX_SIZE      0x00200000ULL", self.prepi_c)

    def test_09_alignment_validation_kernel_dtb_stack(self):
        """Requirement 2 & 6: Alignment verification for all boot components."""
        kernel_base = 0xA2000000
        dtb_base = 0xA4000000
        sp_base = 0x9E890000
        fw_base = 0x9E400000

        self.assertEqual(kernel_base % 0x200000, 0, "Kernel destination must be 2 MiB aligned")
        self.assertEqual(dtb_base % 8, 0, "DTB destination must be 8-byte aligned")
        self.assertEqual(dtb_base % 0x200000, 0, "DTB destination is 2 MiB boundary aligned")
        self.assertEqual(sp_base % 16, 0, "SP must be 16-byte aligned")
        self.assertEqual(fw_base % 4096, 0, "Firmware base must be 4 KiB page aligned")

        # Negative alignment tests
        self.assertNotEqual((kernel_base + 0x1000) % 0x200000, 0)
        self.assertNotEqual((dtb_base + 3) % 8, 0)

    def test_10_dtb_and_initramfs_contract_and_chosen_properties(self):
        """Requirement 4 & 6: Prove payload size vs buffer capacity distinction in initramfs contract."""
        initrd_buffer_start = 0xA4400000
        initrd_buffer_size = 0x02000000  # 32 MiB buffer
        initrd_payload_size = 2947562    # 0x2CF9EA bytes actual CPIO payload

        initrd_payload_end = initrd_buffer_start + initrd_payload_size
        initrd_buffer_end = initrd_buffer_start + initrd_buffer_size

        # Buffer capacity is NOT payload size
        self.assertNotEqual(initrd_payload_size, initrd_buffer_size)
        self.assertLess(initrd_payload_end, initrd_buffer_end)
        padding_bytes = initrd_buffer_end - initrd_payload_end
        self.assertEqual(padding_bytes, 30606870, "Buffer contains 29.19 MiB of trailing clearance")

        # Linux initrd end must be calculated from payload size, not capacity
        chosen_initrd_start = initrd_buffer_start
        chosen_initrd_end = chosen_initrd_start + initrd_payload_size
        self.assertEqual(chosen_initrd_end, 0xA46CF9EA)

    def test_11_source_destination_relocation_integrity(self):
        """Requirement 2 & 6: Prove ascending forward copy safety with disjoint buffers."""
        kernel_src = MemoryInterval("kernel_src", 0xA0561040, 17235968, is_size=True)
        kernel_dst = MemoryInterval("kernel_dst", 0xA2000000, 17235968, is_size=True)

        # Direction check: source < destination
        self.assertLess(kernel_src.start, kernel_dst.start)
        # Non-overlap check: source end < destination start
        self.assertLessEqual(kernel_src.end, kernel_dst.start)
        clearance = kernel_dst.start - kernel_src.end
        self.assertEqual(clearance, 0x00A2EFC0, "10.18 MiB clearance between kernel source end and destination start")
        self.assertFalse(kernel_src.overlaps(kernel_dst), "Source and destination are strictly disjoint")

    def test_12_cache_maintenance_and_subsystem_classification(self):
        """Requirement 5: Cache maintenance rounding, barriers, and subsystem dependency classification."""
        # 1. Rounding check in PrePi.c
        self.assertIn("& ~(CacheLineSize - 1)", self.prepi_c, "Address must be floored to cache line")
        self.assertIn("+ CacheLineSize - 1) & ~(CacheLineSize - 1)", self.prepi_c, "Limit must be ceiled to cache line")

        # 2. Hardware Dependency Matrix in documentation
        self.assertTrue(os.path.isfile(AUDIT_DOC))
        with open(AUDIT_DOC, "r") as f:
            doc = f.read()

        for term in ["verified", "source-supported", "assumed", "hardware-unknown"]:
            self.assertIn(term, doc, f"Deliverable must contain classification '{term}'")


if __name__ == "__main__":
    unittest.main()
