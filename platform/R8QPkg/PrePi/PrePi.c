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

STATIC UINT64 gPassedDtbBase = 0;

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

/**
  C Entry point invoked from ModuleEntryPoint.S.
  x0 contains the DTB physical base address passed by Samsung ABL.
**/
VOID
EFIAPI
CEntryPoint (
  IN UINT64 DtbPhysBase
  )
{
  gPassedDtbBase = DtbPhysBase;

  // Draw visual confirmation bar across the top of AMOLED panel
  // Color: Royal Blue Header bar (0x001B365D)
  DrawColorBlock(0, 0, FB_WIDTH, 120, 0x001B365D);
  // Accent bar: Emerald Green (0x0000A86B)
  DrawColorBlock(0, 120, FB_WIDTH, 20, 0x0000A86B);

  // Status indicator: Center confirmation block
  DrawColorBlock(440, 1150, 200, 100, 0x0000A86B);

  // In early prototype, wait in low-power state
  while (TRUE) {
    ArmCallWFE();
  }
}
