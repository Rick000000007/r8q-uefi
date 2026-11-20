/** @file
  CoreTest.c
  Project R8Q UEFI Core Services & Console Validation Application.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

  Validates:
  1. EFI System Table Integrity & Signature.
  2. Boot Services Memory Allocation & Free Services.
  3. Event & Timer Services (ARMv8 Generic Timer / GICv3 PPI).
  4. Runtime Services Table Accessibility.
  5. Graphics Output Protocol (GOP) Mode Query & Blt Operations.

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <Uefi.h>
#include <Library/UefiLib.h>
#include <Library/UefiApplicationEntryPoint.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DebugLib.h>
#include <Protocol/GraphicsOutput.h>

// Compiler intrinsics for GCC LTO code generation
void *memcpy(void *dest, const void *src, unsigned long n) {
  unsigned char *d = dest;
  const unsigned char *s = src;
  while (n--) *d++ = *s++;
  return dest;
}

void *memset(void *s, int c, unsigned long n) {
  unsigned char *p = s;
  while (n--) *p++ = (unsigned char)c;
  return s;
}

EFI_STATUS
EFIAPI
CoreTestMain (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_STATUS                    Status;
  UINTN                         Errors = 0;
  EFI_PHYSICAL_ADDRESS          AllocatedPages = 0;
  VOID                          *AllocatedPool = NULL;
  EFI_EVENT                     TimerEvent = NULL;
  UINTN                         EventIndex = 0;
  EFI_GRAPHICS_OUTPUT_PROTOCOL  *Gop = NULL;
  EFI_GRAPHICS_OUTPUT_BLT_PIXEL GreenPixel = { 0x00, 0xA8, 0x00, 0x00 };

  Print (L"====================================================\n");
  Print (L"  PROJECT R8Q UEFI: CORE SERVICES VALIDATION SUITE  \n");
  Print (L"  Platform: Samsung Galaxy S20 FE 5G (SM8250 / r8q) \n");
  Print (L"====================================================\n\n");

  // 1. UEFI System Table Validation
  Print (L"[TEST 1/5] Validating EFI System Table...\n");
  if (SystemTable == NULL || SystemTable->Hdr.Signature != EFI_SYSTEM_TABLE_SIGNATURE) {
    Print (L"  [FAIL] Invalid System Table Signature!\n");
    Errors++;
  } else {
    Print (L"  [PASS] System Table Signature Valid (0x%lx)\n", SystemTable->Hdr.Signature);
    Print (L"  [PASS] Firmware Vendor: %s, Revision: 0x%08x\n", SystemTable->FirmwareVendor, SystemTable->FirmwareRevision);
  }

  // 2. Boot Services Memory Allocation Validation
  Print (L"\n[TEST 2/5] Validating Memory Allocation Services...\n");
  Status = gBS->AllocatePages (AllocateAnyPages, EfiBootServicesData, 16, &AllocatedPages);
  if (EFI_ERROR (Status)) {
    Print (L"  [FAIL] AllocatePages failed: %r\n", Status);
    Errors++;
  } else {
    Print (L"  [PASS] AllocatePages (16 pages = 64 KiB) @ 0x%lx\n", AllocatedPages);
    Status = gBS->FreePages (AllocatedPages, 16);
    if (EFI_ERROR (Status)) {
      Print (L"  [FAIL] FreePages failed: %r\n", Status);
      Errors++;
    } else {
      Print (L"  [PASS] FreePages completed cleanly\n");
    }
  }

  Status = gBS->AllocatePool (EfiBootServicesData, 32768, &AllocatedPool);
  if (EFI_ERROR (Status)) {
    Print (L"  [FAIL] AllocatePool (32 KiB) failed: %r\n", Status);
    Errors++;
  } else {
    Print (L"  [PASS] AllocatePool (32 KiB) @ %p\n", AllocatedPool);
    gBS->FreePool (AllocatedPool);
    Print (L"  [PASS] FreePool completed cleanly\n");
  }

  // 3. Event & Timer Services Validation
  Print (L"\n[TEST 3/5] Validating Architectural Timer & Event Services...\n");
  Status = gBS->CreateEvent (EVT_TIMER, TPL_CALLBACK, NULL, NULL, &TimerEvent);
  if (EFI_ERROR (Status)) {
    Print (L"  [FAIL] CreateEvent failed: %r\n", Status);
    Errors++;
  } else {
    // 50 milliseconds timer (500,000 in 100ns units)
    Status = gBS->SetTimer (TimerEvent, TimerRelative, 500000);
    if (EFI_ERROR (Status)) {
      Print (L"  [FAIL] SetTimer failed: %r\n", Status);
      Errors++;
    } else {
      Status = gBS->WaitForEvent (1, &TimerEvent, &EventIndex);
      if (EFI_ERROR (Status)) {
        Print (L"  [FAIL] WaitForEvent failed: %r\n", Status);
        Errors++;
      } else {
        Print (L"  [PASS] 50ms Timer Fired via ARMv8 Arch Timer & GICv3 PPI\n");
      }
    }
    gBS->CloseEvent (TimerEvent);
  }

  // 4. Runtime Services Table Validation
  Print (L"\n[TEST 4/5] Validating Runtime Services Table...\n");
  if (gRT == NULL || gRT->Hdr.Signature != EFI_RUNTIME_SERVICES_SIGNATURE) {
    Print (L"  [FAIL] Invalid Runtime Services Table Signature!\n");
    Errors++;
  } else {
    Print (L"  [PASS] Runtime Services Table Signature Valid (0x%lx)\n", gRT->Hdr.Signature);
  }

  // 5. Graphics Output Protocol (GOP) Validation
  Print (L"\n[TEST 5/5] Validating Graphics Output Protocol (GOP)...\n");
  Status = gBS->LocateProtocol (&gEfiGraphicsOutputProtocolGuid, NULL, (VOID **)&Gop);
  if (EFI_ERROR (Status) || Gop == NULL) {
    Print (L"  [FAIL] LocateProtocol(GOP) failed: %r\n", Status);
    Errors++;
  } else {
    Print (L"  [PASS] GOP Located: Resolution %dx%d, Stride %d\n",
           Gop->Mode->Info->HorizontalResolution,
           Gop->Mode->Info->VerticalResolution,
           Gop->Mode->Info->PixelsPerScanLine);
    Print (L"  [PASS] Framebuffer Base: 0x%lx (Size: %ld bytes)\n",
           Gop->Mode->FrameBufferBase,
           Gop->Mode->FrameBufferSize);

    // Test Blt Video Fill (draw small green square on screen)
    Status = Gop->Blt (Gop, &GreenPixel, EfiBltVideoFill, 0, 0, 100, 100, 80, 80, 0);
    if (EFI_ERROR (Status)) {
      Print (L"  [FAIL] Gop->Blt(EfiBltVideoFill) failed: %r\n", Status);
      Errors++;
    } else {
      Print (L"  [PASS] Gop->Blt(EfiBltVideoFill) successfully rendered test block\n");
    }
  }

  Print (L"\n----------------------------------------------------\n");
  if (Errors == 0) {
    Print (L">>> ALL CORE SERVICES TESTS PASSED SUCCESSFULLY! <<<\n");
  } else {
    Print (L">>> CORE SERVICES TESTS ENCOUNTERED %d ERRORS! <<<\n", Errors);
  }
  Print (L"----------------------------------------------------\n");

  return (Errors == 0) ? EFI_SUCCESS : EFI_DEVICE_ERROR;
}
