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
                      0x90A00000ULL, // Window D: 182 MiB free System RAM
                      0xA0002000ULL, // Window F: 256.9 MiB free System RAM
                      0x9E890000ULL  // High RAM directly above stack
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

  // 4. Scan candidate staging ranges for Linux ARM64 kernel Image
  for (Index = 0; Index < sizeof(CandidateAddresses)/sizeof(CandidateAddresses[0]); Index++) {
    volatile UINT32 *MagicPtr = (volatile UINT32 *)(UINTN)(CandidateAddresses[Index] + 0x38);
    if (*MagicPtr == LINUX_ARM64_MAGIC) {
      KernelCandidate = CandidateAddresses[Index];
      break;
    }
  }

  // 5. Transfer execution to Linux EFI Stub / ARM64 Kernel Entry
  if (KernelCandidate != 0) {
    volatile UINT64 *TextOffsetPtr = (volatile UINT64 *)(UINTN)(KernelCandidate + 0x08);
    UINT64 EntryOffset = *TextOffsetPtr;

    // Handoff badge: Emerald Green full block indicating successful dispatch
    DrawColorBlock(440, 1300, 200, 60, 0x0000FF00);

    // Calling convention for Linux ARM64 kernel:
    // x0 = Physical address of Device Tree Blob (FDT)
    // x1 = 0, x2 = 0, x3 = 0 (Reserved)
    LinuxEntry = (LINUX_ENTRY_POINT)(UINTN)(KernelCandidate + EntryOffset);
    LinuxEntry(DtbPhysBase, 0, 0, 0);
  }

  // In production firmware without embedded kernel, handoff is completed via BDS/LinuxBoot
  DrawColorBlock(440, 1300, 200, 60, 0x0000A86B);
}
