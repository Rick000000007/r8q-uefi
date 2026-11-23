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

    // Save actual physical load address of this entry point in x27 (AAPCS64 callee-saved)
    adr     x27, _ModuleEntryPoint

    // 2. Mask all interrupts (Debug, SError, IRQ, FIQ)
    msr     daifset, #0xf

    // 3. Exception Level Detection and FP/SIMD Coprocessor Enable
    // Inspect CurrentEL without clobbering argument registers (bits [3:2]: 1=EL1, 2=EL2)
    mrs     x2, CurrentEL
    lsr     x2, x2, #2                  // Extract bits [3:2]: 1=EL1, 2=EL2
    cmp     x2, #2
    b.eq    .Lhandle_el2
    cmp     x2, #1
    b.eq    .Lhandle_el1

    // Unsupported Exception Level (EL0 or EL3): park core
    b       .Lhalt

.Lhandle_el2:
    // Running at EL2: Disable coprocessor/FP/SIMD traps in CPTR_EL2
    msr     cptr_el2, xzr
    // Set HCR_EL2.RW = 1 (AArch64 execution state for EL1)
    mov     x1, #(1 << 31)
    msr     hcr_el2, x1
    // Clear virtual timer offset
    msr     cntvoff_el2, xzr
    // Enable EL1 physical counter access in CNTHCTL_EL2
    mrs     x1, cnthctl_el2
    orr     x1, x1, #0x3
    msr     cnthctl_el2, x1
    isb

.Lhandle_el1:
    // Running at EL1 or EL2: Enable FP/SIMD access in CPACR_EL1 (bits 20:21 = 0b11)
    mrs     x1, cpacr_el1
    orr     x1, x1, #(0x3 << 20)
    msr     cpacr_el1, x1
    isb

.Lcache_init:
    // 4. Invalidate instruction cache
    ic      iallu
    isb

    // 5. Establish early stack at safe DRAM offset in 12 MiB unreserved gap
    // Base of stack buffer: 0x9E880000, Top of stack: 0x9E890000 (64 KiB, descending)
    ldr     x2, =0x9E890000
    mov     sp, x2

    // 6. Check if firmware volume needs relocation to compiled base (0x9E400000)
    // CRITICAL-01 FIX: In AArch64, entry offset is subtracted using register arithmetic
    // Primary TE entry offset is 0x1418 (5,144 bytes).
    adr     x20, _ModuleEntryPoint      // Current entry point in DRAM
    movz    x22, #0x1418                // TE entry offset within FV: 0x1418 (5,144 bytes)
    sub     x20, x20, x22               // x20 = Calculated Firmware Volume Base (offset 0)

    // Authoritative direct derived candidates: _ModuleEntryPoint is compiled at offset 0x2F00 (or 0x2E80) within FV
    adr     x20, _ModuleEntryPoint
    ldr     x22, =0x2F00
    sub     x20, x20, x22               // Derived FV Base (handles both wrapped and raw alignments)
    bl      .Lverify_fv_candidate
    b.eq    .Lfv_confirmed

    adr     x20, _ModuleEntryPoint
    ldr     x22, =0x2E80
    sub     x20, x20, x22
    bl      .Lverify_fv_candidate
    b.eq    .Lfv_confirmed

    // Fallback dual-phase scan: handles both +0x40 wrapped and raw alignments
    adr     x20, _ModuleEntryPoint
    and     x20, x20, #~0xFFF

.Lscan_fvh:
    // Boundary check: Candidate base must be >= DRAM_BASE_PHYS (0x80000000)
    ldr     x23, =0x80000000
    cmp     x20, x23
    b.lo    .Lhalt                      // Scanned below physical DRAM, abort

    // Phase A: Test wrapped container alignment (PageBase + 0x40)
    add     x20, x20, #0x40
    bl      .Lverify_fv_candidate
    b.eq    .Lfv_confirmed
    sub     x20, x20, #0x40

    // Phase B: Test raw volume alignment (PageBase + 0x00)
    bl      .Lverify_fv_candidate
    b.eq    .Lfv_confirmed

.Lnext_page:
    sub     x20, x20, #0x1000
    b       .Lscan_fvh

.Lverify_fv_candidate:
    // 1. Signature check: '_FVH' (0x4856465F) at offset 0x28
    ldr     w23, [x20, #0x28]
    ldr     w24, =0x4856465F
    cmp     w23, w24
    b.ne    .Lcand_invalid

    // 2. FvLength check: Exactly 4 MiB (0x00400000) at offset 0x20
    ldr     x23, [x20, #0x20]
    ldr     x24, =0x00400000
    cmp     x23, x24
    b.ne    .Lcand_invalid

    // 3. HeaderLength check: 72 bytes (0x0048) at offset 0x30
    ldrh    w23, [x20, #0x30]
    cmp     w23, #0x0048
    b.ne    .Lcand_invalid

    // 4. Reset Vector Branch Instruction Verification
    // Decode unconditional B instruction, extract signed imm26, and verify target == x27
    ldr     w23, [x20, #0x00]
    lsr     w24, w23, #26               // Extract opcode bits [31:26]
    cmp     w24, #5                     // Must be unconditional B (0b000101 = 5, rejects BL, B.cond, CBZ)
    b.ne    .Lcand_invalid

    sbfx    x24, x23, #0, #26           // Sign-extend imm26 to 64-bit signed displacement
    lsl     x24, x24, #2                // Multiply by 4 (byte displacement)

    cmp     x24, #72                    // Must branch forward past header
    b.lt    .Lcand_invalid
    ldr     x25, =0x00400000
    cmp     x24, x25                    // Must be within 4 MiB volume
    b.ge    .Lcand_invalid

    add     x25, x20, x24               // Computed target = FV_Base + Displacement
    cmp     x25, x27                    // Target must match running _ModuleEntryPoint
    b.ne    .Lcand_invalid

    // Candidate validated successfully
    cmp     xzr, xzr                    // Set EQ flag
    ret

.Lcand_invalid:
    mov     x23, #1
    cmp     x23, xzr                    // Set NE flag
    ret

.Lfv_confirmed:
    // Save original physical Firmware Volume base in x28 (AAPCS64 callee-saved)
    mov     x28, x20

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
    mov     x1, x28                     // x1 = Authoritative original physical FV base in DRAM
    br      x25

.Lalready_relocated:
    // Transition to PrePi C main with DTB pointer in x0 and Staged FV Base in x1
    mov     x0, x19
    mov     x1, x28
    bl      CEntryPoint

    // If CEntryPoint ever returns, park core in safe WFI loop
.Lhalt:
    wfi
    b       .Lhalt

//==============================================================================
// ArmLaunchLinuxKernel
//
// Arguments (AAPCS64):
//   x0 = KernelEntry (Physical 2 MiB-aligned entry address of Linux Image)
//   x1 = DtbBase     (Physical address of Device Tree Blob in DRAM)
//
// Conforms strictly to Linux ARM64 Boot Protocol (Documentation/arm64/booting.rst)
// Does NOT return.
//==============================================================================
.global ArmLaunchLinuxKernel
.type ArmLaunchLinuxKernel, %function
.align 4

ArmLaunchLinuxKernel:
    // Arguments:
    //   x0 = Kernel entry point (physical address of Linux Image, offset +0x00 / code0)
    //   x1 = Validated Device Tree Blob physical base address

    // 1. Mask all interrupts (Debug, SError, IRQ, FIQ)
    msr     daifset, #0xf

    // 2. Ensure 16-byte stack alignment per AAPCS64
    mov     x2, sp
    bic     x2, x2, #0xf
    mov     sp, x2

    // 3. Inspect Current Exception Level (CurrentEL[3:2])
    mrs     x2, CurrentEL
    lsr     x2, x2, #2                  // 1=EL1, 2=EL2
    cmp     x2, #2
    b.eq    .Lhandoff_el2
    cmp     x2, #1
    b.eq    .Lhandoff_el1
    b       .Lhalt

.Lhandoff_el2:
    // Running at EL2 (Hypervisor Mode):
    // Disable MMU (Bit 0) and Data Cache (Bit 2) in SCTLR_EL2
    mrs     x3, sctlr_el2
    bic     x3, x3, #(1 << 0)           // Clear M (MMU disabled)
    bic     x3, x3, #(1 << 2)           // Clear C (Data cache disabled)
    msr     sctlr_el2, x3
    isb

    // Invalidate EL2 TLB
    tlbi    alle2
    dsb     sy
    isb

    // Configure HCR_EL2: Set RW (Bit 31) = 1 to mandate AArch64 state for EL1
    mov     x3, #(1 << 31)              // HCR_EL2.RW = 1
    msr     hcr_el2, x3

    // Allow EL1 full access to physical counter and timer
    mrs     x3, cnthctl_el2
    orr     x3, x3, #0x3                // Bits [1:0] = 0b11
    msr     cnthctl_el2, x3

    // Zero virtual timer offset (CNTVOFF_EL2 = 0)
    msr     cntvoff_el2, xzr

    // Disable coprocessor/FP/SIMD traps in CPTR_EL2
    msr     cptr_el2, xzr
    isb

    // Program Exception Link Register (ELR_EL2) with Kernel Entry Address
    msr     elr_el2, x0

    // Program Saved Program Status Register (SPSR_EL2):
    //   M[3:0] = 0b1001 (EL2h: Exception Level 2 with SP_EL2)
    //   M[4]   = 0 (AArch64 execution state)
    //   DAIF   = 0b1111 (Debug, SError, IRQ, FIQ masked: bits [9:6] = 0x3C0)
    //   Value  = 0x3C9
    mov     x3, #0x3C9
    msr     spsr_el2, x3
    isb
    b       .Ldo_kernel_jump

.Lhandoff_el1:
    // Running at EL1 (Supervisor Mode):
    // Disable MMU (Bit 0) and Data Cache (Bit 2) in SCTLR_EL1
    mrs     x3, sctlr_el1
    bic     x3, x3, #(1 << 0)           // Clear M (MMU disabled)
    bic     x3, x3, #(1 << 2)           // Clear C (Data cache disabled)
    msr     sctlr_el1, x3
    isb

    // Invalidate EL1 TLB
    tlbi    vmalle1
    dsb     sy
    isb

    // Enable FP/SIMD coprocessor access in CPACR_EL1 (Bits [21:20] = 0b11)
    mrs     x3, cpacr_el1
    orr     x3, x3, #(0x3 << 20)
    msr     cpacr_el1, x3
    isb

    // Program Exception Link Register (ELR_EL1) with Kernel Entry Address
    msr     elr_el1, x0

    // Program Saved Program Status Register (SPSR_EL1):
    //   M[3:0] = 0b0101 (EL1h: Exception Level 1 with SP_EL1)
    //   M[4]   = 0 (AArch64 execution state)
    //   DAIF   = 0b1111 (Debug, SError, IRQ, FIQ masked: bits [9:6] = 0x3C0)
    //   Value  = 0x3C5
    mov     x3, #0x3C5
    msr     spsr_el1, x3
    isb

.Ldo_kernel_jump:
    // Invalidate all instruction caches to Point of Unification (PoU)
    ic      iallu
    dsb     sy                          // Ensure I-cache and TLB operations complete
    isb                                 // Flush CPU instruction pipeline

    // Establish authoritative ARM64 Linux Register Handoff Convention:
    // Documentation/arch/arm64/booting.rst:
    //   x0 = Physical address of Device Tree Blob (must be 8-byte aligned)
    //   x1 = 0 (Reserved for future use)
    //   x2 = 0 (Reserved for future use)
    //   x3 = 0 (Reserved for future use)
    //   x4..x30 = 0 (All general-purpose registers zeroed)
    mov     x0, x1                      // x0 = DTB physical base (from incoming x1)
    mov     x1, xzr                     // x1 = 0
    mov     x2, xzr                     // x2 = 0
    mov     x3, xzr                     // x3 = 0

    // Clear remaining general-purpose registers
    mov     x4, xzr
    mov     x5, xzr
    mov     x6, xzr
    mov     x7, xzr
    mov     x8, xzr
    mov     x9, xzr
    mov     x10, xzr
    mov     x11, xzr
    mov     x12, xzr
    mov     x13, xzr
    mov     x14, xzr
    mov     x15, xzr
    mov     x16, xzr
    mov     x17, xzr
    mov     x18, xzr
    mov     x19, xzr                    // x19 = 0 (100% compliant, entry address in ELR_ELx)
    mov     x20, xzr                    // x20 = 0
    mov     x21, xzr
    mov     x22, xzr
    mov     x23, xzr
    mov     x24, xzr
    mov     x25, xzr
    mov     x26, xzr
    mov     x27, xzr
    mov     x28, xzr
    mov     x29, xzr                    // Frame pointer = 0 (top-of-stack)
    mov     x30, xzr                    // Link register = 0 (no return)

    // Terminal Exception Return directly to Linux Image:
    // Transitions atomically to Target PC from ELR_ELx and PSTATE from SPSR_ELx.
    // ZERO general-purpose registers retain the kernel entry address!
    eret
