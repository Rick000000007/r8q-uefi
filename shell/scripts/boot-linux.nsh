# Project R8Q UEFI Linux Boot Script
# Platform: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
# Subsystem: Native ARM64 Linux EFI Stub Handoff

@echo -off
cls
echo "================================================================="
echo "   PROJECT R8Q NATIVE LINUX BOOT ENGINE (MILESTONE 6)"
echo "   Target Device: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "   SoC:           Qualcomm Snapdragon 865 (SM8250 / Kona)"
echo "   Standard:      Native ARM64 Linux EFI Stub (PE/COFF 0xAA64)"
echo "================================================================="
echo ""

echo "Checking for dedicated Linux Bootloader Application (LinuxBoot.efi)..."
LinuxBoot.efi

if exist fs0:\EFI\Linux\Image then
    echo "Direct EFI Stub fallback: fs0:\EFI\Linux\Image"
    fs0:\EFI\Linux\Image console=tty0 console=ttyHS8,115200n8 earlycon=msm_geni_serial,0x00A90000 clk_ignore_unused pd_ignore_unused root=/dev/ram0 rw
else
    if exist fs1:\EFI\Linux\Image then
        echo "Direct EFI Stub fallback on MicroSD (fs1)"
        fs1:\EFI\Linux\Image console=tty0 console=ttyHS8,115200n8 earlycon=msm_geni_serial,0x00A90000 clk_ignore_unused pd_ignore_unused root=/dev/ram0 rw
    endif
endif
