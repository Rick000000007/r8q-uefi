# Project R8Q UEFI Linux Boot Script
# Platform: Samsung Galaxy S20 FE 5G (SM-G781B)

@echo -off
echo "Initiating Native Linux Boot on Samsung Galaxy S20 FE 5G..."

if exist fs0:\EFI\Linux\Image then
    echo "Found Linux Kernel Image on fs0:\EFI\Linux\Image"
    fs0:\EFI\Linux\Image initrd=fs0:\EFI\Linux\initramfs.img console=tty0 clk_ignore_unused pd_ignore_unused
else
    if exist fs1:\EFI\Linux\Image then
        echo "Found Linux Kernel Image on MicroSD (fs1)"
        fs1:\EFI\Linux\Image initrd=fs1:\EFI\Linux\initramfs.img console=tty0 clk_ignore_unused pd_ignore_unused
    else
        echo "ERROR: Linux kernel Image not found on fs0 or fs1."
    endif
endif
