# Project R8Q — Phase 3.3: ARM64 Firmware & Boot-Chain Audit

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650)  
**Document ID:** `R8Q-DOC-P33-03-BOOT`  
**Baseline Commit:** [`4e62ec4`](file:///root/r8q-uefi) (*"feat(phase3.2): architecture remediation, memory decoupling, native kernel 7.2.15 & full validation suite"*)  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Workstream Verdict:** **FAIL (Critical Architectural & Execution Deficiencies)**  

---

## 1. Executive Summary

This audit conducted an instruction-level and architectural evaluation of the low-level ARM64 entry code ([ModuleEntryPoint.S](file:///root/r8q-uefi/platform/R8QPkg/PrePi/ModuleEntryPoint.S)), early C platform logic ([PrePi.c](file:///root/r8q-uefi/platform/R8QPkg/PrePi/PrePi.c)), EDK II firmware volume packaging ([R8QPkg.fdf](file:///root/r8q-uefi/platform/R8QPkg/R8QPkg.fdf)), and Linux kernel dispatch mechanisms.

The audit revealed three critical architectural blockers and one high-severity coherency issue:
1. **Critical Relocation Offset Error (`P33-ARM64-BOOT-01`):** In `ModuleEntryPoint.S`, self-relocation copies 4 MiB starting from `_ModuleEntryPoint` (`0x80081420`) rather than the firmware volume base (`0x80080040`). It then branches via `br x25` to `0x9E401488`, landing exactly 5,088 bytes past the relocated code into uninitialized data / unmapped memory.
2. **Missing RAM Kernel Staging (`P33-BOOTCHAIN-ARCH-01`):** Decoupling `build/Image` (16 MiB) from `r8q-uefi-boot-complete.img` means no loader stages the kernel into physical RAM. `PrePi.c` scans empty memory candidates and falls into an unconditional `.Lhalt: wfi` loop.
3. **Unreachable DXE Core (`P33-BOOTCHAIN-ARCH-02`):** `PrePi.c` lacks Hand-Off Block (HOB) construction and never invokes DXE Core; furthermore, `MdeModulePkg/Core/Dxe/DxeMain.inf` is omitted from `R8QPkg.fdf`. All packaged DXE drivers and UEFI applications are dead code.
4. **Cache Coherency Omission (`P33-ARM64-BOOT-02`):** `ModuleEntryPoint.S` invalidates instruction cache (`ic iallu`) without cleaning dirty stores from the data cache to Point of Unification (`dc cvau`).

---

## 2. Low-Level Disassembly & Instruction Trace

### 2.1 The Assembly Relocation Sequence
In `platform/R8QPkg/PrePi/ModuleEntryPoint.S`:
```assembly
real_entry_point:
    mov     x19, x0                     // Preserve DTB pointer in x19
    msr     daifset, #0xf               // Mask all interrupts
    mrs     x1, cpacr_el1               // Enable FP/SIMD in CPACR_EL1
    orr     x1, x1, #(0x3 << 20)
    msr     cpacr_el1, x1
    isb
    ic      iallu                       // Early I-cache invalidation
    isb

    ldr     x2, =0x9E890000             // Establish early descending stack
    mov     sp, x2

    adr     x20, _ModuleEntryPoint      // Current execution address
    ldr     x21, =0x9E400000            // Target relocation base
    cmp     x20, x21
    b.eq    .Lalready_relocated

    mov     x22, x20
    mov     x23, x21
    ldr     x24, =0x00400000            // 4 MiB copy size
.Lreloc_loop:
    ldp     x25, x26, [x22], #16
    stp     x25, x26, [x23], #16
    subs    x24, x24, #16
    b.gt    .Lreloc_loop

    ic      iallu
    isb

    ldr     x25, =.Lalready_relocated   // Target branch address
    mov     x0, x19
    br      x25                         // Jump to relocated code
```

### 2.2 Concrete Binary Disassembly from `build/R8Q_EFI.fd`
Disassembly of `build/R8Q_EFI.fd` beginning at offset `0x13E0` (`_ModuleEntryPoint`):
```text
Offset    Hex Opcode    Assembly Instruction            Analysis
--------------------------------------------------------------------------------------------------
0x1420:   aa0003f3      mov     x19, x0                 ; Preserve DTB pointer
0x1424:   d5034fdf      msr     daifset, #0xf           ; Mask DAIF
0x1428:   d5381041      mrs     x1, cpacr_el1           ; Read CPACR_EL1
0x142c:   b26c0421      orr     x1, x1, #0x300000       ; Enable bits 20:21
0x1430:   d5181041      msr     cpacr_el1, x1           ; Write CPACR_EL1
0x1434:   d5033fdf      isb
0x1438:   d508751f      ic      iallu
0x143c:   d5033fdf      isb
0x1440:   580002c2      ldr     x2, 0x1498              ; Literal pool: 0x9E890000
0x1444:   9100005f      mov     sp, x2                  ; SP = 0x9E890000
0x1448:   10fffcd4      adr     x20, 0x13e0             ; x20 = PC - 0x68 = _ModuleEntryPoint
0x144c:   580002b5      ldr     x21, 0x14a0             ; Literal pool: 0x9E400000
0x1450:   eb15029f      cmp     x20, x21
0x1454:   540001a0      b.eq    0x1488                  ; Branch if already at 0x9E400000
0x1458:   aa1403f6      mov     x22, x20                ; x22 = 0x80081420 (Source Base)
0x145c:   aa1503f7      mov     x23, x21                ; x23 = 0x9E400000 (Dest Base)
0x1460:   58000258      ldr     x24, 0x14a8             ; Literal pool: 0x00400000 (4 MiB)
0x1464:   a8c16ad9      ldp     x25, x26, [x22], #16    ; Copy loop
0x1468:   a8816af9      stp     x25, x26, [x23], #16
0x146c:   f1004318      subs    x24, x24, #0x10
0x1470:   54ffffac      b.gt    0x1464
0x1474:   d508751f      ic      iallu                   ; I-cache invalidate (NO D-CACHE FLUSH!)
0x1478:   d5033fdf      isb
0x147c:   580001b9      ldr     x25, 0x14b0             ; Literal pool: 0x9E401488
0x1480:   aa1303e0      mov     x0, x19                 ; x0 = DTB pointer
0x1484:   d61f0320      br      x25                     ; JUMP TO 0x9E401488 (CRITICAL FAULT!)
0x1488:   aa1303e0      mov     x0, x19                 ; Target: .Lalready_relocated
0x148c:   97ffff81      bl      CEntryPoint
0x1490:   d503207f      wfi                             ; Core park
0x1494:   17ffffff      b       0x1490
--------------------------------------------------------------------------------------------------
Literal Pool (Offsets relative to FD base):
0x1498:   9e890000 00000000  -> 0x000000009E890000 (SP Base)
0x14a0:   9e400000 00000000  -> 0x000000009E400000 (Relocation Destination Base)
0x14a8:   00400000 00000000  -> 0x0000000000400000 (4 MiB Size)
0x14b0:   9e401488 00000000  -> 0x000000009E401488 (br x25 Target)
```

---

## 3. Mathematical Proof of the 5,088-Byte Relocation Shift

1. **Load Geometry in Physical DRAM:**
   - Samsung ABL loads `r8q-uefi-boot-complete.img` at `0x80080000`.
   - The kernel segment contains a 64-byte wrapper header (`arm64_hdr`) followed by `R8Q_EFI.fd`.
   - Physical load base of `R8Q_EFI.fd` = `0x80080000 + 0x40 = 0x80080040`.
   - Physical address of `_ModuleEntryPoint` (offset `0x13E0` in FD) = `0x80080040 + 0x13E0 = 0x80081420`.
   - Relative offset of `.Lalready_relocated` from `_ModuleEntryPoint` = `0xA8` bytes.
   - Physical address of `.Lalready_relocated` = `0x80081420 + 0xA8 = 0x800814C8`.

2. **Destination Geometry as Copied by `ModuleEntryPoint.S`:**
   - Source pointer `x22` is loaded via `adr x20, _ModuleEntryPoint`. Therefore `x22 = 0x80081420`.
   - Destination pointer `x23` is loaded with `0x9E400000`.
   - The loop copies 4 MiB starting from `0x80081420` into `0x9E400000`.
   - Crucially: **the first `0x13E0` bytes (5,088 bytes) of the firmware volume are skipped!**
   - At destination `0x9E400000`, the byte stored is `_ModuleEntryPoint`!
   - Therefore, at destination `0x9E400000`, `.Lalready_relocated` is stored at:
     $$\text{Actual Destination Address} = 0x9E400000 + 0x00A8 = \mathbf{0x9E4000A8}$$

3. **Branch Address Stored in Literal Pool:**
   - The linker assumed the firmware volume base is `0x9E400000`.
   - Therefore, the linker placed `_ModuleEntryPoint` at `0x9E400000 + 0x13E0 = 0x9E4013E0`.
   - And the linker placed `.Lalready_relocated` at `0x9E4013E0 + 0x00A8 = \mathbf{0x9E401488}`.
   - The literal pool at `0x14B0` explicitly stores `0x9E401488`.

4. **The Collision:**
   - `ModuleEntryPoint.S` executes: `ldr x25, =.Lalready_relocated` (loads `0x9E401488`).
   - It executes: `br x25`.
   - The processor branches to `0x9E401488`.
   - But the copied `.Lalready_relocated` instructions are located at `0x9E4000A8`!
   - Difference:
     $$0x9E401488 - 0x9E4000A8 = \mathbf{0x13E0\ \text{bytes}\ (5,088\ \text{bytes})}$$
   - The CPU jumps 5,088 bytes past the code into the middle of the copied firmware volume (which came from `0x80081420 + 0x1488 = 0x800828A8`).
   - What resides at `0x800828A8`? Unaligned data bytes, strings, or unlinked tables.
   - Result: **The CPU executes illegal instructions or encounters unaligned memory access, immediately crashing with an Instruction Abort / Synchronous Exception at the physical vector.**

---

## 4. Boot Protocol Analysis: Direct Boot vs EFI Stub Boot

The table below contrasts the direct ARM64 Linux boot protocol against the UEFI EFI Stub boot protocol, illustrating why signature checks alone do not prove bootability:

| Attribute | Direct Linux ARM64 Boot Protocol | UEFI EFI Stub Boot Protocol |
|---|---|---|
| **Entry Point Calling Convention** | Raw binary branch to `stext` (offset specified by `text_offset` in header, typically offset 0) | Standard UEFI API: `EFI_IMAGE_ENTRY_POINT` via `LoadImage()` / `StartImage()` |
| **Input Register `x0`** | Physical address of Flattened Device Tree (`FDT`) blob in DRAM | Image Handle (`EFI_HANDLE ImageHandle`) |
| **Input Register `x1`** | `0` (Must be zero / reserved) | System Table Pointer (`EFI_SYSTEM_TABLE *SystemTable`) |
| **Input Registers `x2, x3`**| `0, 0` (Reserved) | Undefined |
| **MMU State on Entry** | **MMU Disabled** (Identity map, caching disabled) | **MMU Enabled** (Identity or virtual mapping established by UEFI) |
| **D-Cache State** | Clean to Point of Coherency (PoC) or off | Active and enabled |
| **Execution Level** | EL2 (hypervisor mode recommended) or Non-Secure EL1 | Current UEFI privilege level (typically EL1 or EL2) |
| **Kernel PE/COFF Signature** | Ignored by raw loader | **Mandatory** (`PE\0\0`, machine `0xAA64`) for UEFI PE/COFF loader |

### Why `PrePi.c` Fails at Both Protocols:
1. **Direct Boot Failure:** `PrePi.c` attempts to execute:
   ```c
   LinuxEntry = (LINUX_ENTRY_POINT)(UINTN)(KernelCandidate + EntryOffset);
   LinuxEntry(DtbPhysBase, 0, 0, 0);
   ```
   This implements the Direct Boot convention (`x0 = FDT, x1 = 0, x2 = 0, x3 = 0`). However, `KernelCandidate` is never found in RAM because `build/Image` was decoupled and not loaded by ABL!
2. **EFI Stub Boot Failure:** `PrePi.c` has no implementation of `gBS->LoadImage()` or `gBS->StartImage()`, cannot pass `ImageHandle` or `SystemTable`, and cannot provide runtime services.
3. Therefore, neither boot protocol can be executed on physical hardware.

---

## 5. Audit Findings

### Finding P33-ARM64-BOOT-01: Critical Relocation Target Shift Error in `ModuleEntryPoint.S`
* **Finding ID:** `P33-ARM64-BOOT-01`
* **Severity:** **CRITICAL**
* **Affected Component:** [platform/R8QPkg/PrePi/ModuleEntryPoint.S](file:///root/r8q-uefi/platform/R8QPkg/PrePi/ModuleEntryPoint.S#L48-L75)
* **Evidence:**
  Disassembly of `build/R8Q_EFI.fd` at offset `0x147C` executes `ldr x25, 0x14B0` (loading `0x9E401488`) and `br x25`. Because `adr x20, _ModuleEntryPoint` copies from offset `0x13E0`, `.Lalready_relocated` is stored at `0x9E4000A8`. The branch jumps `0x13E0` bytes (5,088 bytes) past executable code.
* **Reproduction Procedure:**
  Execute automated test:
  ```bash
  python3 -m unittest tests.test_phase3_3_independent_audit.TestPhase33IndependentAudit.test_audit_01_prepi_relocation_offset_mismatch
  ```
* **Engineering Impact:**
  Fatal prefetch abort on instruction fetch immediately upon self-relocation. Device crashes before executing a single instruction in `PrePi.c`.
* **Recommended Remediation:**
  In `ModuleEntryPoint.S`:
  1. Calculate the base of the firmware volume by subtracting the entry offset from `PC`:
     `adr x20, _ModuleEntryPoint - 0x13E0` (or place a label at the exact FV base).
  2. Compute the branch target dynamically relative to the relocated base:
     ```assembly
     adr     x20, _FvBase
     ldr     x21, =0x9E400000
     ... [relocate 4MB from x20 to x21] ...
     ldr     x25, =.Lalready_relocated
     br      x25
     ```
* **Verification Result:**
  Verified as a true fatal defect via `test_audit_01_prepi_relocation_offset_mismatch` in [test_phase3_3_independent_audit.py](file:///root/r8q-uefi/tests/test_phase3_3_independent_audit.py).

---

### Finding P33-ARM64-BOOT-02: Missing Data Cache Clean to Point of Unification in Self-Relocation
* **Finding ID:** `P33-ARM64-BOOT-02`
* **Severity:** **HIGH**
* **Affected Component:** [platform/R8QPkg/PrePi/ModuleEntryPoint.S](file:///root/r8q-uefi/platform/R8QPkg/PrePi/ModuleEntryPoint.S#L70-L75)
* **Evidence:**
  At line 72 of `ModuleEntryPoint.S`, after the `ldp`/`stp` copy loop, the code executes:
  ```assembly
  ic      iallu
  isb
  ```
  There is no preceding `dc cvau` loop or data synchronization barrier (`dsb ish`).
* **Reproduction Procedure:**
  Inspect disassembly of lines `0x1470 - 0x1478` in `build/R8Q_EFI.fd`.
* **Engineering Impact:**
  Under ARMv8-A architecture, stores written via data registers (`stp`) reside in L1/L2 data cache lines. The instruction cache does not snoop the data cache. Without flushing data cache lines to Point of Unification (`dc cvau`) followed by `dsb ish`, the instruction fetch unit may fetch stale, unwritten DRAM contents when branching to the relocated code.
* **Recommended Remediation:**
  Implement a cache maintenance loop across `[0x9E400000, 0x9E800000)`:
  ```assembly
      mov     x22, x21
      ldr     x24, =0x00400000
  1:  dc      cvau, x22
      add     x22, x22, #64
      subs    x24, x24, #64
      b.gt    1b
      dsb     ish
      ic      iallu
      dsb     ish
      isb
  ```
* **Verification Result:**
  Confirmed by static code inspection and binary disassembly.

---

### Finding P33-BOOTCHAIN-ARCH-01: Native Kernel `Image` Omission in Boot Container
* **Finding ID:** `P33-BOOTCHAIN-ARCH-01`
* **Severity:** **CRITICAL**
* **Affected Component:** [scripts/package_complete_boot_img.py](file:///root/r8q-uefi/scripts/package_complete_boot_img.py), [platform/R8QPkg/PrePi/PrePi.c](file:///root/r8q-uefi/platform/R8QPkg/PrePi/PrePi.c#L122-L148)
* **Evidence:**
  `build/r8q-uefi-boot-complete.img` kernel size is 4,194,368 bytes (contains only `R8Q_EFI.fd`). `build/Image` (16,802,304 bytes) is not included in the image. In `PrePi.c`, `CandidateAddresses` (`0x90A00000`, `0xA0002000`, `0x9E890000`) are scanned, but no loader ever populated DRAM with `Image`.
* **Reproduction Procedure:**
  Execute automated test:
  ```bash
  python3 -m unittest tests.test_phase3_3_independent_audit.TestPhase33IndependentAudit.test_audit_02_kernel_image_absence_in_boot_image
  ```
* **Engineering Impact:**
  `KernelCandidate` remains 0. `CEntryPoint()` returns to `ModuleEntryPoint.S`, which executes `.Lhalt: wfi; b .Lhalt`. Execution freezes permanently with no operating system handoff.
* **Recommended Remediation:**
  Design and implement a viable physical kernel handoff strategy:
  - Option A: Load `Image` from the ESP FAT32 partition on MicroSD or UFS storage via storage drivers.
  - Option B: Repackage Android Boot Image v2 to include `Image` in a dedicated staging slot loaded to an unreserved DRAM window (e.g. `0xA0002000`) that does not collide with TrustZone.
* **Verification Result:**
  Verified via `test_audit_02_kernel_image_absence_in_boot_image`.

---

### Finding P33-BOOTCHAIN-ARCH-02: Unreachable DXE Core and UEFI Applications
* **Finding ID:** `P33-BOOTCHAIN-ARCH-02`
* **Severity:** **CRITICAL**
* **Affected Component:** [platform/R8QPkg/R8QPkg.fdf](file:///root/r8q-uefi/platform/R8QPkg/R8QPkg.fdf#L41-L66), [platform/R8QPkg/PrePi/PrePi.c](file:///root/r8q-uefi/platform/R8QPkg/PrePi/PrePi.c)
* **Evidence:**
  - `R8QPkg.fdf` bundles `SimpleFbDxe`, `FileVariableDxe`, `StorageProtectionDxe`, `Shell.inf`, `LinuxBoot.inf`.
  - `PrePi.c` contains no HOB construction and never calls `DxeMain`.
  - `R8QPkg.fdf` omits `MdeModulePkg/Core/Dxe/DxeMain.inf`.
* **Reproduction Procedure:**
  Inspect `platform/R8QPkg/R8QPkg.fdf` and `PrePi.c` source code.
* **Engineering Impact:**
  The entire DXE driver stack, UEFI shell, and EFI application environment packaged into `R8Q_EFI.fd` is dead code taking up 3+ MiB in the flash volume.
* **Recommended Remediation:**
  Decide on firmware architecture: If full UEFI is desired, link `DxeMain.inf`, construct HOBs in `PrePi`, and jump to `DxeMain(HobList)`. If a minimal direct bootloader is desired, strip unreached DXE drivers from `R8QPkg.fdf`.
* **Verification Result:**
  Confirmed by architectural analysis of `R8QPkg.fdf` and `PrePi.c`.
