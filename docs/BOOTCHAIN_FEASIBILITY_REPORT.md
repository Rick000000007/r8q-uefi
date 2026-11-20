# Project R8Q UEFI: Boot-Chain Feasibility & Image Format Investigation

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M2  
**Status:** Approved Architectural Baseline  

---

## 1. Executive Summary & Objective

In accordance with Section 3 of the Milestone 2 Engineering Constraints, this report provides a read-only investigation of the Samsung Galaxy S20 FE 5G boot chain, the exact Android boot image format accepted by the hardware, the ground reality of `fastboot boot` on retail Samsung platforms, and the structural requirements of the firmware payload.

---

## 2. Boot Image Header Analysis (Live Device Evidence)

Inspection of the primary boot partition (`/dev/block/sda23`) reveals the following structural parameters:

| Header Field | Value on SM-G781B | Technical Implication |
|---|---|---|
| **Magic** | `ANDROID!` (`0x414e44524f494421`) | Standard Android Boot Image |
| **Header Version** | **v2** | Requires kernel, ramdisk, and optionally dtb fields |
| **Page Size** | **4096 bytes** | Alignment boundary for all segments |
| **Kernel Size** | 55,767,064 bytes (~53.18 MiB) | Physical envelope for kernel payload |
| **Kernel Load Address Offset** | `0x8000` (from DRAM base `0x80000000`) | Physical DRAM entry: `0x80008000` (or `0x80080000`) |
| **Ramdisk Size** | 1,300,726 bytes (~1.24 MiB) | Initramfs payload size |
| **Ramdisk Load Address Offset**| `0x1000000` (`0x81000000` in DRAM) | Safe separation between kernel and initrd |
| **Recovery DTBO Size** | 0 bytes | Handled via dedicated `dtbo` partition (`sda22`) |
| **DTB Size** | 0 bytes | Inherited from platform firmware / `dtbo` |

---

## 3. Fastboot & Bootloader Mode Investigation

### 3.1 Samsung ABL Bootloader Reality
A common misconception in Android firmware porting is assuming all Qualcomm devices implement standard Android fastboot in ABL. On the Samsung SM-G781B:
1. **Samsung Download Mode (Loke / Odin):**
   - The primary bootloader interface exposed by ABL over USB is Samsung's proprietary Loke/Odin protocol.
   - It communicates using Samsung-specific USB endpoints (Bulk-In/Out) and accepts `.tar` / `.tar.md5` archives containing raw partition images.
2. **Userspace `fastbootd` in Recovery:**
   - On Android 10+ / One UI / LineageOS, fastboot is hosted inside the recovery ramdisk as the `fastbootd` daemon.
   - `fastbootd` exclusively supports partition-level operations (`fastboot flash boot ...`, `fastboot erase ...`, `fastboot getvar ...`).
   - Standard `fastboot boot <image>` (which transmits the image to RAM and invokes a direct jump) **is NOT supported on retail Samsung devices**. When executed, `fastbootd` returns:
     `FAILED (remote: 'Command not supported in fastbootd')`.
   - Samsung ABL does not listen on the standard fastboot protocol port during early boot.

### 3.2 Feasible & Safe Execution Paths
Because `fastboot boot` is not available in hardware ABL, the following execution strategies are feasible:
1. **Auxiliary / Recovery Slot Booting (Primary Safe Testing Strategy):**
   - Package R8Q UEFI into an Android Boot Image v2 container.
   - Install to a disposable/secondary test partition (or an external MicroSD-based chained loader), leaving the primary OS untouched.
2. **Samsung Odin Flashable Package:**
   - Package the boot image into a standard `boot.img.tar` for testing on unlocked devices.
3. **Chained EFI Application:**
   - If an existing Linux environment is running, kexec or an early chainloader can transition directly to R8Q UEFI in memory.

---

## 4. Executable Payload Architecture: ARM64 Linux Kernel Format

Samsung ABL validates the executable kernel inside `boot.img` before jumping to it. It expects a **standard ARM64 Linux Kernel Image format**:

```
Offset  Size  Field          Value on SM-G781B               Purpose
0x00    4     code0          0x14BE0000 (b 0x2F80000)        Branch to entry point past 64B header
0x04    4     code1          0x00000000                      NOP / reserved
0x08    8     text_offset    0x0000000000080000 (512 KiB)   Physical load offset from DRAM base
0x10    8     image_size     0x00000000046EE000 (~70.9 MiB) Total image execution size
0x18    8     flags          0x000000000000000A              Flags: Little-endian, 4KB page size
0x20    24    reserved       All zeros                       Reserved for future expansion
0x38    4     magic          0x644D5241 ("ARM\x64")          ARM64 Linux Kernel Image Magic
0x3C    4     res5           0x00000000                      Reserved
```

### 4.1 Requirement for a PrePi First-Stage Loader Wrapper
- A raw EDK II Firmware Device (`R8Q_EFI.fd`) starts with firmware volume headers or reset vectors that do **not** conform to the 64-byte ARM64 Linux Kernel Image format.
- If an unadorned EDK II FD is placed in `boot.img`, Samsung ABL will reject the image or jump into invalid opcodes.
- **Conclusion:** A dedicated first-stage loader wrapper (`PrePi/ModuleEntryPoint.S`) **is strictly required**.
- The wrapper presents the exact 64-byte ARM64 kernel header to ABL, catches the jump at `code0`, preserves `x0` (DTB pointer), initializes stack/MMU, and transitions cleanly into EDK II C code.

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
