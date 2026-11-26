#!/usr/bin/env bash
# Project R8Q — Safe Rollback & Recovery Orchestrator
# Physical block writes remain strictly locked unless explicitly authorized with verified backups.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config/device.conf
source "$SCRIPT_DIR/config/device.conf"
# shellcheck source=config/partition-map.conf
source "$SCRIPT_DIR/config/partition-map.conf"

MODE="plan"
BACKUP_IMG=""
TARGET_PART=""
ALLOW_FLASH=0

usage() {
    cat << 'EOF'
Usage: uninstall-or-rollback.sh [OPTIONS]

Non-destructive Project R8Q rollback & recovery verification utility.
Preserves Android/LineageOS boot (sda23) and Knox Keyrefuge (sda25).

Options:
  --plan                      Display multi-tier recovery & rollback plan (no writes)
  --verify-backup <img_path>  Verify recovery partition backup (82,694,144 bytes) integrity
  --target-partition <node>   Target recovery node for verification (sda25/sda23 forbidden)
  --help                      Show usage
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --plan) MODE="plan"; shift ;;
        --verify-backup) BACKUP_IMG="${2:-}"; shift 2 ;;
        --target-partition) TARGET_PART="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "[ERROR] Unknown option: $1" >&2; exit 2 ;;
    esac
done

echo "================================================================="
echo "   PROJECT R8Q: ROLLBACK & HARDWARE RECOVERY VERIFIER"
echo "================================================================="
echo "Tier 1 (Default): Normal boot (Power button without Vol Up) boots untouched sda23 (LineageOS)."
echo "Tier 2 (Recovery Backup): Restore verified 82,694,144-byte backup to sda24 only after audit."
echo "Tier 3 (Download Mode): Vol Up + Vol Down + USB -> Heimdall / Odin3 factory restore."
echo "Strict Policy: /dev/block/sda25 (keyrefuge) and /dev/block/sda (whole disk) NEVER accessed."

if [ -n "$TARGET_PART" ]; then
    R8Q_TARGET_PARTITION="$TARGET_PART" "$SCRIPT_DIR/verify-device.sh" --mode verify --target-profile r8q --target-partition "$TARGET_PART" || exit $?
fi

if [ -n "$BACKUP_IMG" ]; then
    [ -f "$BACKUP_IMG" ] || { echo "[ERROR] Backup image missing: $BACKUP_IMG" >&2; exit 3; }
    SIZE="$(stat -c '%s' "$BACKUP_IMG" 2>/dev/null || wc -c < "$BACKUP_IMG")"
    [ "$SIZE" -eq "$SDA24_BYTES" ] || {
        echo "[ERROR] Backup size mismatch: got $SIZE B, expected exact sda24 size $SDA24_BYTES B." >&2
        exit 4
    }
    echo "[PASS] Backup image geometry verified ($SIZE bytes). SHA-256: $(sha256sum "$BACKUP_IMG" | awk '{print $1}')"
fi

if [ "$ALLOW_FLASH" -eq 0 ]; then
    echo "[SAFE] Physical partition restoration remains disabled; no storage writes performed."
fi
