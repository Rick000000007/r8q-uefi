# Project R8Q UEFI: Milestone 3 GOP & SimpleFbDxe Hardware Verification Report
**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona, Rev 2.1)  
**Document Revision:** 1.0.0-M3  
**Status:** Hardware Verified (Device-Observed `D` / Directly Present `V`)  

---

## 1. Framebuffer Physical Address & Memory Range

Empirical verification from the live device (`/sys/firmware/fdt` and `devicetree/r8q-live.dts`):
- **Node:** `/reserved-memory/cont_splash_region@9c000000`
- **Physical Base Address:** `0x9C000000`
- **Carveout Size:** `0x02300000` (36,700,160 bytes / 35.00 MiB)
- **Physical Memory Range:** `0x9C000000` to `0x9E300000`
- **Ownership:** Initialized by Samsung Application Bootloader (`ABL`) and Mobile Display Subsystem (`MDSS`) / Display Processing Unit (`DPU`). Handed off with continuous splash scanout enabled.

### 1.1 Resolution, Pixel Format, Bytes per Pixel & Stride
- **Installed Panel:** Samsung AMOLED `S6E3FC3_AMS646YD01_FHD` (`lcd_id=0x805081`)
- **Horizontal Resolution:** 1080 pixels
- **Vertical Resolution:** 2400 pixels
- **Pixel Format:** 32-bit BGRX (`PixelBlueGreenRedReserved8BitPerColor`)
  - Byte 0: Blue (8-bit)
  - Byte 1: Green (8-bit)
  - Byte 2: Red (8-bit)
  - Byte 3: Reserved (8-bit)
- **Bytes per Pixel:** 4 bytes
- **Active Scanout Stride:** 1080 pixels per scanline = 4320 bytes per scanline
- **Active Framebuffer Size:** $1080 \times 2400 \times 4 = 10,368,000$ bytes (approx. 9.888 MiB)
- **Headroom within Carveout:** $35.00\,\text{MiB} - 9.888\,\text{MiB} = 25.112\,\text{MiB}$

---

## 2. Reserved-Memory Ownership & Overlap Analysis

The contiguous splash framebuffer carveout interacts with adjacent regions as follows:

| Region Name | Physical Address Range | Size | Purpose & Overlap Analysis |
| :--- | :--- | :--- | :--- |
| `cont_splash_region` | `0x9C000000` – `0x9E300000` | 35.00 MiB | Primary continuous splash scanout buffer. |
| `disp_rdump_region` | `0x9C000000` – `0x9D200000` | 18.00 MiB | Display RAM dump buffer. Used exclusively by Samsung kernel panic handler for post-mortem analysis. Inactive during live firmware boot. |
| `dfps_data_region` | `0x9E300000` – `0x9E400000` | 1.00 MiB | Dynamic frame-rate data. Immediately adjacent; completely disjoint from active scanout range (`0x9C000000` – `0x9C9E3400`). |
| `sec_debug_region` | `0x9F000000` – `0x9F800000` | 8.00 MiB | Samsung security debug buffer. Disjoint. |

**Conclusion:** The active scanout area ($1080 \times 2400 \times 4 = \text{0x9E3400}$ bytes) occupies `0x9C000000` to `0x9C9E3400`. It does not collide with any active firmware or hardware region.

---

## 3. Cacheability & Memory Attributes

In the ARM64 translation tables established by EDK II (`ArmMmuLib`):
- **Memory Type:** `EFI_MEMORY_WC` (Write-Combining / Normal Non-Cacheable).
- **Attributes:** Outer & Inner Non-Cacheable, Normal memory, Shareable (`OSH`).
- **Rationale:** Mapping the display buffer as write-combining allows the CPU to aggregate sequential pixel writes into burst transactions on the Qualcomm NoC interconnect without polluting L1/L2/L3 caches. It eliminates the need for expensive cache flush operations (`DC CIVAC`) before hardware scanout by the DPU DMA pipeline.

---

## 4. Boot-Chain Handoff & Preservation

- **ABL Scanout State:** Samsung ABL configures the Qualcomm DPU 5.0 pipelines, DSI controller 0, DSI 2.5 GHz PLLs, PMIC OLED power rails (VREG_L11A, VREG_L13A), and AMOLED panel DCS commands (`S6E3FC3`). ABL presents the Samsung Galaxy boot logo and leaves the scanout engine running at 60 Hz.
- **Handoff Invariant:** ABL jumps to the payload at `text_offset = 0x80000` with the DPU scanout fully active.
- **Why Controller Reinitialization is Avoided:**
  - Re-clocking or resetting the Qualcomm MDSS/DPU from early UEFI without the complete Qualcomm display engine stack risks hard bus lockups, DSI PLL unlock, and panel blackout.
  - S6E3FC3 AMOLED requires strict DCS initialization and power sequencing. Re-issuing panel commands risks causing permanent retention or OLED panel stress.
  - `SimpleFbDxe` inherits the active scanout buffer without modifying any DPU hardware registers.

---

## 5. Dual-Mode Text Console Engine

To address the high pixel density (~407 PPI) of the 1080×2400 display, `SimpleFbDxe` implements `EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL` with two selectable modes:

| Mode | Font Geometry | Usable Columns | Usable Rows | Character Size (approx.) | Target Use Case |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **Mode 0** | $8 \times 19$ glyphs | **135** | **126** | $\sim 1.1\,\text{mm} \times 2.6\,\text{mm}$ | Full standard UEFI compatibility / dense diagnostic logs |
| **Mode 1** | $16 \times 38$ glyphs ($2\times$ pixel quad) | **67** | **63** | $\sim 2.2\,\text{mm} \times 5.2\,\text{mm}$ | High-readability interactive shell & menu mode |

### Implementation Features:
1. **Dynamic Font Scaling:** In Mode 1, each bit of the 8×19 glyph bitmap is expanded to a $2 \times 2$ pixel block on the display scanout.
2. **Overlap-Safe Scrolling:** When text output exceeds the maximum row limit, `GopBlt(EfiBltVideoToVideo)` shifts the display upward by 19 scanlines (Mode 0) or 38 scanlines (Mode 1), and `GopBlt(EfiBltVideoFill)` clears the newly exposed bottom row.
3. **Mode Switching:** Accessible via standard UEFI `SetMode` API and shell `mode` command. Mode change resets cursor position and clears the screen cleanly.
