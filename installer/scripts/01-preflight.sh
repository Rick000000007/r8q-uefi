#!/bin/sh
# Stage 01 [Steps 1-5]: Environment, root privilege, device/arch, storage & firmware preflight
set -eu

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-verify}"
# shellcheck source=lib-common.sh
. "$ROOT/scripts/lib-common.sh"
# shellcheck source=../config/device.conf
. "$ROOT/config/device.conf"

SH_BIN="$(r8q_detect_sh)"

echo "[STAGE 01/11] [STEP 1/19] Checking execution environment & root privilege policy..."
UID_NOW="$(id -u 2>/dev/null || echo 1000)"
if [ "$MODE" = "install" ]; then
    if [ "${CI:-}" = "true" ] || [ "${GITHUB_ACTIONS:-}" = "true" ]; then
        echo "[ERROR] Refusing --install inside CI environment." >&2
        exit 30
    fi
    if [ "$UID_NOW" -ne 0 ] && [ "$REQUIRE_ROOT_FOR_INSTALL" -eq 1 ]; then
        echo "[ERROR] --install requires root privileges (uid=0), current uid=$UID_NOW." >&2
        exit 31
    fi
fi

# Require only POSIX / TWRP recovery standard tools (zero bash or python3 dependency)
for tool in sh sha256sum gzip tar cpio dd od wc awk df; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "[ERROR] Required installation utility missing: $tool" >&2
        exit 32
    }
done

echo "[STAGE 01/11] [STEPS 2-4/19] Running SM-G781B / r8q, ARM64 & storage preflight checks..."
if [ "${R8Q_SIMULATE_PROFILE:-}" = "r8q" ]; then
    "$SH_BIN" "$ROOT/verify-device.sh" --mode "$MODE" --target-profile r8q
else
    "$SH_BIN" "$ROOT/verify-device.sh" --mode "$MODE"
fi

echo "[STAGE 01/11] [STEP 5/19] Verifying firmware and bootloader prerequisite payloads exist..."
for req in \
    "$ROOT/payload/firmware/R8Q_EFI.fd" \
    "$ROOT/payload/firmware/r8q-uefi-boot-complete.img" \
    "$ROOT/payload/boot-manager/BootManager.efi" \
    "$ROOT/payload/setup/Setup.efi"; do
    [ -s "$req" ] || { echo "[ERROR] Missing firmware/bootloader prerequisite: $req" >&2; exit 33; }
done

echo "[STAGE 01/11] Preflight checks PASSED."
