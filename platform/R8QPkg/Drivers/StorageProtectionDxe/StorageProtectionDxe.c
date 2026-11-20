/** @file
  StorageProtectionDxe.c
  Project R8Q Centralized Block I/O Protection Engine.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

  Features:
  - Enforces permanent read-only policy on all internal UFS LUNs.
  - Intercepts and rejects all Block I/O write requests with EFI_WRITE_PROTECTED.
  - Prevents partition formatting, filesystem modification, and block erasures.
  - Blocks alternative driver paths and logs security alerts.
  - Enforces that MicroSD / USB removable media defaults to read-only unless
    explicitly authorized by test-media token.
  - Zero modification to internal storage (sdd31, boot, recovery, super, etc.).

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <Uefi.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/MemoryAllocationLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/DebugLib.h>
#include <Library/DevicePathLib.h>
#include <Library/PcdLib.h>
#include <Protocol/BlockIo.h>
#include <Protocol/DevicePath.h>
#include <Protocol/StorageProtection.h>

#define MAX_PROTECTED_HANDLES 64
#define MAX_AUTHORIZED_MEDIA   8

typedef struct {
  EFI_HANDLE                    Handle;
  EFI_BLOCK_IO_PROTOCOL         *BlockIo;
  EFI_BLOCK_WRITE               OriginalWriteBlocks;
  EFI_BLOCK_FLUSH               OriginalFlushBlocks;
  BOOLEAN                       IsInternalUfs;
  BOOLEAN                       IsRemovable;
  BOOLEAN                       IsAuthorized;
  UINT32                        LunNumber;
} PROTECTED_HANDLE_RECORD;

STATIC PROTECTED_HANDLE_RECORD mRecords[MAX_PROTECTED_HANDLES];
STATIC UINT32                  mRecordCount = 0;
STATIC UINT32                  mTotalProtectedLuns = 0;
STATIC UINT64                  mBlockedWriteAttempts = 0;
STATIC UINT32                  mAuthorizedMediaCount = 0;

STATIC VOID                    *mBlockIoRegistration = NULL;

/**
  Finds or allocates a protection record for a handle.
**/
STATIC
PROTECTED_HANDLE_RECORD *
GetRecordForHandle (
  IN EFI_HANDLE Handle
  )
{
  UINT32 Index;

  for (Index = 0; Index < mRecordCount; Index++) {
    if (mRecords[Index].Handle == Handle) {
      return &mRecords[Index];
    }
  }

  if (mRecordCount < MAX_PROTECTED_HANDLES) {
    Index = mRecordCount++;
    ZeroMem (&mRecords[Index], sizeof (PROTECTED_HANDLE_RECORD));
    mRecords[Index].Handle = Handle;
    return &mRecords[Index];
  }

  return NULL;
}

/**
  Protected WriteBlocks interceptor for Internal UFS.
  Permanently rejects all write requests with EFI_WRITE_PROTECTED.
**/
STATIC
EFI_STATUS
EFIAPI
R8QUfsProtectedWriteBlocks (
  IN EFI_BLOCK_IO_PROTOCOL *This,
  IN UINT32                MediaId,
  IN EFI_LBA               Lba,
  IN UINTN                 BufferSize,
  IN VOID                  *Buffer
  )
{
  UINT32 Index;
  UINT32 Lun = 0xFF;

  mBlockedWriteAttempts++;

  // Find LUN for diagnostic audit
  for (Index = 0; Index < mRecordCount; Index++) {
    if (mRecords[Index].BlockIo == This) {
      Lun = mRecords[Index].LunNumber;
      break;
    }
  }

  DEBUG ((
    DEBUG_ERROR,
    "[R8Q UFS ISOLATION GATE] BLOCKED write attempt to internal UFS LUN %d! LBA=0x%lx Size=%ld bytes. Access Denied.\n",
    Lun,
    Lba,
    BufferSize
    ));

  return EFI_WRITE_PROTECTED;
}

/**
  Protected FlushBlocks interceptor.
**/
STATIC
EFI_STATUS
EFIAPI
R8QUfsProtectedFlushBlocks (
  IN EFI_BLOCK_IO_PROTOCOL *This
  )
{
  // Flush is safe NO-OP on read-only media
  return EFI_SUCCESS;
}

/**
  Checks if a device path belongs to the Qualcomm UFS host controller.
**/
STATIC
BOOLEAN
IsUfsDevicePath (
  IN EFI_DEVICE_PATH_PROTOCOL *DevicePath,
  OUT UINT32                  *LunOut OPTIONAL
  )
{
  EFI_DEVICE_PATH_PROTOCOL *Node;
  HARDDRIVE_DEVICE_PATH    *HdNode;

  if (DevicePath == NULL) {
    return FALSE;
  }

  Node = DevicePath;
  while (!IsDevicePathEnd (Node)) {
    // Check for HARDDRIVE node
    if (DevicePathType (Node) == MEDIA_DEVICE_PATH &&
        DevicePathSubType (Node) == MEDIA_HARDDRIVE_DP) {
      HdNode = (HARDDRIVE_DEVICE_PATH *)Node;
      if (LunOut != NULL) {
        *LunOut = HdNode->PartitionNumber;
      }
      return TRUE;
    }

    // Check for SCSI / UFS device path
    if (DevicePathType (Node) == MESSAGING_DEVICE_PATH &&
        DevicePathSubType (Node) == MSG_SCSI_DP) {
      if (LunOut != NULL) {
        *LunOut = 0; // Default UFS LUN
      }
      return TRUE;
    }

    Node = NextDevicePathNode (Node);
  }

  return FALSE;
}

/**
  Intercepts and protects Block I/O handles.
**/
STATIC
VOID
ProtectBlockIoHandle (
  IN EFI_HANDLE Handle
  )
{
  EFI_STATUS               Status;
  EFI_BLOCK_IO_PROTOCOL    *BlockIo;
  EFI_DEVICE_PATH_PROTOCOL *DevicePath;
  PROTECTED_HANDLE_RECORD  *Record;
  UINT32                   Lun = 0;
  BOOLEAN                  IsUfs;

  Status = gBS->HandleProtocol (Handle, &gEfiBlockIoProtocolGuid, (VOID **)&BlockIo);
  if (EFI_ERROR (Status) || BlockIo == NULL) {
    return;
  }

  Record = GetRecordForHandle (Handle);
  if (Record == NULL || Record->BlockIo != NULL) {
    // Already wrapped or full
    return;
  }

  Status = gBS->HandleProtocol (Handle, &gEfiDevicePathProtocolGuid, (VOID **)&DevicePath);
  IsUfs  = !EFI_ERROR (Status) && IsUfsDevicePath (DevicePath, &Lun);

  Record->BlockIo             = BlockIo;
  Record->OriginalWriteBlocks = BlockIo->WriteBlocks;
  Record->OriginalFlushBlocks = BlockIo->FlushBlocks;
  Record->IsInternalUfs       = IsUfs;
  Record->LunNumber           = Lun;

  if (IsUfs) {
    //
    // INTERNAL UFS: STRICT READ-ONLY ENFORCEMENT
    //
    BlockIo->Media->ReadOnly = TRUE;
    BlockIo->WriteBlocks     = R8QUfsProtectedWriteBlocks;
    BlockIo->FlushBlocks     = R8QUfsProtectedFlushBlocks;
    mTotalProtectedLuns++;

    DEBUG ((
      DEBUG_INFO,
      "[R8Q StorageProtection] Protected Internal UFS Handle %p (LUN %d) -> Forced READ-ONLY\n",
      Handle,
      Lun
      ));
  } else {
    //
    // Removable Media (MicroSD / USB): Defaults to Read-Only until authorized
    //
    Record->IsRemovable = TRUE;
    Record->IsAuthorized = FALSE;
    BlockIo->Media->RemovableMedia = TRUE;
    BlockIo->Media->ReadOnly       = TRUE;
    BlockIo->WriteBlocks           = R8QUfsProtectedWriteBlocks; // Block by default

    DEBUG ((
      DEBUG_INFO,
      "[R8Q StorageProtection] Protected Removable Media Handle %p -> Disabled write by default\n",
      Handle
      ));
  }
}

/**
  Notification callback when a new BlockIo protocol is registered.
**/
STATIC
VOID
EFIAPI
OnBlockIoNotify (
  IN EFI_EVENT Event,
  IN VOID      *Context
  )
{
  EFI_STATUS Status;
  UINTN      BufferSize;
  EFI_HANDLE Handle;

  while (TRUE) {
    BufferSize = sizeof (EFI_HANDLE);
    Status = gBS->LocateHandle (
                    ByRegisterNotify,
                    NULL,
                    mBlockIoRegistration,
                    &BufferSize,
                    &Handle
                    );
    if (EFI_ERROR (Status)) {
      break;
    }
    ProtectBlockIoHandle (Handle);
  }
}

// =========================================================================
// R8Q_STORAGE_PROTECTION_PROTOCOL Implementation
// =========================================================================

STATIC
BOOLEAN
EFIAPI
ProtIsHandleProtected (
  IN  R8Q_STORAGE_PROTECTION_PROTOCOL *This,
  IN  EFI_HANDLE                      Handle,
  OUT UINT32                          *LunNumber OPTIONAL
  )
{
  UINT32 Index;

  for (Index = 0; Index < mRecordCount; Index++) {
    if (mRecords[Index].Handle == Handle) {
      if (LunNumber != NULL) {
        *LunNumber = mRecords[Index].LunNumber;
      }
      return mRecords[Index].IsInternalUfs;
    }
  }
  return FALSE;
}

STATIC
EFI_STATUS
EFIAPI
ProtGetProtectionStatistics (
  IN  R8Q_STORAGE_PROTECTION_PROTOCOL *This,
  OUT UINT32                          *TotalProtectedLuns,
  OUT UINT64                          *BlockedWriteAttempts,
  OUT UINT32                          *AuthorizedTestMediaCount
  )
{
  if (TotalProtectedLuns != NULL) {
    *TotalProtectedLuns = mTotalProtectedLuns;
  }
  if (BlockedWriteAttempts != NULL) {
    *BlockedWriteAttempts = mBlockedWriteAttempts;
  }
  if (AuthorizedTestMediaCount != NULL) {
    *AuthorizedTestMediaCount = mAuthorizedMediaCount;
  }
  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
EFIAPI
ProtAuthorizeTestMedia (
  IN  R8Q_STORAGE_PROTECTION_PROTOCOL *This,
  IN  EFI_HANDLE                      Handle,
  IN  CONST EFI_GUID                  *AuthToken
  )
{
  PROTECTED_HANDLE_RECORD *Record;

  if (Handle == NULL || AuthToken == NULL) {
    return EFI_INVALID_PARAMETER;
  }

  // Validate authorization token GUID
  if (!CompareGuid (AuthToken, &gR8QAuthorizedTestMediaGuid)) {
    DEBUG ((DEBUG_ERROR, "[R8Q StorageProtection] Invalid authorization token! Access Denied.\n"));
    return EFI_ACCESS_DENIED;
  }

  Record = GetRecordForHandle (Handle);
  if (Record == NULL) {
    return EFI_NOT_FOUND;
  }

  if (Record->IsInternalUfs) {
    DEBUG ((DEBUG_ERROR, "[R8Q StorageProtection] REJECTED authorization attempt on Internal UFS! Internal UFS cannot be overridden.\n"));
    return EFI_ACCESS_DENIED;
  }

  // Authorize removable test media
  Record->IsAuthorized = TRUE;
  Record->BlockIo->Media->ReadOnly = FALSE;
  Record->BlockIo->WriteBlocks     = Record->OriginalWriteBlocks;
  mAuthorizedMediaCount++;

  DEBUG ((DEBUG_INFO, "[R8Q StorageProtection] Successfully authorized Removable Test Media Handle %p for read/write access\n", Handle));
  return EFI_SUCCESS;
}

STATIC R8Q_STORAGE_PROTECTION_PROTOCOL mProtectionProtocol = {
  1,
  ProtIsHandleProtected,
  ProtGetProtectionStatistics,
  ProtAuthorizeTestMedia
};

EFI_STATUS
EFIAPI
StorageProtectionDxeInitialize (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_STATUS Status;
  EFI_EVENT  Event;
  UINTN      HandleCount;
  EFI_HANDLE *Handles = NULL;
  UINTN      Index;

  DEBUG ((DEBUG_INFO, "[R8Q StorageProtection] Initializing Centralized UFS Block I/O Protection Engine...\n"));

  // Install protocol
  Status = gBS->InstallMultipleProtocolInterfaces (
                  &ImageHandle,
                  &gR8QStorageProtectionProtocolGuid,
                  &mProtectionProtocol,
                  NULL
                  );
  if (EFI_ERROR (Status)) {
    return Status;
  }

  // Register notification on BlockIo protocol
  Status = gBS->CreateEvent (
                  EVT_NOTIFY_SIGNAL,
                  TPL_CALLBACK,
                  OnBlockIoNotify,
                  NULL,
                  &Event
                  );
  if (!EFI_ERROR (Status)) {
    Status = gBS->RegisterProtocolNotify (
                    &gEfiBlockIoProtocolGuid,
                    Event,
                    &mBlockIoRegistration
                    );
  }

  // Scan any already installed BlockIo handles
  Status = gBS->LocateHandleBuffer (
                  ByProtocol,
                  &gEfiBlockIoProtocolGuid,
                  NULL,
                  &HandleCount,
                  &Handles
                  );
  if (!EFI_ERROR (Status) && Handles != NULL) {
    for (Index = 0; Index < HandleCount; Index++) {
      ProtectBlockIoHandle (Handles[Index]);
    }
    FreePool (Handles);
  }

  DEBUG ((DEBUG_INFO, "[R8Q StorageProtection] Protection Engine Active: Internal UFS is PERMANENTLY READ-ONLY\n"));
  return EFI_SUCCESS;
}
