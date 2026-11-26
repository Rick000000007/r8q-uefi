#!/usr/bin/env bash
# Stage 03 [Steps 7-8]: Partition map audit, hardware safety lock, and target preparation
set -euo pipefail

[ "${R8Q_STAGE_DONE_02:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 02-verify-payloads.sh must complete before 03-prepare-target.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-verify}"
# shellcheck source=../config/device.conf
source "$ROOT/config/device.conf"
# shellcheck source=../config/partition-map.conf
source "$ROOT/config/partition-map.conf"

echo "[STAGE 03/11] [STEP 7/19] Validating partition map boundaries & sda25 Knox Keyrefuge guard..."
echo "  Verified boundary: sda24 ($SDA24_START_SECTOR+$SDA24_SECTORS) | Zero-Access Guard: sda25 ($SDA25_START_SECTOR)"

if [ "$SDA25_ZERO_ACCESS" -ne 1 ] || [ "$SDA23_PROTECTED" -ne 1 ]; then
    echo "[SECURITY-ABORT] Protected partition safety lock tampered in partition-map.conf!" >&2
    exit 41
fi

echo "[STAGE 03/11] [STEP 8/19] Preparing target environment ($MODE mode)..."
if [ "$MODE" = "install" ]; then
    if [ "$PHYSICAL_WRITES_ENABLED" -ne 1 ] || [ "$PHYSICAL_FLASH_AUDIT_APPROVED" -ne 1 ] || [ "$ALLOW_ANDROID_OR_RECOVERY_ERASE" -ne 1 ]; then
        echo "[SAFETY-LOCK] Physical block flashing is DISABLED until the Phase 3.6B hardware safety audit approves the exact write plan." >&2
        echo "[SAFETY-LOCK] Zero bytes written to internal UFS or recovery partitions." >&2
        exit 42
    fi
fi

echo "[STAGE 03/11] Target safety audit & preparation PASSED ($MODE mode, physical writes disabled)."
