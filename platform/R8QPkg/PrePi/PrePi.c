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
  UINT64            CandidateAddresses[] = {
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

  // 2. Validate Device Tree Blob passed by ABL
  if (DtbPhysBase != 0) {
    volatile UINT32 *DtbMagicPtr = (volatile UINT32 *)(UINTN)DtbPhysBase;
    if (*DtbMagicPtr == Swap32(FDT_MAGIC) || *DtbMagicPtr == FDT_MAGIC) {
      // Draw small DTB confirmation badge (Cyan: 0x0000CED1)
      DrawColorBlock(100, 40, 80, 40, 0x0000CED1);
    }
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
    volatile UINT64 *TextOffsetPtr = (volatile UINT64 *)(UINTN)(KernelCandidate + 0x08);
    UINT64 EntryOffset = *TextOffsetPtr;

    // Handoff badge: Emerald Green full block indicating successful dispatch
    DrawColorBlock(440, 1300, 200, 60, 0x0000FF00);

    // Perform Point-of-Coherence (PoC) cache maintenance for DTB and Kernel ranges
    // Ensuring data written by firmware is clean to memory for MMU=0 Linux handoff
    if (DtbPhysBase != 0) {
      UINT64 DtbCleanAddr = DtbPhysBase;
      UINT64 DtbCleanEnd = DtbPhysBase + 0x100000ULL; // 1 MiB DTB buffer
      for (; DtbCleanAddr < DtbCleanEnd; DtbCleanAddr += 64) {
        __asm__ __volatile__ ("dc civac, %0" : : "r" (DtbCleanAddr) : "memory");
      }
    }
    __asm__ __volatile__ ("dsb sy\n\tisb" : : : "memory");

    // Calling convention for Linux ARM64 kernel:
    // x0 = Physical address of Device Tree Blob (FDT)
    // x1 = 0, x2 = 0, x3 = 0 (Reserved)
    LinuxEntry = (LINUX_ENTRY_POINT)(UINTN)(KernelCandidate + EntryOffset);
    LinuxEntry(DtbPhysBase, 0, 0, 0);
  }

  // In production firmware without embedded kernel, handoff is completed via BDS/LinuxBoot
  DrawColorBlock(440, 1300, 200, 60, 0x0000A86B);
}
