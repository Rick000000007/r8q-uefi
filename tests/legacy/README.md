# Project R8Q: Historical & Legacy Test Suites
**Directory:** `/root/r8q-uefi/tests/legacy`  
**Classification:** Historical Forensic Archive (Phase 3.0 - Phase 3.3)  

## Purpose & Scope
This directory preserves historical test suites developed during earlier engineering phases of Project R8Q prior to the Phase 3.4 Custom Bootloader and Native Linux Handoff Architecture.

These test suites are preserved to maintain an immutable forensic record of the project's development progression and defect remediation history. They are separated from the primary active regression test directory (`/root/r8q-uefi/tests`) to ensure that automated test discovery targets the active compound architecture.

## Catalog of Historical Test Suites

### 1. `test_phase3_3_independent_audit.py`
* **Historical Phase:** Phase 3.3 (Independent Technical Audit).
* **Role:** Designed specifically as an adversarial audit verification suite to prove the existence of Phase 3.2 defects before they were resolved in Phase 3.4.
* **Preserved Artifact Assertions:**
  - `test_audit_01_prepi_relocation_offset_mismatch`: Proved that the unpatched TE entry offset was `0x13E0` (5,088 bytes) rather than `0x1418` (5,248 bytes in FD). Remediated in Phase 3.4 (`CRITICAL-01`).
  - `test_audit_02_kernel_image_absence_in_boot_image`: Proved that the early Phase 3.2 boot image was only 4 MiB (`4,194,368` bytes) and lacked the embedded Linux kernel. Remediated in Phase 3.4 (`CRITICAL-02`).
  - `test_audit_07_artifact_manifest_exact_checksums`: Asserted against the Phase 3.3 milestone manifest.

### 2. `test_phase3_hardware_readiness.py`
* **Historical Phase:** Phase 3.2 (Hardware Readiness Verification).
* **Role:** Early hardware readiness checks predicated on the single 4.00 MiB UEFI firmware volume before the compound boot container (20.03 MiB kernel payload) was introduced.

### 3. `test_final_boot_readiness.py`
* **Historical Phase:** Milestone 5 / Phase 3.0.
* **Role:** Acceptance suite developed when testing an unstripped 48 MiB development kernel (`48,269,824` bytes) before the streamlined 16.02 MiB mainline kernel (`16,802,304` bytes) was integrated.

## Execution Policy
These suites are not executed during normal regression runs. They remain directly executable for historical audits:
```bash
python3 /root/r8q-uefi/tests/legacy/test_phase3_3_independent_audit.py
python3 /root/r8q-uefi/tests/legacy/test_phase3_hardware_readiness.py
python3 /root/r8q-uefi/tests/legacy/test_final_boot_readiness.py
```
