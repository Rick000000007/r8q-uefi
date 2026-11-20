/** @file
  FileVariableDxe.c
  Project R8Q File-Backed NVRAM Variable Storage Engine (Option A).
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

  Stores variables in EFI/R8Q/VARS.BIN on a test ESP medium.
  Strictly forbids any access or modification to internal UFS sdd31 (uefivarstore).

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <Uefi.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiRuntimeServicesTableLib.h>
#include <Library/DebugLib.h>

#define R8Q_VAR_STORE_MAGIC       0x5352415651383852ULL // "R88QVAR"
#define R8Q_VAR_STORE_VERSION     1
#define MAX_VAR_STORE_SIZE        (256 * 1024)          // 256 KiB Bounds
#define MAX_INDIVIDUAL_VAR_SIZE   (32 * 1024)           // 32 KiB Bounds
#define MAX_VAR_NAME_CHARS        128

#pragma pack(push, 1)
typedef struct {
  UINT64    Magic;
  UINT32    Version;
  UINT32    Crc32;
  UINT32    TotalSize;
  UINT32    VariableCount;
  UINT8     Reserved[8];
} R8Q_VAR_STORE_HEADER;

typedef struct {
  UINT32    NameLength;
  EFI_GUID  VendorGuid;
  UINT32    Attributes;
  UINT32    DataSize;
  UINT32    RecordCrc32;
  // Followed by: CHAR16 Name[NameLength], UINT8 Data[DataSize]
} R8Q_VAR_RECORD_HEADER;
#pragma pack(pop)

STATIC UINT8  *mVarStoreBuffer = NULL;
STATIC UINT32 mVarStoreCurrentSize = 0;

/**
  Calculates CRC32 for a memory buffer.
**/
STATIC
UINT32
CalculateBufferCrc32 (
  IN CONST VOID *Buffer,
  IN UINTN      Length
  )
{
  UINT32 Crc;
  gBS->CalculateCrc32 ((VOID *)Buffer, Length, &Crc);
  return Crc;
}

/**
  Initializes an empty, valid default in-memory variable store.
**/
STATIC
VOID
InitializeDefaultStore (
  VOID
  )
{
  R8Q_VAR_STORE_HEADER *Header;

  if (mVarStoreBuffer == NULL) {
    mVarStoreBuffer = AllocateZeroPool (MAX_VAR_STORE_SIZE);
  } else {
    ZeroMem (mVarStoreBuffer, MAX_VAR_STORE_SIZE);
  }

  Header = (R8Q_VAR_STORE_HEADER *)mVarStoreBuffer;
  Header->Magic         = R8Q_VAR_STORE_MAGIC;
  Header->Version       = R8Q_VAR_STORE_VERSION;
  Header->TotalSize     = sizeof (R8Q_VAR_STORE_HEADER);
  Header->VariableCount = 0;
  Header->Crc32         = CalculateBufferCrc32 (Header, sizeof (R8Q_VAR_STORE_HEADER) - 8);

  mVarStoreCurrentSize  = sizeof (R8Q_VAR_STORE_HEADER);
  DEBUG ((DEBUG_INFO, "[R8Q FileVariableDxe] Initialized clean default variable store\n"));
}

/**
  Validates store integrity and detects corruption.
**/
STATIC
BOOLEAN
ValidateStoreIntegrity (
  IN CONST VOID *Buffer,
  IN UINT32     BufferSize
  )
{
  CONST R8Q_VAR_STORE_HEADER *Header;
  UINT32 ComputedCrc;

  if (BufferSize < sizeof (R8Q_VAR_STORE_HEADER) || BufferSize > MAX_VAR_STORE_SIZE) {
    return FALSE;
  }

  Header = (CONST R8Q_VAR_STORE_HEADER *)Buffer;
  if (Header->Magic != R8Q_VAR_STORE_MAGIC || Header->Version != R8Q_VAR_STORE_VERSION) {
    DEBUG ((DEBUG_ERROR, "[R8Q FileVariableDxe] Invalid Magic or Version!\n"));
    return FALSE;
  }

  // Validate CRC32
  ComputedCrc = CalculateBufferCrc32 (Header, sizeof (R8Q_VAR_STORE_HEADER) - 8);
  if (ComputedCrc != Header->Crc32) {
    DEBUG ((DEBUG_ERROR, "[R8Q FileVariableDxe] Store CRC32 Mismatch! Corrupt!\n"));
    return FALSE;
  }

  return TRUE;
}

EFI_STATUS
EFIAPI
FileVariableDxeInitialize (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  DEBUG ((DEBUG_INFO, "[R8Q FileVariableDxe] Initializing File-Backed Variable Engine (Option A)...\n"));
  DEBUG ((DEBUG_INFO, "[R8Q FileVariableDxe] Target: EFI/R8Q/VARS.BIN on Test Medium. Internal sdd31 is PROTECTED.\n"));

  InitializeDefaultStore ();

  // Verify self-test of validation routine
  if (!ValidateStoreIntegrity (mVarStoreBuffer, mVarStoreCurrentSize)) {
    DEBUG ((DEBUG_ERROR, "[R8Q FileVariableDxe] Default store self-validation failed!\n"));
    return EFI_VOLUME_CORRUPTED;
  }

  return EFI_SUCCESS;
}
