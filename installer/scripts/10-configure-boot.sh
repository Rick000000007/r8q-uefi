#!/usr/bin/env bash
# Stage 10 [Steps 15-17]: Configure systemd terminal-first, optional GNOME layer (opt-in), & boot entries
set -euo pipefail

[ "${R8Q_STAGE_DONE_09:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 09-install-rootfs.sh must complete before 10-configure-boot.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=../config/boot.conf
source "$ROOT/config/boot.conf"

echo "[STAGE 10/11] [STEPS 15-17/19] Validating systemd terminal-first, optional GNOME policy, and boot entries..."

[ "$SYSTEMD_DEFAULT_TARGET" = "multi-user.target" ] || {
    echo "[ERROR] BOOT POLICY VIOLATION: systemd default target must be multi-user.target." >&2
    exit 45
}
[ "$OPTIONAL_GNOME_ENABLED" -eq 0 ] || {
    echo "[ERROR] BOOT POLICY VIOLATION: optional GNOME must NOT be enabled as default." >&2
    exit 46
}

python3 -B - "$ROOT/payload/debian-rootfs/r8q-rootfs.tar.gz" "$ROOT/payload/boot-manager/Config" "$BOOT_DEFAULT_ENTRY" "$BOOT_TIMEOUT_SECONDS" << 'PYEOF'
import os, sys, tarfile

tar_path, cfg_dir, exp_default, exp_timeout = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

with tarfile.open(tar_path, "r:gz") as tar:
    by_name = {m.name.lstrip("./"): m for m in tar}

default_target = by_name.get("etc/systemd/system/default.target")
assert default_target is not None and default_target.issym(), "default.target symlink missing in Debian rootfs"
assert "multi-user.target" in default_target.linkname, f"Expected multi-user.target, got {default_target.linkname}"
assert "graphical.target" not in default_target.linkname, "GNOME graphical.target must NOT be default"
assert "etc/systemd/system/display-manager.service" not in by_name, "display-manager.service must NOT auto-start"
assert "etc/systemd/system/getty.target.wants/getty@tty1.service" in by_name, "Missing getty@tty1.service"
assert "etc/systemd/system/getty.target.wants/serial-getty@ttyMSM0.service" in by_name, "Missing serial-getty@ttyMSM0.service"

boot_cfg = open(os.path.join(cfg_dir, "boot.cfg"), encoding="utf-8").read()
assert f"default={exp_default}" in boot_cfg, "boot.cfg default OS mismatch"
assert f"timeout={exp_timeout}" in boot_cfg, "boot.cfg timeout mismatch"

for entry in ["debian.conf", "kali.conf", "ubuntu.conf"]:
    p = os.path.join(cfg_dir, "entries", entry)
    assert os.path.isfile(p), f"Missing boot entry config: {p}"
    content = open(p, encoding="utf-8").read()
    for field in ["title", "linux", "initrd", "dtb", "options"]:
        assert field in content, f"{entry}: missing field '{field}'"

print("  [VERIFIED] Terminal-first systemd (multi-user.target), optional GNOME opt-in only, and BootManager entries OK.")
PYEOF

echo "  [$MODE] Optional GNOME remains opt-in only ($OPTIONAL_GNOME_TARGET not active by default)."
echo "[STAGE 10/11] Boot & systemd configuration stage PASSED."
