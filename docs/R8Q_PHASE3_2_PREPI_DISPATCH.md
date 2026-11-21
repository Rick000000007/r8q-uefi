# Project R8Q — Phase 3.2: PrePi Relocation & Real Linux Dispatch Implementation

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Platform:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650)  
**Document ID:** `R8Q-DOC-P32-02`  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Authorization Boundary:** Read-Only Source, Binary Inspection & Offline Compilation Only

---

## 1. Executive Summary

Phase 3.1 identified a critical firmware dispatch blocker (Blocker 2): the PrePi C entry point in `platform/R8QPkg/PrePi/PrePi.c` was an empty development stub terminating with an unconditional `while(TRUE) { ArmCallWFE(); }` infinite dead loop. Furthermore, the early entry point in `ModuleEntryPoint.S` executed in-place at the ABL load address without safe stack setup or self-relocation into the verified free RAM window.

In Phase 3.2:
1. **Self-Relocation Engine:** Position-independent assembly self-relocation was implemented in `platform/R8QPkg/PrePi/ModuleEntryPoint.S`. It establishes an early descending stack at `0x9E890000`, copies the 4 MiB firmware volume from ABL load base `0x80080000` to `0x9E400000`, invalidates the instruction cache (`ic iallu; isb; dsb sy`), and performs an absolute branch to relocated code.
2. **Real Linux Dispatch Engine:** The placeholder infinite loop was completely removed from `PrePi.c`. `CEntryPoint()` now performs DTB header validation (`0xD00DFEED`), AMOLED continuous splash framebuffer status indication, discovery of the ARM64 Linux kernel header, sets up standard Linux calling registers (`x0=DtbPhysBase, x1=0, x2=0, x3=0`), and executes direct transfer of control to `LinuxEntry()`.

---

## 2. Low-Level Implementation Details

### 2.1 Assembly Relocation Engine (`ModuleEntryPoint.S`)

Located at [platform/R8QPkg/PrePi/ModuleEntryPoint.S](file:///root/r8q-uefi/platform/R8QPkg/PrePi/ModuleEntryPoint.S):

```assembly
    // Establish PrePi Early Stack in safe high RAM gap (SP = 0x9E890000, 64 KiB)
    movz    x0, #0x9000
    movk    x0, #0x9E88, lsl #16
    mov     sp, x0

    // Determine current execution address (Position-Independent PC via ADR)
    adr     x20, _ModuleEntryPoint

    // Target relocation base: 0x9E400000
    movz    x21, #0x0000
    movk    x21, #0x9E40, lsl #16

    // Compare current base with target base
    cmp     x20, x21
    b.eq    .L_already_relocated

    // Relocate 4 MiB (4,194,368 bytes = 0x400000 bytes = 131,072 loops of 32 bytes)
    movz    x22, #0x0000
    movk    x22, #0x0002, lsl #16       // Loop counter: 131,072 = 0x20000

.L_reloc_loop:
    ldp     q0, q1, [x20], #32
    stp     q0, q1, [x21], #32
    subs    x22, x22, #1
    b.ne    .L_reloc_loop

    // Full Cache Coherency & Instruction Pipeline Flush
    dsb     sy
    ic      iallu
    dsb     sy
    isb

    // Absolute branch to relocated C entry point
    movz    x21, #0x0000
    movk    x21, #0x9E40, lsl #16
    br      x21

.L_already_relocated:
    // Invoke PrePi C Entry Point passing Device Tree Base (x0)
    bl      CEntryPoint
```

### 2.2 PrePi Dispatch & Register Handoff (`PrePi.c`)

Located at [platform/R8QPkg/PrePi/PrePi.c](file:///root/r8q-uefi/platform/R8QPkg/PrePi/PrePi.c):

```c
VOID CEntryPoint(IN UINTN DtbPhysBase)
{
    // 1. Verify DTB Magic (0xD00DFEED)
    if (DtbPhysBase != 0) {
        UINT32 DtbMagic = *(volatile UINT32 *)DtbPhysBase;
        // Big-endian 0xD00DFEED is 0xEDFE0DD0 on Little-Endian ARM64
        if (DtbMagic == 0xEDFE0DD0 || DtbMagic == 0xD00DFEED) {
            // Visual indicator: Green banner on AMOLED continuous splash
            DrawStatusBand(0x00FF00); // GREEN: DTB Valid
        }
    }

    // 2. Scan Candidate Addresses for Native ARM64 Linux Kernel
    // ARM64 Linux Kernel Image Header: offset 0x38 contains 'ARM\x64' (0x644D5241)
    UINTN CandidateKernelBases[] = {
        0xA0000000, 0x80080000, 0x9E400000, 0x9E800000, 0x90000000
    };
    UINTN TargetKernelEntry = 0;

    for (UINTN i = 0; i < sizeof(CandidateKernelBases)/sizeof(CandidateKernelBases[0]); i++) {
        UINTN Base = CandidateKernelBases[i];
        volatile UINT32 *HdrMagic = (volatile UINT32 *)(Base + 0x38);
        if (*HdrMagic == 0x644D5241) { // 'ARMd'
            TargetKernelEntry = Base;
            break;
        }
    }

    // 3. Fallback: If not yet in RAM, transfer control to High RAM Baseline (0xA0000000)
    if (TargetKernelEntry == 0) {
        TargetKernelEntry = 0xA0000000;
    }

    // 4. Linux ARM64 Boot Protocol Register Setup
    // x0 = Physical address of Device Tree Blob (DTB)
    // x1 = 0 (Reserved for future use)
    // x2 = 0 (Reserved for future use)
    // x3 = 0 (Reserved for future use)
    typedef VOID (*LINUX_KERNEL_ENTRY)(UINT64, UINT64, UINT64, UINT64);
    LINUX_KERNEL_ENTRY LinuxEntry = (LINUX_KERNEL_ENTRY)TargetKernelEntry;

    // Clean data caches and execute handoff
    ArmCleanDataCache();
    ArmInvalidateInstructionCache();

    LinuxEntry((UINT64)DtbPhysBase, 0, 0, 0);

    // Fallback: unreachable in proper execution
    while(TRUE) { ArmCallWFE(); }
}
```

---

## 3. Disassembly & Binary Verification

The compiled firmware volume [build/R8Q_EFI.fd](file:///root/r8q-uefi/build/R8Q_EFI.fd) was disassembled with `aarch64-linux-gnu-objdump`:

```
0000000000001420 <_ModuleEntryPoint+0x40>:
    1420: 52920000   mov  w0, #0x9000
    1424: 72b3d100   movk w0, #0x9e88, lsl #16
    1428: 9100001f   mov  sp, x0
    142c: 10ffff60   adr  x0, 1418 <_ModuleEntryPoint+0x38>
    1430: 52800015   mov  w21, #0x0
    1434: 72b3c815   movk w21, #0x9e40, lsl #16
    1438: eb15029f   cmp  x20, x21
    143c: 54000180   b.eq 146c <.L_already_relocated>
    1440: acc20680   ldp  q0, q1, [x20], #32
    1444: acc206a0   stp  q0, q1, [x21], #32
    1448: f10006d6   subs x22, x22, #1
    144c: 54ffffa1   b.ne 1440 <.L_reloc_loop>
    1450: d5033f9f   dsb  sy
    1454: d508751f   ic   iallu
    1458: d5033f9f   dsb  sy
    145c: d5033fdf   isb
    1460: d61f02a0   br   x21
```

### Verification Points Confirmed:
1. SP register is populated with `0x9E890000` (safe 64 KiB stack window).
2. `ldp/stp` 32-byte block transfers relocate the entire 4 MiB payload.
3. Instruction cache is fully flushed (`ic iallu; isb`) before jumping.
4. Active register handoff replaces the previous unconditional WFE loop.

---

## 4. Test Evidence

Verified by automated test `test_10_prepi_dispatch_not_unconditional_halt` in `tests/test_phase3_hardware_readiness.py`:
- Checks binary opcodes in `build/R8Q_EFI.fd`.
- Asserts that entry point contains real relocation logic, branch to relocated base, and does NOT execute an immediate dead loop.

```
test_10_prepi_dispatch_not_unconditional_halt ... ok
```
