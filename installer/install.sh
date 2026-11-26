#!/bin/sh
# Project R8Q — Master 19-Step Debian 12 ARM64 Installer Orchestrator
# Compatible with TWRP recovery (/sbin/sh / BusyBox ash / mksh) and Linux workstations.
set -eu

R8Q_INSTALLER_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export R8Q_INSTALLER_ROOT
# shellcheck source=scripts/lib-common.sh
. "$R8Q_INSTALLER_ROOT/scripts/lib-common.sh"

R8Q_SH_BIN="$(r8q_detect_sh)" || {
    echo "[FATAL] No POSIX sh interpreter found." >&2
    exit 127
}
export R8Q_SH_BIN

export R8Q_MODE=""
export R8Q_SIMULATE_PROFILE="${R8Q_SIMULATE_PROFILE:-}"
export R8Q_DEVICE_MODEL="${R8Q_DEVICE_MODEL:-}"
export R8Q_DEVICE_CODENAME="${R8Q_DEVICE_CODENAME:-}"
export R8Q_DEVICE_ARCH="${R8Q_DEVICE_ARCH:-}"
export R8Q_DEVICE_SOC="${R8Q_DEVICE_SOC:-}"
export R8Q_TARGET_PARTITION="${R8Q_TARGET_PARTITION:-}"
export R8Q_PARTITION_MAP_FILE="${R8Q_PARTITION_MAP_FILE:-}"
export R8Q_MIN_SPACE_BYTES="${R8Q_MIN_SPACE_BYTES:-}"
export R8Q_SPACE_CHECK_DIR="${R8Q_SPACE_CHECK_DIR:-}"
export R8Q_REPORT_OUT="${R8Q_REPORT_OUT:-}"
export R8Q_WORKSTATION_DRYRUN=0
SIMULATE_PROFILE=""

show_help() {
    cat << 'EOF'
Project R8Q — Unified Debian 12 ARM64 Installation Utility

Usage:
  ./install.sh --dry-run [OPTIONS]   Simulate all 19 installation stages with zero storage writes
  ./install.sh --verify  [OPTIONS]   Verify device compatibility, partition safety, and all payloads
  ./install.sh --install [OPTIONS]   Perform installation (enforces root, live hardware & safety audit lock)
  ./install.sh --help                Display this help message

Options:
  --target-profile r8q       Use SM-G781B/r8q profile for workstation --verify (disallowed for --install)
  --device-model <model>     Explicit/test device model (e.g., SM-G781B)
  --device-codename <code>   Explicit/test device codename (e.g., r8q)
  --arch <arch>              Explicit/test architecture (aarch64)
  --soc <compatible>         Explicit/test SoC string (qcom,sm8250)
  --target-partition <node>  Explicit target block partition to audit against protection list
  --partition-map <file>     Independently verified partition map JSON file
  --min-space-bytes <bytes>  Minimum required free space threshold
  --check-space-dir <dir>    Directory checked for available storage headroom
  --report-file <path>       Optional path for structured report output

Mandatory Stage Execution Order (halt immediately on error):
  01-preflight.sh               [Steps 1-5]  Env/root, SM-G781B/r8q, SM8250/ARM64, storage, firmware prereqs
  02-verify-payloads.sh         [Step 6]     Verify every payload SHA-256 and manifest entry
  03-prepare-target.sh          [Steps 7-8]  Validate partition mappings, sda25 guard, prepare target plan
  04-install-firmware.sh        [Step 9]     Validate & install firmware components (R8Q_EFI.fd)
  05-install-uefi.sh            [Step 10]    Validate & install UEFI apps & BootManager/Setup
  06-install-esp.sh             [Step 11]    Validate & install 256 MiB FAT32 ESP & EFI scripts
  07-install-kernel.sh          [Step 12]    Validate & install ARM64 Linux kernel & matching DTB
  08-install-initramfs.sh       [Step 13]    Validate & install initramfs & kernel modules
  09-install-rootfs.sh          [Step 14]    Validate & install Debian 12 ARM64 root filesystem
  10-configure-boot.sh          [Steps 15-17] Configure terminal-first systemd, optional GNOME, boot entries
  11-post-install-validation.sh [Steps 18-19] Run post-install checks & generate installation report
EOF
}

if [ $# -eq 0 ]; then
    show_help >&2
    echo "[ERROR] Explicit mode flag required (--dry-run, --verify, --install, or --help)." >&2
    exit 2
fi

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)
            [ -z "$R8Q_MODE" ] || { echo "[ERROR] Multiple modes specified." >&2; exit 2; }
            R8Q_MODE="dry-run"
            R8Q_WORKSTATION_DRYRUN=1
            shift
            ;;
        --verify)
            [ -z "$R8Q_MODE" ] || { echo "[ERROR] Multiple modes specified." >&2; exit 2; }
            R8Q_MODE="verify"
            shift
            ;;
        --install)
            [ -z "$R8Q_MODE" ] || { echo "[ERROR] Multiple modes specified." >&2; exit 2; }
            R8Q_MODE="install"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        --target-profile)
            SIMULATE_PROFILE="${2:-}"
            shift 2
            ;;
        --device-model)
            R8Q_DEVICE_MODEL="${2:-}"
            shift 2
            ;;
        --device-codename)
            R8Q_DEVICE_CODENAME="${2:-}"
            shift 2
            ;;
        --arch)
            R8Q_DEVICE_ARCH="${2:-}"
            shift 2
            ;;
        --soc)
            R8Q_DEVICE_SOC="${2:-}"
            shift 2
            ;;
        --target-partition)
            R8Q_TARGET_PARTITION="${2:-}"
            shift 2
            ;;
        --partition-map)
            R8Q_PARTITION_MAP_FILE="${2:-}"
            shift 2
            ;;
        --min-space-bytes)
            R8Q_MIN_SPACE_BYTES="${2:-}"
            shift 2
            ;;
        --check-space-dir)
            R8Q_SPACE_CHECK_DIR="${2:-}"
            shift 2
            ;;
        --report-file)
            R8Q_REPORT_OUT="${2:-}"
            shift 2
            ;;
        *)
            echo "[ERROR] Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

[ -n "$R8Q_MODE" ] || { echo "[ERROR] No installation mode specified." >&2; exit 2; }

if [ -n "$SIMULATE_PROFILE" ]; then
    [ "$SIMULATE_PROFILE" = "r8q" ] || { echo "[ERROR] Invalid --target-profile: $SIMULATE_PROFILE" >&2; exit 2; }
    if [ "$R8Q_MODE" = "install" ]; then
        echo "[ERROR] --target-profile simulation cannot be combined with --install." >&2
        exit 2
    fi
    export R8Q_SIMULATE_PROFILE="r8q"
else
    export R8Q_SIMULATE_PROFILE=""
fi

# Track strict in-memory dependency token chain across stages (zero disk writes in dry-run)
export R8Q_PIPELINE_TOKEN="r8q-$(date -u +%Y%m%dT%H%M%SZ)-$$"
export R8Q_COMPLETED_STEPS=""

run_stage() {
    stage_id="$1"
    script_name="$2"
    stage_path="$R8Q_INSTALLER_ROOT/scripts/$script_name"
    if [ ! -f "$stage_path" ]; then
        echo "[FATAL] Missing mandatory installer stage script: $stage_path" >&2
        exit 20
    fi
    "$R8Q_SH_BIN" "$stage_path"
    eval "export R8Q_STAGE_DONE_${stage_id}=1"
    if [ -z "$R8Q_COMPLETED_STEPS" ]; then
        R8Q_COMPLETED_STEPS="$stage_id"
    else
        R8Q_COMPLETED_STEPS="${R8Q_COMPLETED_STEPS},${stage_id}"
    fi
    export R8Q_COMPLETED_STEPS
}

# Always validate cryptographic package integrity FIRST in all modes
run_stage "01" "01-preflight.sh"
run_stage "02" "02-verify-payloads.sh"
run_stage "03" "03-prepare-target.sh"

if [ "$R8Q_MODE" = "verify" ]; then
    echo "================================================================="
    echo "  [VERIFY COMPLETE] Stages 01-03 PASSED cleanly (no writes performed)."
    echo "================================================================="
    exit 0
fi

# Ordered execution Stages 04 -> 11 (Steps 9 -> 19)
run_stage "04" "04-install-firmware.sh"
run_stage "05" "05-install-uefi.sh"
run_stage "06" "06-install-esp.sh"
run_stage "07" "07-install-kernel.sh"
run_stage "08" "08-install-initramfs.sh"
run_stage "09" "09-install-rootfs.sh"
run_stage "10" "10-configure-boot.sh"
run_stage "11" "11-post-install-validation.sh"
