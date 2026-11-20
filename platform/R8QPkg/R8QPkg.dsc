## @file
#  R8QPkg.dsc
#  Project R8Q Platform Description & Build File
#  Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
#  SoC: Qualcomm Snapdragon 865 (SM8250)
#
#  Copyright (c) 2026, Antigravity Engineering. All rights reserved.
##

[Defines]
  PLATFORM_NAME                  = R8Q
  PLATFORM_GUID                  = 2b49b251-1824-4f2b-8254-8c19456566b4
  PLATFORM_VERSION               = 1.0.0
  DSC_SPECIFICATION              = 0x0001001A
  OUTPUT_DIRECTORY               = Build/R8Q
  SUPPORTED_ARCHITECTURES        = AARCH64
  BUILD_TARGETS                  = DEBUG|RELEASE
  SKUID_IDENTIFIER               = DEFAULT
  FLASH_DEFINITION               = R8QPkg/R8QPkg.fdf

[LibraryClasses.common]
  BaseLib|MdePkg/Library/BaseLib/BaseLib.inf
  BaseMemoryLib|MdePkg/Library/BaseMemoryLib/BaseMemoryLib.inf
  PrintLib|MdePkg/Library/BasePrintLib/BasePrintLib.inf
  SerialPortLib|R8QPkg/Library/SerialPortLib/SerialPortLib.inf
  DebugLib|MdePkg/Library/BaseDebugLibSerialPort/BaseDebugLibSerialPort.inf
  DebugPrintErrorLevelLib|MdePkg/Library/BaseDebugPrintErrorLevelLib/BaseDebugPrintErrorLevelLib.inf
  PcdLib|MdePkg/Library/BasePcdLibNull/BasePcdLibNull.inf
  IoLib|MdePkg/Library/BaseIoLibIntrinsic/BaseIoLibIntrinsic.inf
  RegisterFilterLib|MdePkg/Library/RegisterFilterLibNull/RegisterFilterLibNull.inf
  ArmLib|ArmPkg/Library/ArmLib/ArmBaseLib.inf
  UefiLib|MdePkg/Library/UefiLib/UefiLib.inf
  UefiBootServicesTableLib|MdePkg/Library/UefiBootServicesTableLib/UefiBootServicesTableLib.inf
  UefiRuntimeServicesTableLib|MdePkg/Library/UefiRuntimeServicesTableLib/UefiRuntimeServicesTableLib.inf
  UefiDriverEntryPoint|MdePkg/Library/UefiDriverEntryPoint/UefiDriverEntryPoint.inf
  UefiApplicationEntryPoint|MdePkg/Library/UefiApplicationEntryPoint/UefiApplicationEntryPoint.inf
  MemoryAllocationLib|MdePkg/Library/UefiMemoryAllocationLib/UefiMemoryAllocationLib.inf
  DevicePathLib|MdePkg/Library/UefiDevicePathLib/UefiDevicePathLib.inf
  StackCheckLib|MdePkg/Library/StackCheckLibNull/StackCheckLibNull.inf
  NULL|MdePkg/Library/StackCheckLibNull/StackCheckLibNull.inf

[PcdsFixedAtBuild.common]
  # Platform Framebuffer
  gR8QPkgTokenSpaceGuid.PcdFrameBufferBase|0x9C000000
  gR8QPkgTokenSpaceGuid.PcdFrameBufferSize|0x02300000
  gR8QPkgTokenSpaceGuid.PcdDisplayWidth|1080
  gR8QPkgTokenSpaceGuid.PcdDisplayHeight|2400
  gR8QPkgTokenSpaceGuid.PcdDisplayBpp|32

  # Serial Console & Hardware Controllers
  gR8QPkgTokenSpaceGuid.PcdUartBaseAddress|0x00A90000
  gR8QPkgTokenSpaceGuid.PcdUartBaudRate|115200
  gR8QPkgTokenSpaceGuid.PcdUfsHostControllerBase|0x01D84000
  gR8QPkgTokenSpaceGuid.PcdSdhciControllerBase|0x08804000

[Components.common]
  R8QPkg/PrePi/PrePi.inf
  R8QPkg/Drivers/SimpleFbDxe/SimpleFbDxe.inf
  R8QPkg/Drivers/FileVariableDxe/FileVariableDxe.inf
  R8QPkg/Drivers/StorageProtectionDxe/StorageProtectionDxe.inf
  MdeModulePkg/Universal/Disk/DiskIoDxe/DiskIoDxe.inf
  MdeModulePkg/Universal/Disk/PartitionDxe/PartitionDxe.inf
  FatPkg/EnhancedFatDxe/Fat.inf
  MdeModulePkg/Bus/Usb/UsbMassStorageDxe/UsbMassStorageDxe.inf
  R8QPkg/Applications/CoreTest/CoreTest.inf
  R8QPkg/Applications/StorageTest/StorageTest.inf
