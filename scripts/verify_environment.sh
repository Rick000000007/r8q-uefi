#!/usr/bin/env bash
# Project R8Q UEFI: Environment & Toolchain Verification Script
# Platform: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)

set -e

echo "=== PROJECT R8Q UEFI: ENVIRONMENT VERIFICATION ==="
ERRORS=0

check_tool() {
    local cmd="$1"
    local name="$2"
    if which "$cmd" > /dev/null 2>&1; then
        echo "[PASS] $name found: $(which "$cmd")"
    else
        echo "[FAIL] $name NOT found ($cmd)"
        ERRORS=$((ERRORS + 1))
    fi
}

check_tool gcc "Native GCC Compiler"
check_tool clang "Clang Compiler"
check_tool make "GNU Make"
check_tool dtc "Device Tree Compiler"
check_tool iasl "ACPI iASL Compiler"
check_tool git "Git SCM"
check_tool python3 "Python 3 Engine"

echo ""
echo "=== TOOL VERSIONS ==="
gcc --version | head -n 1
clang --version | head -n 1
dtc --version
iasl -v | head -n 1

echo ""
echo "=== TARGET HARDWARE VERIFICATION ==="
if [ -f "/sys/firmware/devicetree/base/model" ]; then
    MODEL=$(tr -d '\0' < /sys/firmware/devicetree/base/model)
    echo "[PASS] Hardware Device Model: $MODEL"
else
    echo "[WARN] /sys/firmware/devicetree/base/model not found (non-live host?)"
fi

if [ -f "/sys/devices/soc0/soc_id" ]; then
    SOC_ID=$(cat /sys/devices/soc0/soc_id)
    echo "[PASS] Qualcomm SoC ID: $SOC_ID (Expected: 356 for SM8250)"
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo ">>> ALL ENVIRONMENT VERIFICATION CHECKS PASSED <<<"
    exit 0
else
    echo ">>> VERIFICATION FAILED WITH $ERRORS ERRORS <<<"
    exit 1
fi
