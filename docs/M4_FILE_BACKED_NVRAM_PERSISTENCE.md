# Project R8Q UEFI: Milestone 4 File-Backed NVRAM Persistence Report
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona, Rev 2.1)  
**Document Revision:** 1.0.0-M4  
**Status:** Implemented & Validated  

---

## 1. Storage Location & Isolation Boundary

In accordance with Option A, UEFI variable persistence is hosted strictly on external authorized test media:
- **Canonical Store Path:** `EFI/R8Q/VARS.BIN` on the test EFI System Partition (ESP).
- **Size Bounds:** Capped at 256 KiB (`MAX_VAR_STORE_SIZE`).
- **Internal UFS Isolation:** Internal partition `sdd31` (`uefivarstore`) is completely untouched and isolated from the driver.

---

## 2. Two-Phase Atomic Transaction Commit

To prevent store corruption during unexpected power loss, phone battery removal, or reset:

```
[In-Memory Variable Changes]
            |
            v
1. Phase 1: Write Candidate File -> "EFI/R8Q/VARS.NEW" (State: IN_PROGRESS)
            |
            v
2. Phase 2: Compute & Verify CRC32 on Disk -> Mismatch? -> Abort & Delete
            |
            v
3. Phase 3: Archive Existing Store -> "EFI/R8Q/VARS.BIN" -> "EFI/R8Q/VARS.BAK"
            |
            v
4. Phase 4: Promote & Finalize     -> "EFI/R8Q/VARS.NEW" -> "EFI/R8Q/VARS.BIN" (State: COMMITTED)
```

1. **State Flags:** The store header tracks transaction status (`VAR_STORE_STATE_IN_PROGRESS` vs `VAR_STORE_STATE_COMMITTED`).
2. **Crash Resilience:** If power is cut during Phase 1 or 2, `VARS.BIN` remains intact and unaffected.
3. **Backup Guarantee:** `VARS.BAK` is always retained from the prior successful commit.

---

## 3. Corruption Detection & Recovery Engine

During firmware boot (`FileVariableDxeInitialize`):
1. **Primary Store Validation:** Inspects `EFI/R8Q/VARS.BIN`. Checks magic signature `R88QVAR`, version `1`, size $\le 256\,\text{KiB}$, and verifies header CRC32.
2. **Recovery from Backup:** If `VARS.BIN` is truncated, missing, or has a CRC mismatch:
   - Inspects `EFI/R8Q/VARS.BAK`.
   - If `VARS.BAK` passes CRC validation, the driver restores variables from backup and logs a diagnostic warning.
3. **Quarantine & Reset:** If both primary and backup stores are corrupt:
   - Isolates the corrupt file to `EFI/R8Q/VARS_CORRUPT.BIN` for diagnostic inspection.
   - Automatically initializes a clean default variable store in memory.
4. **Stale Cleanup:** Deletes any incomplete `VARS.NEW` file left over from an interrupted write.

---

## 4. Zero Fallback to Internal Storage

> [!IMPORTANT]
> If external test media is not detected, unformatted, or disconnected, the variable driver functions in **volatile mode** (changes persist in RAM during the boot session). The driver **NEVER falls back** to internal UFS storage under any circumstance.
