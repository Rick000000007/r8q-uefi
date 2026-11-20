/** @file
  SimpleFbDxe.c
  Project R8Q Continuous Splash Framebuffer Graphics Output Protocol Driver.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <Uefi.h>
#include <Library/BaseLib.h>
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
  // Simplified early Blt implementation
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

  return Status;
}
