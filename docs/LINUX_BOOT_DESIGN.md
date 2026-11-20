# Project R8Q UEFI: Native Linux Boot Design & Protocol Handoff

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M1  
**Status:** Approved Architectural Baseline  

---

## 1. Primary Operating System Target: Native Linux

Native Linux is the primary operating system target of Project R8Q UEFI. The firmware provides a clean, standards-compliant UEFI handoff to the ARM64 Linux kernel, supporting both EFI Stub loading and direct Image execution.

---

## 2. Kernel Boot Protocols & Handoff Mechanics

### 2.1 Supported Boot Paths
1. **UEFI EFI Stub Boot (Recommended & Standard):**
   - The Linux kernel binary (`Image` or `vmlinuz`) contains a built-in PE/COFF header and ARM64 EFI stub.
   - R8Q UEFI invokes the kernel using the standard UEFI `gBS->LoadImage()` and `gBS->StartImage()` services.
   - The EFI stub handles memory allocation, relocates the kernel, installs the EFI Configuration Table containing the Device Tree Blob (DTB), calls `ExitBootServices()`, and transitions to the kernel entry point.
2. **Direct Kernel Boot (Fallback / Custom Boot Loader):**
   - R8Q Boot Manager loads the raw uncompressed kernel `Image` to 2 MB-aligned physical RAM (e.g., `0x80200000` or `0x88400000`).
   - Copies the prepared DTB to an 8-byte aligned memory address.
   - Updates the DTB `/chosen` node with kernel command line, `linux,initrd-start`, and `linux,initrd-end`.
   - Calls `gBS->ExitBootServices()`.
   - Sets CPU registers according to the ARM64 Boot Protocol:
     - `x0`: Physical address of Device Tree Blob in RAM.
     - `x1`: `0x0000000000000000` (reserved).
     - `x2`: `0x0000000000000000` (reserved).
     - `x3`: `0x0000000000000000` (reserved).
   - Jumps directly to the kernel entry address.

---

## 3. Device Tree Blob (DTB) Runtime Synthesis & Patching

Rather than relying on a static out-of-date DTB, R8Q UEFI implements dynamic device tree preparation:
1. **Baseline Source:** The live hardware device tree inherited from ABL or loaded from the boot partition.
2. **Dynamic Injections performed by R8Q UEFI:**
   - **`/chosen/bootargs`**: Appends device-specific parameters (`console=ttyMSM0,115200n8 androidboot.hardware=qcom clk_ignore_unused pd_ignore_unused`).
   - **`/chosen/linux,initrd-start` and `/chosen/linux,initrd-end`**: Injected when an initramfs payload is loaded.
   - **`/reserved-memory`**: R8Q UEFI ensures that all Qualcomm TrustZone, modem, and continuous splash memory regions are strictly preserved in the DTB reserved-memory map to prevent kernel clobbering.
   - **`simple-framebuffer` node**: Injected at `/chosen/framebuffer` to provide early kernel console output via the continuous splash buffer (`0x9C000000`) before the native Qualcomm DRM KMS driver initializes:
     ```dts
     framebuffer {
         compatible = "simple-framebuffer";
         reg = <0x00 0x9c000000 0x00 0x02300000>;
         width = <1080>;
         height = <2400>;
         stride = <4320>;
         format = "a8r8g8b8";
     };
     ```

---

## 4. ExitBootServices Protocol Compliance

A critical failure point on Qualcomm ARM64 devices during kernel handoff is improper handling of `ExitBootServices()`:
1. **Timer Quiescence:** The UEFI architectural timer interrupt must be completely masked in the GIC before shutting down boot services.
2. **Memory Map Stability:** The memory map key (`MapKey`) must be valid. R8Q UEFI ensures that no memory allocations or deallocations occur between `GetMemoryMap()` and `ExitBootServices()`.
3. **Event Notification:** All registered `EVT_SIGNAL_EXIT_BOOT_SERVICES` events are signaled, allowing drivers (such as XHCI and UFS) to gracefully shut down DMA engines and place controllers in quiescent states.

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
