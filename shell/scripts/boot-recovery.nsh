# Project R8Q UEFI Emergency Recovery Boot Script
# Platform: Samsung Galaxy S20 FE 5G (SM-G781B)

@echo -off
echo "Initiating R8Q Emergency Recovery Environment..."

if exist fs0:\EFI\Recovery\recovery.img then
    echo "Found Recovery Image on fs0. Launching..."
    fs0:\EFI\Recovery\recovery.img console=tty0 clk_ignore_unused pd_ignore_unused recovery_mode=1
else
    echo "WARNING: Recovery image not found. Entering recovery shell..."
    recovery
endif
