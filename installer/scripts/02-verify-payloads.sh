#!/usr/bin/env bash
# Stage 02 [Step 6]: Cryptographic SHA-256 verification of every payload and manifest entry
set -euo pipefail

[ "${R8Q_STAGE_DONE_01:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 01-preflight.sh must complete before 02-verify-payloads.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
echo "[STAGE 02/11] [STEP 6/19] Verifying SHA-256 checksums and MANIFEST.json integrity..."
"$ROOT/verify-checksums.sh"
echo "[STAGE 02/11] Payload checksum verification PASSED."
