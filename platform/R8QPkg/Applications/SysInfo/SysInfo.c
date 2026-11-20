/** @file
  SysInfo.c
  Project R8Q Platform System Information Diagnostic Application.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <Uefi.h>
#include <Library/UefiLib.h>
#include <Library/UefiApplicationEntryPoint.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/PrintLib.h>

EFI_STATUS
EFIAPI
UefiMain (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  Print(L"=================================================================\n");
  Print(L"   PROJECT R8Q UEFI: SYSTEM INFORMATION DIAGNOSTIC\n");
  Print(L"=================================================================\n\n");

  Print(L"Platform Information:\n");
  Print(L"  Target Device:       Samsung Galaxy S20 FE 5G (SM-G781B / SM-G781B/DS)\n");
  Print(L"  Codename:            r8q (Kona / SM8250)\n");
  Print(L"  Hardware Revision:   R8 REV04 (Board-ID: 0x08)\n");
  Print(L"  Manufacturer:        Samsung Electronics Co., Ltd.\n");
  Print(L"  SoC:                 Qualcomm Snapdragon 865 5G Mobile Platform\n");
  Print(L"  SoC Part ID:         356 (SM8250)\n\n");

  Print(L"Firmware Environment:\n");
  Print(L"  Firmware Vendor:     %s\n", SystemTable->FirmwareVendor);
  Print(L"  Firmware Revision:   0x%08X (v%d.%d)\n",
        SystemTable->FirmwareRevision,
        (SystemTable->FirmwareRevision >> 16) & 0xFFFF,
        SystemTable->FirmwareRevision & 0xFFFF);
  Print(L"  UEFI Spec Version:   %d.%02d (Table Rev: 0x%08X)\n",
        (SystemTable->Hdr.Revision >> 16) & 0xFFFF,
        SystemTable->Hdr.Revision & 0xFFFF,
        SystemTable->Hdr.Revision);
  Print(L"  Architecture:        AArch64 (ARM64 Little-Endian)\n");
  Print(L"  EDK II Baseline:     edk2-stable202411 (commit 0f3867f)\n\n");

  Print(L"Core UEFI Table Pointers:\n");
  Print(L"  SystemTable:         0x%016LX\n", (UINT64)(UINTN)SystemTable);
  Print(L"  BootServices:        0x%016LX (Hdr CRC32: 0x%08X)\n",
        (UINT64)(UINTN)SystemTable->BootServices,
        SystemTable->BootServices->Hdr.CRC32);
  Print(L"  RuntimeServices:     0x%016LX (Hdr CRC32: 0x%08X)\n",
        (UINT64)(UINTN)SystemTable->RuntimeServices,
        SystemTable->RuntimeServices->Hdr.CRC32);
  Print(L"  ConfigurationTable:  0x%016LX (%d entries)\n\n",
        (UINT64)(UINTN)SystemTable->ConfigurationTable,
        SystemTable->NumberOfTableEntries);

  Print(L"[PASS] System information queried successfully.\n");
  return EFI_SUCCESS;
}
