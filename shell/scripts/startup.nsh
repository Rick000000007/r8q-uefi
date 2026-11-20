# Project R8Q UEFI Startup Automation Script
# Platform: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
# Architecture: ARMv8.2-A (AArch64) | Qualcomm Snapdragon 865 (SM8250)

@echo -off
cls
echo "================================================================="
echo "   PROJECT R8Q UEFI FIRMWARE PLATFORM - INTERACTIVE SHELL 2.2"
echo "   Target Device: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "   SoC:           Qualcomm Snapdragon 865 (SM8250 / Kona)"
echo "   Firmware:      Project R8Q UEFI v1.0.0 (EDK II stable202411)"
echo "   OS Handoff:    Native ARM64 Linux EFI Stub (Milestone 6)"
echo "================================================================="
echo ""

# 3-Second Interactive Startup Countdown Delay
echo "Automatic boot countdown: 3 seconds."
echo "Press any key to pause startup and enter interactive UEFI Shell..."
stall 3000000

# Check for external ESP boot scripts on removable media
if exist fs0:\EFI\R8Q\boot-linux.nsh then
    echo "Found authorized Linux boot script: fs0:\EFI\R8Q\boot-linux.nsh"
    fs0:\EFI\R8Q\boot-linux.nsh
endif

if exist fs1:\EFI\BOOT\BOOTAA64.EFI then
    echo "Found standard UEFI bootloader: fs1:\EFI\BOOT\BOOTAA64.EFI"
    fs1:\EFI\BOOT\BOOTAA64.EFI
endif

echo ""
echo "Interactive R8Q UEFI Shell 2.2 Ready."
echo "Native Linux Boot Command:"
echo "  LinuxBoot.efi     - Launch native ARM64 Linux kernel via EFI Stub"
echo "Diagnostic Commands:"
echo "  diagnostics.efi   - Execute complete 9-suite platform hardware audit"
echo "  sysinfo.efi       - Inspect SoC, board revision, and firmware tables"
echo "  cpuinfo.efi       - Inspect Kryo 585 topology, MIDR, and arch timer"
echo "  memmap.efi        - Inspect 8 GB LPDDR5 DRAM map and carveouts"
echo "  display.efi       - Inspect GOP (1080x2400) and dual-mode console"
echo "  storage.efi       - Inspect storage devices & verify UFS read-only"
echo "  ShellTest.efi     - Run automated Shell 2.2 acceptance test suite"
echo "Scripts:"
echo "  boot-linux.nsh     - Native Linux automated boot sequence"
echo "  hardware-audit.nsh - Execute sequential hardware audit script"
echo "  storage-audit.nsh  - Execute storage safety & write-protection audit"
echo "Type 'help' for built-in UEFI Shell commands."
echo ""
