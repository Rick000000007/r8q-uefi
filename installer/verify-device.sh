#!/usr/bin/env bash
# Project R8Q — Target Device, Architecture, Partition Map & Hardware Safety Verifier
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config/device.conf
source "$SCRIPT_DIR/config/device.conf"
# shellcheck source=config/partition-map.conf
source "$SCRIPT_DIR/config/partition-map.conf"

MODE="verify"
SIMULATE_TARGET=0
DEVICE_MODEL_OVERRIDE="${R8Q_DEVICE_MODEL:-}"
DEVICE_CODENAME_OVERRIDE="${R8Q_DEVICE_CODENAME:-}"
DEVICE_ARCH_OVERRIDE="${R8Q_DEVICE_ARCH:-}"
DEVICE_SOC_OVERRIDE="${R8Q_DEVICE_SOC:-}"
TARGET_PARTITION="${R8Q_TARGET_PARTITION:-}"
PARTITION_MAP_FILE="${R8Q_PARTITION_MAP_FILE:-}"
MIN_SPACE_OVERRIDE="${R8Q_MIN_SPACE_BYTES:-}"
SPACE_CHECK_DIR="${R8Q_SPACE_CHECK_DIR:-$SCRIPT_DIR}"
ALLOW_WORKSTATION_DRYRUN="${R8Q_WORKSTATION_DRYRUN:-0}"

usage() {
    cat << 'EOF'
Usage: verify-device.sh [OPTIONS]

Validates Samsung Galaxy S20 FE 5G (SM-G781B / r8q), Qualcomm SM8250 / ARM64,
storage headroom, and hardware safety guards against protected partitions.

Options:
  --target-profile r8q       Evaluate against validated SM-G781B (r8q) profile
                             (allowed only in --verify/--dry-run checks, never --install)
  --device-model <model>     Override/test detected device model string
  --device-codename <code>   Override/test detected device codename
  --arch <arch>              Override/test CPU architecture (must match aarch64)
  --soc <compatible>         Override/test SoC compatible string (must match sm8250)
  --target-partition <node>  Validate proposed target partition against safety exclusions
  --partition-map <file>     Path to independently verified partition map file
  --min-space-bytes <bytes>  Minimum required free bytes for staging/installation
  --check-space-dir <dir>    Directory used to check free storage capacity
  --mode <verify|dry-run|install>
  --help                     Show this help
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --target-profile)
            [ "${2:-}" = "r8q" ] || { echo "[ERROR] Unsupported target profile: ${2:-}" >&2; exit 2; }
            SIMULATE_TARGET=1
            shift 2
            ;;
        --device-model)
            DEVICE_MODEL_OVERRIDE="${2:-}"
            shift 2
            ;;
        --device-codename)
            DEVICE_CODENAME_OVERRIDE="${2:-}"
            shift 2
            ;;
        --arch)
            DEVICE_ARCH_OVERRIDE="${2:-}"
            shift 2
            ;;
        --soc)
            DEVICE_SOC_OVERRIDE="${2:-}"
            shift 2
            ;;
        --target-partition)
            TARGET_PARTITION="${2:-}"
            shift 2
            ;;
        --partition-map)
            PARTITION_MAP_FILE="${2:-}"
            shift 2
            ;;
        --min-space-bytes)
            MIN_SPACE_OVERRIDE="${2:-}"
            shift 2
            ;;
        --check-space-dir)
            SPACE_CHECK_DIR="${2:-}"
            shift 2
            ;;
        --mode)
            MODE="${2:-verify}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "[ERROR] Unknown option: $1" >&2
            exit 2
            ;;
    esac
done

detect_live_device() {
    LIVE_ARCH="$(uname -m)"
    LIVE_CODENAME=""
    LIVE_MODEL=""
    LIVE_SOC=""

    if command -v getprop >/dev/null 2>&1; then
        LIVE_CODENAME="$(getprop ro.product.device 2>/dev/null || getprop ro.build.product 2>/dev/null || true)"
        LIVE_MODEL="$(getprop ro.product.model 2>/dev/null || getprop ro.product.system.model 2>/dev/null || true)"
    fi
    if [ -r /proc/device-tree/compatible ]; then
        LIVE_SOC="$(tr '\0' ' ' < /proc/device-tree/compatible 2>/dev/null || true)"
    elif [ -r /sys/firmware/devicetree/base/compatible ]; then
        LIVE_SOC="$(tr '\0' ' ' < /sys/firmware/devicetree/base/compatible 2>/dev/null || true)"
    fi
    if [ -z "$LIVE_MODEL" ] && [ -r /proc/device-tree/model ]; then
        LIVE_MODEL="$(tr '\0' ' ' < /proc/device-tree/model 2>/dev/null || true)"
    fi
    if [ -z "$LIVE_CODENAME" ]; then
        case "${LIVE_SOC}:${LIVE_MODEL}" in
            *samsung,r8q*|*"Samsung R8Q EUR"*) LIVE_CODENAME="r8q" ;;
        esac
    fi
}

detect_live_device

# Determine effective values, never silently accepting wrong overrides or non-target --install hosts
ARCH_TO_CHECK="${DEVICE_ARCH_OVERRIDE:-$LIVE_ARCH}"
CODENAME_TO_CHECK="${DEVICE_CODENAME_OVERRIDE:-$LIVE_CODENAME}"
MODEL_TO_CHECK="${DEVICE_MODEL_OVERRIDE:-$LIVE_MODEL}"
SOC_TO_CHECK="${DEVICE_SOC_OVERRIDE:-$LIVE_SOC}"

IS_SIMULATED_ALLOWED=0
if [ "$MODE" = "dry-run" ] && [ "$ALLOW_WORKSTATION_DRYRUN" = "1" ]; then
    IS_SIMULATED_ALLOWED=1
elif [ "$SIMULATE_TARGET" -eq 1 ] && [ "$MODE" != "install" ]; then
    IS_SIMULATED_ALLOWED=1
fi

if [ "$IS_SIMULATED_ALLOWED" -eq 1 ] && \
   [ -z "$DEVICE_MODEL_OVERRIDE" ] && \
   [ -z "$DEVICE_CODENAME_OVERRIDE" ] && \
   [ -z "$DEVICE_ARCH_OVERRIDE" ] && \
   [ -z "$DEVICE_SOC_OVERRIDE" ] && \
   { [ "$LIVE_ARCH" != "$TARGET_ARCH" ] || [ -z "$CODENAME_TO_CHECK" ] || [ -z "$MODEL_TO_CHECK" ]; }; then
    echo "[NOTE] Non-target host ($LIVE_ARCH) detected; validating target profile SM-G781B (r8q / SM8250 / aarch64) in $MODE mode."
    ARCH_TO_CHECK="$TARGET_ARCH"
    CODENAME_TO_CHECK="$TARGET_CODENAME"
    MODEL_TO_CHECK="SM-G781B"
    SOC_TO_CHECK="$TARGET_SOC_COMPATIBLE"
fi

echo "[DEVICE-CHECK] Architecture: $ARCH_TO_CHECK (required: $TARGET_ARCH)"
if [ "$ARCH_TO_CHECK" != "$TARGET_ARCH" ]; then
    echo "[ERROR] Architecture mismatch: expected '$TARGET_ARCH' (ARM64), found '$ARCH_TO_CHECK'." >&2
    exit 10
fi

CODENAME_OK=0
for c in $SUPPORTED_CODENAMES; do
    if [ "$CODENAME_TO_CHECK" = "$c" ]; then
        CODENAME_OK=1
        break
    fi
done
MODEL_OK=0
case "$MODEL_TO_CHECK" in
    *SM-G781B*|*G781B*|*"Samsung R8Q EUR"*) MODEL_OK=1 ;;
esac

echo "[DEVICE-CHECK] Device Codename: '${CODENAME_TO_CHECK:-<none>}' | Model: '${MODEL_TO_CHECK:-<none>}'"
if [ "$CODENAME_OK" -ne 1 ] || [ "$MODEL_OK" -ne 1 ]; then
    echo "[ERROR] Unsupported or mismatched device: expected Samsung SM-G781B (r8q), found model='${MODEL_TO_CHECK:-unknown}', codename='${CODENAME_TO_CHECK:-unknown}'." >&2
    exit 11
fi

echo "[DEVICE-CHECK] SoC Platform: '${SOC_TO_CHECK:-<none>}'"
case "$SOC_TO_CHECK" in
    *sm8250*|*SM8250*|*kona*) ;;
    *)
        echo "[ERROR] SoC mismatch: expected Qualcomm Snapdragon 865 ($TARGET_SOC_COMPATIBLE), found '${SOC_TO_CHECK:-unknown}'." >&2
        exit 12
        ;;
esac

# Check available free storage headroom cleanly
REQ_FREE="${MIN_SPACE_OVERRIDE:-$MIN_TOTAL_INSTALL_FREE_BYTES}"
AVAIL_BYTES="$(df -PB1 "$SPACE_CHECK_DIR" | awk 'NR==2 {print $4}')"
echo "[STORAGE-CHECK] Available space in '$SPACE_CHECK_DIR': $AVAIL_BYTES bytes (required: $REQ_FREE bytes)"
if [ -z "$AVAIL_BYTES" ] || [ "$AVAIL_BYTES" -lt "$REQ_FREE" ]; then
    echo "[ERROR] Insufficient storage space: available $AVAIL_BYTES B < required $REQ_FREE B." >&2
    exit 13
fi

# Strict partition target and protection check
if [ -n "$TARGET_PARTITION" ]; then
    LOWER_PART="$(printf '%s' "$TARGET_PARTITION" | tr '[:upper:]' '[:lower:]')"
    BASE_PART="$(basename "$LOWER_PART")"
    case "$LOWER_PART" in
        *sda25*|*keyrefuge*|*sda26*|*keydata*|*sda27*|*vbmeta*|*sda23*|*by-name/boot*|*sda21*|*sda22*|*/dev/block/sda|sda)
            echo "[SECURITY-ABORT] Refusing protected or whole-disk target partition: '$TARGET_PARTITION'." >&2
            exit 14
            ;;
    esac
    for forbidden in $FORBIDDEN_TARGETS; do
        if [ "$LOWER_PART" = "$forbidden" ] || [ "$BASE_PART" = "$forbidden" ]; then
            echo "[SECURITY-ABORT] Target '$TARGET_PARTITION' is explicitly forbidden by hardware safety policy." >&2
            exit 14
        fi
    done

    # Do not assume sda24 or Android/recovery partitions are safe without independent map + authorization
    if [ "$ALLOW_ANDROID_OR_RECOVERY_ERASE" -ne 1 ] || [ "$PHYSICAL_FLASH_AUDIT_APPROVED" -ne 1 ]; then
        echo "[SAFETY-GATE] Partition '$TARGET_PARTITION' requires an independently verified partition map and explicit hardware audit authorization before writing." >&2
        if [ "$MODE" = "install" ]; then
            exit 15
        fi
    fi
fi

# Validate independently provided partition map if supplied, or required in install mode
if [ -n "$PARTITION_MAP_FILE" ]; then
    [ -f "$PARTITION_MAP_FILE" ] || { echo "[ERROR] Partition map file not found: $PARTITION_MAP_FILE" >&2; exit 16; }
    python3 -B - "$PARTITION_MAP_FILE" "$SDA23_START_SECTOR" "$SDA23_SECTORS" "$SDA24_START_SECTOR" "$SDA24_SECTORS" "$SDA25_START_SECTOR" "$SDA25_SECTORS" << 'PYEOF'
import json, sys
path = sys.argv[1]
s23, n23, s24, n24, s25, n25 = [int(x) for x in sys.argv[2:8]]
with open(path, "r", encoding="utf-8") as f:
    pmap = json.load(f)
for name, start, sectors in [("sda23", s23, n23), ("sda24", s24, n24), ("sda25", s25, n25)]:
    entry = pmap.get(name)
    if not entry or int(entry.get("start", -1)) != start or int(entry.get("sectors", -1)) != sectors:
        print(f"[ERROR] Partition map mismatch or missing entry for {name}: {entry}", file=sys.stderr)
        sys.exit(17)
if s23 + n23 != s24 or s24 + n24 != s25:
    print("[ERROR] Partition contiguity sanity invariant violated", file=sys.stderr)
    sys.exit(17)
print("[PASS] Independent partition map matches SM8250 sda23/sda24/sda25 zero-gap boundary table.")
PYEOF
elif [ "$MODE" = "install" ]; then
    if [ -r /sys/block/sda/sda24/start ] && [ -r /sys/block/sda/sda25/start ]; then
        echo "[DEVICE-CHECK] Live sysfs partition nodes present; auditing geometry..."
        [ "$(cat /sys/block/sda/sda24/start)" -eq "$SDA24_START_SECTOR" ] || { echo "[ERROR] Live sda24 start mismatch!" >&2; exit 17; }
        [ "$(cat /sys/block/sda/sda24/size)" -eq "$SDA24_SECTORS" ] || { echo "[ERROR] Live sda24 size mismatch!" >&2; exit 17; }
        [ "$(cat /sys/block/sda/sda25/start)" -eq "$SDA25_START_SECTOR" ] || { echo "[ERROR] Live sda25 boundary mismatch!" >&2; exit 17; }
    else
        echo "[ERROR] --install requires either live verified /sys/block/sda partition sysfs or --partition-map <verified.json>." >&2
        exit 16
    fi
fi

echo "[PASS] Device and hardware safety checks passed (mode=$MODE, physical writes remain locked)."
