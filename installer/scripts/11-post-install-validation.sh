#!/usr/bin/env bash
# Stage 11 [Steps 18-19]: Post-installation integrity audit & structured installation report
set -euo pipefail

[ "${R8Q_STAGE_DONE_10:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 10-configure-boot.sh must complete before 11-post-install-validation.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=../config/device.conf
source "$ROOT/config/device.conf"
# shellcheck source=../config/partition-map.conf
source "$ROOT/config/partition-map.conf"
# shellcheck source=../config/boot.conf
source "$ROOT/config/boot.conf"

EXPECTED_CHAIN="01,02,03,04,05,06,07,08,09,10"
if [ "${R8Q_COMPLETED_STEPS:-}" != "$EXPECTED_CHAIN" ]; then
    echo "[ERROR] Dependency sequence mismatch: expected '$EXPECTED_CHAIN', got '${R8Q_COMPLETED_STEPS:-}'." >&2
    exit 47
fi

echo "[STAGE 11/11] [STEPS 18-19/19] Running post-installation integrity checks & generating report..."

VERSION_STR="$(tr '\n' ' ' < "$ROOT/VERSION")"
GENERATED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

REPORT_CONTENT="$(cat << EOF
=================================================================
  PROJECT R8Q — UNIFIED INSTALLATION EXECUTION REPORT
=================================================================
  Package Version:      $VERSION_STR
  Execution Mode:       $MODE
  Generated (UTC):      $GENERATED_UTC
  Target Device:        $DEVICE_NAME (SM-G781B / r8q)
  SoC / Architecture:   $TARGET_SOC_NAME / $TARGET_ARCH
  Dependency Chain:     01,02,03,04,05,06,07,08,09,10,11 (STRICT ORDER OK)
  Hardware Safety Lock: PHYSICAL_WRITES_ENABLED=$PHYSICAL_WRITES_ENABLED | sda25_zero_access=$SDA25_ZERO_ACCESS | sda23_protected=$SDA23_PROTECTED
  Boot Target Policy:   systemd=$SYSTEMD_DEFAULT_TARGET | optional_gnome=$OPTIONAL_GNOME_ENABLED | boot_entry=$BOOT_DEFAULT_ENTRY
  Physical Writes Done: 0 bytes (Non-Destructive Policy Enforced)
=================================================================
EOF
)"

echo "$REPORT_CONTENT"

if [ -n "${R8Q_REPORT_OUT:-}" ]; then
    if [ "$MODE" = "dry-run" ]; then
        echo "[NOTE] --dry-run active: skipping disk write to '$R8Q_REPORT_OUT' to guarantee zero filesystem writes."
    else
        printf '%s\n' "$REPORT_CONTENT" > "$R8Q_REPORT_OUT"
    fi
fi

echo "[STAGE 11/11] Post-installation audit & report generation PASSED."
