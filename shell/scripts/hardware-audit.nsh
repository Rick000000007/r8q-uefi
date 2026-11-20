# Project R8Q UEFI Hardware Audit Script
# Platform: Samsung Galaxy S20 FE 5G (SM-G781B)

@echo -off
cls
echo "================================================="
echo "   PROJECT R8Q AUTOMATED HARDWARE AUDIT"
echo "================================================="
echo ""

echo "--- [1/6] SYSTEM INFORMATION ---"
sysinfo

echo ""
echo "--- [2/6] CPU TOPOLOGY & ARCH TIMER ---"
cpuinfo

echo ""
echo "--- [3/6] PHYSICAL MEMORY & RESERVED CARVEOUTS ---"
memmap

echo ""
echo "--- [4/6] STORAGE LUNS & PARTITIONS ---"
storage
partitions

echo ""
echo "--- [5/6] DISPLAY GOP & AMOEL PANEL ---"
display

echo ""
echo "--- [6/6] BATTERY & THERMAL SENSORS ---"
battery
thermal

echo ""
echo "Hardware audit complete."
