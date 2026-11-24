#!/usr/bin/env python3
"""
test_phase3_6a_2_validation.py
Project R8Q UEFI: Phase 3.6A.2 Boot-Chain Evidence Validation Suite.
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250 Kona)

Validates:
1. Classification of ABL acceptance: Specification compatibility proven; physical acceptance unproven.
2. EL1 Non-Secure entry environment: Qualcomm QHEE at EL2 (hyp_region), ABL at EL1.
3. Memory and XPU classification: Window E (0x9E400000-0x9F000000) unreserved in devicetree/iomem;
   XPU protection classified as unproven assumption requiring canary probing.
4. Rollback validation: ADB recovery restore proven in LineageOS; Odin on Windows verified;
   Heimdall on Linux classified as unproven assumption due to SM8250 PIT handshake issues.
5. First-boot 7-stage acceptance criteria: PrePi, Relocation, Discovery, Kernel Entry, Console,
   Initramfs, and Native Kali Rootfs.
6. Documentation integrity for docs/phase3_6/PHASE3_6A_2_BOOTCHAIN_EVIDENCE_VALIDATION.md.
"""

import os
import sys
import unittest

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
DOC_36A_2 = os.path.join(PROJECT_ROOT, "docs/phase3_6/PHASE3_6A_2_BOOTCHAIN_EVIDENCE_VALIDATION.md")

class TestPhase36A2Validation(unittest.TestCase):

    def test_01_doc_exists(self):
        """Task 6: Ensure Phase 3.6A.2 document exists."""
        self.assertTrue(os.path.isfile(DOC_36A_2),
                        f"Missing required deliverable: {DOC_36A_2}")

    def test_02_evidence_classifications(self):
        """Task 1-4: Verify distinct evidence classifications in document."""
        with open(DOC_36A_2, "r") as f:
            content = f.read()

        # Check required architectural and evidence markers
        required_evidence_markers = [
            "Project R8Q — Phase 3.6A.2: Final Boot-Chain Evidence Validation",
            "SM-G781B",
            "SM8250",
            "G781BXXSIHYJ4",
            "EL1 Non-Secure",
            "QHEE",
            "hyp_region@80000000",
            "0x9E400000",
            "Window E",
            "dfps_data_region@9e300000",
            "sec_debug_region@0",
            "ARM64 Linux Image Magic",
            "0x644D5241",
            "0x14000010",
            "Odin3 v3.14.4",
            "Heimdall",
            "UNPROVEN ASSUMPTION",
            "VERIFIED FACT",
            "Canary",
            "CONDITIONAL GO FOR PHASE 3.6B",
        ]

        for marker in required_evidence_markers:
            self.assertIn(marker, content, f"Missing required validation marker: {marker}")

    def test_03_strict_safety_and_no_unauthorized_go(self):
        """Strict Safety: Ensure document does NOT self-authorize Phase 3.6B."""
        with open(DOC_36A_2, "r") as f:
            content = f.read()

        self.assertIn("STRICT SAFETY", content.upper(), "Document must emphasize strict safety")
        self.assertIn("EXPLICIT USER AUTHORIZATION", content.upper(),
                      "Phase 3.6B must require explicit user authorization")
        self.assertNotIn("AUTHORIZATION GRANTED BY AGENT", content.upper(),
                         "Agent must never grant Phase 3.6B authorization on user's behalf")

    def test_04_seven_stage_milestones(self):
        """Task 5: Verify all 7 distinct milestones are defined."""
        with open(DOC_36A_2, "r") as f:
            content = f.read()

        stages = [
            "Stage 1: PrePi Entry",
            "Stage 2: Relocation",
            "Stage 3: Discovery",
            "Stage 4: Kernel Entry",
            "Stage 5: Early Console",
            "Stage 6: Initramfs",
            "Stage 7: Native Kali Rootfs",
        ]
        for stage in stages:
            self.assertIn(stage, content, f"Missing required boot stage: {stage}")

if __name__ == "__main__":
    unittest.main()
