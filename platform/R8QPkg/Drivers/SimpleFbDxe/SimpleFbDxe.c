/** @file
  SimpleFbDxe.c
  Project R8Q Continuous Splash Framebuffer Graphics Output & Text Console Driver.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

  Features:
  - 1080x2400 @ 32bpp BGRX display scanout on Samsung AMOLED panel (0x9C000000).
  - Complete GOP Blt implementation: Fill, VideoToBuffer, BufferToVideo, VideoToVideo.
  - Dual-Mode Text Console (EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL):
      Mode 0 (1x compatibility): 8x19 glyphs -> 135 columns x 126 rows.
      Mode 1 (2x readability):  16x38 glyphs ->  67 columns x  63 rows.
  - Complete cursor management, line wrapping, overlap-safe scrolling, and clearing.

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
#include <Protocol/SimpleTextOut.h>

#include "SimpleFbDxeFont.h"

//
// EFI Standard 16-color palette (BGRX 32-bit values)
//
STATIC CONST UINT32 mColorPalette[16] = {
  0x00000000, // 0: Black
  0x000000A8, // 1: Blue
  0x0000A800, // 2: Green
  0x0000A8A8, // 3: Cyan
  0x00A80000, // 4: Red
  0x00A800A8, // 5: Magenta
  0x00A85400, // 6: Brown
  0x00A8A8A8, // 7: Light Gray
  0x00545454, // 8: Dark Gray
  0x005454FE, // 9: Light Blue
  0x0054FE54, // 10: Light Green
  0x0054FEFE, // 11: Light Cyan
  0x00FE5454, // 12: Light Red
  0x00FE54FE, // 13: Light Magenta
  0x00FEFE54, // 14: Yellow
  0x00FFFFFF  // 15: White
};

//
// GOP Structures
//
STATIC EFI_GRAPHICS_OUTPUT_MODE_INFORMATION mGopModeInfo = {
  0,                                    // Version
  1080,                                 // HorizontalResolution
  2400,                                 // VerticalResolution
  PixelBlueGreenRedReserved8BitPerColor,// PixelFormat
  { 0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000 },
  1080                                  // PixelsPerScanLine
};

STATIC EFI_GRAPHICS_OUTPUT_PROTOCOL_MODE mGopMode = {
  1,                                    // MaxMode
  0,                                    // Mode
  &mGopModeInfo,                        // Info
  sizeof (EFI_GRAPHICS_OUTPUT_MODE_INFORMATION),
  0x9C000000ULL,                        // FrameBufferBase
  (1080 * 2400 * 4)                     // FrameBufferSize
};

//
// Text Console State
//
STATIC EFI_SIMPLE_TEXT_OUTPUT_MODE mTextMode = {
  2,                                    // MaxMode: 0 (1x), 1 (2x)
  0,                                    // Mode (default 1x compatibility)
  EFI_TEXT_ATTR (EFI_LIGHTGRAY, EFI_BLACK), // Attribute
  0,                                    // CursorColumn
  0,                                    // CursorRow
  TRUE                                  // CursorVisible
};

// Mode 0: 1x (8x19), Mode 1: 2x (16x38)
STATIC CONST UINT32 mTextColumns[2] = { 1080 / GLYPH_WIDTH_1X,  1080 / GLYPH_WIDTH_2X };  // 135, 67
STATIC CONST UINT32 mTextRows[2]    = { 2400 / GLYPH_HEIGHT_1X, 2400 / GLYPH_HEIGHT_2X }; // 126, 63

// Forward declarations
STATIC EFI_STATUS EFIAPI GopBlt (
  IN EFI_GRAPHICS_OUTPUT_PROTOCOL       *This,
  IN EFI_GRAPHICS_OUTPUT_BLT_PIXEL      *BltBuffer, OPTIONAL
  IN EFI_GRAPHICS_OUTPUT_BLT_OPERATION  BltOperation,
  IN UINTN                              SourceX,
  IN UINTN                              SourceY,
  IN UINTN                              DestinationX,
  IN UINTN                              DestinationY,
  IN UINTN                              Width,
  IN UINTN                              Height,
  IN UINTN                              Delta OPTIONAL
  );

// =========================================================================
// GOP Functions
// =========================================================================

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
      for (Y = 0; Y < Height; Y++) {
        UINT32 *Src = &Fb[(SourceY + Y) * Stride + SourceX];
        UINT32 *Dst = &Fb[(DestinationY + Y) * Stride + DestinationX];
        CopyMem (Dst, Src, Width * sizeof (UINT32));
      }
    } else {
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

// =========================================================================
// Text Console Implementation (EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL)
// =========================================================================

STATIC
VOID
RenderCharGlyph (
  IN CHAR16 Char,
  IN UINT32 Col,
  IN UINT32 Row,
  IN INT32  Mode,
  IN INT32  Attribute
  )
{
  CONST UINT8 *Glyph;
  UINT32      *Fb;
  UINT32      Stride;
  UINT32      FgColor;
  UINT32      BgColor;
  UINT32      DestX, DestY;
  UINTN       gx, gy;

  Glyph   = GetGlyph8x19 (Char);
  Fb      = (UINT32 *)(UINTN)mGopMode.FrameBufferBase;
  Stride  = mGopModeInfo.PixelsPerScanLine;
  FgColor = mColorPalette[Attribute & 0x0F];
  BgColor = mColorPalette[(Attribute >> 4) & 0x07];

  if (Mode == 0) {
    // 1x Mode: 8x19 pixels
    DestX = Col * GLYPH_WIDTH_1X;
    DestY = Row * GLYPH_HEIGHT_1X;

    for (gy = 0; gy < GLYPH_HEIGHT_1X; gy++) {
      UINT8 LineBits = Glyph[gy];
      UINT32 *RowPtr = &Fb[(DestY + gy) * Stride + DestX];
      for (gx = 0; gx < GLYPH_WIDTH_1X; gx++) {
        RowPtr[gx] = (LineBits & (0x80 >> gx)) ? FgColor : BgColor;
      }
    }
  } else {
    // 2x Mode: 16x38 pixels (2x2 pixel expansion per font bit)
    DestX = Col * GLYPH_WIDTH_2X;
    DestY = Row * GLYPH_HEIGHT_2X;

    for (gy = 0; gy < GLYPH_HEIGHT_1X; gy++) {
      UINT8 LineBits = Glyph[gy];
      UINT32 *RowPtr0 = &Fb[(DestY + gy * 2) * Stride + DestX];
      UINT32 *RowPtr1 = &Fb[(DestY + gy * 2 + 1) * Stride + DestX];
      for (gx = 0; gx < GLYPH_WIDTH_1X; gx++) {
        UINT32 PixelColor = (LineBits & (0x80 >> gx)) ? FgColor : BgColor;
        RowPtr0[gx * 2]     = PixelColor;
        RowPtr0[gx * 2 + 1] = PixelColor;
        RowPtr1[gx * 2]     = PixelColor;
        RowPtr1[gx * 2 + 1] = PixelColor;
      }
    }
  }
}

STATIC
VOID
ScrollConsoleUp (
  IN INT32 Mode,
  IN INT32 Attribute
  )
{
  UINTN LineHeight;
  EFI_GRAPHICS_OUTPUT_BLT_PIXEL BgPixel;

  LineHeight = (Mode == 0) ? GLYPH_HEIGHT_1X : GLYPH_HEIGHT_2X;
  BgPixel = *(EFI_GRAPHICS_OUTPUT_BLT_PIXEL *)&mColorPalette[(Attribute >> 4) & 0x07];

  // Shift video upward by one line
  GopBlt (
    &mGopProtocol,
    NULL,
    EfiBltVideoToVideo,
    0, LineHeight,
    0, 0,
    1080, 2400 - LineHeight,
    0
    );

  // Blank bottom line
  GopBlt (
    &mGopProtocol,
    &BgPixel,
    EfiBltVideoFill,
    0, 0,
    0, 2400 - LineHeight,
    1080, LineHeight,
    0
    );
}

STATIC
EFI_STATUS
EFIAPI
TextReset (
  IN EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
  IN BOOLEAN                         ExtendedVerification
  )
{
  return This->ClearScreen (This);
}

STATIC
EFI_STATUS
EFIAPI
TextOutputString (
  IN EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
  IN CHAR16                          *String
  )
{
  INT32  CurrentMode;
  UINT32 MaxCols;
  UINT32 MaxRows;
  CHAR16 Ch;

  if (This == NULL || String == NULL) {
    return EFI_INVALID_PARAMETER;
  }

  CurrentMode = mTextMode.Mode;
  MaxCols     = mTextColumns[CurrentMode];
  MaxRows     = mTextRows[CurrentMode];

  while (*String != L'\0') {
    Ch = *String++;

    if (Ch == L'\r') {
      mTextMode.CursorColumn = 0;
    } else if (Ch == L'\n') {
      mTextMode.CursorColumn = 0;
      mTextMode.CursorRow++;
      if ((UINT32)mTextMode.CursorRow >= MaxRows) {
        ScrollConsoleUp (CurrentMode, mTextMode.Attribute);
        mTextMode.CursorRow = MaxRows - 1;
      }
    } else if (Ch == L'\b') {
      if (mTextMode.CursorColumn > 0) {
        mTextMode.CursorColumn--;
        RenderCharGlyph (L' ', mTextMode.CursorColumn, mTextMode.CursorRow, CurrentMode, mTextMode.Attribute);
      }
    } else {
      RenderCharGlyph (Ch, mTextMode.CursorColumn, mTextMode.CursorRow, CurrentMode, mTextMode.Attribute);
      mTextMode.CursorColumn++;
      if ((UINT32)mTextMode.CursorColumn >= MaxCols) {
        mTextMode.CursorColumn = 0;
        mTextMode.CursorRow++;
        if ((UINT32)mTextMode.CursorRow >= MaxRows) {
          ScrollConsoleUp (CurrentMode, mTextMode.Attribute);
          mTextMode.CursorRow = MaxRows - 1;
        }
      }
    }
  }

  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
TextTestString (
  IN EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
  IN CHAR16                          *String
  )
{
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
TextQueryMode (
  IN  EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
  IN  UINTN                           ModeNumber,
  OUT UINTN                           *Columns,
  OUT UINTN                           *Rows
  )
{
  if (Columns == NULL || Rows == NULL) {
    return EFI_INVALID_PARAMETER;
  }

  if (ModeNumber >= 2) {
    return EFI_UNSUPPORTED;
  }

  *Columns = mTextColumns[ModeNumber];
  *Rows    = mTextRows[ModeNumber];
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
TextSetMode (
  IN EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
  IN UINTN                           ModeNumber
  )
{
  if (ModeNumber >= 2) {
    return EFI_UNSUPPORTED;
  }

  mTextMode.Mode = (INT32)ModeNumber;
  return This->ClearScreen (This);
}

STATIC
EFI_STATUS
EFIAPI
TextSetAttribute (
  IN EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
  IN UINTN                           Attribute
  )
{
  mTextMode.Attribute = (INT32)Attribute;
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
TextClearScreen (
  IN EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This
  )
{
  EFI_GRAPHICS_OUTPUT_BLT_PIXEL BgPixel;

  BgPixel = *(EFI_GRAPHICS_OUTPUT_BLT_PIXEL *)&mColorPalette[(mTextMode.Attribute >> 4) & 0x07];

  GopBlt (
    &mGopProtocol,
    &BgPixel,
    EfiBltVideoFill,
    0, 0,
    0, 0,
    1080, 2400,
    0
    );

  mTextMode.CursorColumn = 0;
  mTextMode.CursorRow    = 0;
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
TextSetCursorPosition (
  IN EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
  IN UINTN                           Column,
  IN UINTN                           Row
  )
{
  INT32 CurrentMode = mTextMode.Mode;

  if (Column >= mTextColumns[CurrentMode] || Row >= mTextRows[CurrentMode]) {
    return EFI_INVALID_PARAMETER;
  }

  mTextMode.CursorColumn = (INT32)Column;
  mTextMode.CursorRow    = (INT32)Row;
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
TextEnableCursor (
  IN EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
  IN BOOLEAN                         Visible
  )
{
  mTextMode.CursorVisible = Visible;
  return EFI_SUCCESS;
}

STATIC EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL mTextOutProtocol = {
  TextReset,
  TextOutputString,
  TextTestString,
  TextQueryMode,
  TextSetMode,
  TextSetAttribute,
  TextClearScreen,
  TextSetCursorPosition,
  TextEnableCursor,
  &mTextMode
};

// =========================================================================
// Driver Entry Point
// =========================================================================

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

  // Install both GOP and TextOut protocols on ImageHandle
  Status = gBS->InstallMultipleProtocolInterfaces (
                  &ImageHandle,
                  &gEfiGraphicsOutputProtocolGuid,
                  &mGopProtocol,
                  &gEfiSimpleTextOutProtocolGuid,
                  &mTextOutProtocol,
                  NULL
                  );

  if (!EFI_ERROR (Status)) {
    // Hook standard console out
    SystemTable->ConOut = &mTextOutProtocol;
    SystemTable->ConsoleOutHandle = ImageHandle;
  }

  DEBUG ((DEBUG_INFO, "[R8Q SimpleFbDxe] Continuous Splash GOP + Dual-Mode Console Installed: 1080x2400 @ 0x%lx\n", mGopMode.FrameBufferBase));
  return Status;
}
