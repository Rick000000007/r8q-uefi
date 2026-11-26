#!/bin/sh
# Stage 02 [Step 6]: Cryptographic SHA-256 verification of every payload and manifest entry
set -eu

[ "${R8Q_STAGE_DONE_01:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 01-preflight.sh must complete before 02-verify-payloads.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
# shellcheck source=lib-common.sh
. "$ROOT/scripts/lib-common.sh"
SH_BIN="$(r8q_detect_sh)"

echo "[STAGE 02/11] [STEP 6/19] Verifying SHA-256 checksums and MANIFEST.json integrity..."
"$SH_BIN" "$ROOT/verify-checksums.sh"
echo "[STAGE 02/11] Payload checksum verification PASSED."
