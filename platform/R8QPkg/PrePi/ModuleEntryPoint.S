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

    // 4. Invalidate instruction cache
    ic      iallu
    isb

    // 5. Establish early stack at safe DRAM offset in 12 MiB unreserved gap
    // Base of stack buffer: 0x9E880000, Top of stack: 0x9E890000 (64 KiB, descending)
    ldr     x2, =0x9E890000
    mov     sp, x2

    // 6. Check if firmware volume needs relocation to compiled base (0x9E400000)
    adr     x20, _ModuleEntryPoint      // Current entry point in DRAM (e.g. 0x800813E0)
    movz    x22, #0x13e0                // Entry offset within FV: 0x13E0 (5,088 bytes)
    sub     x20, x20, x22               // x20 = True Firmware Volume Base (offset 0)
    ldr     x21, =0x9E400000            // Target relocation base
    cmp     x20, x21
    b.eq    .Lalready_relocated

    // Relocate 4 MiB (0x00400000 bytes) from x20 to x21 using 16-byte ldp/stp
    mov     x22, x20
    mov     x23, x21
    ldr     x24, =0x00400000
.Lreloc_loop:
    ldp     x25, x26, [x22], #16
    stp     x25, x26, [x23], #16
    subs    x24, x24, #16
    b.gt    .Lreloc_loop

    // Clean data cache to Point of Unification (PoU) across relocated memory
    mov     x22, x21
    ldr     x23, =0x00400000
.Lclean_pou_loop:
    dc      cvau, x22                   // Clean data cache by VA to PoU
    add     x22, x22, #64               // Stride by 64-byte cache line
    subs    x23, x23, #64
    b.gt    .Lclean_pou_loop

    // Memory barriers and instruction cache invalidation
    dsb     ish                         // Ensure all cache clean operations complete
    ic      iallu                       // Invalidate all instruction caches to PoU
    dsb     ish                         // Wait for I-cache invalidation to complete
    isb                                 // Flush instruction pipeline

    // Jump to the relocated code at 0x9E400000 (Exact match, delta = 0)
    ldr     x25, =.Lalready_relocated
    mov     x0, x19
    br      x25

.Lalready_relocated:
    // Transition to PrePi C main with DTB pointer in x0
    mov     x0, x19
    bl      CEntryPoint

    // If CEntryPoint ever returns, park core in safe WFI loop
.Lhalt:
    wfi
    b       .Lhalt
