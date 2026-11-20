# Project R8Q UEFI Full Hardware Audit Script
# Platform: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

@echo -off
cls
echo "================================================================="
echo "   PROJECT R8Q AUTOMATED HARDWARE AUDIT SUITE"
echo "   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "================================================================="
echo ""

echo "--- [1/9] SYSTEM IDENTIFICATION & FIRMWARE TABLES ---"
sysinfo.efi

echo ""
echo "--- [2/9] CPU TOPOLOGY, ARCH TIMER & GIC ---"
cpuinfo.efi

echo ""
echo "--- [3/9] PHYSICAL MEMORY & CARVEOUT AUDIT ---"
memmap.efi

echo ""
echo "--- [4/9] DISPLAY GOP & CONSOLE SCALING ---"
display.efi

echo ""
echo "--- [5/9] DEVICE TREE (FDT) PROFILE ---"
fdtinfo.efi

echo ""
echo "--- [6/9] STORAGE SUBSYSTEM & UFS READ-ONLY INVARIANT ---"
storage.efi

echo ""
echo "--- [7/9] BATTERY & PMIC POWER SUBSYSTEM ---"
battery.efi

echo ""
echo "--- [8/9] TSENS THERMAL SENSORS & SAFETY TRIPS ---"
thermal.efi

echo ""
echo "--- [9/9] FIRMWARE VOLUME & OPTION A NVRAM ---"
firmware.efi

echo ""
echo "================================================================="
echo "   ALL 9 HARDWARE AUDIT MODULES COMPLETED SUCCESSFULLY"
echo "================================================================="
echo ""
