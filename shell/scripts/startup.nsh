# Project R8Q UEFI Startup Automation Script
# Platform: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

@echo -off
cls
echo "================================================================="
echo "   PROJECT R8Q UEFI FIRMWARE - MULTI-OS PLATFORM ENGINE"
echo "   Device: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)"
echo "   Architecture: ARMv8.2-A (AArch64) | 8 GB LPDDR5 | UFS 3.1"
echo "================================================================="
echo ""

# Probe for automated boot countdown
echo "Press any key within 3 seconds to enter interactive UEFI Shell..."
stall 3000000

# If user did not interrupt, check for default boot script on ESP
if exist fs0:\EFI\R8Q\boot-linux.nsh then
    echo "Executing default boot script fs0:\EFI\R8Q\boot-linux.nsh..."
    fs0:\EFI\R8Q\boot-linux.nsh
endif

if exist fs1:\EFI\BOOT\BOOTAA64.EFI then
    echo "Found external UEFI bootloader on fs1. Launching..."
    fs1:\EFI\BOOT\BOOTAA64.EFI
endif

echo "Dropping into interactive R8Q Shell..."
echo "Type 'diagnostics' to run full hardware audit."
echo "Type 'help' for standard UEFI commands."
echo ""
