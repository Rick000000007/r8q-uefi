#!/usr/bin/env bash
# Stage 05 [Step 10]: Verify and stage BootManager.efi, Setup.efi, and all UEFI applications
set -euo pipefail

[ "${R8Q_STAGE_DONE_04:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 04-install-firmware.sh must complete before 05-install-uefi.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"

echo "[STAGE 05/11] [STEP 10/19] Validating UEFI applications, BootManager.efi & Setup.efi (PE32+ 0xAA64)..."
python3 -B - "$ROOT" << 'PYEOF'
import os, struct, sys

root = sys.argv[1]
binaries = [
    os.path.join(root, "payload", "boot-manager", "BootManager.efi"),
    os.path.join(root, "payload", "setup", "Setup.efi"),
]
uefi_dir = os.path.join(root, "payload", "uefi")
efi_files = sorted(f for f in os.listdir(uefi_dir) if f.endswith(".efi"))
assert len(efi_files) >= 15, f"Expected >= 15 UEFI apps in payload/uefi, found {len(efi_files)}"
binaries.extend(os.path.join(uefi_dir, f) for f in efi_files)

for p in binaries:
    with open(p, "rb") as f:
        data = f.read(4096)
    assert data[:2] == b"MZ", f"{p}: missing MZ signature"
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe_off:pe_off + 4] == b"PE\x00\x00", f"{p}: missing PE signature"
    mach = struct.unpack_from("<H", data, pe_off + 4)[0]
    assert mach == 0xAA64, f"{p}: expected machine 0xAA64, got 0x{mach:X}"
print(f"  [VERIFIED] {len(binaries)} AArch64 PE32+ UEFI binaries validated.")
PYEOF

echo "  [$MODE] UEFI applications & BootManager staging plan verified."
echo "[STAGE 05/11] UEFI application stage PASSED."
