# Project R8Q — Installation Guide

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Document Revision:** 3.0.0 (Non-Destructive Dual-Boot Deployment)  
**Status:** Authoritative Installation Manual  

---

## 1. Safety Directives & Dual-Boot Guarantee

Project R8Q is engineered as a **non-destructive, auxiliary installation**. It does not overwrite your primary Android or LineageOS boot partition (`sda23`), nor does it alter encrypted personal data in `userdata` (`sda36`).

```
+---------------------------------------------------------------------------------+
|                               DEVICE BOOT VECTOR                                |
+---------------------------------------------------------------------------------+
                                         |
            +----------------------------+----------------------------+
            |                                                         |
  [Normal Power Button]                                     [Power + Vol Up + USB]
            |                                                         |
            v                                                         v
   Boot Partition: sda23                                     Recovery Partition: sda24
+-----------------------------+                           +-----------------------------+
|   Primary Operating System  |                           |     Project R8Q Platform    |
|   LineageOS 23 / Magisk     |                           |     EDK II UEFI Firmware    |
|   100% Intact & Untouched   |                           |     Native Debian 12 ARM64  |
+-----------------------------+                           +-----------------------------+
```

> [!CAUTION]
> **Zero Phone Access Boundary:**  
> During automated software development and CI/CD pipelines, no commands are executed against a physical phone. Physical deployment is executed solely by the device owner following complete static verification.

---

## 2. Prerequisites & Verification

1. **Target Device:** Samsung Galaxy S20 FE 5G Snapdragon (Model: `SM-G781B` or `SM-G781B/DS`, Codename: `r8q`).
2. **Bootloader:** Unlocked bootloader (OEM Unlocking enabled in Developer Options).
3. **Recovery Environment:** LineageOS Recovery or TWRP installed.
4. **Verified Release Artifacts:**
   - `R8Q-Debian12-Recovery.zip` (SHA-256: `d969430b84cc69f40cdf3325add813dcbdf0c9704f0e9e226af6b59ad3ec1fe6`)
   - `r8q-rootfs.ext4.gz` (SHA-256: `72ed1deb873639bc0c36b5da60ca9faa4815e91599774e882e0b981b47445058`)

---

## 3. Installation Methods

### Method 1: LineageOS Recovery Flashable ZIP (Recommended)
This method installs the R8Q UEFI boot container into the recovery slot (`sda24`) directly from a USB drive or microSD card:

1. Copy `R8Q-Debian12-Recovery.zip` to a USB-C flash drive or MicroSD card.
2. Boot phone into LineageOS Recovery:
   - Power off device.
   - Connect USB cable to a PC, charger, or USB-C drive.
   - Hold `Power + Volume Up` until the recovery screen appears.
3. In LineageOS Recovery, select **Apply Update** -> **Choose from USB storage** (or **Apply from ADB** -> `adb sideload R8Q-Debian12-Recovery.zip`).
4. The automated installer will execute:
   - Step 1: Hardware model check (`r8q` / `SM-G781B`).
   - Step 2: Target partition audit (resolves `sda24`, verifies 82,694,144 byte capacity, verifies `sda25` is strictly avoided).
   - Step 3: Payload extraction to staging buffer.
   - Step 4: Cryptographic SHA-256 integrity verification.
   - Step 5: Headroom calculation (+55.53 MiB safety margin).
   - Step 6: Flashing to `sda24` with readback SHA-256 validation.
5. Once complete, reboot device.

### Method 2: Bootable USB Drive Installation (Live Mobile Workstation)
To boot Debian 12 directly from an external high-speed USB-C SSD or flash drive without touching internal flash storage:
1. Format a USB-C flash drive with a GPT partition table.
2. Partition 1: 512 MiB FAT32 formatted with label `R8Q_BOOT` (ESP).
3. Partition 2: Remainder formatted as ext4 with label `r8q-rootfs`.
4. Extract `R8Q-Debian12-Full-System.tar.gz` and write `r8q-rootfs.ext4` to the second partition:
   ```bash
   gunzip -c rootfs/r8q-rootfs.ext4.gz | dd of=/dev/sdX2 bs=4M status=progress conv=fsync
   ```
5. Copy EFI binaries, DTB, and kernel to Partition 1 (`R8Q_BOOT`).
6. Connect the USB drive to the phone via USB-C and power on into Recovery mode (`Power + Volume Up`). R8Q UEFI Boot Manager will discover the USB drive and boot Debian 12 ARM64.

---

## 4. First Boot & Initial Login

1. Power on holding `Power + Volume Up` (with USB connected).
2. The AMOLED display initializes in continuous splash mode.
3. R8Q UEFI starts; the R8Q Boot Manager countdown appears (3 seconds).
4. Debian 12 ARM64 boots into the native text console on the AMOLED display (`tty1`).
5. Login prompt:
   - **User:** `r8q`
   - **Default Shell:** `bash`
   - **Root Privileges:** `sudo su` (passwordless sudo for administrative user `r8q`).
6. Launch interactive development tools or configure Wi-Fi using `nmcli`:
   ```bash
   nmcli dev wifi list
   nmcli dev wifi connect "MyNetwork" password "MyPassword"
   ```
