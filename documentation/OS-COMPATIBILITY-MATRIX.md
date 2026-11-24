# Project R8Q — Operating System Compatibility Matrix

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 5G (`SM8250` / Kona)  
**Document Revision:** 3.0.0 (Multi-OS Evaluation & Technical Boundaries)  
**Status:** Approved Technical Evaluation  

---

## 1. Multi-OS Architecture Principle

Project R8Q provides an open, vendor-neutral firmware and boot manager foundation. Installing, updating, or replacing an operating system does not require rebuilding or reflashing the R8Q UEFI firmware.

Each operating system requires:
1. An independent root filesystem (ext4 / btrfs).
2. A compatible Linux ARM64 kernel (or shared SM8250 platform kernel).
3. An initramfs capable of storage discovery and `switch_root`.
4. A Flattened Device Tree Blob (DTB) matching the r8q SM8250 hardware.
5. A boot configuration entry file (`EFI/R8Q/Config/entries/<os-name>.conf`).

> [!WARNING]
> **Generic ARM64 PC ISO Incompatibility Notice:**  
> R8Q cannot boot off-the-shelf standard ARM64 PC ISO installers (such as generic Ubuntu Server ISOs or Fedora Workstation ISOs designed for UEFI ACPI servers). The Snapdragon 865 SoC requires Device Tree (FDT) hardware descriptions and specialized clock/regulator initialization. Distributions must be packaged with SM8250 device tree bindings.

---

## 2. Operating System Compatibility Matrix

| Operating System | Architecture | Primary UI Mode | Compatibility Tier | Boot Media Supported | Notes & Prerequisites |
|---|---|---|---|---|---|
| **Debian 12 (Bookworm)** | `arm64` / AArch64 | **Native Terminal (Bash)** / Optional GNOME | **Tier 1 (Official / Primary)** | Internal UFS, MicroSD, USB OTG | Native root filesystem generated, tested, and included in release. Multi-user console default. |
| **Kali Linux ARM64** | `arm64` / AArch64 | Terminal / Optional XFCE | **Tier 2 (Supported)** | MicroSD, USB OTG, Internal | Fully compatible using r8q kernel & DTB. Ideal for mobile security diagnostics. |
| **Ubuntu 24.04 LTS** | `arm64` / AArch64 | Terminal / Optional Ubuntu Desktop | **Tier 2 (Compatible)** | MicroSD, USB OTG | Compatible with standard debootstrap rootfs and r8q platform kernel. |
| **postmarketOS / Alpine**| `aarch64` (musl) | Terminal / Phosh | **Tier 3 (Planned)** | MicroSD, USB OTG | Lightweight musl-based userspace; rapid boot times (< 3s); excellent for mobile terminal use. |
| **Generic ARM64 Distros**| `arm64` (systemd) | Any | **Tier 3 (Community)** | USB OTG, MicroSD | Must supply SM8250 DTB and EFI-stub kernel; cannot rely on UEFI ACPI tables. |

---

## 3. OS Deployment Layout on Storage

Each operating system is isolated within its own dedicated storage volume and EFI configuration file:

```
EFI/R8Q/
├── Config/
│   ├── boot.cfg               # Global boot priorities & default timeout
│   └── entries/
│       ├── debian.conf        # Tier 1 Debian 12 Terminal entry
│       ├── kali.conf          # Tier 2 Kali Linux entry
│       └── ubuntu.conf        # Tier 2 Ubuntu Linux entry
└── Kernels/
    ├── vmlinuz-r8q            # Shared or per-distro Linux ARM64 EFI Stub Kernel
    ├── initramfs-r8q.img      # Early userspace ramdisk
    └── sm8250-samsung-r8q.dtb # Flattened Device Tree Blob
```

### Sample Multi-Boot Entry: Kali Linux
```ini
title Kali Linux ARM64
version 2026.3
linux /EFI/R8Q/Kernels/vmlinuz-r8q
initrd /EFI/R8Q/Kernels/initramfs-r8q.img
dtb /EFI/R8Q/Kernels/sm8250-samsung-r8q.dtb
options root=LABEL=kali-rootfs rw console=tty0 console=ttyMSM0,115200n8 quiet
```

### Sample Multi-Boot Entry: Ubuntu 24.04
```ini
title Ubuntu 24.04 LTS
version 24.04
linux /EFI/R8Q/Kernels/vmlinuz-r8q
initrd /EFI/R8Q/Kernels/initramfs-r8q.img
dtb /EFI/R8Q/Kernels/sm8250-samsung-r8q.dtb
options root=LABEL=ubuntu-rootfs rw console=tty0 console=ttyMSM0,115200n8
```
