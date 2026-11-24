#!/usr/bin/env python3
"""
test_phase3_6a_1_verification.py
Project R8Q UEFI: Phase 3.6A.1 Partition Map & Boot-Chain Verification Suite.
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250 Kona)

Validates:
1. Authoritative sysfs partition geometry on /dev/block/sda (sda21 through sda26).
2. Exact sector contiguity, zero-gap and zero-overlap proofs.
3. Backup command sector and block arithmetic for sda23 (boot) and sda24 (recovery).
4. ARM64 Linux Image Header structure in r8q-uefi-boot-complete.img (code0, magic 0x644D5241, text_offset, image_size).
5. Elimination of Telnet in favor of SSH and UART/earlycon diagnostics.
6. Documentation consistency in PHASE3_6A_1_PARTITION_AND_BOOTCHAIN_VERIFICATION.md.
"""

import os
import sys
import struct
import unittest

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
COMPLETE_IMG = os.path.join(PROJECT_ROOT, "build/r8q-uefi-boot-complete.img")
DOC_36A = os.path.join(PROJECT_ROOT, "docs/phase3_6/PHASE3_6A_NON_DESTRUCTIVE_HARDWARE_PREPARATION.md")
DOC_36A_1 = os.path.join(PROJECT_ROOT, "docs/phase3_6/PHASE3_6A_1_PARTITION_AND_BOOTCHAIN_VERIFICATION.md")

class TestPhase36A1Verification(unittest.TestCase):

    def test_01_authoritative_partition_map_geometry(self):
        """Task 1: Verify authoritative partition geometry and contiguity for sda21-sda26."""
        # Authoritative sysfs data from /sys/block/sda/ on SM-G781B
        partitions = {
            "sda21": {"start": 1085592, "size": 131072, "name": "dsp", "bytes": 67108864},
            "sda22": {"start": 1216664, "size": 20480,  "name": "dtbo", "bytes": 10485760},
            "sda23": {"start": 1237144, "size": 131072, "name": "boot", "bytes": 67108864},
            "sda24": {"start": 1368216, "size": 161512, "name": "recovery", "bytes": 82694144},
            "sda25": {"start": 1529728, "size": 32768,  "name": "keyrefuge", "bytes": 16777216},
            "sda26": {"start": 1562496, "size": 32768,  "name": "keydata", "bytes": 16777216},
        }

        # Verify byte capacity arithmetic: sectors * 512 == bytes
        for p, data in partitions.items():
            self.assertEqual(data["size"] * 512, data["bytes"],
                             f"Byte count mismatch for partition {p}")

        # Verify strict contiguity (zero gap and zero overlap)
        self.assertEqual(partitions["sda21"]["start"] + partitions["sda21"]["size"], partitions["sda22"]["start"],
                         "Contiguity failure: sda21 -> sda22")
        self.assertEqual(partitions["sda22"]["start"] + partitions["sda22"]["size"], partitions["sda23"]["start"],
                         "Contiguity failure: sda22 -> sda23")
        self.assertEqual(partitions["sda23"]["start"] + partitions["sda23"]["size"], partitions["sda24"]["start"],
                         "Contiguity failure: sda23 -> sda24")
        self.assertEqual(partitions["sda24"]["start"] + partitions["sda24"]["size"], partitions["sda25"]["start"],
                         "Contiguity failure: sda24 -> sda25 (Zero-gap keyrefuge boundary)")
        self.assertEqual(partitions["sda25"]["start"] + partitions["sda25"]["size"], partitions["sda26"]["start"],
                         "Contiguity failure: sda25 -> sda26")

        # Verify sda23 is exactly 64.00 MiB (not 47.85 MiB)
        sda23_mib = partitions["sda23"]["bytes"] / (1024 * 1024)
        self.assertEqual(sda23_mib, 64.0, "sda23 must be exactly 64.00 MiB")
        self.assertEqual(partitions["sda23"]["start"], 1237144, "sda23 start must be 1237144")
        self.assertEqual(partitions["sda23"]["start"] + partitions["sda23"]["size"] - 1, 1368215,
                         "sda23 end sector inclusive must be 1368215")

        # Verify sda24 is 78.86 MiB
        sda24_mib = partitions["sda24"]["bytes"] / (1024 * 1024)
        self.assertAlmostEqual(sda24_mib, 78.864, places=2, msg="sda24 must be 78.86 MiB")

    def test_02_backup_command_arithmetic(self):
        """Task 2: Validate proposed backup command parameters for sda23 and sda24."""
        # sda24 (recovery): 161512 sectors of 512B = 82,694,144 bytes
        sda24_bytes = 82694144
        self.assertEqual(161512 * 512, sda24_bytes, "sda24 512B sector arithmetic failed")
        self.assertEqual(sda24_bytes % 4096, 0, "sda24 must be evenly divisible by 4096B pages")
        self.assertEqual(20189 * 4096, sda24_bytes, "sda24 4096B block arithmetic failed")

        # sda23 (boot): 131072 sectors of 512B = 67,108,864 bytes
        sda23_bytes = 67108864
        self.assertEqual(131072 * 512, sda23_bytes, "sda23 512B sector arithmetic failed")
        self.assertEqual(sda23_bytes % 4096, 0, "sda23 must be evenly divisible by 4096B pages")
        self.assertEqual(16384 * 4096, sda23_bytes, "sda23 4096B block arithmetic failed")

    def test_03_arm64_linux_image_header_in_boot_image(self):
        """Task 4: Verify ARM64 Linux Image Header structure in r8q-uefi-boot-complete.img."""
        self.assertTrue(os.path.isfile(COMPLETE_IMG), "Boot image must exist")
        with open(COMPLETE_IMG, "rb") as f:
            # Read Android Boot Header (4096 bytes)
            android_hdr = f.read(4096)
            self.assertEqual(android_hdr[:8], b"ANDROID!", "Invalid Android boot magic")
            kernel_size = struct.unpack("<I", android_hdr[8:12])[0]

            # Read 64-byte compound kernel header
            k_hdr = f.read(64)

        # Unpack ARM64 Linux Kernel Image header
        code0, code1, text_offset, image_size, flags, res_bytes, magic, res5 = struct.unpack(
            "<IIQQQ24s4sI", k_hdr
        )

        # 1. code0: ARM64 instruction 'b 0x40' (opcode 0x14000010)
        self.assertEqual(code0, 0x14000010, "code0 must be ARM64 branch forward 64 bytes (b 0x40)")
        self.assertEqual(code1, 0x00000000, "code1 must be 0")

        # 2. text_offset: 512 KiB load alignment (0x80000)
        self.assertEqual(text_offset, 0x80000, "text_offset must be 512 KiB (0x80000)")

        # 3. image_size: declares compound payload size
        self.assertEqual(image_size, kernel_size, "image_size must match header kernel_size")
        self.assertGreater(image_size, 20 * 1024 * 1024, "image_size must exceed 20 MiB")

        # 4. flags: Little-endian, 4K page (0x0A)
        self.assertEqual(flags, 0x0A, "flags must be 0x0A")

        # 5. magic: ARM64 Linux Image Magic 0x644D5241 ("ARM\x64"), NOT PE magic!
        self.assertEqual(magic, b"ARM\x64", "Magic at offset 0x38 must be 'ARM\\x64'")
        magic_int = struct.unpack("<I", magic)[0]
        self.assertEqual(magic_int, 0x644D5241, "Magic at offset 0x38 must be 0x644D5241")

    def test_04_phase3_6a_doc_corrections(self):
        """Verify that Phase 3.6A doc has corrected sda23 start sector and no Telnet."""
        self.assertTrue(os.path.isfile(DOC_36A), "Phase 3.6A doc must exist")
        with open(DOC_36A, "r") as f:
            content = f.read()

        # sda23 start sector must be 1,237,144 (not 1,237,160 or 1,368,216)
        self.assertIn("1,237,144", content, "Phase 3.6A doc must contain corrected sda23 start sector 1,237,144")
        self.assertNotIn("1,237,160", content, "Typo 1,237,160 must be removed from Phase 3.6A doc")
        self.assertNotIn("Telnet", content, "Telnet must not be recommended in Phase 3.6A doc")

    def test_05_phase3_6a_1_doc_exists_and_verified(self):
        """Task 6: Verify Phase 3.6A.1 verification report exists and contains required sections."""
        self.assertTrue(os.path.isfile(DOC_36A_1), "Phase 3.6A.1 doc must exist")
        with open(DOC_36A_1, "r") as f:
            content = f.read()

        required_strings = [
            "Phase 3.6A.1: Partition Map and Boot-Chain Verification",
            "1,237,144",
            "1,368,216",
            "1,529,728",
            "0x644D5241",
            "ARM64 Linux Image Magic",
            "zero gap and zero overlap",
            "CONDITIONAL GO FOR PHASE 3.6B",
        ]
        for s in required_strings:
            self.assertIn(s, content, f"Missing required string in Phase 3.6A.1 doc: {s}")

if __name__ == "__main__":
    unittest.main()
