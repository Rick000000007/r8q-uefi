# Project R8Q UEFI: Milestone 3 Technical Specification
## UEFI Console, Graphics Output Protocol & Core Services Architecture

**Target Platform:** Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)  
**Document Revision:** 1.0.0-M3  
**Status:** Approved Architectural Specification  

---

## 1. Overview & Objectives

Milestone 3 transitions Project R8Q UEFI from an early Pre-Pi wrapper into an operational UEFI Core environment providing interactive display output, serial debugging, architectural timer services, and interrupt handling.

### Core Deliverables:
1. **Full Graphics Output Protocol (GOP) Engine:** Enhanced `SimpleFbDxe` supporting all four standard `Blt` operations (`EfiBltVideoFill`, `EfiBltBufferToVideo`, `EfiBltVideoToBuffer`, `EfiBltVideoToVideo`) on the Samsung AMOLED panel at physical base `0x9C000000`.
2. **Resolution-Aware Console Font Scaling:** High-DPI 2× font scaling engine (16×38 pixel glyphs) delivering an ergonomic 67-column × 63-row console on the 407 PPI AMOLED display.
3. **Qualcomm GENI UART Driver (`SerialPortLib`):** Hardware serial debugging stream at `0x00988000` (115200 8N1).
4. **Architectural Timer & Interrupt Services:** ARM GICv3 distributor/redistributor mapping (`0x17A00000` / `0x17A60000`) and ARMv8 generic timer (`CNTFRQ_EL0` = 19.2 MHz).
5. **UEFI Core Services Test Suite (`CoreTest`):** Diagnostic validation EFI application validating System Tables, Memory Allocation Services, Event/Timer Services, and GOP operations.

---

## 2. Graphics Output Protocol & Blt Engine Specification

### 2.1 Display Hardware Geometry
- **Panel:** Samsung S6E3FC3 AMOLED (`ss_dsi_panel_S6E3FC3_AMS646YD01_FHD`)
- **Native Dimensions:** 1080 horizontal × 2400 vertical
- **Color Depth:** 32-bit BGRX (8 bits Blue, 8 bits Green, 8 bits Red, 8 bits Reserved)
- **Stride:** 4320 bytes per scanline (1080 × 4 bytes)
- **Framebuffer Base:** `0x9C000000` (Continuous Splash Carveout, 35 MiB)

### 2.2 Blt Operations Implementation
```c
typedef enum {
  EfiBltVideoFill,
  EfiBltVideoToBltBuffer,
  EfiBltBufferToVideo,
  EfiBltVideoToVideo,
  EfiGraphicsOutputBltOperationMax
} EFI_GRAPHICS_OUTPUT_BLT_OPERATION;
```
- **`EfiBltVideoFill`:** Fills a rectangular region `[Width × Height]` with a single color. Optimized using 64-bit store pairs (`stp` on ARM64) when scanline-aligned.
- **`EfiBltBufferToVideo`:** Transfers off-screen pixel buffer to AMOLED display scanout memory.
- **`EfiBltVideoToBltBuffer`:** Captures on-screen display content back to memory for windowing / screenshots.
- **`EfiBltVideoToVideo`:** Performs fast rectangular blits within scanout memory for terminal text scrolling.

---

## 3. Font Scaling Architecture for High-DPI Displays

Standard UEFI fonts provide 8×19 pixel glyphs. On the 6.46-inch FHD+ AMOLED screen (407 PPI), unscaled glyphs measure approximately 0.5mm × 1.2mm, rendering text difficult to read without magnification.

### 2× Glyph Scaling Algorithm:
- Each source glyph bit expands to a 2×2 pixel square in video memory:
  ```
  Source Bit 1 -> [Pixel (2x, 2y), Pixel (2x+1, 2y), Pixel (2x, 2y+1), Pixel (2x+1, 2y+1)]
  ```
- Resulting glyph dimensions: **16 pixels wide × 38 pixels tall**.
- Screen layout: **67 text columns × 63 text rows** (leaving 4 pixels horizontal margin and 6 pixels vertical margin).

---

## 4. Qualcomm GENI UART Serial Console (`SerialPortLib`)

The Qualcomm Generic Interface (GENI) UART at `0x00988000` provides serial output for development diagnostics:
- **Base MMIO Address:** `0x00988000`
- **FIFO Depth:** 64 words (256 bytes)
- **Baud Rate:** 115200 bps
- **Format:** 8 data bits, no parity, 1 stop bit (8N1)
- **Operation:** Non-blocking FIFO write with polling of transmit status registers.

---

## 5. Architectural Core Services Integration

| Core Service | Driver Module | Physical Address / Protocol | Verification Gate |
|---|---|---|---|
| **DXE Core Engine** | `MdeModulePkg/Core/Dxe/DxeMain.inf` | Top-level dispatcher | Dispatches all architectural protocols |
| **GICv3 Interrupts** | `ArmPkg/Drivers/ArmGic/ArmGicDxe.inf` | `0x17A00000`, `0x17A60000` | Installs `EFI_HARDWARE_INTERRUPT_PROTOCOL` |
| **System Timer** | `ArmPkg/Drivers/TimerDxe/TimerDxe.inf` | 19,200,000 Hz (`CNTFRQ_EL0`) | Installs `EFI_TIMER_ARCH_PROTOCOL` |
| **Console Splitter** | `MdeModulePkg/Universal/Console/ConSplitterDxe/` | Virtual Console | Merges GOP and Serial into `ConOut` / `ConIn` |
| **Graphics Console** | `MdeModulePkg/Universal/Console/GraphicsConsoleDxe/` | Glyph renderer on GOP | Bridges `GraphicsOutput` to `SimpleTextOut` |

---

*Authored by Antigravity Engineering for Project R8Q UEFI.*
