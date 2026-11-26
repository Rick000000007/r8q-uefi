#!/usr/bin/env bash
# Stage 01 [Steps 1-5]: Execution environment, root/device/SoC/storage & firmware preflight
set -euo pipefail

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-verify}"

# shellcheck source=../config/device.conf
source "$ROOT/config/device.conf"

echo "[STAGE 01/11] [STEP 1/19] Detecting execution environment ($MODE) and privileges..."
echo "  Pipeline Token: ${R8Q_PIPELINE_TOKEN:-unset}"
echo "  User ID: $(id -u) ($(id -un)) | Kernel: $(uname -s) $(uname -m)"

if [ "$MODE" = "install" ]; then
    if [ "${CI:-}" = "true" ] || [ "${GITHUB_ACTIONS:-}" = "true" ]; then
        echo "[SECURITY-ABORT] --install physical execution is forbidden inside CI/CD environments." >&2
        exit 30
    fi
    if [ "$REQUIRE_ROOT_FOR_INSTALL" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
        echo "[ERROR] Root privileges (uid 0) are required for --install mode." >&2
        exit 31
    fi
fi

for tool in bash python3 sha256sum gzip tar df; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "[ERROR] Required system tool not found: $tool" >&2
        exit 32
    }
done

echo "[STAGE 01/11] [STEPS 2-4/19] Identifying Samsung SM-G781B/r8q, SM8250/ARM64, and storage headroom..."
ARGS=(--mode "$MODE")
[ "${R8Q_SIMULATE_PROFILE:-}" = "r8q" ] && ARGS+=(--target-profile r8q)
[ -n "${R8Q_DEVICE_MODEL:-}" ] && ARGS+=(--device-model "$R8Q_DEVICE_MODEL")
[ -n "${R8Q_DEVICE_CODENAME:-}" ] && ARGS+=(--device-codename "$R8Q_DEVICE_CODENAME")
[ -n "${R8Q_DEVICE_ARCH:-}" ] && ARGS+=(--arch "$R8Q_DEVICE_ARCH")
[ -n "${R8Q_DEVICE_SOC:-}" ] && ARGS+=(--soc "$R8Q_DEVICE_SOC")
[ -n "${R8Q_TARGET_PARTITION:-}" ] && ARGS+=(--target-partition "$R8Q_TARGET_PARTITION")
[ -n "${R8Q_PARTITION_MAP_FILE:-}" ] && ARGS+=(--partition-map "$R8Q_PARTITION_MAP_FILE")
[ -n "${R8Q_MIN_SPACE_BYTES:-}" ] && ARGS+=(--min-space-bytes "$R8Q_MIN_SPACE_BYTES")
[ -n "${R8Q_SPACE_CHECK_DIR:-}" ] && ARGS+=(--check-space-dir "$R8Q_SPACE_CHECK_DIR")

"$ROOT/verify-device.sh" "${ARGS[@]}"

echo "[STAGE 01/11] [STEP 5/19] Verifying firmware and bootloader prerequisite payloads exist..."
for req in \
    "$ROOT/payload/firmware/R8Q_EFI.fd" \
    "$ROOT/payload/firmware/r8q-uefi-boot-complete.img" \
    "$ROOT/payload/boot-manager/BootManager.efi" \
    "$ROOT/payload/setup/Setup.efi"; do
    [ -s "$req" ] || { echo "[ERROR] Missing firmware/bootloader prerequisite: $req" >&2; exit 33; }
done

echo "[STAGE 01/11] Preflight checks PASSED."
