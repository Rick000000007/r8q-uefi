#!/usr/bin/env bash
# Stage 07 [Step 12]: Verify and stage ARM64 EFI Stub Linux Kernel & SM8250 Device Trees
set -euo pipefail

[ "${R8Q_STAGE_DONE_06:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 06-install-esp.sh must complete before 07-install-kernel.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"

echo "[STAGE 07/11] [STEP 12/19] Validating ARM64 Linux kernel and matching SM8250 DTBs..."
python3 -B - "$ROOT" << 'PYEOF'
import os, struct, sys

root = sys.argv[1]
img_path = os.path.join(root, "payload", "kernel", "Image")
with open(img_path, "rb") as f:
    hdr = f.read(64)
assert hdr[:2] == b"MZ" and hdr[0x38:0x3C] == b"ARM\x64", "Invalid ARM64 EFI stub kernel Image"

for dtb_name in ["sm8250-samsung-r8q.dtb", "r8q.dtb"]:
    dtb_path = os.path.join(root, "payload", "dtb", dtb_name)
    with open(dtb_path, "rb") as f:
        data = f.read()
    magic, totalsize, _, _, _, version = struct.unpack_from(">6I", data, 0)
    assert magic == 0xD00DFEED, f"{dtb_name}: invalid FDT magic 0x{magic:08X}"
    assert version == 17, f"{dtb_name}: expected FDT version 17, got {version}"
    assert totalsize == len(data), f"{dtb_name}: FDT size mismatch"

print("  [VERIFIED] Kernel Image (ARM\\x64 EFI Stub) and SM8250 FDT v17 DTBs validated.")
PYEOF

echo "  [$MODE] Kernel and DTB staging plan verified."
echo "[STAGE 07/11] Kernel & DTB stage PASSED."
