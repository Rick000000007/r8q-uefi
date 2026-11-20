# Project R8Q UEFI: Linux Boot Design

**Target:** Samsung Galaxy S20 FE 5G (`SM-G781B`, `r8q`, SM8250)
**Document revision:** 1.1.0-M1 (corrected baseline)
**Status:** Design. No Linux kernel has been booted on R8Q UEFI.

---

## 1. Scope

Linux is the primary operating-system target. The firmware should support two paths:

1. **EFI stub (preferred):** the ARM64 kernel `Image` contains a PE/COFF header and EFI stub. UEFI loads it with `LoadImage()`/`StartImage()`, passes the DTB and initrd, and the stub calls `ExitBootServices()`.
2. **Direct boot (fallback):** the firmware loads a raw `Image`, prepares the DTB, exits boot services, and jumps to the kernel entry with the ARM64 boot protocol registers.

Neither path has been validated on this device.

---

## 2. EFI-stub path

### 2.1 Prerequisites

- A working GOP or serial console.
- A block device and FAT driver to read the kernel, DTB, and initrd.
- A file-backed or otherwise safe variable store.
- A validated memory map that preserves all vendor carveouts.
- An ARM64 kernel with EFI stub support.

### 2.2 Flow

```text
Boot manager
  → locate EFI/BOOT/BOOTAA64.EFI or a configured Linux entry
  → LoadImage(kernel Image)
  → build/patch DTB
  → install EFI configuration table (DTB) and/or initrd
  → StartImage()
  → Linux EFI stub
  → ExitBootServices()
  → kernel entry
```

The exact mechanism for passing the DTB and initrd depends on the kernel configuration and the EFI stub. The firmware must not assume that a particular `/chosen` property or configuration-table GUID is accepted; it should follow the documented Linux arm64 EFI stub interface and test it.

### 2.3 Kernel command line

A candidate command line is:

```text
console=tty0 clk_ignore_unused pd_ignore_unused
```

This is a starting point, not a validated line. The final line must be derived from the kernel config, the display/console path, and the storage root device. Do not copy Android vendor bootargs blindly; many of them are Android-specific and may confuse a mainline kernel.

---

## 3. Direct-boot path

### 3.1 ARM64 boot protocol

At kernel entry:

| Register | Value |
|---|---|
| `x0` | Physical address of the DTB |
| `x1` | 0 |
| `x2` | 0 |
| `x3` | 0 |
| `PC` | Kernel entry point |

The kernel must be loaded at a 2 MiB-aligned address (the arm64 `text_offset` rules apply). The exact load address is **unknown** for this device; the firmware must choose a free region from the live memory map and must not overlap the kernel/initrd/DTB or any carveout.

### 3.2 Image header

A raw ARM64 `Image` starts with a 64-byte header:

| Offset | Field | Notes |
|---:|---|---|
| `0x00` | `code0` | Branch instruction |
| `0x04` | `code1` | Reserved/NOP |
| `0x08` | `text_offset` | Load offset from RAM base |
| `0x10` | `image_size` | Effective image size |
| `0x18` | `flags` | Endianness/page-size flags |
| `0x20` | reserved | 24 bytes |
| `0x38` | magic | `ARM\x64` |
| `0x3C` | reserved | 4 bytes |

The firmware should validate the magic and the image size before jumping. It must not assume that an arbitrary FD or EFI binary is a valid ARM64 `Image`.

### 3.3 DTB preparation

The firmware should:

- start from the live FDT inherited from ABL, or a DTB stored on the ESP;
- preserve all `/reserved-memory` nodes and `no-map` semantics;
- update `/chosen/bootargs`;
- add `linux,initrd-start`/`linux,initrd-end` if an initrd is used;
- ensure the DTB itself is in a reserved, non-overlapping region;
- keep the DTB size within the available space;
- validate the FDT header and structure before use.

Do not synthesize a minimal DTB from scratch for the first hardware boot. The vendor FDT contains critical carveouts and device descriptions that a minimal DTB would lose.

---

## 4. Memory and carveout handling

The downstream map has a large number of reserved regions (hypervisor, XBL/AOP, SMEM, PIL firmware, splash, Samsung debug/log/TIMA, RDX, etc.). The kernel must receive a DTB whose `/reserved-memory` nodes match the live map. If the firmware passes a truncated map, the kernel may allocate over firmware or secure-world memory.

Rules:

- Never mark a vendor carveout as `EfiConventionalMemory`.
- Never delete a `/reserved-memory` node to "free" memory.
- Keep the framebuffer reserved even if a simple framebuffer is advertised.
- If the kernel does not understand a vendor node, leave it reserved rather than dropping it.
- Re-check the map after `ExitBootServices()` if the kernel/DTB is reloaded.

---

## 5. ExitBootServices

Before calling `ExitBootServices()`:

1. Stop the UEFI timer and mask timer interrupts.
2. Quiesce DMA-capable controllers that the OS will reinitialize.
3. Ensure the memory map key is current and no allocations occur between `GetMemoryMap()` and `ExitBootServices()`.
4. Signal `EVT_SIGNAL_EXIT_BOOT_SERVICES` events.
5. Preserve the DTB and initrd in memory that is not freed.
6. Do not rely on boot-services file I/O after exit.

The exact controller-quiesce sequence for UFS, USB, and PCIe is driver-specific and must be implemented and tested. A driver that leaves DMA active can corrupt memory after the OS takes over.

---

## 6. Open questions

1. Does the stock ABL path accept an EFI-stub kernel directly, or does it require an Android boot-image wrapper?
2. What load address and `text_offset` does ABL use?
3. Is the inherited DTB complete enough for a mainline kernel, or does it need vendor fixups?
4. Which console works first: inherited framebuffer, debug UART, or USB?
5. Does the kernel need vendor firmware for UFS, display, or PMIC?
6. What is the tested root filesystem and initrd layout?
7. Can the kernel survive without the vendor's Android bootargs?

These questions must be answered before claiming Linux boot support.

---

## 7. Non-claims

- No Linux kernel has been booted on R8Q UEFI.
- No root filesystem, initrd, or display handoff has been validated.
- No performance, power, or thermal claim is made.
- The `console=tty0` candidate line is not a guarantee that the inherited framebuffer works.
