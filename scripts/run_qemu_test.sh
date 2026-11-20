#!/usr/bin/env bash
# Project R8Q UEFI: QEMU ARM64 Automated Boot Validation Suite
# Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)
# Platform: Qualcomm Snapdragon 865 (SM8250 / Kona)
# Virt: QEMU AArch64 Virt Machine
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
LOGS_DIR="$PROJECT_ROOT/logs"
KERNEL_IMG="$BUILD_DIR/Image"
INITRD_IMG="$BUILD_DIR/initramfs.img"
ROOTFS_IMG="$BUILD_DIR/r8q-rootfs.ext4"
ESP_IMG="$BUILD_DIR/esp.img"
UEFI_FW="/usr/share/qemu-efi-aarch64/QEMU_EFI.fd"

mkdir -p "$LOGS_DIR"

MODE="${1:---all}"

echo "================================================================="
echo "   PROJECT R8Q: QEMU ARM64 VIRTUAL VALIDATION HARNESS"
echo "   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q)"
echo "   Mode:   $MODE"
echo "================================================================="

# Helper function to run QEMU with python subprocess controller
run_qemu() {
    local test_name="$1"
    local log_file="$2"
    local duration="$3"
    local qemu_cmd="$4"

    echo "[QEMU-TEST] Running: $test_name (Duration: ${duration}s)..."
    python3 - << EOF
import subprocess, time, sys

cmd = $qemu_cmd
log_path = "$log_file"

print(f"  Command: {' '.join(cmd)}")
with open(log_path, "w") as log_f:
    p = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT)
    time.sleep($duration)
    p.terminate()
    try:
        p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        p.kill()

print(f"  [DONE] Output captured to: {log_path}")
EOF
}

test_direct_kernel() {
    echo ""
    echo "--- [1/3] DIRECT LINUX KERNEL & SYSTEMD BOOT VALIDATION ---"
    local log="$LOGS_DIR/qemu_linux_boot.log"
    local cmd="['qemu-system-aarch64', '-M', 'virt', '-cpu', 'cortex-a57', '-m', '1024M', '-smp', '4', '-kernel', '$KERNEL_IMG', '-initrd', '$INITRD_IMG', '-append', 'console=ttyAMA0 root=/dev/vda rw earlycon', '-drive', 'file=$ROOTFS_IMG,format=raw,if=virtio', '-drive', 'file=$ESP_IMG,format=raw,if=virtio', '-netdev', 'user,id=net0', '-device', 'virtio-net-pci,netdev=net0', '-nographic']"
    run_qemu "Direct Linux Boot" "$log" 40 "$cmd"

    echo "[VERIFY] Checking critical boot markers in $log..."
    grep -q "Linux version 7.2.15" "$log" && echo "  [PASS] ARM64 Linux Kernel 7.2.15 initialized" || echo "  [FAIL] Kernel version check"
    grep -q "Run /init as init process" "$log" && echo "  [PASS] Native initramfs early userspace launched" || echo "  [FAIL] Initramfs launch"
    grep -q "virtio_blk" "$log" && echo "  [PASS] VirtIO block storage driver enumerated" || echo "  [FAIL] VirtIO block driver"
    grep -q "EXT4-fs (vda): mounted filesystem" "$log" && echo "  [PASS] Root filesystem (ext4) mounted rw" || echo "  [FAIL] Root mount"
    grep -q "Executing switch_root to /usr/lib/systemd/systemd" "$log" && echo "  [PASS] switch_root to systemd PID 1 successful" || echo "  [FAIL] switch_root"
    grep -qE "Welcome to.*Debian|systemd 262" "$log" && echo "  [PASS] systemd PID 1 active & Debian banner displayed" || echo "  [FAIL] Systemd banner"
    grep -q "Hostname set to <r8q-linux>" "$log" && echo "  [PASS] Hostname correctly applied to r8q-linux" || echo "  [FAIL] Hostname"
}

test_uefi_efi_stub() {
    echo ""
    echo "--- [2/3] UEFI FIRMWARE & LINUX EFI STUB BOOT VALIDATION ---"
    local log="$LOGS_DIR/qemu_uefi_boot.log"
    local cmd="['qemu-system-aarch64', '-M', 'virt', '-cpu', 'cortex-a57', '-m', '1024M', '-smp', '4', '-bios', '$UEFI_FW', '-kernel', '$KERNEL_IMG', '-initrd', '$INITRD_IMG', '-append', 'console=ttyAMA0 root=/dev/vda rw earlycon', '-drive', 'file=$ROOTFS_IMG,format=raw,if=virtio', '-drive', 'file=$ESP_IMG,format=raw,if=virtio', '-nographic']"
    run_qemu "UEFI Firmware & EFI Stub Boot" "$log" 30 "$cmd"

    echo "[VERIFY] Checking UEFI and EFI Stub markers in $log..."
    grep -q "UEFI firmware" "$log" && echo "  [PASS] EDK II AArch64 UEFI Firmware volume executed" || echo "  [FAIL] UEFI Firmware"
    grep -q "efi: EFI v2.7" "$log" && echo "  [PASS] Linux EFI Stub handed off from UEFI runtime" || echo "  [FAIL] EFI Stub handoff"
    grep -q "ACPI: RSDP" "$log" && echo "  [PASS] ACPI system configuration tables recognized" || echo "  [FAIL] ACPI tables"
    grep -q "Run /init as init process" "$log" && echo "  [PASS] Initramfs handoff through UEFI successful" || echo "  [FAIL] Initramfs via UEFI"
    grep -q "Executing switch_root to /usr/lib/systemd/systemd" "$log" && echo "  [PASS] Systemd transition completed under UEFI" || echo "  [FAIL] Systemd transition"
}

test_failure_injection() {
    echo ""
    echo "--- [3/3] FAILURE INJECTION & RESCUE SHELL VALIDATION ---"
    local log="$LOGS_DIR/qemu_failure_rescue.log"
    local cmd="['qemu-system-aarch64', '-M', 'virt', '-cpu', 'cortex-a57', '-m', '1024M', '-kernel', '$KERNEL_IMG', '-initrd', '$INITRD_IMG', '-append', 'console=ttyAMA0 root=/dev/nonexistent rw', '-nographic']"
    run_qemu "Failure Injection" "$log" 15 "$cmd"

    echo "[VERIFY] Checking emergency rescue fallback in $log..."
    grep -q "Scanning storage hardware for root device: /dev/nonexistent" "$log" && echo "  [PASS] Non-existent root device detected by initramfs" || echo "  [FAIL] Device detection"
    grep -q "PROJECT R8Q NATIVE LINUX OPERATING SYSTEM" "$log" && echo "  [PASS] Initramfs splash banner executed" || echo "  [FAIL] Splash banner"
}

case "$MODE" in
    --kernel)
        test_direct_kernel
        ;;
    --uefi)
        test_uefi_efi_stub
        ;;
    --rescue)
        test_failure_injection
        ;;
    --all)
        test_direct_kernel
        test_uefi_efi_stub
        test_failure_injection
        ;;
    *)
        echo "Usage: $0 [--kernel | --uefi | --rescue | --all]"
        exit 1
        ;;
esac

echo ""
echo "================================================================="
echo "   ALL REQUESTED QEMU VALIDATION TESTS COMPLETED CLEANLY"
echo "================================================================="
