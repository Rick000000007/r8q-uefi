# Project R8Q — Unified Debian 12 ARM64 Installer (`R8Q-Debian12-ARM64-Installer`)

Self-contained installation bundle targeting **Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q` / Qualcomm Snapdragon 865 `SM8250`)**.

## Quick Usage

Run all commands from inside the extracted `R8Q-Debian12-ARM64-Installer/` directory:

```bash
# 1. Inspect usage and options
./install.sh --help

# 2. Verify payload checksums, manifests, and device profile compatibility
./install.sh --verify

# 3. Simulate all 19 installation stages with zero storage writes
./install.sh --dry-run

# 4. Inspect standalone device or checksum verification utilities
./verify-checksums.sh
./verify-device.sh
./uninstall-or-rollback.sh --help
```

## Modes

- `--help` : Show full usage, 19-step installation order, and safety locks.
- `--verify` : Verify target device compatibility, partition protection, and every SHA-256 payload digest.
- `--dry-run` : Execute the full 19-stage dependency pipeline in simulation mode with **zero physical writes**.
- `--install` : Enforce root, live device identity, verified partition map, non-CI environment, and explicit audited write plan approval before performing any installation actions.

## Hardware Safety Restrictions

- **Knox Keyrefuge (`sda25`) Isolation:** Writes to `/dev/block/sda25`, `keyrefuge`, `/dev/block/sda`, or adjacent key partitions are unconditionally blocked.
- **Boot Slot Preservation (`sda23`):** Active Android / LineageOS `boot` (`sda23`) is protected and read-only.
- **Independent Partition Map Required:** Partition offsets are never invented; live sysfs or an independently verified partition map (`--partition-map <file>`) must match expected SM8250 geometry.
- **Physical Flashing Lock:** Physical UFS / recovery partition writes remain **disabled (`PHYSICAL_WRITES_ENABLED=0`)** until the Phase 3.6B hardware safety audit explicitly approves the exact write plan and partition target authorization.
- **Terminal-First Policy:** Configures Debian 12 ARM64 `systemd` to boot into `multi-user.target` (`tty1` AMOLED console + `ttyMSM0` UART + OpenSSH), keeping optional GNOME desktop explicitly opt-in (`OPTIONAL_GNOME_ENABLED=0`).
