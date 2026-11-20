# Project R8Q — Phase 3.1: Memory Safety, Carveout & Relocation Audit
**Document ID:** `R8Q-DOC-AUD-002`  
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Platform SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona)  
**Baseline Evidence:** Live devicetree carveouts (`/sys/firmware/devicetree/base/reserved-memory`), `R8QPkg.fdf`, `PrePi.map`, [build/r8q-uefi-boot-complete.img](file:///root/r8q-uefi/build/r8q-uefi-boot-complete.img)  
**Audit Status:** CRITICAL DEFECT IDENTIFIED (Showstopping Memory Overlap Exposed)  

---

## 1. Executive Summary: Showstopping Memory Defect

This independent audit evaluated linker scripts, FDF definitions, compiled map files, disassembly, and runtime memory placement for Project R8Q.

> [!CAUTION]
> **CRITICAL SHOWSTOPPING DEFECT IDENTIFIED [FAILED CHECK]:**  
> **A 39.53 MiB OVERLAP EXISTS BETWEEN THE COMPOUND BOOT IMAGE AND SECURE TRUSTZONE / QSEE MEMORY.**  
> - ABL is commanded to load the compound kernel segment (50.03 MiB / `52,464,192` bytes) starting at `0x80080000`.  
> - The load envelope extends from **`0x80080000` to `0x83288A40`**.  
> - Physical hardware evidence proves Qualcomm TrustZone / QSEE (`removed_region@80b00000`) resides at **`0x80B00000` – `0x88400000`** (121.00 MiB).  
> - **The compound image overwrites the first 39.53 MiB of TrustZone secure RAM.**  
> If booted on physical hardware, this condition would trigger an immediate Qualcomm XPU memory protection fault, kernel panic, or crash directly into Emergency Download Mode (EDL 9008).

```
+-------------------------------------------------------------------------------------------------+
|                    PHYSICAL RAM CARVEOUT & COMPOUND LOAD OVERLAP DISASTER                       |
+-------------------------------------------------------------------------------------------------+
|  0x80000000 +---------------------------------------------------------------------------------+ |
|             | Hypervisor Region (0x80000000 - 0x80600000, 6.0 MiB)                            | |
|  0x80603000 +---------------------------------------------------------------------------------+ |
|             | XBL / AOP Carveout (0x80603000 - 0x80860000, 2.36 MiB)                          | |
|  0x80900000 +---------------------------------------------------------------------------------+ |
|             | SMEM Shared Memory (0x80900000 - 0x80B00000, 2.0 MiB)                           | |
|  0x80080000 + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - + |
|             | [COMPOUND KERNEL LOAD ENVELOPE: 0x80080000 - 0x83288A40 (50.03 MiB)]             | |
|             | - 0x80080000 - 0x80B00000 (10.5 MiB): Permitted Non-Secure RAM                   | |
|  0x80B00000 |=================================================================================| |
|             | !!! 39.53 MiB OVERLAP COLLISION WITH QUALCOMM TRUSTZONE / QSEE SECURE WORLD !!!   | |
|             | TrustZone / removed_region: 0x80B00000 - 0x88400000 (121.0 MiB Protected RAM)   | |
|  0x83288A40 + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - + |
|             | Remaining TrustZone RAM (0x83288A40 - 0x88400000, 81.47 MiB)                   | |
|  0x88400000 +=================================================================================| |
```

---

## 2. Linker Scripts, FDF Definitions & Map Files

### 2.1 EDK II Flash Definition File (`R8QPkg.fdf`)
The platform flash definition file specifies:
```ini
[FD.R8Q_EFI]
BaseAddress   = 0x9E400000|gArmTokenSpaceGuid.PcdFdBaseAddress
Size          = 0x00400000|gArmTokenSpaceGuid.PcdFdSize
ErasePolarity = 1
BlockSize     = 0x00001000
NumBlocks     = 0x400
```
- **Audit Finding [FACT]:** `R8Q_EFI.fd` is hard-linked with `PcdFdBaseAddress = 0x9E400000`.
- **Runtime Discrepancy [FACT]:** Samsung ABL does not know about `0x9E400000`. ABL loads the compound image into low RAM at `0x80080000`.
- **Relocation Absence [FAILED CHECK]:** As proven by binary disassembly of `ModuleEntryPoint.S`, there is no `memcpy` or code relocation loop to move the firmware from `0x80080040` to `0x9E400000`. The code runs in-place at `0x80080000`.

### 2.2 Map File Audit (`PrePi.map`)
Inspection of `/root/r8q-uefi/edk2/Build/R8Q/DEBUG_GCC5/AARCH64/R8QPkg/PrePi/PrePi/DEBUG/PrePi.map`:
- Module entry symbol `_ModuleEntryPoint` is linked at file offset `0x00000000`.
- Text section `.text` occupies `0x00000000` to `0x000003AC` (940 bytes).
- All jumps inside `PrePi.lib` use PC-relative addressing (`b`, `bl`), allowing it to execute at `0x80081328` despite being linked for `0x9E400000`.
- However, any subsequent DXE driver compiled with absolute virtual addressing that assumes it resides at `0x9E400000` will crash upon execution.

---

## 3. PrePi Stack Analysis & Overflow Protection Audit

### 3.1 Stack Pointer Initialization
Binary disassembly of instruction `0x80081388` in `ModuleEntryPoint.S`:
```assembly
80081388:  580000c2   ldr x2, 0x800813a0    // Loads literal 0x000000009E890000
8008138c:  9100005f   mov sp, x2            // Sets SP = 0x9E890000
```
- **Audit Finding [FACT]:** The Stack Pointer is initialized to `0x9E890000`.
- **Discrepancy in Report [FAILED CHECK]:** [R8Q_PHASE3_HARDWARE_INTEGRATION.md](file:///root/r8q-uefi/docs/R8Q_PHASE3_HARDWARE_INTEGRATION.md) stated the stack pointer was `0x9E880000`. It is actually `0x9E890000` (64 KiB higher).

### 3.2 Stack Direction & Allocation Bounds
- AArch64 uses a full-descending stack model: `SP` decrements before data push.
- Initial SP: `0x9E890000`.
- Allocation envelope: Intended stack window is 64 KiB down to `0x9E880000` (or 576 KiB down to `0x9E800000`).
- Target memory range: Resides inside the 12 MiB unreserved DRAM gap (`0x9E400000` – `0x9F000000`).

### 3.3 Stack Overflow & Guard Mechanisms
- **Audit Finding [FAILED CHECK]:**
  1. **Zero Stack Limit Enforcement:** The ARMv8-A Stack Pointer Limit register (`SP_EL0` / `MSCR_EL1`) is **not configured**.
  2. **Zero MMU Guard Pages:** The MMU is disabled (`SCTLR_EL1.M = 0`) during PrePi execution. No unmapped guard page exists below `0x9E800000` or `0x9E880000`.
  3. **Zero Stack Canaries:** `PrePi.map` confirms `/root/r8q-uefi/edk2/MdePkg/Library/StackCheckLibNull` was linked (`StackCheckLibNullGcc.obj`), which replaces `__stack_chk_fail` with a null stub.
  4. If stack recursion or large local arrays exceed the allocated buffer, the stack will silently corrupt memory below `0x9E880000` with zero hardware detection.

---

## 4. Full Physical Carveout Overlap Verification Ledger

Comparison of all declared physical memory carveouts against ground truth from `/sys/firmware/devicetree/base/reserved-memory`:

| Memory Region | Physical Start | Physical End | Size (MiB) | Hardware Purpose | Overlap Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `hyp_region` | `0x80000000` | `0x80600000` | 6.00 MiB | Qualcomm Hypervisor (EL2) | Clear of kernel entry (`0x80080000`) |
| `xbl_aop_region` | `0x80603000` | `0x80860000` | 2.36 MiB | Always-On Processor | Clear of kernel entry (`0x80080000`) |
| **Compound Kernel (Actual)**| **`0x80080000`**| **`0x83288A40`**| **50.03 MiB** | **Loaded Boot Payload** | **COLLISION WITH TRUSTZONE (39.53 MiB)** |
| **TrustZone (`removed_region`)**| **`0x80B00000`**| **`0x88400000`**| **121.00 MiB**| **QSEE / Secure World** | **OVERWRITTEN BY COMPOUND KERNEL** |
| `pil_slpi_region` | `0x89200000` | `0x8A700000` | 21.00 MiB | Sensor Island DSP | Clear |
| `pil_adsp_region` | `0x8A700000` | `0x8D300000` | 44.00 MiB | Audio Hexagon DSP | Clear |
| `cont_splash_region` | `0x9C000000` | `0x9E300000` | 35.00 MiB | Continuous Splash Scanout | Clear of loaded code (`0x80080000`) |
| `dfps_data_region` | `0x9E300000` | `0x9E400000` | 1.00 MiB | Display Frame Rate Data | Clear |
| **Unreserved High DRAM Gap**| **`0x9E400000`**| **`0x9F000000`**| **12.00 MiB** | **Free Physical DRAM** | **PrePi Stack resides here (`0x9E890000`)** |
| `sec_debug_region` | `0x9F000000` | `0x9F800000` | 8.00 MiB | Samsung SEC Debug Buffer | Clear |
| `ramoops` | `0x9FA00000` | `0x9FB00000` | 1.00 MiB | Crash Log Pstore Console | Clear |
| `Dynamic RAM Pool` | `0xA0002000` | `0x280000000`| ~5.5 GiB | Linux System Memory | Clear |

---

## 5. Architectural Root Cause & Required Remediation

### 5.1 Why the PoC Image Worked While Complete Image Fails
1. **The PoC Image (`r8q-uefi-boot-poc.img`):**
   - Payload size: 4.19 MiB (`0x00400000`).
   - Load span: `0x80080000` – `0x80480000`.
   - Distance to TrustZone (`0x80B00000`): **+6.50 MiB margin**.
   - Result: Perfectly safe, zero overlap with TrustZone.
2. **The Complete Compound Image (`r8q-uefi-boot-complete.img`):**
   - Appended a 46.03 MiB uncompressed Linux kernel (`build/Image`).
   - Total payload size: 50.03 MiB.
   - Load span: `0x80080000` – `0x83288A40`.
   - Result: TrustZone starts at `0x80B00000`, causing a **39.53 MiB catastrophic collision**.

### 5.2 Mandatory Engineering Remediation
To eliminate this fatal collision, the compound architecture must be redesigned:
1. **Do not bundle the uncompressed Linux kernel into the ABL kernel slot.**  
   The Linux kernel must reside either:
   - On the EFI System Partition (`build/esp.img`) on the external MicroSD card as `/EFI/BOOT/BOOTAA64.EFI`.
   - Or compressed with LZ4 / XZ inside the recovery ramdisk slot (`0x81000000`).
2. **Restore the ABL kernel payload size to <= 6.0 MiB.**  
   Only `R8Q_EFI.fd` and its early wrapper should be packaged in the ABL kernel slot, preserving the safe envelope `0x80080000` – `0x80480000` (well below `0x80B00000`).

---

## 6. Audit Verdict

| Evaluation Criterion | Finding | Verdict |
| :--- | :--- | :--- |
| **TrustZone Carveout Safety** | 39.53 MiB overlap between compound image and QSEE | **FATAL FAILURE** |
| **Runtime FV Relocation** | Wrapper does not relocate code to `0x9E400000` | **DEFECT** |
| **Stack Allocation Safety** | Stack at `0x9E890000` is disjoint from code at `0x80080000` | **PASS (Stack only)** |
| **Stack Overflow Guards** | No guard pages, no limit registers, null stack check | **WARNING** |
| **Overall Memory Safety** | **CRITICAL MEMORY COLLISION MUST BE RESOLVED BEFORE BOOT** | **NOT READY** |
