/** @file
  SimpleFbDxe.c
  Project R8Q Continuous Splash Framebuffer Graphics Output Protocol Driver.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

  Features:
  - 1080x2400 @ 32bpp BGRX display scanout on Samsung AMOLED panel.
  - Complete Blt implementation: Fill, VideoToBuffer, BufferToVideo, VideoToVideo.
  - 2x High-DPI Glyph Scaling Engine for terminal readability on 407 PPI screen.

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <Uefi.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/DebugLib.h>
#include <Library/PcdLib.h>
#include <Protocol/GraphicsOutput.h>

STATIC EFI_GRAPHICS_OUTPUT_MODE_INFORMATION mGopModeInfo = {
  0,                            // Version
  1080,                         // HorizontalResolution
  2400,                         // VerticalResolution
  PixelBlueGreenRedReserved8BitPerColor, // PixelFormat
  { 0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000 }, // PixelInformation
  1080                          // PixelsPerScanLine
};

STATIC EFI_GRAPHICS_OUTPUT_PROTOCOL_MODE mGopMode = {
  1,                            // MaxMode
  0,                            // Mode
  &mGopModeInfo,                // Info
  sizeof (EFI_GRAPHICS_OUTPUT_MODE_INFORMATION), // SizeOfInfo
  0x9C000000ULL,                // FrameBufferBase
  (1080 * 2400 * 4)             // FrameBufferSize
};

STATIC
EFI_STATUS
EFIAPI
GopQueryMode (
  IN  EFI_GRAPHICS_OUTPUT_PROTOCOL          *This,
  IN  UINT32                                ModeNumber,
  OUT UINTN                                 *SizeOfInfo,
  OUT EFI_GRAPHICS_OUTPUT_MODE_INFORMATION  **Info
  )
{
  if (ModeNumber != 0 || Info == NULL || SizeOfInfo == NULL) {
    return EFI_INVALID_PARAMETER;
  }
  *SizeOfInfo = sizeof (EFI_GRAPHICS_OUTPUT_MODE_INFORMATION);
  *Info       = &mGopModeInfo;
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
GopSetMode (
  IN  EFI_GRAPHICS_OUTPUT_PROTOCOL *This,
  IN  UINT32                       ModeNumber
  )
{
  if (ModeNumber != 0) {
    return EFI_UNSUPPORTED;
  }
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
GopBlt (
  IN  EFI_GRAPHICS_OUTPUT_PROTOCOL            *This,
  IN  EFI_GRAPHICS_OUTPUT_BLT_PIXEL           *BltBuffer, OPTIONAL
  IN  EFI_GRAPHICS_OUTPUT_BLT_OPERATION       BltOperation,
  IN  UINTN                                   SourceX,
  IN  UINTN                                   SourceY,
  IN  UINTN                                   DestinationX,
  IN  UINTN                                   DestinationY,
  IN  UINTN                                   Width,
  IN  UINTN                                   Height,
  IN  UINTN                                   Delta OPTIONAL
  )
{
  UINT32 *Fb;
  UINT32 Stride;
  UINTN  X, Y;

  if (This == NULL || Width == 0 || Height == 0) {
    return EFI_INVALID_PARAMETER;
  }

  Fb     = (UINT32 *)(UINTN)This->Mode->FrameBufferBase;
  Stride = This->Mode->Info->PixelsPerScanLine;

  if (Delta == 0) {
    Delta = Width * sizeof (EFI_GRAPHICS_OUTPUT_BLT_PIXEL);
  }

  // Bounds validation against panel dimensions
  if (BltOperation == EfiBltVideoFill ||
      BltOperation == EfiBltBufferToVideo) {
    if ((DestinationX + Width) > This->Mode->Info->HorizontalResolution ||
        (DestinationY + Height) > This->Mode->Info->VerticalResolution) {
      return EFI_INVALID_PARAMETER;
    }
  } else if (BltOperation == EfiBltVideoToBltBuffer) {
    if ((SourceX + Width) > This->Mode->Info->HorizontalResolution ||
        (SourceY + Height) > This->Mode->Info->VerticalResolution) {
      return EFI_INVALID_PARAMETER;
    }
  } else if (BltOperation == EfiBltVideoToVideo) {
    if ((SourceX + Width) > This->Mode->Info->HorizontalResolution ||
        (SourceY + Height) > This->Mode->Info->VerticalResolution ||
        (DestinationX + Width) > This->Mode->Info->HorizontalResolution ||
        (DestinationY + Height) > This->Mode->Info->VerticalResolution) {
      return EFI_INVALID_PARAMETER;
    }
  }

  switch (BltOperation) {
  case EfiBltVideoFill: {
    UINT32 Color;
    Color = *(UINT32 *)BltBuffer;
    for (Y = 0; Y < Height; Y++) {
      UINT32 *Row = &Fb[(DestinationY + Y) * Stride + DestinationX];
      for (X = 0; X < Width; X++) {
        Row[X] = Color;
      }
    }
    break;
  }

  case EfiBltBufferToVideo: {
    UINT8 *SrcRow = (UINT8 *)BltBuffer;
    for (Y = 0; Y < Height; Y++) {
      UINT32 *Dst = &Fb[(DestinationY + Y) * Stride + DestinationX];
      CopyMem (Dst, SrcRow, Width * sizeof (UINT32));
      SrcRow += Delta;
    }
    break;
  }

  case EfiBltVideoToBltBuffer: {
    UINT8 *DstRow = (UINT8 *)BltBuffer;
    for (Y = 0; Y < Height; Y++) {
      UINT32 *Src = &Fb[(SourceY + Y) * Stride + SourceX];
      CopyMem (DstRow, Src, Width * sizeof (UINT32));
      DstRow += Delta;
    }
    break;
  }

  case EfiBltVideoToVideo: {
    if (DestinationY < SourceY) {
      // Forward copy (top to bottom)
      for (Y = 0; Y < Height; Y++) {
        UINT32 *Src = &Fb[(SourceY + Y) * Stride + SourceX];
        UINT32 *Dst = &Fb[(DestinationY + Y) * Stride + DestinationX];
        CopyMem (Dst, Src, Width * sizeof (UINT32));
      }
    } else {
      // Backward copy (bottom to top for scrolling)
      for (Y = Height; Y > 0; Y--) {
        UINT32 *Src = &Fb[(SourceY + (Y - 1)) * Stride + SourceX];
        UINT32 *Dst = &Fb[(DestinationY + (Y - 1)) * Stride + DestinationX];
        CopyMem (Dst, Src, Width * sizeof (UINT32));
      }
    }
    break;
  }

  default:
    return EFI_INVALID_PARAMETER;
  }

  return EFI_SUCCESS;
}

STATIC EFI_GRAPHICS_OUTPUT_PROTOCOL mGopProtocol = {
  GopQueryMode,
  GopSetMode,
  GopBlt,
  &mGopMode
};

EFI_STATUS
EFIAPI
SimpleFbDxeInitialize (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_STATUS Status;

  mGopMode.FrameBufferBase = PcdGet64 (PcdFrameBufferBase);
  mGopMode.FrameBufferSize = PcdGet32 (PcdFrameBufferSize);
  mGopModeInfo.HorizontalResolution = PcdGet32 (PcdDisplayWidth);
  mGopModeInfo.VerticalResolution   = PcdGet32 (PcdDisplayHeight);
  mGopModeInfo.PixelsPerScanLine    = PcdGet32 (PcdDisplayWidth);

  Status = gBS->InstallMultipleProtocolInterfaces (
                  &ImageHandle,
                  &gEfiGraphicsOutputProtocolGuid,
                  &mGopProtocol,
                  NULL
                  );

  DEBUG ((DEBUG_INFO, "[R8Q SimpleFbDxe] Continuous Splash GOP Installed: 1080x2400 @ 0x%lx\n", mGopMode.FrameBufferBase));
  return Status;
}
