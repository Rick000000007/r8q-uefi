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
  FdtLib|EmbeddedPkg/Library/FdtLib/FdtLib.inf
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

  # UEFI Shell & HII Support Libraries
  FileHandleLib|MdePkg/Library/UefiFileHandleLib/UefiFileHandleLib.inf
  SortLib|MdeModulePkg/Library/UefiSortLib/UefiSortLib.inf
  UefiHiiServicesLib|MdeModulePkg/Library/UefiHiiServicesLib/UefiHiiServicesLib.inf
  HiiLib|MdeModulePkg/Library/UefiHiiLib/UefiHiiLib.inf
  ShellLib|ShellPkg/Library/UefiShellLib/UefiShellLib.inf
  ShellCommandLib|ShellPkg/Library/UefiShellCommandLib/UefiShellCommandLib.inf
  ShellCEntryLib|ShellPkg/Library/UefiShellCEntryLib/UefiShellCEntryLib.inf
  HandleParsingLib|ShellPkg/Library/UefiHandleParsingLib/UefiHandleParsingLib.inf
  OrderedCollectionLib|MdePkg/Library/BaseOrderedCollectionRedBlackTreeLib/BaseOrderedCollectionRedBlackTreeLib.inf
  PeCoffGetEntryPointLib|MdePkg/Library/BasePeCoffGetEntryPointLib/BasePeCoffGetEntryPointLib.inf
  BcfgCommandLib|ShellPkg/Library/UefiShellBcfgCommandLib/UefiShellBcfgCommandLib.inf
  UefiBootManagerLib|MdeModulePkg/Library/UefiBootManagerLib/UefiBootManagerLib.inf
  VariablePolicyHelperLib|MdeModulePkg/Library/VariablePolicyHelperLib/VariablePolicyHelperLib.inf
  HobLib|MdePkg/Library/DxeHobLib/DxeHobLib.inf
  PerformanceLib|MdePkg/Library/BasePerformanceLibNull/BasePerformanceLibNull.inf
  DxeServicesTableLib|MdePkg/Library/DxeServicesTableLib/DxeServicesTableLib.inf
  DxeServicesLib|MdePkg/Library/DxeServicesLib/DxeServicesLib.inf
  ReportStatusCodeLib|MdePkg/Library/BaseReportStatusCodeLibNull/BaseReportStatusCodeLibNull.inf
  SafeIntLib|MdePkg/Library/BaseSafeIntLib/BaseSafeIntLib.inf

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

  # UEFI Shell 2.2 Profile & 3-Second Startup Delay
  gEfiShellPkgTokenSpaceGuid.PcdShellDefaultDelay|3
  gEfiShellPkgTokenSpaceGuid.PcdShellSupportLevel|3
  gEfiShellPkgTokenSpaceGuid.PcdShellProfileMask|0xFF

[PcdsFeatureFlag.common]
  gEfiMdeModulePkgTokenSpaceGuid.PcdUnicodeCollationSupport|TRUE
  gEfiMdeModulePkgTokenSpaceGuid.PcdUnicodeCollation2Support|TRUE

[Components.common]
  R8QPkg/PrePi/PrePi.inf
  R8QPkg/Drivers/SimpleFbDxe/SimpleFbDxe.inf
  R8QPkg/Drivers/FileVariableDxe/FileVariableDxe.inf
  R8QPkg/Drivers/StorageProtectionDxe/StorageProtectionDxe.inf
  MdeModulePkg/Universal/HiiDatabaseDxe/HiiDatabaseDxe.inf
  MdeModulePkg/Universal/Disk/UnicodeCollation/EnglishDxe/EnglishDxe.inf
  MdeModulePkg/Universal/Disk/DiskIoDxe/DiskIoDxe.inf
  MdeModulePkg/Universal/Disk/PartitionDxe/PartitionDxe.inf
  FatPkg/EnhancedFatDxe/Fat.inf
  MdeModulePkg/Bus/Usb/UsbMassStorageDxe/UsbMassStorageDxe.inf
  R8QPkg/Applications/CoreTest/CoreTest.inf
  R8QPkg/Applications/StorageTest/StorageTest.inf
  R8QPkg/Applications/SysInfo/SysInfo.inf
  R8QPkg/Applications/CpuInfo/CpuInfo.inf
  R8QPkg/Applications/MemMap/MemMap.inf
  R8QPkg/Applications/Display/Display.inf
  R8QPkg/Applications/FdtInfo/FdtInfo.inf
  R8QPkg/Applications/Storage/Storage.inf
  R8QPkg/Applications/Battery/Battery.inf
  R8QPkg/Applications/Thermal/Thermal.inf
  R8QPkg/Applications/Firmware/Firmware.inf
  R8QPkg/Applications/Diagnostics/Diagnostics.inf
  R8QPkg/Applications/ShellTest/ShellTest.inf
  R8QPkg/Applications/LinuxBoot/LinuxBoot.inf

  ShellPkg/Application/Shell/Shell.inf {
    <PcdsFixedAtBuild>
      gEfiShellPkgTokenSpaceGuid.PcdShellLibAutoInitialize|FALSE
    <LibraryClasses>
      NULL|ShellPkg/Library/UefiShellLevel2CommandsLib/UefiShellLevel2CommandsLib.inf
      NULL|ShellPkg/Library/UefiShellLevel1CommandsLib/UefiShellLevel1CommandsLib.inf
      NULL|ShellPkg/Library/UefiShellLevel3CommandsLib/UefiShellLevel3CommandsLib.inf
      NULL|ShellPkg/Library/UefiShellDriver1CommandsLib/UefiShellDriver1CommandsLib.inf
      NULL|ShellPkg/Library/UefiShellInstall1CommandsLib/UefiShellInstall1CommandsLib.inf
      NULL|ShellPkg/Library/UefiShellDebug1CommandsLib/UefiShellDebug1CommandsLib.inf
  }
