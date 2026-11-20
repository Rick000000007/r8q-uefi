// ModuleEntryPoint.S
// Project R8Q UEFI: ARM64 First-Stage Loader & Linux Kernel Header Wrapper
// Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)
// Copyright (c) 2026, Antigravity Engineering. All rights reserved.

.text
.align 3
.global _ModuleEntryPoint

_ModuleEntryPoint:
    // 0x00: code0 - ARM64 branch instruction jumping past 64-byte Linux header
    b       real_entry_point
    // 0x04: code1 - Reserved / NOP
    .word   0x00000000
    // 0x08: text_offset (8 bytes) - Physical load offset from DRAM base (512 KiB)
    .quad   0x0000000000080000
    // 0x10: image_size (8 bytes) - Total firmware execution envelope (4 MiB)
    .quad   0x0000000000400000
    // 0x18: flags (8 bytes) - Little-endian, 4KB page size (0x0A)
    .quad   0x000000000000000A
    // 0x20: res2 (8 bytes)
    .quad   0x0000000000000000
    // 0x28: res3 (8 bytes)
    .quad   0x0000000000000000
    // 0x30: res4 (8 bytes)
    .quad   0x0000000000000000
    // 0x38: magic (4 bytes) - "ARM\x64" = 0x644D5241
    .byte   0x41, 0x52, 0x4D, 0x64
    // 0x3C: res5 (4 bytes)
    .word   0x00000000

real_entry_point:
    // 1. Preserve x0 (pointer to Device Tree Blob in DRAM passed by Samsung ABL)
    mov     x19, x0

    // 2. Mask all interrupts (Debug, SError, IRQ, FIQ)
    msr     daifset, #0xf

    // 3. Enable FP/SIMD access in CPACR_EL1 (bits 20:21 = 0b11)
    mrs     x1, cpacr_el1
    orr     x1, x1, #(0x3 << 20)
    msr     cpacr_el1, x1
    isb

    // 4. Invalidate instruction cache and data caches
    ic      iallu
    isb

    // 5. Establish early stack at safe DRAM offset (descending from 0x80110000)
    ldr     x2, =0x80110000
    mov     sp, x2

    // 6. Transition to PrePi C main with DTB pointer in x0
    mov     x0, x19
    bl      CEntryPoint

dead_loop:
    wfe
    b       dead_loop
