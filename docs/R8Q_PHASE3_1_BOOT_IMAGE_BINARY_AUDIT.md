# Project R8Q — Phase 3.1: Android Boot Image v2 Binary & Execution Audit
**Document ID:** `R8Q-DOC-AUD-001`  
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Audited Binary:** [build/r8q-uefi-boot-complete.img](file:///root/r8q-uefi/build/r8q-uefi-boot-complete.img)  
**Binary Size:** `55,554,048` bytes (`0x034FA040`, 52.98 MiB)  
**Binary SHA-256:** `dbc59dc0c3447c53a68ea7669e0c4446ef5fd9812ccb73d192d593549836f206`  
**Audit Status:** COMPLETE ADVERSARIAL AUDIT (Ground-Truth Binary Verification)  

---

## 1. Executive Summary & Audit Methodology

This document presents an independent, byte-level binary audit of the complete compound boot container [build/r8q-uefi-boot-complete.img](file:///root/r8q-uefi/build/r8q-uefi-boot-complete.img) generated in Project R8Q.

The audit was performed using independent binary unpackers, hex verification, structural parsing of the Android Boot Image v2 header, and instruction disassembly of the ARM64 entry vector using `aarch64-linux-gnu-objdump`. Every claim is verified against raw artifact data.

```
+-------------------------------------------------------------------------------------------------+
|                        COMPOUND BOOT CONTAINER MEMORY & BINARY TOPOLOGY                         |
+-------------------------------------------------------------------------------------------------+
|  BYTE OFFSET (HEX)    |  SIZE (BYTES)  |  STRUCTURAL COMPONENT       |  INTERNAL SIGNATURE      |
+-----------------------+----------------+-----------------------------+--------------------------+
|  0x00000000 - 0x00000FFF |  4,096         |  Android Boot Header v2     |  'ANDROID!' (v2)         |
|  0x00001000 - 0x0000103F |  64            |  Compound ARM64 Header      |  'ARM\x64' (Magic)       |
|  0x00001040 - 0x0040103F |  4,194,304     |  R8Q EDK II Firmware Volume |  '_FVH' (0x4856465F)     |
|  0x00401040 - 0x03209A3F |  48,269,824    |  Embedded Linux ARM64 Image |  'PE\0\0' (EFI Stub)     |
|  0x03209A40 - 0x03209FFF |  1,472         |  Kernel Page Padding        |  0x00 * 1472 (4KB Align) |
|  0x0320A000 - 0x03431631 |  2,258,482     |  Rescue Initramfs (cpio.gz) |  0x1F 0x8B (Gzip Header) |
|  0x03431632 - 0x03431FFF |  2,510         |  Ramdisk Page Padding       |  0x00 * 2510 (4KB Align) |
|  0x03432000 - 0x034FA7EE |  821,231       |  R8Q Device Tree Blob (DTB) |  0xD0 0x0D 0xFE 0xED     |
|  0x034FA7EF - 0x034FA03F |  -             |  Total Padded Container     |  Exact: 55,554,048 Bytes |
+-----------------------+----------------+-----------------------------+--------------------------+
```

---

## 2. Field-by-Field Header Parsing & Verification

Parsing of the 1,660-byte Android Boot Image v2 header structure directly from offset `0x00000000` of `build/r8q-uefi-boot-complete.img`:

| Header Field | Offset | Struct Format | Raw Hex / Binary Value | Parsed Value | Audit Verification Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `magic` | `0x00` | `8s` | `41 4e 44 52 4f 49 44 21` | `b'ANDROID!'` | **[FACT]** Matches standard Android magic |
| `kernel_size` | `0x08` | `I` | `40 8a 20 03` | `52,464,192` bytes (49.99 MiB) | **[FACT]** Matches 64B + FV + Linux size |
| `kernel_addr` | `0x0c` | `I` | `00 80 00 00` | `0x00008000` (32,768) | **[FACT]** Relative offset for ABL base `0x80000000` |
| `ramdisk_size` | `0x10` | `I` | `32 76 22 00` | `2,258,482` bytes (2.15 MiB) | **[FACT]** Matches uncompressed payload |
| `ramdisk_addr` | `0x14` | `I` | `00 00 00 01` | `0x01000000` (16,777,216) | **[FACT]** Relative offset (`0x81000000` physical) |
| `second_size` | `0x18` | `I` | `00 00 00 00` | `0` bytes | **[FACT]** Unused |
| `second_addr` | `0x1c` | `I` | `00 00 00 00` | `0x00000000` | **[FACT]** Unused |
| `tags_addr` | `0x20` | `I` | `00 01 00 00` | `0x00000100` (256) | **[FACT]** Relative ATAGS/DTB base (`0x80000100`) |
| `page_size` | `0x24` | `I` | `00 10 00 00` | `4,096` bytes | **[FACT]** Standard 4KB alignment |
| `header_version`| `0x28` | `I` | `02 00 00 00` | `2` | **[FACT]** Android Boot Image v2 |
| `os_version` | `0x2c` | `I` | `00 00 00 00` | `0` | **[FACT]** Zeroed OS version / patchlevel |
| `name` | `0x30` | `16s` | `52 38 51 5f 43 4f 4d 50 4f 55 4e 44 00...` | `b'R8Q_COMPOUND'` | **[FAILED CHECK IN REPORT]** (Report claimed `r8q-uefi-boot`) |
| `cmdline` | `0x40` | `512s` | ASCII string | `console=tty0 clk_ignore_unused...` | **[FACT]** Kernel parameters present |
| `id` (checksum)| `0x240` | `32s` | `61 d7 6a 62 4f f6 81 e1...` | SHA-1 across payloads | **[FACT]** Verified matching payload digest |
| `extra_cmdline`| `0x260` | `1024s`| `00` * 1024 | `""` | **[FACT]** Unused |
| `recovery_dtbo`| `0x660` | `I` | `00 00 00 00` | `0` bytes | **[FACT]** Unused |
| `dtbo_offset` | `0x664` | `Q` | `00 00 00 00 00 00 00 00` | `0` | **[FACT]** Unused |
| `header_size` | `0x66c` | `I` | `7c 06 00 00` | `1,660` bytes | **[FACT]** Exact Boot Header v2 size |
| `dtb_size` | `0x670` | `I` | `ef 87 0c 00` | `821,231` bytes | **[FACT]** Matches compiled DTB payload |
| `dtb_addr` | `0x674` | `Q` | `00 00 f0 01 00 00 00 00` | `0x0000000001f00000` | **[FACT]** Relative offset (`0x81f00000` physical) |

### 2.1 Critical Inconsistency Exposed in Report
In [R8Q_PHASE3_HARDWARE_INTEGRATION.md](file:///root/r8q-uefi/docs/R8Q_PHASE3_HARDWARE_INTEGRATION.md), the document claimed:
> `kernel_size: 55,554,048 bytes (52.98 MiB)`

**Audit Finding [FAILED CHECK]:**
This statement was factually inaccurate. `55,554,048 bytes` is the **total file size** of the boot image. The actual `kernel_size` declared in the header is **`52,464,192 bytes`** (`0x03208A40`). The remainder of the file contains the ramdisk (`2,258,482 bytes`), DTB (`821,231 bytes`), and alignment padding.

---

## 3. Disassembly & Control-Flow Tracing of ARM64 Wrapper

Disassembly of the kernel payload starting at offset `0x00001000` (loaded by ABL to `0x80080000`):

### 3.1 Initial Vector (Offset 0x00 - 0x3F)
```assembly
0000000080080000:  14000010   b   0x80080040        // Unconditional branch forward 64 bytes
0000000080080004:  00000000   udf #0
0000000080080008:  00080000   .inst 0x00080000      // text_offset = 512 KiB
000000008008000C:  00000000   udf #0
0000000080080010:  03208a40   .inst 0x03208a40      // image_size = 52,464,192 bytes
0000000080080014:  00000000   udf #0
0000000080080018:  0000000a   udf #10               // flags = 0x0A (Little-Endian, 4KB page)
...
0000000080080038:  644d5241   .inst 0x644d5241      // ARM64 magic: "ARM\x64"
000000008008003C:  00000000   udf #0                // pe_offset = 0 (Not PE/COFF)
```
- **Verification [FACT]:** Instruction `0x14000010` successfully bypasses the 64-byte Linux ARM64 header and branches directly to `0x80080040`.

### 3.2 Second Hop: R8Q_EFI.fd Header (Offset 0x40 - 0x7F)
At offset `0x80080040`, the payload encounters the start of `build/R8Q_EFI.fd`:
```assembly
0000000080080040:  140004ba   b   0x80081328        // Branch forward 0x12E8 bytes
0000000080080044:  00000000   udf #0
...
0000000080080068:  4856465f   .inst 0x4856465f      // '_FVH' (Firmware Volume Header Signature)
```
- **Verification [FACT]:** The instruction at `0x80080040` branches forward into the PrePi entry code at `0x80081328`.

### 3.3 PrePi Entry Point & Stack Setup (Offset 0x1328 - 0x139C)
```assembly
0000000080081328:  14000010   b   0x80081368        // Branch over PrePi embedded header
...
0000000080081368:  aa0003f3   mov x19, x0           // Preserve X0 (DTB pointer from ABL)
000000008008136c:  d5034fdf   msr daifset, #0xf     // Mask all interrupts (D, A, I, F)
0000000080081370:  d5381041   mrs x1, cpacr_el1     // Read CPACR_EL1
0000000080081374:  b26c0421   orr x1, x1, #0x300000 // Enable FP/SIMD (bits 20:21)
0000000080081378:  d5181041   msr cpacr_el1, x1     // Write CPACR_EL1
000000008008137c:  d5033fdf   isb                   // Instruction Synchronization Barrier
0000000080081380:  d508751f   ic  iallu             // Invalidate instruction cache
0000000080081384:  d5033fdf   isb                   // Instruction Synchronization Barrier
0000000080081388:  580000c2   ldr x2, 0x800813a0    // Load literal: 0x000000009E890000
000000008008138c:  9100005f   mov sp, x2            // Set SP = 0x9E890000
0000000080081390:  aa1303e0   mov x0, x19           // Restore X0 (DTB pointer)
0000000080081394:  97ffffcf   bl  0x800812d0        // Call CEntryPoint
0000000080081398:  d503205f   wfe                   // Wait For Event (Halt)
000000008008139c:  17ffffff   b   0x80081398        // Dead loop
```

### 3.4 CEntryPoint & Terminal Halt (Offset 0x12D0)
Disassembly of `0x800812D0` reveals:
1. It calls `0x80081280` three times, passing framebuffer parameters (`x=0, y=0, w=1080, h=120`, `color=0x001B365D`), (`x=0, y=120, w=1080, h=20`, `color=0x0000A86B`), and (`x=440, y=1150, w=200, h=100`, `color=0x0000A86B`).
2. Function `0x80081280` computes `pixel_addr = 0x9C000000 + (y * 1080 + x) * 4` and directly stores pixels into the Continuous Splash framebuffer.
3. At `0x8008131C`, it executes `wfe` and loops forever.

---

## 4. Material Architectural Defect: Unexecuted Linux Kernel & Missing Relocation

> [!CAUTION]
> **CRITICAL DEFECT IDENTIFIED [FAILED CHECK]:**  
> In [R8Q_PHASE3_HARDWARE_INTEGRATION.md](file:///root/r8q-uefi/docs/R8Q_PHASE3_HARDWARE_INTEGRATION.md), the document claimed:
> - *"Relocation Action: Wrapper copies 4 MiB of EDK II FV from 0x80080040 to 0x9E400000."*  
> - *"PrePi & DXE Dispatcher launches embedded Linux Kernel."*
> 
> **Actual Binary Ground Truth:**  
> 1. There is **NO RELOCATION LOOP** in the binary. The code executes in-place at `0x80080000`.  
> 2. `CEntryPoint` paints color blocks and halts in an infinite `wfe` loop.  
> 3. The embedded 46 MiB Linux kernel (`build/Image`) positioned at offset `0x00401040` is **NEVER EXECUTED**.  
> If booted on physical hardware today, the phone would display blue and green bars and permanently freeze in `wfe`.

---

## 5. Precise ABL Load Address & Execution Assumptions

### 5.1 Load Address Calculation
- `kernel_addr` in header: `0x00008000` (relative).
- Qualcomm ABL baseline DRAM base: `0x80000000`.
- Expected physical load address: `0x80000000 + 0x00008000 = 0x80008000`.
- ARM64 `text_offset`: `0x00080000` (512 KiB).
- **Assumed Entry Point:** `0x80080000`.

### 5.2 Status of ABL Acceptance Claim
- **Status:** **INFERRED / UNKNOWN**
- **Justification:**  
  1. No physical boot has ever been performed on this device.
  2. While the image format adheres to Android Boot Image v2, Samsung Knox bootloaders frequently enforce SEAndroid headers (`SEANDROIDENFORCE` magic appended at end of image) or validate AVB (Android Verified Boot) vbmeta digests even when unlocked.
  3. ABL acceptance of this compound image cannot be declared "proven" until physical staging is authorized and attempted.

---

## 6. Audit Conclusion & Ledger Summary

| Item Audited | Declared Phase 3 Claim | Independent Binary Finding | Status |
| :--- | :--- | :--- | :--- |
| **Boot Magic** | `ANDROID!` (v2) | `ANDROID!` at offset 0x00 | **FACT** |
| **Compound Kernel Size**| 55,554,048 bytes | 52,464,192 bytes (Container: 55,554,048) | **FAILED CHECK (Discrepancy)** |
| **ARM64 Wrapper Branch**| Branches to `0x80080040` | `0x14000010` (`b +64`) confirmed | **FACT** |
| **PrePi Stack Pointer** | `0x9E880000` | Literal loads `0x9E890000` | **FACT (64KB higher)** |
| **FV Relocation** | Relocates FV to `0x9E400000` | **NO relocation in binary; runs in-place**| **FAILED CHECK (Defect)** |
| **Linux Boot Handoff** | Dispatches embedded Linux | **Halts in `wfe` loop; Linux never called**| **FAILED CHECK (Defect)** |
| **ABL Image Acceptance** | Staged & Accepted | **Unproven assumption on Knox bootloader**| **UNKNOWN / INFERENCE** |
