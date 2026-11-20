# Project R8Q UEFI: Memory Placement & Firmware Entry Handoff Design

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M2  
**Status:** Approved Architectural Baseline  

---

## 1. Memory Execution Geometry

When Samsung ABL loads the boot payload, it places the image at `0x80000000 + text_offset`. On SM8250, standard kernel placement is:
- **Image Load Base:** `0x80080000` (or `0x80008000`)
- **Ramdisk Load Base:** `0x81000000` (16 MiB above kernel base)
- **Device Tree Blob (DTB):** Dynamically allocated by ABL in high memory; pointer passed in register `x0`.

### 1.1 Early Memory Layout during Pre-Pi Execution

```
0x80000000 +---------------------------------------------------------+
           | Qualcomm Hypervisor & Secure Monitor Carveout (6 MiB)   | EfiReservedMemoryType
0x80080000 +---------------------------------------------------------+
           | R8Q First-Stage Loader Wrapper & Pre-Pi Binary (~512 KB)| EfiBootServicesCode
           | - 64-byte ARM64 Linux Kernel Header at byte 0           |
           | - Early Entry Point Assembly (ModuleEntryPoint.S)       |
           | - Early C Initialization (PrePi.c)                      |
0x80100000 +---------------------------------------------------------+
           | Early Stack (64 KiB descending from 0x80110000)         | EfiBootServicesData
0x80110000 +---------------------------------------------------------+
           | Early Heap (1 MiB for Pre-Pi Memory Allocation)         | EfiBootServicesData
0x80210000 +---------------------------------------------------------+
           | Free System Memory Buffer                               | EfiConventionalMemory
0x9C000000 +---------------------------------------------------------+
           | Continuous Splash Framebuffer (35.00 MiB)               | EfiReservedMemoryType / GOP
0x9E400000 +---------------------------------------------------------+
           | Firmware Device Image (R8Q_EFI.fd Relocation Base, 4MB) | EfiBootServicesCode
0xA0002000 +---------------------------------------------------------+
           | DXE System Pool & UEFI Page Allocations (255 MiB)       | EfiConventionalMemory
0x10AD00000+---------------------------------------------------------+
           | High System Memory Pool (~5.7 GiB Usable DRAM)          | EfiConventionalMemory
0x27FFFFFFF+---------------------------------------------------------+
```

---

## 2. First-Stage Loader Wrapper (`ModuleEntryPoint.S`)

The assembly entry point bridges the architectural gap between the ARM64 Linux boot protocol and EDK II:

```assembly
// ModuleEntryPoint.S - R8Q First-Stage Loader Entry Point
.text
.align 3
.global _ModuleEntryPoint

_ModuleEntryPoint:
    // 0x00: code0 - ARM64 branch instruction jumping past 64-byte header
    b       real_entry_point
    // 0x04: code1 - Reserved / NOP
    .word   0x00000000
    // 0x08: text_offset (8 bytes)
    .quad   0x0000000000080000
    // 0x10: image_size (8 bytes)
    .quad   0x0000000000400000  // 4 MiB firmware envelope
    // 0x18: flags (8 bytes) - Little-endian, 4KB page size
    .quad   0x000000000000000A
    // 0x20: reserved (24 bytes)
    .quad   0x0000000000000000
    .quad   0x0000000000000000
    .quad   0x0000000000000000
    // 0x38: magic (4 bytes) - "ARM\x64" = 0x644D5241
    .ascii  "ARM\x64"
    // 0x3C: res5 (4 bytes)
    .word   0x00000000

real_entry_point:
    // 1. Preserve x0 (pointer to DTB passed by ABL)
    mov     x19, x0

    // 2. Disable interrupts
    msr     daifset, #0xf

    // 3. Enable FP/SIMD access in CPACR_EL1
    mrs     x1, cpacr_el1
    orr     x1, x1, #(0x3 << 20)
    msr     cpacr_el1, x1
    isb

    // 4. Establish early stack
    ldr     x2, =0x80110000
    mov     sp, x2

    // 5. Pass DTB pointer to PrePi C Entry Point
    mov     x0, x19
    bl      PrePiMain

dead_loop:
    wfe
    b       dead_loop
```

---

## 3. Register State & Security Level Transitions

| Register | Value at ABL Handoff | Handled By PrePi | State at DXE Dispatch |
|---|---|---|---|
| `x0` | Physical address of DTB | Stored in global `gDeviceTreeBase` | Exposed via `EFI_DEVICE_TREE_PROTOCOL` |
| `x1`-`x4` | 0 (reserved) | Cleared / ignored | Standard ABI parameters |
| `SP` | Undefined / ABL stack | Set to `0x80110000` (64 KiB stack) | Managed by DXE Core memory allocator |
| `SCTLR_EL1` | MMU/Caches configured by ABL | Caches flushed, MMU identity mapped | Managed by `ArmPkg/CpuDxe` |
| `VBAR_EL1` | ABL exception vectors | Pointed to R8Q vector table | Managed by `ArmPkg/CpuDxe` |

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
