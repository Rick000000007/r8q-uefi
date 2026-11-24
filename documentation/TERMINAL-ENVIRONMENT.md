# Project R8Q — Terminal-First Operating Environment

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Operating System:** Debian GNU/Linux 12 (Bookworm) ARM64  
**Primary User Interface:** Native Linux Console & Bash Shell  
**Document Revision:** 3.0.0 (Terminal-First Architectural Design)  
**Status:** Authoritative Terminal Specification  

---

## 1. Overview & Architectural Shift

Project R8Q establishes the **Terminal-First Operating Environment** as the default and primary user experience. The initial release does not automatically start GNOME, GDM, X11, or any graphical display manager.

When powered on, the device executes the complete hardware boot chain directly into a native Linux text console on the phone's built-in 2400 × 1080 AMOLED display, prompting for login and opening directly to an interactive ARM64 Bash shell.

```
[Power On]
   │
   ▼
[Samsung/Qualcomm Boot Chain] (PBL -> XBL -> Samsung ABL)
   │
   ▼
[R8Q UEFI Firmware] (PrePi -> EDK II -> GOP Display 0x9C000000)
   │
   ▼
[R8Q Boot Manager] (Scans internal UFS, SD, USB; 3s timeout)
   │
   ▼
[Debian 12 ARM64 Kernel & Initramfs] (EFI Stub -> switch_root)
   │
   ▼
[systemd Init] (Target: multi-user.target)
   │
   ▼
[Native Linux Console / Login] (getty@tty1 on AMOLED / serial-getty@ttyMSM0)
   │
   ▼
[Bash Shell] (GNU Bash 5.2+ ARM64 with full dev suite)
```

---

## 2. Core Operating System & Software Suite

The terminal environment is a complete, self-contained native Debian 12 ARM64 userspace (not Termux, not a chroot, not an Android application).

### 2.1 Essential Toolsets

| Functional Domain | Included Packages / Utilities | Purpose |
|---|---|---|
| **Shell & Session** | `bash`, `tmux`, `screen` | Default interactive login shell and multi-window terminal multiplexer |
| **Package Management** | `apt`, `dpkg` | Official Debian Bookworm package management, security updates, and software repository access |
| **Remote Access & Networking** | `openssh-client`, `openssh-server`, `NetworkManager`, `wpasupplicant`, `iproute2`, `curl`, `wget` | Hardened SSH access over Wi-Fi, USB Ethernet, or OTG; wireless network configuration via `nmcli` |
| **Development Toolchain** | `gcc`, `clang`, `binutils`, `make`, `cmake`, `python3`, `pkg-config`, `git` | Local native compilation and building of ARM64 software directly on the phone |
| **Text Editors** | `vim`, `nano` | Console-based text editing and code development |
| **Process & System Monitoring** | `htop`, `procps`, `iotop`, `ps`, `top` | Real-time CPU, RAM, process, and disk I/O monitoring |
| **Storage & USB Management** | `util-linux`, `e2fsprogs`, `parted`, `dosfstools`, `usbutils` (`lsusb`), `fdisk`, `blkid` | Partitioning, formatting, mounting, and managing internal UFS, SD cards, and USB OTG drives |
| **Diagnostics & Hardware Telemetry** | `lm-sensors`, `dmesg`, `journalctl`, `dmidecode`, `udev` | Battery charging telemetry, thermal zone readings, kernel ring buffer diagnostics |

---

## 3. AMOLED Display & Console Integration

The Samsung Galaxy S20 FE 5G features a 6.5-inch Super AMOLED display with a physical native resolution of 2400 × 1080 pixels (20:9 aspect ratio) in portrait orientation.

### 3.1 Display Drivers & Console Infrastructure
1. **Early Firmware Console:** `SimpleFbDxe` inside UEFI binds to the continuous splash buffer at physical address `0x9C000000`. Text output is rendered via UEFI standard text protocols.
2. **Kernel Framebuffer Handoff (`simplefb` / DRM `fbcon`):**
   - The Linux kernel receives the framebuffer memory reservation via Device Tree (`/chosen/framebuffer`).
   - The Linux framebuffer console driver (`fbcon`) binds immediately to the display.
   - Once initialized, the Qualcomm MSM DRM/KMS driver (`msm_drm`) with Freedreno transitions the panel into accelerated mode without blanking or flicker.

### 3.2 Resolution, Font Scaling & Readability
On a 2400 × 1080 screen at 407 PPI, standard 8x16 console fonts are illegibly small (~1 mm high).
To ensure comfortable visual usability without a desktop environment:
- **High-DPI Console Font:** Configure the virtual console (`/etc/default/console-setup`) to use high-resolution Terminus fonts:
  ```ini
  FONTFACE="Terminus"
  FONTSIZE="16x32"
  ```
  At 16×32 pixels per character, the 1080-pixel width accommodates ~67 characters per line in portrait orientation, rendering crisp, legible text.
- **Orientation Control:**
  - Default: Portrait orientation (`fbcon=rotate:0`).
  - Landscape Mode: Can be rotated dynamically via kernel command line (`fbcon=rotate:1` for 90° clockwise or `fbcon=rotate:3` for 270°) or through `/sys/class/graphics/fbcon/rotate`.
  - In landscape orientation (2400 width × 1080 height), a 16×32 font yields a 150-column × 33-row standard terminal display.

---

## 4. Input Architecture & Peripherals

### 4.1 USB Keyboard & Mouse (Primary Hardware Input)
- The phone's USB Type-C port supports USB 3.0 OTG (On-The-Go) host mode.
- Connecting a standard USB keyboard, USB mouse, or wireless RF dongle via a USB-C adapter triggers automatic detection via Linux kernel HID drivers (`hid-generic`, `usbhid`).
- Input keystrokes are received directly by the active Linux virtual terminal (`/dev/tty1`), providing immediate tactile typing capability.

### 4.2 Touchscreen Console Input Reality & Implementation
A standard Linux virtual terminal (`tty1` / `fbcon`) does not inherently translate capacitive touchscreen gestures into ASCII keystrokes.
1. **Touch Controller Hardware:** FocalTech / Samsung Touchscreen IC (`sec_touchscreen` on I2C/SPI).
2. **Kernel Event Generation:** Touch coordinates and contact events are emitted to `/dev/input/event*`.
3. **Console Touchscreen Solutions:**
   - **GPM (General Purpose Mouse):** Configured to bind to `/dev/input/touchscreen0` to provide touch-based cursor positioning, text selection, and pasting on the virtual console.
   - **Virtual Console On-Screen Keyboard:** For mobile typing without physical peripherals, an on-screen console keyboard (such as `tuir` or a lightweight direct-to-framebuffer keyboard daemon `fbpad` / `kmscon-touch`) can be spawned to render an on-screen keyboard layer.
   - **Secondary Input Recommendation:** SSH terminal access (over Wi-Fi or USB-C Ethernet) is recommended for intensive programming sessions prior to configuring physical USB keyboards.

---

## 5. Resource Optimization & Efficiency

In terminal-first mode, background resource utilization is minimized:
- **Idle RAM Usage:** Under 120 MiB of system memory (compared to ~1.2 GiB with GNOME running).
- **CPU Scaling Governor:** Configured to `schedutil` for responsive performance bursts during compilation while throttling to 710 MHz during idle text input.
- **Thermal Footprint:** Zero GPU 3D rendering load; device operates cold to the touch with passive dissipation.
- **Power Consumption:** AMOLED display power is significantly reduced by black console backgrounds (`#000000` pixels consume zero power on OLED panels).
