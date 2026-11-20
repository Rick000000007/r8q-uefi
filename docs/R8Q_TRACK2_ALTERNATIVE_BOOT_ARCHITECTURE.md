# Project R8Q UEFI: Track 2 — Alternative Boot Architecture Report
**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q` / Qualcomm Snapdragon 865 `SM8250` Kona)  
**Host Environment:** LineageOS 23.2 (Android 16), Magisk Root, Kali Linux ARM64 Chroot  
**Track Focus:** Comprehensive Investigation of Alternative Boot Chains & Fallback Pathways  
**Document Status:** Complete & Audited  
**Date:** November 20, 2026  

---

## 1. Executive Summary & Track 2 Objective

Track 2 investigates alternative engineering pathways to execute custom R8Q UEFI firmware and native ARM64 Linux without relying on the primary Track 1 recovery-slot (`sda24`) staging approach. The purpose of this investigation is to identify a viable, practical fallback architecture in the event that Samsung ABL exhibits an unavoidable bootloader restriction with the compound image.

> [!IMPORTANT]
> **Operational Safety Notice:** All alternative execution pathways were analyzed using empirical hardware data, kernel configuration audits, and bootloader specifications. No experimental bootloaders, shims, or kernel replacements were flashed.

---

## 2. Exhaustive Alternative Boot Chain Matrix

| Alternative Execution Pathway | Required Capabilities | Image Format | Partition / Media Access | Memory & Security Requirements | Recovery Implications | Feasibility Classification |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Alt 1: ABL Fastboot Protocol** | Fastboot OEM commands in ABL (`fastboot boot / flash`) | Raw ELF or Android Boot v2 | Host USB cable access | Unlocked bootloader (`orange` state) | Zero partition risk for `fastboot boot` | **UNSUPPORTED** (Samsung ABL omits standard fastboot entirely) |
| **Alt 2: LineageOS Kernel Kexec** | In-kernel kexec syscall (`sys_kexec_load`) | Raw ARM64 binary or PE/COFF Image | Root access on running OS (`/dev/kmem`) | Normal DRAM page allocation; requires disabling MMU | 100% safe to storage; zero brick risk | **THEORETICALLY POSSIBLE** (Requires custom LineageOS kernel with `CONFIG_KEXEC=y`) |
| **Alt 3: Primary Slot Dual-Boot Shim** | Custom ARM64 early shim replacing `sda23` | Android Boot v2 with embedded shim | Replaces primary boot slot (`/dev/block/sda23`)| Requires volume-key polling before OS launch | **High Risk:** Overwrites working LineageOS boot partition | **THEORETICALLY POSSIBLE (High Risk)** |
| **Alt 4: Direct MicroSD / USB Boot** | ABL EFI file system driver & external media scan | FAT32 media with `/EFI/BOOT/BOOTAA64.EFI`| External MicroSD or USB-C Mass Storage | Requires ABL to enumerate external storage controllers| Zero internal UFS risk | **UNSUPPORTED** (Samsung ABL hardcodes internal UFS LUNs only) |
| **Alt 5: Intermediate U-Boot / LK Stage** | ABL loading U-Boot as an Android boot payload | Android Boot v2 wrapping U-Boot ELF | Staged to `sda24` or auxiliary UFS slot | U-Boot relocates itself and initializes MicroSD | Dependent on recovery slot viability | **THEORETICALLY POSSIBLE** |
| **Alt 6: Qualcomm EDL Sahara/Firehose** | Emergency Download Mode (9008 via test-point) | Raw MBN / ELF signed programmer | Qualcomm USB bulk endpoint | Requires Samsung-signed programmer ELF (`prog_firehose_*.elf`) | High risk of hard brick if unauthenticated | **UNSUPPORTED / UNVIABLE** |

---

## 3. Deep Analysis of Investigated Alternatives

### 3.1 Alternative 1: Samsung ABL Fastboot Protocol
- **Technical Reality:** On standard Google Pixel or Qualcomm reference devices, `fastboot boot <image>` allows streaming a boot image directly to RAM over USB, bypassing internal storage writes entirely.
- **Device Audit:** On Samsung Galaxy devices (including SM-G781B), Samsung removes the fastboot protocol from ABL, replacing it with the proprietary Odin/LOKE download protocol.
- **Userspace Fastboot Caveat:** Fastboot commands work on this device *only* inside LineageOS Recovery userspace (`fastbootd`). However, `fastbootd` runs within Android userspace after the recovery kernel has booted. It cannot execute an arbitrary raw kernel in RAM.
- **Verdict:** **UNSUPPORTED**. Direct fastboot booting cannot be used as an alternative boot chain.

### 3.2 Alternative 2: Kernel Kexec Trampoline from LineageOS
- **Technical Reality:** The Linux `kexec` mechanism allows an actively running Linux kernel to load a new kernel (or EDK II UEFI binary) into memory and jump directly into it, completely bypassing the device bootloader and hardware resets.
- **Device Audit:** Inspection of the live LineageOS 23 kernel configuration (`/proc/config.gz`) confirms:
  ```
  # CONFIG_KEXEC is not set
  ```
- **Requirements to Enable:**
  1. Build a custom LineageOS kernel with `CONFIG_KEXEC=y` and `CONFIG_KEXEC_FILE=y`.
  2. Flash the modified kernel to `sda23`.
  3. From within the running LineageOS environment (or Kali chroot), execute:
     ```bash
     kexec -l /root/r8q-uefi/build/Image --dtb=/root/r8q-uefi/build/r8q.dtb --initrd=/root/r8q-uefi/build/initramfs.img --command-line="console=tty0 root=/dev/ram0 rw"
     kexec -e
     ```
- **Pros:** Once enabled, native Linux or UEFI can be launched directly from an active terminal in Kali or Termux without touching `sda24` or using hardware button combinations.
- **Cons:** Flashing a custom kernel to `sda23` modifies the primary operating system boot chain, violating the non-interference rule for `sda23`.
- **Verdict:** **THEORETICALLY POSSIBLE (Recommended Secondary Fallback)**.

### 3.3 Alternative 3: Primary Slot Dual-Boot Shim (`sda23`)
- **Technical Reality:** A custom first-stage ARM64 shim is packaged as `boot.img` and flashed to `sda23`. During early boot, the shim polls the hardware volume buttons:
  - If `Volume Down` is held: Jump to R8Q UEFI / Native Linux.
  - Default: Chainload the original LineageOS kernel.
- **Evaluation:** While technically feasible, modifying `sda23` introduces direct risk to the primary LineageOS workstation. If the shim fails, the phone will fail to boot into LineageOS.
- **Verdict:** **NOT RECOMMENDED**. Violates project rule to preserve `sda23` untouched.

### 3.4 Alternative 4: Direct MicroSD / USB Boot
- **Technical Reality:** Standard PC and server UEFI firmwares search external FAT32 storage for `\EFI\BOOT\BOOTAA64.EFI`.
- **Device Audit:** Samsung ABL on SM8250 is compiled without external storage boot drivers. It communicates exclusively with internal UFS (`/dev/block/sda`, `sdb`, `sdd`). External MicroSD (`sdhci`) and USB OTG are initialized only after the Linux kernel loads.
- **Verdict:** **UNSUPPORTED**. External storage boot cannot be achieved at the bootloader stage.

---

## 4. Track 2 Recommendation & Practical Fallback Architecture

### Strategic Verdict: **NO-GO FOR PRIMARY (RETAIN AS CONTINGENCY BLUEPRINT)**

1. **Primary Track 1 Remains Superior:** Track 1 (staging to recovery partition `sda24`) is strictly superior to all investigated alternatives because it leaves the active primary OS (`sda23`) 100% untouched and does not require modifying the running LineageOS kernel.
2. **Designated Contingency Fallback (Alternative 2 - Kexec):**
   - If Track 1 fails due to an unexpected ABL image rejection that cannot be resolved through header tuning, **Alternative 2 (Kexec Trampoline)** is the designated fallback.
   - Enabling `CONFIG_KEXEC=y` within the LineageOS kernel tree would allow launching native Linux directly from the Kali chroot with zero hardware button interaction.
