# Project R8Q UEFI: Milestone 4 MicroSD & USB Storage Integration Report
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona, Rev 2.1)  
**Document Revision:** 1.0.0-M4  
**Status:** Hardware Verified & Integrated  

---

## 1. MicroSD Host Controller Hardware Verification

Direct empirical verification from `devicetree/r8q-live.dts` and sysfs (`/sys/bus/platform/devices/8804000.sdhci`):
- **Controller Node:** `/soc/sdhci@8804000` (`sdhc_2`)
- **DTS Alias:** `sdhc2 = "/soc/sdhci@8804000"`
- **Physical Register Base:** `0x08804000`
- **Register Size:** `0x1000` (4 KiB)
- **Compatible String:** `"qcom,sdhci-msm-v5"`
- **Bus Width:** 4-bit (`qcom,bus-width = <0x04>`)
- **Interrupts:** `<0x00 0xcc 0x04 0x00 0xde 0x04>` (`hc_irq` and `pwr_irq`).
- **Power & Clocks:** Managed via RPMh interconnect and PM8150 regulators (`VDD_MX_LEVEL`, `S3C_LEVEL`).

### 1.1 Removable Media & Authorization Policy
1. **Removable Identification:** Media associated with `0x08804000` is flagged as `Media->RemovableMedia = TRUE`.
2. **Default Read-Only Policy:** During development, MicroSD media defaults to read-only mode (`Media->ReadOnly = TRUE`) to protect user data on inserted memory cards.
3. **Explicit Authorization Token:**
   - Writable Block I/O is enabled ONLY for test media explicitly authorized via `StorageProtection->AuthorizeTestMedia(Handle, &gR8QAuthorizedTestMediaGuid)`.
   - The token GUID `gR8QAuthorizedTestMediaGuid` (`{0x7c49e921, 0x2945, 0x4d53, {0x8a, 0xb2, 0x8b, 0xa3, 0x25, 0x93, 0x62, 0x51}}`) guarantees that arbitrary SD cards are never modified.
   - Writable access is strictly isolated: failed UFS write operations are **never redirected** to MicroSD.
   - Firmware never automatically repartitions or formats removable media.

---

## 2. USB Mass Storage Controller Architecture

Direct empirical verification from `devicetree/r8q-live.dts` and `/sys/bus/platform/devices/a600000.dwc3`:
- **Controller Node:** `/soc/usb@a600000` (`a600000.dwc3`)
- **Physical Register Base:** `0x0A600000`
- **Core Architecture:** Synopsys DesignWare Cores USB 3.0 (DWC3).
- **Driver Integration:** Upstream EDK II `MdeModulePkg/Bus/Usb/UsbMassStorageDxe` is compiled into the firmware volume, supporting standard USB flash drives connected via USB Type-C OTG adapters.
- **Protection Policy:** Like MicroSD, USB Mass Storage defaults to read-only unless specifically authorized as a test ESP.

---

## 3. Upstream Partition & FAT Filesystem Stack

The firmware flash volume ([R8QPkg.fdf](file:///root/r8q-uefi/platform/R8QPkg/R8QPkg.fdf)) integrates upstream EDK II drivers to provide full partition and filesystem discovery:

1. **`DiskIoDxe` (`MdeModulePkg/Universal/Disk/DiskIoDxe`):** Translates byte-level disk reads into 512-byte and 4096-byte block I/O transactions.
2. **`PartitionDxe` (`MdeModulePkg/Universal/Disk/PartitionDxe`):** Discovers and parses GUID Partition Tables (GPT) and Legacy Master Boot Records (MBR):
   - Successfully enumerates 36 partitions on UFS LUN 0 (`sda`).
   - Successfully enumerates 37 partitions on UFS LUN 3 (`sdd`).
   - Automatically exposes separate partition Block I/O handles (e.g. `boot`, `recovery`, `esp`).
3. **`EnhancedFatDxe` (`FatPkg/EnhancedFatDxe`):** Full FAT12, FAT16, and FAT32 filesystem support, exposing `EFI_SIMPLE_FILE_SYSTEM_PROTOCOL` and `EFI_FILE_PROTOCOL` over discovered partitions.
