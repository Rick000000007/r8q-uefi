/** @file
  PrePi.c
  Project R8Q UEFI Early Platform Entry Implementation.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <PiPei.h>
#include <Library/BaseLib.h>
#include <Library/DebugLib.h>
#include <Library/IoLib.h>
#include <Library/ArmLib.h>

#define FB_BASE_PHYS      0x9C000000ULL
#define FB_WIDTH          1080
#define FB_HEIGHT         2400
#define FB_BPP            32
#define FB_STRIDE         (FB_WIDTH * (FB_BPP / 8))

#define FDT_MAGIC         0xD00DFEED
#define FDT_MAX_SIZE      0x00200000ULL // 2 MiB maximum DTB size per Linux ARM64 boot protocol
#define LINUX_ARM64_MAGIC 0x644D5241 // 'ARM\x64'

#define FIRMWARE_BASE     0x9E400000ULL
#define FIRMWARE_SIZE     0x00400000ULL
#define STACK_TOP         0x9E890000ULL
#define STACK_LIMIT       0x9E880000ULL
#define TRUSTZONE_BASE    0x80B00000ULL
#define TRUSTZONE_END     0x88400000ULL

#define FB_BASE_LIMIT      (FB_BASE_PHYS + 0x02300000ULL) // 35 MiB Carveout (0x9E300000)
#define FIRMWARE_STACK_TOP 0x9E890000ULL
#define DRAM_BASE_PHYS     0x80000000ULL
#define DRAM_LIMIT_PHYS    0x200000000ULL // 6GB / 8GB boundary ceiling
#define KERNEL_MIN_SIZE    0x00800000ULL  // 8 MiB (distinguishes Linux kernel from 4 MiB wrapper)
#define KERNEL_MAX_SIZE    0x04000000ULL  // 64 MiB ceiling
#define KERNEL_MAX_OFFSET  0x02000000ULL  // 32 MiB max text_offset
#define KERNEL_ALIGNED_BASE 0xA2000000ULL // 2 MiB-aligned destination in Window F (modulo 0x200000 == 0)
#define DTB_REALLOC_BASE    0xA4000000ULL // 2 MiB-aligned non-overlapping DTB buffer in Window F

STATIC UINT64 gPassedDtbBase = 0;

typedef VOID (*LINUX_ENTRY_POINT)(
  IN UINT64 DtbPhys,
  IN UINT64 Res1,
  IN UINT64 Res2,
  IN UINT64 Res3
  );

/**
  Simple early framebuffer box renderer.
**/
STATIC
VOID
DrawColorBlock (
  IN UINT32 X,
  IN UINT32 Y,
  IN UINT32 Width,
  IN UINT32 Height,
  IN UINT32 Color
  )
{
  volatile UINT32 *FbPtr;
  UINT32 Row, Col;

  FbPtr = (volatile UINT32 *)(UINTN)FB_BASE_PHYS;
  for (Row = Y; Row < (Y + Height) && Row < FB_HEIGHT; Row++) {
    for (Col = X; Col < (X + Width) && Col < FB_WIDTH; Col++) {
      FbPtr[Row * FB_WIDTH + Col] = Color;
    }
  }
}

STATIC
UINT32
Swap32 (
  UINT32 Val
  )
{
  return ((Val >> 24) & 0xFF) |
         (((Val >> 16) & 0xFF) << 8) |
         (((Val >> 8) & 0xFF) << 16) |
         ((Val & 0xFF) << 24);
}

#pragma pack(1)
typedef struct {
  UINT32 Magic;
  UINT32 TotalSize;
  UINT32 OffDtStruct;
  UINT32 OffDtStrings;
  UINT32 OffMemRsvmap;
  UINT32 Version;
  UINT32 LastCompVersion;
  UINT32 BootCpuidPhys;
  UINT32 SizeDtStrings;
  UINT32 SizeDtStruct;
} FDT_HEADER;
#pragma pack()

/**
  Validate that a candidate memory address hosts a genuine Linux ARM64 kernel Image
  and does not collide with TrustZone, Framebuffer, or Firmware execution envelopes.
  Prevents firmware wrapper (4 MiB) false-positives (MAJOR-01 Remediation).
**/
STATIC
BOOLEAN
IsValidLinuxKernel (
  IN UINT64 Candidate
  )
{
  volatile UINT32 *MagicPtr;
  volatile UINT64 *ImgSizePtr;
  volatile UINT64 *TextOffsetPtr;
  UINT64          ImageSize;
  UINT64          TextOffset;

  // 1. Boundary check: Candidate must reside within valid physical DRAM
  if (Candidate < DRAM_BASE_PHYS || Candidate >= DRAM_LIMIT_PHYS) {
    return FALSE;
  }

  // 2. ARM64 Image Magic check: 'ARM\x64' (0x644D5241) at offset +0x38
  MagicPtr = (volatile UINT32 *)(UINTN)(Candidate + 0x38);
  if (*MagicPtr != LINUX_ARM64_MAGIC) {
    return FALSE;
  }

  // 3. Image size check:
  // Distinguishes the 16.02 MiB mainline Linux kernel from the 4 MiB firmware envelope
  // (ModuleEntryPoint.S wrapper declares image_size = 0x00400000 = 4 MiB).
  ImgSizePtr = (volatile UINT64 *)(UINTN)(Candidate + 0x10);
  ImageSize = *ImgSizePtr;
  if (ImageSize < KERNEL_MIN_SIZE || ImageSize > KERNEL_MAX_SIZE) {
    return FALSE;
  }

  // Arithmetic overflow and physical DRAM ceiling check: [Candidate, Candidate + ImageSize)
  if ((Candidate + ImageSize) <= Candidate || (Candidate + ImageSize) > DRAM_LIMIT_PHYS) {
    return FALSE;
  }

  // 4. Text offset sanity check
  TextOffsetPtr = (volatile UINT64 *)(UINTN)(Candidate + 0x08);
  TextOffset = *TextOffsetPtr;
  if (TextOffset > KERNEL_MAX_OFFSET) {
    return FALSE;
  }

  // 5. Memory collision check: Must not intersect TrustZone reservation [0x80B00000, 0x88400000)
  if (Candidate < TRUSTZONE_END && (Candidate + ImageSize) > TRUSTZONE_BASE) {
    return FALSE;
  }

  // 6. Memory collision check: Must not intersect Framebuffer carveout [0x9C000000, 0x9E300000)
  if (Candidate < FB_BASE_LIMIT && (Candidate + ImageSize) > FB_BASE_PHYS) {
    return FALSE;
  }

  // 7. Memory collision check: Must not intersect Firmware/Heap/Stack envelope [0x9E400000, 0x9E890000)
  if (Candidate < FIRMWARE_STACK_TOP && (Candidate + ImageSize) > FIRMWARE_BASE) {
    return FALSE;
  }

  return TRUE;
}

/**
  Validate that a physical address points to a valid, well-formed Device Tree Blob (FDT).
  Verifies:
  1. Pointer non-null and 8-byte alignment (Devicetree Spec & ARM64 boot protocol).
  2. Base resides within physical DRAM boundaries.
  3. FDT Magic matches 0xD00DFEED (big-endian).
  4. TotalSize is within valid bounds (at least 40 bytes header, max 8 MiB).
  5. Complete DTB memory span does not overflow DRAM.
  6. Memory isolation: Does not intersect TrustZone, Framebuffer, Firmware, or Stack.
**/
STATIC
BOOLEAN
IsValidDeviceTree (
  IN UINT64 DtbPhysBase,
  OUT UINT32 *DtbTotalSize OPTIONAL
  )
{
  volatile FDT_HEADER *FdtHdr;
  UINT32              Magic;
  UINT32              TotalSize;
  UINT64              DtbEnd;

  if (DtbTotalSize != NULL) {
    *DtbTotalSize = 0;
  }

  // 1. Non-null and 8-byte alignment check
  if (DtbPhysBase == 0 || (DtbPhysBase & 0x7ULL) != 0) {
    return FALSE;
  }

  // 2. Boundary check: Entire initial FDT header must reside within valid physical DRAM
  // Prevents dereferencing truncated or out-of-bounds header past DRAM boundary
  if (DtbPhysBase < DRAM_BASE_PHYS ||
      (DtbPhysBase + sizeof(FDT_HEADER)) > DRAM_LIMIT_PHYS ||
      (DtbPhysBase + sizeof(FDT_HEADER)) < DtbPhysBase) {
    return FALSE;
  }

  FdtHdr = (volatile FDT_HEADER *)(UINTN)DtbPhysBase;

  // 3. Magic check: 0xD00DFEED in big-endian
  Magic = FdtHdr->Magic;
  if (Magic != Swap32(FDT_MAGIC) && Magic != FDT_MAGIC) {
    return FALSE;
  }

  // 4. TotalSize bounds check (big-endian in standard FDT)
  // Maximum size tightened from 8 MiB to 2 MiB per Linux ARM64 boot protocol (TotalSize > 0x00800000ULL)
  TotalSize = Swap32(FdtHdr->TotalSize);
  if (TotalSize < sizeof(FDT_HEADER) || TotalSize > FDT_MAX_SIZE) { // 2 MiB max ceiling per protocol
    return FALSE;
  }

  DtbEnd = DtbPhysBase + TotalSize;
  if (DtbEnd <= DtbPhysBase || DtbEnd > DRAM_LIMIT_PHYS) {
    return FALSE;
  }

  // 5. Memory collision check: Must not intersect TrustZone reservation [0x80B00000, 0x88400000)
  if (DtbPhysBase < TRUSTZONE_END && DtbEnd > TRUSTZONE_BASE) {
    return FALSE;
  }

  // 6. Memory collision check: Must not intersect Framebuffer carveout [0x9C000000, 0x9E300000)
  if (DtbPhysBase < FB_BASE_LIMIT && DtbEnd > FB_BASE_PHYS) {
    return FALSE;
  }

  // 7. Memory collision check: Must not intersect Firmware/Heap envelope [0x9E400000, 0x9E880000)
  if (DtbPhysBase < 0x9E880000ULL && DtbEnd > FIRMWARE_BASE) {
    return FALSE;
  }

  // 8. Memory collision check: Must not intersect Stack [0x9E880000, 0x9E890000)
  if (DtbPhysBase < FIRMWARE_STACK_TOP && DtbEnd > 0x9E880000ULL) {
    return FALSE;
  }

  if (DtbTotalSize != NULL) {
    *DtbTotalSize = TotalSize;
  }

  return TRUE;
}

/**
  C Entry point invoked from ModuleEntryPoint.S after self-relocation to 0x9E400000.
  x0 contains the DTB physical base address passed by Samsung ABL.
**/
VOID
EFIAPI
CEntryPoint (
  IN UINT64 DtbPhysBase
  )
{
  LINUX_ENTRY_POINT LinuxEntry = NULL;
  UINT64            KernelCandidate = 0;
  UINT32            ValidatedDtbSize = 0;
  UINT64            ValidatedDtbBase = DtbPhysBase;
  UINT64            CandidateAddresses[] = {
                      0xA2000000ULL, // 2 MiB-aligned Window F destination (KERNEL_ALIGNED_BASE)
                      0xA0561040ULL, // Container-offset compound payload (P_load 0xA0160000 + 0x401040)
                      0xA0560040ULL, // Immediate compound payload offset (P_load 0xA0160000 + 0x400040)
                      0xA0561000ULL, // 4K-aligned compound payload offset (P_load 0xA0160000 + 0x401000)
                      0xA0160000ULL, // Direct Window F Kernel Base
                      0x90A00000ULL, // Window D: 182 MiB free System RAM
                      0xA0002000ULL  // Window F: 256.9 MiB free System RAM
                    };
  UINTN             Index;

  gPassedDtbBase = DtbPhysBase;

  // 1. Draw visual confirmation bar across top of AMOLED panel
  // Color: Royal Blue Header bar (0x001B365D)
  DrawColorBlock(0, 0, FB_WIDTH, 120, 0x001B365D);
  // Accent bar: Emerald Green (0x0000A86B)
  DrawColorBlock(0, 120, FB_WIDTH, 20, 0x0000A86B);

  // Status indicator: Center confirmation block (PrePi active)
  DrawColorBlock(440, 1150, 200, 100, 0x0000A86B);

  // 2. Validate Device Tree Blob passed by ABL (Full Structural, Alignment, and Bounds Check)
  if (IsValidDeviceTree(DtbPhysBase, &ValidatedDtbSize)) {
    // Draw small DTB confirmation badge (Cyan: 0x0000CED1)
    DrawColorBlock(100, 40, 80, 40, 0x0000CED1);

    // CRITICAL (Phase 3.6A.7): Prevent Kernel / DTB Collision!
    // The relocated kernel occupies [KERNEL_ALIGNED_BASE, KERNEL_ALIGNED_BASE + KernelSize)
    // with execution envelope up to 0xA4000000.
    // If incoming DTB is located in [0xA2000000, 0xA4000000), e.g. legacy 0xA3000000,
    // the kernel copy will overwrite the DTB!
    // Relocate the validated DTB to DTB_REALLOC_BASE (0xA4000000) BEFORE kernel relocation.
    if (DtbPhysBase < DTB_REALLOC_BASE && (DtbPhysBase + ValidatedDtbSize) > KERNEL_ALIGNED_BASE) {
      volatile UINT8 *DtbSrc = (volatile UINT8 *)(UINTN)DtbPhysBase;
      volatile UINT8 *DtbDst = (volatile UINT8 *)(UINTN)DTB_REALLOC_BASE;
      UINT32 i;
      for (i = 0; i < ValidatedDtbSize; i++) {
        DtbDst[i] = DtbSrc[i];
      }
      ValidatedDtbBase = DTB_REALLOC_BASE;

      // Re-validate DTB at new destination to prove copy integrity
      UINT32 PostRelocSize = 0;
      if (!IsValidDeviceTree(ValidatedDtbBase, &PostRelocSize) || PostRelocSize != ValidatedDtbSize) {
        // Post-relocation DTB verification failed!
        DrawColorBlock(100, 40, 80, 40, 0x00FF0000);
        ValidatedDtbBase = DtbPhysBase; // Fall back to source
      }
    }
  } else {
    // DTB invalid or corrupted: Draw Warning badge (Red: 0x00FF0000)
    DrawColorBlock(100, 40, 80, 40, 0x00FF0000);
  }

  // 3. Mathematical non-overlap verification
  // Verify Firmware [0x9E400000, 0x9E800000) is outside TrustZone [0x80B00000, 0x88400000)
  if (FIRMWARE_BASE >= TRUSTZONE_END || (FIRMWARE_BASE + FIRMWARE_SIZE) <= TRUSTZONE_BASE) {
    // Memory isolation confirmed
    DrawColorBlock(200, 40, 80, 40, 0x0000A86B);
  }

  // 4. Scan candidate staging ranges for Linux ARM64 kernel Image (MAJOR-01 Remediation)
  for (Index = 0; Index < sizeof(CandidateAddresses)/sizeof(CandidateAddresses[0]); Index++) {
    if (IsValidLinuxKernel(CandidateAddresses[Index])) {
      KernelCandidate = CandidateAddresses[Index];
      break;
    }
  }

  // Dynamic Scan: If not found in primary candidates, scan Window F (0xA0000000 - 0xAB000000)
  if (KernelCandidate == 0) {
    UINT64 Probe;
    for (Probe = 0xA0000000ULL; Probe < 0xAB000000ULL; Probe += 0x1000) {
      // Check page-aligned candidate
      if (IsValidLinuxKernel(Probe)) {
        KernelCandidate = Probe;
        break;
      }
      // Check 0x40-offset candidate (covering compound payload offsets like 0xA0560040 and 0xA0561040, probing Probe + 0x40 + 0x38)
      if (IsValidLinuxKernel(Probe + 0x40)) {
        KernelCandidate = Probe + 0x40;
        break;
      }
    }
  }

  // 5. Transfer execution to Linux EFI Stub / ARM64 Kernel Entry
  if (KernelCandidate != 0) {
    volatile UINT64 *ImgSizePtr = (volatile UINT64 *)(UINTN)(KernelCandidate + 0x10);
    UINT64          KernelSize = *ImgSizePtr;
    UINT64          KernelRunBase = KernelCandidate;
    UINT64          Ctr;
    UINT64          DminLine;
    UINT64          CacheLineSize;

    // Derive data cache line size dynamically from CTR_EL0.DminLine
    __asm__ __volatile__ ("mrs %0, ctr_el0" : "=r" (Ctr));
    DminLine = (Ctr >> 16) & 0xF;
    CacheLineSize = 4ULL << DminLine; // Standard 64 bytes on Cortex-A77/A55

    // Handoff badge: Emerald Green full block indicating successful dispatch
    DrawColorBlock(440, 1300, 200, 60, 0x0000FF00);

    // 0. Kernel Placement Protocol Check (Documentation/arm64/booting.rst)
    // The Image must be located at text_offset bytes from a 2 MiB-aligned base.
    // When text_offset = 0, Image must be at an address where (Base % 0x200000) == 0.
    // If Candidate is misaligned relative to 2 MiB boundary, relocate to KERNEL_ALIGNED_BASE (0xA2000000).
    if ((KernelCandidate & 0x001FFFFFULL) != 0) {
      UINT64 DstEnd = KERNEL_ALIGNED_BASE + KernelSize;
      if (DstEnd <= DRAM_LIMIT_PHYS && DstEnd > KERNEL_ALIGNED_BASE) {
        volatile UINT64 *Src = (volatile UINT64 *)(UINTN)KernelCandidate;
        volatile UINT64 *Dst = (volatile UINT64 *)(UINTN)KERNEL_ALIGNED_BASE;
        UINT64 CopyBytes = KernelSize;
        // Hardening: Avoid copying beyond actual kernel payload into adjacent ramdisk at 0xA1568000
        if (KernelCandidate == 0xA0561040ULL && CopyBytes > 0x01006200ULL) {
          CopyBytes = 0x01006200ULL;
        }
        UINT64 Words = (CopyBytes + 7) / 8;
        UINT64 TotalWords = (KernelSize + 7) / 8;
        UINT64 Idx;
        for (Idx = 0; Idx < Words; Idx++) {
          Dst[Idx] = Src[Idx];
        }
        // Zero BSS remainder in destination buffer
        for (Idx = Words; Idx < TotalWords; Idx++) {
          Dst[Idx] = 0;
        }
        KernelRunBase = KERNEL_ALIGNED_BASE;
      }
    }

    // 1. Perform Point-of-Coherence (PoC) cache maintenance for validated DTB
    if (ValidatedDtbBase != 0 && ValidatedDtbSize != 0) {
      UINT64 DtbCleanAddr = ValidatedDtbBase & ~(CacheLineSize - 1);
      UINT64 DtbCleanLimit = (ValidatedDtbBase + ValidatedDtbSize + CacheLineSize - 1) & ~(CacheLineSize - 1);
      if (DtbCleanLimit <= DRAM_LIMIT_PHYS && DtbCleanLimit > DtbCleanAddr) {
        for (; DtbCleanAddr < DtbCleanLimit; DtbCleanAddr += CacheLineSize) {
          __asm__ __volatile__ ("dc civac, %0" : : "r" (DtbCleanAddr) : "memory");
        }
      }
    }

    // 2. Perform Point-of-Coherence (PoC) cache maintenance for entire loaded Linux Image
    // Mandated by Linux ARM64 Boot Protocol (Documentation/arm64/booting.rst)
    if (KernelSize >= KERNEL_MIN_SIZE && KernelSize <= KERNEL_MAX_SIZE) {
      UINT64 KernelCleanAddr = KernelRunBase & ~(CacheLineSize - 1);
      UINT64 KernelCleanLimit = (KernelRunBase + KernelSize + CacheLineSize - 1) & ~(CacheLineSize - 1);
      if (KernelCleanLimit <= DRAM_LIMIT_PHYS && KernelCleanLimit > KernelCleanAddr) {
        for (; KernelCleanAddr < KernelCleanLimit; KernelCleanAddr += CacheLineSize) {
          __asm__ __volatile__ ("dc civac, %0" : : "r" (KernelCleanAddr) : "memory");
        }
      }
    }

    // Full system data barrier and instruction pipeline barrier before kernel branch
    __asm__ __volatile__ ("dsb sy\n\tisb" : : : "memory");

    // Calling convention for Linux ARM64 kernel (Documentation/arm64/booting.rst):
    // Execution begins at the very first instruction of the Image (offset +0x00 / code0).
    // text_offset in the header specifies load offset relative to 2 MiB alignment, NOT an offset within Image.
    // x0 = Physical address of Device Tree Blob (FDT)
    // x1 = 0, x2 = 0, x3 = 0 (Reserved)
    KernelCandidate = KernelRunBase;
    LinuxEntry = (LINUX_ENTRY_POINT)(UINTN)KernelCandidate;
    LinuxEntry(ValidatedDtbBase, 0, 0, 0);
  }

  // In production firmware without embedded kernel, handoff is completed via BDS/LinuxBoot
  DrawColorBlock(440, 1300, 200, 60, 0x0000A86B);
}
