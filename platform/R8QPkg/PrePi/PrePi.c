/** @file
  PrePi.c
  Project R8Q UEFI Early Platform Entry Implementation.
  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)

  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
**/

#include <PiPei.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DebugLib.h>
#include <Library/IoLib.h>
#include <Library/ArmLib.h>
#include <libfdt.h>

#define FB_BASE_PHYS      0x9C000000ULL
#define FB_WIDTH          1080
#define FB_HEIGHT         2400
#define FB_BPP            32
#define FB_STRIDE         (FB_WIDTH * (FB_BPP / 8))

#define FDT_MAX_SIZE      0x00200000ULL // 2 MiB maximum DTB size per Linux ARM64 boot protocol
#define LINUX_ARM64_MAGIC 0x644D5241 // 'ARM\x64'

#define FIRMWARE_BASE     0x9E400000ULL
#define FIRMWARE_SIZE     0x00400000ULL
#define STACK_TOP         0x9E890000ULL
#define STACK_LIMIT       0x9E880000ULL
#define TRUSTZONE_BASE    0x80B00000ULL
#define TRUSTZONE_END     0x88400000ULL

#define FB_BASE_LIMIT      (FB_BASE_PHYS + 0x02300000ULL) // 35 MiB Carveout (0x9E300000)
#define FIRMWARE_STACK_TOP 0x9E890000ULL
#define DRAM_BASE_PHYS     0x80000000ULL
#define DRAM_LIMIT_PHYS    0x200000000ULL // 6GB / 8GB boundary ceiling
#define KERNEL_MIN_SIZE    0x00800000ULL  // 8 MiB (distinguishes Linux kernel from 4 MiB wrapper)
#define KERNEL_MAX_SIZE    0x04000000ULL  // 64 MiB ceiling
#define KERNEL_MAX_OFFSET  0x02000000ULL  // 32 MiB max text_offset
#define KERNEL_ALIGNED_BASE 0xA2000000ULL // 2 MiB-aligned destination in Window F (modulo 0x200000 == 0)
#define DTB_REALLOC_BASE    0xA4000000ULL // 2 MiB-aligned non-overlapping DTB buffer in Window F
#define BUNDLED_DTB_SOURCE_BASE     0xA1838000ULL // DTB offset in compound container (0xA0160000 + 0x16D8000)
#define BUNDLED_INITRD_SOURCE_BASE  0xA1568000ULL // Initramfs offset in compound container (0xA0160000 + 0x1408000)
#define INITRD_REALLOC_BASE         0xA4400000ULL // 2 MiB-aligned Initramfs destination buffer in Window F
#define INITRD_PAYLOAD_SIZE         0x002CF9EAULL // 2,947,562 bytes authoritative CPIO payload size

STATIC UINT64 gPassedDtbBase = 0;

VOID
EFIAPI
ArmLaunchLinuxKernel (
  IN UINT64 KernelEntry,
  IN UINT64 DtbBase
  );

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

#pragma pack(1)
typedef struct {
  UINT32 Magic;
  UINT32 TotalSize;
  UINT32 OffDtStruct;
  UINT32 OffDtStrings;
  UINT32 OffMemRsvmap;
  UINT32 Version;
  UINT32 LastCompVersion;
  UINT32 BootCpuidPhys;
  UINT32 SizeDtStrings;
  UINT32 SizeDtStruct;
} FDT_HEADER;
#pragma pack()

/**
  Validate that a candidate memory address hosts a genuine Linux ARM64 kernel Image
  and does not collide with TrustZone, Framebuffer, or Firmware execution envelopes.
  Prevents firmware wrapper (4 MiB) false-positives (MAJOR-01 Remediation).
**/
STATIC
BOOLEAN
IsValidLinuxKernel (
  IN UINT64 Candidate
  )
{
  volatile UINT32 *MagicPtr;
  volatile UINT64 *ImgSizePtr;
  volatile UINT64 *TextOffsetPtr;
  UINT64          ImageSize;
  UINT64          TextOffset;

  // 1. Boundary check: Candidate must reside within valid physical DRAM
  if (Candidate < DRAM_BASE_PHYS || Candidate >= DRAM_LIMIT_PHYS) {
    return FALSE;
  }

  // 2. ARM64 Image Magic check: 'ARM\x64' (0x644D5241) at offset +0x38
  MagicPtr = (volatile UINT32 *)(UINTN)(Candidate + 0x38);
  if (*MagicPtr != LINUX_ARM64_MAGIC) {
    return FALSE;
  }

  // 3. Image size check:
  // Distinguishes the 16.02 MiB mainline Linux kernel from the 4 MiB firmware envelope
  // (ModuleEntryPoint.S wrapper declares image_size = 0x00400000 = 4 MiB).
  ImgSizePtr = (volatile UINT64 *)(UINTN)(Candidate + 0x10);
  ImageSize = *ImgSizePtr;
  if (ImageSize < KERNEL_MIN_SIZE || ImageSize > KERNEL_MAX_SIZE) {
    return FALSE;
  }

  // Arithmetic overflow and physical DRAM ceiling check: [Candidate, Candidate + ImageSize)
  if ((Candidate + ImageSize) <= Candidate || (Candidate + ImageSize) > DRAM_LIMIT_PHYS) {
    return FALSE;
  }

  // 4. Text offset sanity check
  TextOffsetPtr = (volatile UINT64 *)(UINTN)(Candidate + 0x08);
  TextOffset = *TextOffsetPtr;
  if (TextOffset > KERNEL_MAX_OFFSET) {
    return FALSE;
  }

  // 5. Memory collision check: Must not intersect TrustZone reservation [0x80B00000, 0x88400000)
  if (Candidate < TRUSTZONE_END && (Candidate + ImageSize) > TRUSTZONE_BASE) {
    return FALSE;
  }

  // 6. Memory collision check: Must not intersect Framebuffer carveout [0x9C000000, 0x9E300000)
  if (Candidate < FB_BASE_LIMIT && (Candidate + ImageSize) > FB_BASE_PHYS) {
    return FALSE;
  }

  // 7. Memory collision check: Must not intersect Firmware/Heap/Stack envelope [0x9E400000, 0x9E890000)
  if (Candidate < FIRMWARE_STACK_TOP && (Candidate + ImageSize) > FIRMWARE_BASE) {
    return FALSE;
  }

  return TRUE;
}

/**
  Validate that a physical address points to a valid, well-formed Device Tree Blob (FDT).
  Verifies:
  1. Pointer non-null and 8-byte alignment (Devicetree Spec & ARM64 boot protocol).
  2. Base resides within physical DRAM boundaries.
  3. FDT Magic matches 0xD00DFEED (big-endian).
  4. TotalSize is within valid bounds (at least 40 bytes header, max 8 MiB).
  5. Complete DTB memory span does not overflow DRAM.
  6. Memory isolation: Does not intersect TrustZone, Framebuffer, Firmware, or Stack.
**/
STATIC
BOOLEAN
IsValidDeviceTree (
  IN UINT64 DtbPhysBase,
  OUT UINT32 *DtbTotalSize OPTIONAL
  )
{
  volatile FDT_HEADER *FdtHdr;
  UINT32              Magic;
  UINT32              TotalSize;
  UINT64              DtbEnd;

  if (DtbTotalSize != NULL) {
    *DtbTotalSize = 0;
  }

  // 1. Non-null and 8-byte alignment check
  if (DtbPhysBase == 0 || (DtbPhysBase & 0x7ULL) != 0) {
    return FALSE;
  }

  // 2. Boundary check: Entire initial FDT header must reside within valid physical DRAM
  // Prevents dereferencing truncated or out-of-bounds header past DRAM boundary
  if (DtbPhysBase < DRAM_BASE_PHYS ||
      (DtbPhysBase + sizeof(FDT_HEADER)) > DRAM_LIMIT_PHYS ||
      (DtbPhysBase + sizeof(FDT_HEADER)) < DtbPhysBase) {
    return FALSE;
  }

  FdtHdr = (volatile FDT_HEADER *)(UINTN)DtbPhysBase;

  // 3. Magic check: 0xD00DFEED in big-endian
  Magic = FdtHdr->Magic;
  if (Magic != Swap32(FDT_MAGIC) && Magic != FDT_MAGIC) {
    return FALSE;
  }

  // 4. TotalSize bounds check (big-endian in standard FDT)
  // Maximum size tightened from 8 MiB to 2 MiB per Linux ARM64 boot protocol (TotalSize > 0x00800000ULL)
  TotalSize = Swap32(FdtHdr->TotalSize);
  if (TotalSize < sizeof(FDT_HEADER) || TotalSize > FDT_MAX_SIZE) { // 2 MiB max ceiling per protocol
    return FALSE;
  }

  DtbEnd = DtbPhysBase + TotalSize;
  if (DtbEnd <= DtbPhysBase || DtbEnd > DRAM_LIMIT_PHYS) {
    return FALSE;
  }

  // 5. Memory collision check: Must not intersect TrustZone reservation [0x80B00000, 0x88400000)
  if (DtbPhysBase < TRUSTZONE_END && DtbEnd > TRUSTZONE_BASE) {
    return FALSE;
  }

  // 6. Memory collision check: Must not intersect Framebuffer carveout [0x9C000000, 0x9E300000)
  if (DtbPhysBase < FB_BASE_LIMIT && DtbEnd > FB_BASE_PHYS) {
    return FALSE;
  }

  // 7. Memory collision check: Must not intersect Firmware/Heap envelope [0x9E400000, 0x9E880000)
  if (DtbPhysBase < 0x9E880000ULL && DtbEnd > FIRMWARE_BASE) {
    return FALSE;
  }

  // 8. Memory collision check: Must not intersect Stack [0x9E880000, 0x9E890000)
  if (DtbPhysBase < FIRMWARE_STACK_TOP && DtbEnd > 0x9E880000ULL) {
    return FALSE;
  }

  if (DtbTotalSize != NULL) {
    *DtbTotalSize = TotalSize;
  }

  return TRUE;
}

/**
  Validate that a candidate memory address hosts the authentic R8Q EDK II Firmware Volume.
  Verifies:
  1. Base pointer non-null and 8-byte aligned.
  2. Complete 4 MiB span resides in valid physical DRAM without arithmetic overflow.
  3. No collision with TrustZone, Framebuffer, or Stack reservations.
  4. Firmware Volume signature matches '_FVH' (0x4856465F).
  5. FvLength matches FIRMWARE_SIZE (4,194,304 bytes / 0x00400000).
  6. HeaderLength matches 72 bytes (0x0048).
  7. 16-bit header checksum sums to 0x0000 over HeaderLength.
  8. FileSystemGuid matches EFI_FIRMWARE_FILE_SYSTEM2_GUID.
  9. ZeroVector reset instruction branches to expected entry point (+0x2CB0).
  10. Entry point at +0x2CB0 hosts valid ARM64 wrapper header ('ARM\x64' at +0x38).
**/
STATIC
BOOLEAN
IsValidFirmwareVolume (
  IN UINT64 FvBase
  )
{
  volatile UINT32 *SigPtr;
  volatile UINT64 *FvLenPtr;
  volatile UINT16 *HdrLenPtr;
  volatile UINT16 *Words;
  volatile UINT64 *GuidPtr;
  volatile UINT32 *ResetVec;
  volatile UINT32 *EntryInstr;
  volatile UINT64 *EntryImgSize;
  volatile UINT32 *EntryMagic;
  UINT32          Sum = 0;
  UINT32          i;
  UINT32          Instr;
  INT32           Imm26;
  INT64           BranchOffset;
  UINT64          TargetEntry;

  // 1. Non-null and 8-byte alignment check
  if (FvBase == 0 || (FvBase & 0x7ULL) != 0) {
    return FALSE;
  }

  // 2. DRAM boundary and arithmetic overflow check
  if (FvBase < DRAM_BASE_PHYS || (FvBase + FIRMWARE_SIZE) > DRAM_LIMIT_PHYS || (FvBase + FIRMWARE_SIZE) <= FvBase) {
    return FALSE;
  }

  // 3. Memory collision checks
  if (FvBase < TRUSTZONE_END && (FvBase + FIRMWARE_SIZE) > TRUSTZONE_BASE) {
    return FALSE;
  }
  if (FvBase < FB_BASE_LIMIT && (FvBase + FIRMWARE_SIZE) > FB_BASE_PHYS) {
    return FALSE;
  }

  // 4. Signature check: '_FVH' at offset +0x28
  SigPtr = (volatile UINT32 *)(UINTN)(FvBase + 0x28);
  if (*SigPtr != 0x4856465F) {
    return FALSE;
  }

  // 5. FvLength check: 4 MiB (0x00400000) at offset +0x20
  FvLenPtr = (volatile UINT64 *)(UINTN)(FvBase + 0x20);
  if (*FvLenPtr != FIRMWARE_SIZE) {
    return FALSE;
  }

  // 6. HeaderLength check: 72 bytes (0x0048) at offset +0x30
  HdrLenPtr = (volatile UINT16 *)(UINTN)(FvBase + 0x30);
  if (*HdrLenPtr != 0x0048) {
    return FALSE;
  }

  // 7. 16-bit header checksum check: sum of all 36 halfwords must be 0x0000
  Words = (volatile UINT16 *)(UINTN)FvBase;
  for (i = 0; i < (*HdrLenPtr / 2); i++) {
    Sum += Words[i];
  }
  if ((Sum & 0xFFFF) != 0) {
    return FALSE;
  }

  // 8. FileSystemGuid check at offset +0x10: EFI_FIRMWARE_FILE_SYSTEM2_GUID
  // { 0x8c8ce578, 0x8a3d, 0x4f1c, { 0x99, 0x35, 0x89, 0x61, 0x85, 0xc3, 0x2d, 0xd3 } }
  // Little-endian QWORD 0: 0x4F1C8A3D8C8CE578ULL, QWORD 1: 0xD32DC38561893599ULL
  GuidPtr = (volatile UINT64 *)(UINTN)(FvBase + 0x10);
  if (GuidPtr[0] != 0x4F1C8A3D8C8CE578ULL || GuidPtr[1] != 0xD32DC38561893599ULL) {
    return FALSE;
  }

  // 9. Reset vector branch instruction at offset +0x00:
  // Must be an unconditional B instruction (opcode bits [31:26] == 000101b, i.e. 0x14000000).
  // Dynamically decodes signed imm26 displacement to determine entry point.
  ResetVec = (volatile UINT32 *)(UINTN)FvBase;
  Instr = *ResetVec;
  if ((Instr & 0xFC000000) != 0x14000000) {
    return FALSE;
  }
  Imm26 = (INT32)(Instr & 0x03FFFFFF);
  if ((Imm26 & 0x02000000) != 0) {
    Imm26 |= (INT32)0xFC000000;
  }
  BranchOffset = ((INT64)Imm26) * 4;
  if (BranchOffset < 72 || BranchOffset >= (INT64)FIRMWARE_SIZE) {
    return FALSE;
  }

  TargetEntry = FvBase + (UINT64)BranchOffset;

  // 10. Validate entry point target:
  // First instruction of ModuleEntryPoint must branch forward past 64-byte wrapper (0x14000010)
  EntryInstr = (volatile UINT32 *)(UINTN)TargetEntry;
  if (*EntryInstr != 0x14000010 && (*EntryInstr & 0xFC000000) != 0x14000000) {
    return FALSE;
  }

  // Wrapper image_size field at TargetEntry + 0x10 must match FIRMWARE_SIZE (4 MiB)
  EntryImgSize = (volatile UINT64 *)(UINTN)(TargetEntry + 0x10);
  if (*EntryImgSize != FIRMWARE_SIZE) {
    return FALSE;
  }

  // Expected entry point ARM64 header check: 'ARM\x64' (0x644D5241) at TargetEntry + 0x38
  EntryMagic = (volatile UINT32 *)(UINTN)(TargetEntry + 0x38);
  if (*EntryMagic != LINUX_ARM64_MAGIC) {
    return FALSE;
  }

  return TRUE;
}

#define EXPECTED_INITRD_CRC32       0x032DDBEDULL // CRC-32 of uncompressed CPIO data per RFC 1952
#define EXPECTED_INITRD_ISIZE       7280640ULL    // 0x006F1800 uncompressed CPIO size (ISIZE)

STATIC
BOOLEAN
IsValidInitrd (
  IN UINT64 Addr,
  IN UINT64 StagedFvBase OPTIONAL
  )
{
  volatile UINT8  *Bytes;
  volatile UINT32 *CrcPtr;
  volatile UINT32 *IsizePtr;

  // 1. 8-byte alignment check
  if ((Addr & 0x7ULL) != 0) {
    return FALSE;
  }

  // 2. DRAM physical boundary and arithmetic overflow check
  if (Addr < DRAM_BASE_PHYS || (Addr + INITRD_PAYLOAD_SIZE) > DRAM_LIMIT_PHYS || (Addr + INITRD_PAYLOAD_SIZE) <= Addr) {
    return FALSE;
  }

  // 3. Staging container envelope bounds check (if StagedFvBase is provided)
  if (StagedFvBase != 0) {
    UINT64 ContainerBase = (StagedFvBase >= 0x1040ULL) ? (StagedFvBase - 0x1040ULL) : StagedFvBase;
    UINT64 ContainerEnd = ContainerBase + 0x02000000ULL; // 32 MiB max container envelope
    if (Addr != INITRD_REALLOC_BASE) {
      if (Addr < ContainerBase || (Addr + INITRD_PAYLOAD_SIZE) > ContainerEnd) {
        return FALSE;
      }
    }
  }

  // 4. Memory carveout exclusion checks:
  // Must not intersect TrustZone reservation [0x80B00000, 0x88400000)
  if (Addr < TRUSTZONE_END && (Addr + INITRD_PAYLOAD_SIZE) > TRUSTZONE_BASE) {
    return FALSE;
  }

  // Must not intersect Framebuffer carveout [0x9C000000, 0x9E300000)
  if (Addr < FB_BASE_LIMIT && (Addr + INITRD_PAYLOAD_SIZE) > FB_BASE_PHYS) {
    return FALSE;
  }

  // Must not intersect Firmware & Stack envelope [0x9E400000, 0x9E890000)
  if (Addr < FIRMWARE_STACK_TOP && (Addr + INITRD_PAYLOAD_SIZE) > FIRMWARE_BASE) {
    return FALSE;
  }

  // 5. Gzip magic header & Deflate compression method verification (0x1F, 0x8B, 0x08)
  Bytes = (volatile UINT8 *)(UINTN)Addr;
  if (Bytes[0] != 0x1F || Bytes[1] != 0x8B || Bytes[2] != 0x08) {
    return FALSE;
  }

  // 6. Gzip header flags validation (RFC 1952: reserved bits 5-7 must be 0)
  if ((Bytes[3] & 0xE0) != 0) {
    return FALSE;
  }

  // 7. Expected uncompressed CRC-32 trailer verification (RFC 1952: offset PayloadSize - 8)
  CrcPtr = (volatile UINT32 *)(UINTN)(Addr + INITRD_PAYLOAD_SIZE - 8);
  if ((UINT64)(*CrcPtr) != EXPECTED_INITRD_CRC32) {
    return FALSE;
  }

  // 8. Expected uncompressed ISIZE footer verification (RFC 1952: offset PayloadSize - 4)
  IsizePtr = (volatile UINT32 *)(UINTN)(Addr + INITRD_PAYLOAD_SIZE - 4);
  if ((UINT64)(*IsizePtr) != EXPECTED_INITRD_ISIZE) {
    return FALSE;
  }

  return TRUE;
}

/**
  C Entry point invoked from ModuleEntryPoint.S after self-relocation to 0x9E400000.
  x0 contains the DTB physical base address passed by Samsung ABL.
  x1 contains the authoritative physical base address of R8Q_EFI.fd in DRAM (StagedFvBase).
**/
VOID
EFIAPI
CEntryPoint (
  IN UINT64 DtbPhysBase,
  IN UINT64 StagedFvBase
  )
{
  UINT64            KernelCandidate = 0;
  UINT32            ValidatedDtbSize = 0;
  UINT64            ValidatedDtbBase = 0;
  UINT64            SelectedDtbSrc = 0;
  UINT64            CurrentElVal = 0;
  UINT64            CandidateAddresses[] = {
                      0xA2000000ULL, // 2 MiB-aligned Window F destination (KERNEL_ALIGNED_BASE)
                      0xA0561040ULL, // Container-offset compound payload (P_load 0xA0160000 + 0x401040)
                      0xA0560040ULL, // Immediate compound payload offset (P_load 0xA0160000 + 0x400040)
                      0xA0561000ULL, // 4K-aligned compound payload offset (P_load 0xA0160000 + 0x401000)
                      0xA0160000ULL, // Direct Window F Kernel Base
                      0x90A00000ULL, // Window D: 182 MiB free System RAM
                      0xA0002000ULL  // Window F: 256.9 MiB free System RAM
                    };
  UINTN             Index;

  gPassedDtbBase = DtbPhysBase;

  // 0. Comprehensive Firmware Volume Validation
  if (StagedFvBase == 0 || !IsValidFirmwareVolume(StagedFvBase)) {
    // Corrupted or spoofed FV: Alert indicator (Red: 0x00FF0000)
    DrawColorBlock(440, 1150, 200, 100, 0x00FF0000);
    for (;;) { __asm__ __volatile__ ("wfi"); }
  }

  // Read Current Exception Level (bits [3:2]: 0=EL0, 1=EL1, 2=EL2, 3=EL3)
  __asm__ __volatile__ ("mrs %0, CurrentEL" : "=r" (CurrentElVal));
  CurrentElVal = (CurrentElVal >> 2) & 0x3;

  // 1. Draw visual confirmation bar across top of AMOLED panel
  // Color: Royal Blue Header bar (0x001B365D)
  DrawColorBlock(0, 0, FB_WIDTH, 120, 0x001B365D);
  // Accent bar: Emerald Green (0x0000A86B)
  DrawColorBlock(0, 120, FB_WIDTH, 20, 0x0000A86B);

  // Status indicator: Center confirmation block (PrePi active)
  DrawColorBlock(440, 1150, 200, 100, 0x0000A86B);

  // Exception Level status badge:
  // EL2: Gold (0x00FFD700) indicating hypervisor execution
  // EL1: Emerald Green (0x0000A86B) indicating supervisor execution
  // EL0 / EL3: Unsupported execution level, alert indicator (Red: 0x00FF0000) and halt
  if (CurrentElVal == 2) {
    DrawColorBlock(20, 40, 60, 40, 0x00FFD700);
  } else if (CurrentElVal == 1) {
    DrawColorBlock(20, 40, 60, 40, 0x0000A86B);
  } else {
    DrawColorBlock(20, 40, 60, 40, 0x00FF0000);
    for (;;) { __asm__ __volatile__ ("wfi"); }
  }

  // 2. Select Source Device Tree Blob (Priority 1: ABL runtime DTB in x0; Fallback: Bundled/Container DTB)
  if (IsValidDeviceTree(DtbPhysBase, &ValidatedDtbSize)) {
    SelectedDtbSrc = DtbPhysBase; // ABL passed hardware-configured DTB
  } else if (StagedFvBase != 0 && IsValidDeviceTree(StagedFvBase + 0x16D6FC0ULL, &ValidatedDtbSize)) {
    SelectedDtbSrc = StagedFvBase + 0x16D6FC0ULL;
  } else if (StagedFvBase != 0 && IsValidDeviceTree(StagedFvBase + 0x16D7FC0ULL, &ValidatedDtbSize)) {
    SelectedDtbSrc = StagedFvBase + 0x16D7FC0ULL;
  } else if (IsValidDeviceTree(BUNDLED_DTB_SOURCE_BASE, &ValidatedDtbSize)) {
    SelectedDtbSrc = BUNDLED_DTB_SOURCE_BASE;
  } else if (StagedFvBase != 0 && IsValidDeviceTree(StagedFvBase + 0x16D7000ULL, &ValidatedDtbSize)) {
    SelectedDtbSrc = StagedFvBase + 0x16D7000ULL;
  } else if (StagedFvBase != 0 && IsValidDeviceTree(StagedFvBase + 0x16D8000ULL, &ValidatedDtbSize)) {
    SelectedDtbSrc = StagedFvBase + 0x16D8000ULL;
  }

  // Dynamic Scan: If DTB not found at primary offsets, probe 4K boundaries across container envelope
  if (SelectedDtbSrc == 0 && StagedFvBase != 0) {
    UINT64 ContainerBase = (StagedFvBase >= 0x1040ULL) ? (StagedFvBase - 0x1040ULL) : StagedFvBase;
    UINT64 DtbProbe;
    for (DtbProbe = ContainerBase + 0x00400000ULL; DtbProbe < ContainerBase + 0x02000000ULL; DtbProbe += 0x1000) {
      if (IsValidDeviceTree(DtbProbe, &ValidatedDtbSize)) {
        SelectedDtbSrc = DtbProbe;
        break;
      }
    }
  }

  // Runtime DTB Unpacking, /chosen property injection, and preservation of hardware nodes
  if (SelectedDtbSrc != 0) {
    // Draw small DTB confirmation badge (Cyan: 0x0000CED1)
    DrawColorBlock(100, 40, 80, 40, 0x0000CED1);

    // Unpack and expand selected DTB into dedicated 2 MiB buffer at DTB_REALLOC_BASE (0xA4000000)
    int FdtErr = fdt_open_into((CONST VOID *)(UINTN)SelectedDtbSrc, (VOID *)(UINTN)DTB_REALLOC_BASE, 0x200000);
    if (FdtErr == 0) {
      VOID *Fdt = (VOID *)(UINTN)DTB_REALLOC_BASE;
      int ChosenNode = fdt_path_offset(Fdt, "/chosen");
      if (ChosenNode < 0) {
        ChosenNode = fdt_add_subnode(Fdt, 0, "chosen");
      }
      if (ChosenNode >= 0) {
        CONST CHAR8 RequiredBootArgs[] = "console=tty0 console=ttyMSM0,115200n8 earlycon=msm_geni_serial,0xa90000 clk_ignore_unused pd_ignore_unused initcall_debug loglevel=8 root=/dev/ram0 rw init=/init";
        int ArgLen = 0;
        CONST CHAR8 *ExistingArgs = (CONST CHAR8 *)fdt_getprop(Fdt, ChosenNode, "bootargs", &ArgLen);
        CHAR8 MergedArgs[2048];
        MergedArgs[0] = '\0';
        if (ExistingArgs != NULL && ArgLen > 1) {
          AsciiStrCpyS(MergedArgs, sizeof(MergedArgs), ExistingArgs);
          AsciiStrCatS(MergedArgs, sizeof(MergedArgs), " ");
          AsciiStrCatS(MergedArgs, sizeof(MergedArgs), RequiredBootArgs);
        } else {
          AsciiStrCpyS(MergedArgs, sizeof(MergedArgs), RequiredBootArgs);
        }
        fdt_setprop_string(Fdt, ChosenNode, "bootargs", MergedArgs);
        fdt_setprop_u64(Fdt, ChosenNode, "linux,initrd-start", INITRD_REALLOC_BASE);
        fdt_setprop_u64(Fdt, ChosenNode, "linux,initrd-end", INITRD_REALLOC_BASE + INITRD_PAYLOAD_SIZE);
      }
      fdt_pack(Fdt);
      ValidatedDtbBase = DTB_REALLOC_BASE;
      ValidatedDtbSize = (UINT32)fdt_totalsize(Fdt);
    } else {
      // Direct copy fallback if fdt_open_into encountered unexpected error
      volatile UINT8 *DtbSrc = (volatile UINT8 *)(UINTN)SelectedDtbSrc;
      volatile UINT8 *DtbDst = (volatile UINT8 *)(UINTN)DTB_REALLOC_BASE;
      UINT32 i;
      for (i = 0; i < ValidatedDtbSize; i++) {
        DtbDst[i] = DtbSrc[i];
      }
      ValidatedDtbBase = DTB_REALLOC_BASE;
    }

    // Re-validate DTB at new destination to prove copy integrity
    UINT32 PostRelocSize = 0;
    if (!IsValidDeviceTree(ValidatedDtbBase, &PostRelocSize)) {
      // Post-relocation DTB verification failed!
      DrawColorBlock(100, 40, 80, 40, 0x00FF0000);
    }
  } else {
    // DTB invalid or corrupted: Draw Warning badge (Red: 0x00FF0000)
    DrawColorBlock(100, 40, 80, 40, 0x00FF0000);
  }

  // 3. Dynamic Initramfs Relocation from Container Staging to Dedicated 32 MiB Buffer (0xA4400000)
  {
    UINT64 InitrdSrc = 0;
    if (StagedFvBase != 0 && IsValidInitrd(StagedFvBase + 0x1406FC0ULL, StagedFvBase)) {
      InitrdSrc = StagedFvBase + 0x1406FC0ULL;
    } else if (StagedFvBase != 0 && IsValidInitrd(StagedFvBase + 0x1407FC0ULL, StagedFvBase)) {
      InitrdSrc = StagedFvBase + 0x1407FC0ULL;
    } else if (StagedFvBase != 0 && IsValidInitrd(StagedFvBase + 0x1407000ULL, StagedFvBase)) {
      InitrdSrc = StagedFvBase + 0x1407000ULL;
    } else if (StagedFvBase != 0 && IsValidInitrd(StagedFvBase + 0x1408000ULL, StagedFvBase)) {
      InitrdSrc = StagedFvBase + 0x1408000ULL;
    } else if (IsValidInitrd(BUNDLED_INITRD_SOURCE_BASE, 0)) {
      InitrdSrc = BUNDLED_INITRD_SOURCE_BASE;
    }

    // Dynamic Scan: If Initrd not found at primary offsets, probe 4K boundaries across container envelope
    if (InitrdSrc == 0 && StagedFvBase != 0) {
      UINT64 ContainerBase = (StagedFvBase >= 0x1040ULL) ? (StagedFvBase - 0x1040ULL) : StagedFvBase;
      UINT64 RdProbe;
      for (RdProbe = ContainerBase + 0x00400000ULL; RdProbe < ContainerBase + 0x02000000ULL; RdProbe += 0x1000) {
        if (IsValidInitrd(RdProbe, StagedFvBase)) {
          InitrdSrc = RdProbe;
          break;
        }
      }
    }

    if (InitrdSrc != 0) {
      volatile UINT64 *RdSrc = (volatile UINT64 *)(UINTN)InitrdSrc;
      volatile UINT64 *RdDst = (volatile UINT64 *)(UINTN)INITRD_REALLOC_BASE;
      UINT64 RdWords = (INITRD_PAYLOAD_SIZE + 7) / 8;
      UINT64 RdIdx;
      for (RdIdx = 0; RdIdx < RdWords; RdIdx++) {
        RdDst[RdIdx] = RdSrc[RdIdx];
      }
    }
  }

  // 4. Mathematical non-overlap verification
  // Verify Firmware [0x9E400000, 0x9E800000) is outside TrustZone [0x80B00000, 0x88400000)
  if (FIRMWARE_BASE >= TRUSTZONE_END || (FIRMWARE_BASE + FIRMWARE_SIZE) <= TRUSTZONE_BASE) {
    // Memory isolation confirmed
    DrawColorBlock(200, 40, 80, 40, 0x0000A86B);
  }

  // 5. Locate Embedded Mainline Linux ARM64 Kernel Image
  // Priority 0: Exact derived offset from authoritative StagedFvBase (StagedFvBase + 0x00400000ULL)
  if (StagedFvBase != 0 && IsValidLinuxKernel(StagedFvBase + 0x00400000ULL)) {
    KernelCandidate = StagedFvBase + 0x00400000ULL;
  } else if (StagedFvBase != 0 && IsValidLinuxKernel(StagedFvBase + 0x400040ULL)) {
    KernelCandidate = StagedFvBase + 0x400040ULL;
  } else {
    for (Index = 0; Index < sizeof(CandidateAddresses)/sizeof(CandidateAddresses[0]); Index++) {
      if (IsValidLinuxKernel(CandidateAddresses[Index])) {
        KernelCandidate = CandidateAddresses[Index];
        break;
      }
    }
  }

  // Dynamic Scan: If not found in primary candidates, scan Window F (0xA0000000 - 0xAB000000)
  if (KernelCandidate == 0) {
    UINT64 Probe;
    for (Probe = 0xA0000000ULL; Probe < 0xAB000000ULL; Probe += 0x1000) {
      // Check page-aligned candidate
      if (IsValidLinuxKernel(Probe)) {
        KernelCandidate = Probe;
        break;
      }
      // Check 0x40-offset candidate (covering compound payload offsets like 0xA0560040 and 0xA0561040, probing Probe + 0x40 + 0x38)
      if (IsValidLinuxKernel(Probe + 0x40)) {
        KernelCandidate = Probe + 0x40;
        break;
      }
    }
  }

  // 6. Transfer execution to Linux EFI Stub / ARM64 Kernel Entry
  if (KernelCandidate != 0) {
    volatile UINT64 *ImgSizePtr = (volatile UINT64 *)(UINTN)(KernelCandidate + 0x10);
    UINT64          KernelSize = *ImgSizePtr;
    UINT64          KernelRunBase = KernelCandidate;
    UINT64          Ctr;
    UINT64          DminLine;
    UINT64          CacheLineSize;

    // Derive data cache line size dynamically from CTR_EL0.DminLine
    __asm__ __volatile__ ("mrs %0, ctr_el0" : "=r" (Ctr));
    DminLine = (Ctr >> 16) & 0xF;
    CacheLineSize = 4ULL << DminLine; // Standard 64 bytes on Cortex-A77/A55

    // Handoff badge: Emerald Green full block indicating successful dispatch
    DrawColorBlock(440, 1300, 200, 60, 0x0000FF00);

    // 0. Kernel Placement Protocol Check (Documentation/arm64/booting.rst)
    // The Image must be located at text_offset bytes from a 2 MiB-aligned base.
    // When text_offset = 0, Image must be at an address where (Base % 0x200000) == 0.
    // If Candidate is misaligned relative to 2 MiB boundary, relocate to KERNEL_ALIGNED_BASE (0xA2000000).
    if ((KernelCandidate & 0x001FFFFFULL) != 0) {
      UINT64 DstEnd = KERNEL_ALIGNED_BASE + KernelSize;
      if (DstEnd <= DRAM_LIMIT_PHYS && DstEnd > KERNEL_ALIGNED_BASE) {
        volatile UINT64 *Src = (volatile UINT64 *)(UINTN)KernelCandidate;
        volatile UINT64 *Dst = (volatile UINT64 *)(UINTN)KERNEL_ALIGNED_BASE;
        UINT64 CopyBytes = KernelSize;
        // Hardening: Clamp copy length to actual payload size (16,802,304 bytes = 0x01006200).
        // Discrepancy resolution: 0x01070000 - 0x01006200 = 433,664 bytes (0x69E00) is BSS.
        if (CopyBytes > 0x01006200ULL) {
          CopyBytes = 0x01006200ULL;
        }
        UINT64 Words = (CopyBytes + 7) / 8;
        UINT64 TotalWords = (KernelSize + 7) / 8;
        UINT64 Idx;
        for (Idx = 0; Idx < Words; Idx++) {
          Dst[Idx] = Src[Idx];
        }
        // Zero BSS remainder in destination buffer (433,664 bytes)
        for (Idx = Words; Idx < TotalWords; Idx++) {
          Dst[Idx] = 0;
        }
        KernelRunBase = KERNEL_ALIGNED_BASE;
      }
    }

    // 1. Perform Point-of-Coherence (PoC) cache maintenance for validated DTB
    if (ValidatedDtbBase != 0 && ValidatedDtbSize != 0) {
      UINT64 DtbCleanAddr = ValidatedDtbBase & ~(CacheLineSize - 1);
      UINT64 DtbCleanLimit = (ValidatedDtbBase + ValidatedDtbSize + CacheLineSize - 1) & ~(CacheLineSize - 1);
      if (DtbCleanLimit <= DRAM_LIMIT_PHYS && DtbCleanLimit > DtbCleanAddr) {
        for (; DtbCleanAddr < DtbCleanLimit; DtbCleanAddr += CacheLineSize) {
          __asm__ __volatile__ ("dc civac, %0" : : "r" (DtbCleanAddr) : "memory");
        }
      }
    }

    // 2. Perform Point-of-Coherence (PoC) cache maintenance for relocated Rescue Initramfs
    {
      UINT64 RdCleanAddr = INITRD_REALLOC_BASE & ~(CacheLineSize - 1);
      UINT64 RdCleanLimit = (INITRD_REALLOC_BASE + INITRD_PAYLOAD_SIZE + CacheLineSize - 1) & ~(CacheLineSize - 1);
      if (RdCleanLimit <= DRAM_LIMIT_PHYS && RdCleanLimit > RdCleanAddr) {
        for (; RdCleanAddr < RdCleanLimit; RdCleanAddr += CacheLineSize) {
          __asm__ __volatile__ ("dc civac, %0" : : "r" (RdCleanAddr) : "memory");
        }
      }
    }

    // 3. Perform Point-of-Coherence (PoC) cache maintenance for entire loaded Linux Image
    // Mandated by Linux ARM64 Boot Protocol (Documentation/arm64/booting.rst)
    if (KernelSize >= KERNEL_MIN_SIZE && KernelSize <= KERNEL_MAX_SIZE) {
      UINT64 KernelCleanAddr = KernelRunBase & ~(CacheLineSize - 1);
      UINT64 KernelCleanLimit = (KernelRunBase + KernelSize + CacheLineSize - 1) & ~(CacheLineSize - 1);
      if (KernelCleanLimit <= DRAM_LIMIT_PHYS && KernelCleanLimit > KernelCleanAddr) {
        for (; KernelCleanAddr < KernelCleanLimit; KernelCleanAddr += CacheLineSize) {
          __asm__ __volatile__ ("dc civac, %0" : : "r" (KernelCleanAddr) : "memory");
        }
      }
    }

    // 4. Perform Point-of-Coherence (PoC) cache maintenance for early stack envelope [0x9E880000, 0x9E890000)
    {
      UINT64 StackCleanAddr = FIRMWARE_STACK_BASE & ~(CacheLineSize - 1);
      UINT64 StackCleanLimit = (FIRMWARE_STACK_TOP + CacheLineSize - 1) & ~(CacheLineSize - 1);
      if (StackCleanLimit <= DRAM_LIMIT_PHYS && StackCleanLimit > StackCleanAddr) {
        for (; StackCleanAddr < StackCleanLimit; StackCleanAddr += CacheLineSize) {
          __asm__ __volatile__ ("dc civac, %0" : : "r" (StackCleanAddr) : "memory");
        }
      }
    }

    // Full system data barrier and instruction pipeline barrier before kernel branch
    __asm__ __volatile__ ("dsb sy\n\tisb" : : : "memory");

    // 5. Ensure all interrupts are masked per Linux ARM64 Boot Protocol (DAIF = 0xF)
    __asm__ __volatile__ ("msr daifset, #0xf" : : : "memory");

    // 6. Ensure MMU and Data Cache are disabled before handoff if running with MMU enabled
    if (CurrentElVal == 2) {
      UINT64 SctlrEl2;
      __asm__ __volatile__ ("mrs %0, sctlr_el2" : "=r" (SctlrEl2));
      if ((SctlrEl2 & 0x5ULL) != 0) { // Bit 0 (M), Bit 2 (C)
        SctlrEl2 &= ~0x5ULL;
        __asm__ __volatile__ ("msr sctlr_el2, %0\n\tisb" : : "r" (SctlrEl2) : "memory");
      }
      // Invalidate EL2 TLB to prevent stale address translations
      __asm__ __volatile__ ("tlbi alle2\n\tdsb sy\n\tisb" : : : "memory");
    } else if (CurrentElVal == 1) {
      UINT64 SctlrEl1;
      __asm__ __volatile__ ("mrs %0, sctlr_el1" : "=r" (SctlrEl1));
      if ((SctlrEl1 & 0x5ULL) != 0) { // Bit 0 (M), Bit 2 (C)
        SctlrEl1 &= ~0x5ULL;
        __asm__ __volatile__ ("msr sctlr_el1, %0\n\tisb" : : "r" (SctlrEl1) : "memory");
      }
      // Invalidate EL1 TLB to prevent stale address translations
      __asm__ __volatile__ ("tlbi vmalle1\n\tdsb sy\n\tisb" : : : "memory");
    }

    // 7. Invalidate instruction caches and flush pipeline to Point of Unification
    __asm__ __volatile__ ("ic iallu\n\tdsb sy\n\tisb" : : : "memory");

    // Calling convention for Linux ARM64 kernel (Documentation/arm64/booting.rst):
    // Execution begins at the very first instruction of the Image (offset +0x00 / code0).
    // text_offset in the header specifies load offset relative to 2 MiB alignment, NOT an offset within Image.
    // x0 = Physical address of Device Tree Blob (FDT)
    // x1 = 0, x2 = 0, x3 = 0 (Reserved)
    // Terminal branch into ARM64 Linux Kernel via dedicated assembly routine:
    // Establishes exact register handoff convention (x0=DTB, x1=x2=x3=0, x4-x30=0, SP aligned, MMU/Caches disabled).
    KernelCandidate = KernelRunBase;
    ArmLaunchLinuxKernel(KernelCandidate, ValidatedDtbBase);
  }

  // In production firmware without embedded kernel, handoff is completed via BDS/LinuxBoot
  DrawColorBlock(440, 1300, 200, 60, 0x0000A86B);
}
