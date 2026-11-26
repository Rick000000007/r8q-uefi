#!/bin/sh
# Stage 10 [Steps 15-17]: Configure systemd terminal-first, optional GNOME layer (opt-in), & boot entries
set -eu

[ "${R8Q_STAGE_DONE_09:-0}" = "1" ] || {
    echo "[ERROR] Out-of-order execution: 09-install-rootfs.sh must complete before 10-configure-boot.sh" >&2
    exit 40
}

ROOT="${R8Q_INSTALLER_ROOT:?R8Q_INSTALLER_ROOT must be set via install.sh}"
MODE="${R8Q_MODE:-dry-run}"
# shellcheck source=../config/boot.conf
. "$ROOT/config/boot.conf"

echo "[STAGE 10/11] [STEPS 15-17/19] Validating systemd terminal-first, optional GNOME policy, and boot entries..."

[ "$SYSTEMD_DEFAULT_TARGET" = "multi-user.target" ] || {
    echo "[ERROR] BOOT POLICY VIOLATION: systemd default target must be multi-user.target." >&2
    exit 45
}
[ "$OPTIONAL_GNOME_ENABLED" -eq 0 ] || {
    echo "[ERROR] BOOT POLICY VIOLATION: optional GNOME must NOT be enabled as default." >&2
    exit 46
}

ROOTFS_TAR="$ROOT/payload/debian-rootfs/r8q-rootfs.tar.gz"
CFG_DIR="$ROOT/payload/boot-manager/Config"

tar -ztvf "$ROOTFS_TAR" | awk '
{
    perm = $1;
    line = $0;
    arrow = index(line, " -> ");
    if (arrow > 0) {
        left = substr(line, 1, arrow - 1);
        linkname = substr(line, arrow + 4);
        sub(/^.*[[:space:]]/, "", left);
        path = left;
    } else {
        path = $NF;
        linkname = "";
    }
    sub(/^\.\//, "", path);

    if (path == "etc/systemd/system/default.target") {
        has_default = 1;
        is_symlink = (substr(perm, 1, 1) == "l");
        default_link = linkname;
    }
    if (path == "etc/systemd/system/display-manager.service") {
        has_dm = 1;
    }
    if (path == "etc/systemd/system/getty.target.wants/getty@tty1.service") {
        has_tty1 = 1;
    }
    if (path == "etc/systemd/system/getty.target.wants/serial-getty@ttyMSM0.service") {
        has_msm0 = 1;
    }
}
END {
    if (!has_default || !is_symlink) {
        print "[ERROR] default.target symlink missing in Debian rootfs" > "/dev/stderr";
        exit 46;
    }
    if (index(default_link, "multi-user.target") == 0 || index(default_link, "graphical.target") > 0) {
        printf "[ERROR] Expected default.target -> multi-user.target, got %s\n", default_link > "/dev/stderr";
        exit 46;
    }
    if (has_dm) {
        print "[ERROR] display-manager.service must NOT auto-start" > "/dev/stderr";
        exit 46;
    }
    if (!has_tty1) {
        print "[ERROR] Missing getty@tty1.service" > "/dev/stderr";
        exit 46;
    }
    if (!has_msm0) {
        print "[ERROR] Missing serial-getty@ttyMSM0.service" > "/dev/stderr";
        exit 46;
    }
}
'

BOOT_CFG="$CFG_DIR/boot.cfg"
[ -f "$BOOT_CFG" ] || { echo "[ERROR] Missing boot.cfg: $BOOT_CFG" >&2; exit 46; }
grep -Fq "default=$BOOT_DEFAULT_ENTRY" "$BOOT_CFG" || { echo "[ERROR] boot.cfg default OS mismatch" >&2; exit 46; }
grep -Fq "timeout=$BOOT_TIMEOUT_SECONDS" "$BOOT_CFG" || { echo "[ERROR] boot.cfg timeout mismatch" >&2; exit 46; }

for entry in debian.conf kali.conf ubuntu.conf; do
    p="$CFG_DIR/entries/$entry"
    [ -f "$p" ] || { echo "[ERROR] Missing boot entry config: $p" >&2; exit 46; }
    for field in title linux initrd dtb options; do
        grep -Fq "$field" "$p" || { echo "[ERROR] $entry: missing field '$field'" >&2; exit 46; }
    done
done

echo "  [VERIFIED] Terminal-first systemd (multi-user.target), optional GNOME opt-in only, and BootManager entries OK."
echo "  [$MODE] Optional GNOME remains opt-in only ($OPTIONAL_GNOME_TARGET not active by default)."
echo "[STAGE 10/11] Boot & systemd configuration stage PASSED."
