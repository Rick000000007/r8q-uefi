# Project R8Q — Storage Architecture

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Storage Subsystem:** Qualcomm SM8250 UFS 3.0 Host Controller + Removable Media  
**Document Revision:** 3.0.0 (Hybrid Storage Model & Keystore Isolation)  
**Status:** Authoritative Architectural Standard  

---

## 1. Storage Architecture Overview

Project R8Q implements a **Hybrid Storage Architecture** combining internal Universal Flash Storage (UFS 3.0) with removable storage (MicroSD and USB-C OTG). This design achieves three vital goals:
1. **Zero Impact on Existing Android Workflow:** The primary Android operating system, Magisk root data, and partition structure on internal storage remain intact.
2. **Deterministic Firmware Execution:** The R8Q boot container resides in the dedicated recovery partition (`sda24`), booted via Samsung ABL.
3. **Pluggable & Expandable Multi-OS Management:** Operating systems can be installed internally or booted directly from external MicroSD or USB flash drives without rebuilding the UEFI firmware.

---

## 2. Internal UFS 3.0 Partition Map (SM8250 / r8q)

The internal UFS 3.0 storage presents multiple Logical Unit Numbers (LUNs). The main user data LUN0 is exposed as `/dev/block/sda` with 36 discrete partitions:

```
Physical Block Device: /dev/block/sda (UFS LUN0: 128 GB / 256 GB)
├── sda1 - sda21 : Qualcomm Modem, DSP, Sensors, Bluetooth, EFS calibration
├── sda22        : dtbo        (Dedicated Device Tree Overlay partition)
├── sda23        : boot        (64.00 MiB / 67,108,864 B) -> Untouched Primary Android Boot
├── sda24        : recovery    (78.86 MiB / 82,694,144 B) -> Dedicated R8Q Boot Container
├── sda25        : keyrefuge   (CRITICAL KEYSTORE)        -> ABSOLUTELY PROTECTED
├── sda26 - sda28: vbmeta, vbmeta_system, metadata
├── sda29        : super       (Dynamic Partitions: system, vendor, product, odm)
└── sda36        : userdata    (Large user storage; dm-crypt / FBE encrypted)
```

### 2.1 The Protected Keystore: `sda25` (`keyrefuge`)
Partition `sda25` contains device-unique cryptographic root keys, Knox attestation certificates, and hardware encryption secrets. 
- **Strict Blacklist Rule:** In accordance with Part 5 of the Master Engineering Specification, `sda25` is strictly forbidden from being read, dumped, mounted, inspected, copied, modified, formatted, or included in any build or installer.
- **Hardware & Software Enforcement:**
  1. `StorageProtectionDxe` inside UEFI intercepts and blocks write requests targeting `sda25`.
  2. The recovery installer script (`update-binary`) enforces a regex rejection guard refusing to proceed if the target points to `sda25`, `keyrefuge`, or the raw whole disk `/dev/block/sda`.
  3. Pre-execution checks assert a **55.53 MiB safety headroom** between the R8Q payload (24.46 MiB) and the total capacity of `sda24` (78.86 MiB), guaranteeing that data cannot bleed into `sda25`.

---

## 3. Filesystem Layout & Naming Standards

To prevent failures caused by kernel device re-enumeration (e.g., UFS probing before or after USB/SD), Project R8Q enforces a strict **UUID and Volume Label Policy**:

> [!IMPORTANT]
> **Zero Hardcoded Partition Policy:**  
> Neither the bootloader, initramfs, nor `/etc/fstab` may ever rely on hardcoded device node names (e.g., `/dev/sdaXX`, `/dev/sdbX`). All filesystem references must resolve dynamically via `LABEL=` or `UUID=`.

### 3.1 Primary Filesystem Roles

| Filesystem Role | Volume Label | Format | Mount Point | Contents |
|---|---|---|---|---|
| **EFI System Partition** | `R8Q_BOOT` | FAT32 (GPT Type `C12A...`) | `/boot/efi` | `EFI/BOOT/BOOTAA64.EFI`, `EFI/R8Q/BootManager.efi`, `EFI/R8Q/Config/boot.cfg`, `entries/*.conf`, `nvram.bin`, kernels, DTBs |
| **Native Debian Rootfs**| `r8q-rootfs` | ext4 (barrier=1) | `/` | Standard FHS 3.0 Debian 12 ARM64 root filesystem |
| **Swap Storage** | `r8q-swap` | Linux Swap | `[SWAP]` | Optional swapfile (`/swapfile`) or dedicated swap partition |

---

## 4. Multi-Drive & Removable Storage Model

```
+-----------------------------------------------------------------------------------+
|                              STORAGE RESOLUTION LOGIC                             |
+-----------------------------------------------------------------------------------+
                                          |
            +-----------------------------+-----------------------------+
            |                                                           |
            v                                                           v
+-----------------------+                                   +-----------------------+
|  Internal UFS Storage |                                   |   Removable Media     |
|  - Recovery: sda24    |                                   |   - MicroSD Card      |
|  - Boot: sda23        |                                   |   - USB Type-C Flash  |
|  - ESP: R8Q_BOOT      |                                   |   - USB NVMe / SSD    |
+-----------------------+                                   +-----------------------+
            |                                                           |
            +-----------------------------+-----------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Early Initramfs Autoprobe:                                                        |
|   1. Search all block devices for UUID or LABEL=r8q-rootfs.                       |
|   2. If block device is a raw ext4 partition -> mount directly to /newroot.       |
|   3. If block device contains r8q-rootfs.ext4 disk image -> setup loopback dev.   |
|   4. If not found -> trigger 10-second timeout, then drop to emergency shell.     |
+-----------------------------------------------------------------------------------+
```

### 4.1 Internal UFS Installation Model
- The native Debian 12 rootfs can reside as a dedicated physical partition (if repititioning is elected by the user) or as a raw disk image (`/data/r8q-rootfs.ext4`) mounted transparently via loopback by the initramfs.
- This allows genuine bare-metal Linux execution without requiring destructive repartitioning of the phone's internal storage.

### 4.2 MicroSD & USB OTG Installation Model
- The R8Q Boot Manager probes all attached mass storage interfaces during early startup.
- If a bootable configuration (`EFI/R8Q/Config/boot.cfg`) is discovered on a USB drive or MicroSD card, it is added to the Boot Manager menu.
- Complete standalone operating systems (Kali Linux ARM64, Ubuntu ARM64, Arch ARM) can be deployed to USB drives and booted on demand, turning the phone into a true multi-OS pocket computer.
