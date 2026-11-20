/** @file
  StorageProtection.h
  Project R8Q Centralized Block I/O Protection Protocol.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

  Enforces strict permanent read-only policy on all internal UFS LUNs.
  Intercepts Block I/O write requests and guarantees zero modifications
  to internal storage.

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#ifndef R8Q_STORAGE_PROTECTION_H_
#define R8Q_STORAGE_PROTECTION_H_

#include <Uefi.h>
#include <Protocol/BlockIo.h>

#define R8Q_STORAGE_PROTECTION_PROTOCOL_GUID \
  { 0x6e28f810, 0x1834, 0x4f32, { 0x9b, 0xa1, 0x7a, 0x92, 0x14, 0x82, 0x51, 0x40 } }

typedef struct _R8Q_STORAGE_PROTECTION_PROTOCOL R8Q_STORAGE_PROTECTION_PROTOCOL;

typedef
BOOLEAN
(EFIAPI *R8Q_IS_HANDLE_PROTECTED)(
  IN  R8Q_STORAGE_PROTECTION_PROTOCOL *This,
  IN  EFI_HANDLE                      Handle,
  OUT UINT32                          *LunNumber OPTIONAL
  );

typedef
EFI_STATUS
(EFIAPI *R8Q_GET_PROTECTION_STATISTICS)(
  IN  R8Q_STORAGE_PROTECTION_PROTOCOL *This,
  OUT UINT32                          *TotalProtectedLuns,
  OUT UINT64                          *BlockedWriteAttempts,
  OUT UINT32                          *AuthorizedTestMediaCount
  );

typedef
EFI_STATUS
(EFIAPI *R8Q_AUTHORIZE_TEST_MEDIA)(
  IN  R8Q_STORAGE_PROTECTION_PROTOCOL *This,
  IN  EFI_HANDLE                      Handle,
  IN  CONST EFI_GUID                  *AuthToken
  );

struct _R8Q_STORAGE_PROTECTION_PROTOCOL {
  UINT32                        Revision;
  R8Q_IS_HANDLE_PROTECTED       IsHandleProtected;
  R8Q_GET_PROTECTION_STATISTICS GetProtectionStatistics;
  R8Q_AUTHORIZE_TEST_MEDIA      AuthorizeTestMedia;
};

extern EFI_GUID gR8QStorageProtectionProtocolGuid;
extern EFI_GUID gR8QAuthorizedTestMediaGuid;

#endif // R8Q_STORAGE_PROTECTION_H_
