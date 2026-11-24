# Project R8Q — Optional GNOME Desktop Layer

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Operating System:** Debian GNU/Linux 12 (Bookworm) ARM64  
**Desktop Environment:** GNOME 43+ on Wayland / Mutter  
**Document Revision:** 3.0.0 (Decoupled Optional Desktop Specification)  
**Status:** Approved Desktop Specification  

---

## 1. Architectural Philosophy: Decoupled Desktop Layer

In accordance with the R8Q architecture change, **GNOME is not part of the default boot sequence**. It exists strictly as an optional, separately installable desktop layer that sits on top of the native Debian 12 terminal foundation.

### Core Architectural Invariants
1. **Zero Core Dependency:** The firmware, boot manager, kernel, initramfs, and core system utilities do not depend on GNOME, GDM, X11, or Wayland.
2. **Terminal Inviolability:** Installing, running, or removing GNOME must never break the ability to boot into the native Linux console (`multi-user.target`).
3. **Pluggable & On-Demand:** Users can operate in terminal-only mode for maximum performance and battery life, and launch GNOME only when a graphical workflow is required.

---

## 2. Desktop Components & Stack

```
+---------------------------------------------------------------+
|                       GNOME USERSPACE                         |
|   GNOME Shell 43+ | GNOME Files | GNOME Terminal | Settings   |
|   On-Screen Touch Keyboard (OSK) | Network & Power Settings   |
+---------------------------------------------------------------+
                               |
+---------------------------------------------------------------+
|                    COMPOSITOR & DISPLAY LAYER                 |
|   Mutter Wayland Compositor | GDM3 Display Manager            |
|   Wayland Protocol | XWayland Compatibility Layer             |
+---------------------------------------------------------------+
                               |
+---------------------------------------------------------------+
|                   GRAPHICS & ACCELERATION                     |
|   Mesa 23.x+ (Freedreno Gallium Driver & Turnip Vulkan)       |
|   Qualcomm Adreno 650 GPU Acceleration                        |
+---------------------------------------------------------------+
                               |
+---------------------------------------------------------------+
|              DRM / KMS KERNEL DRIVER (msm_drm)                |
+---------------------------------------------------------------+
```

---

## 3. Installation & Deployment Procedure

Because Debian 12 ARM64 package repositories are fully configured, GNOME can be installed cleanly using `apt`. To maintain system minimalism, installation without bloated extraneous packages is recommended:

```bash
# 1. Update package database
sudo apt update

# 2. Install minimal GNOME Shell, GDM3, and Wayland compositor
sudo apt install --no-install-recommends \
    gnome-session \
    gnome-shell \
    gdm3 \
    mutter \
    gnome-terminal \
    gnome-control-center \
    nautilus \
    pipewire \
    wireplumber \
    mesa-vulkan-drivers \
    libgl1-mesa-dri \
    xwayland

# 3. Ensure multi-user.target remains the default boot target (Terminal-First)
sudo systemctl set-default multi-user.target
```

---

## 4. Operation: Starting, Stopping & Switching

### 4.1 Launching GNOME On-Demand (From Terminal)
A user logged into the terminal console can launch the graphical desktop manager at any time:
```bash
sudo systemctl start gdm3
```
GDM3 will start on `tty7` (or `tty2`), launch the Mutter Wayland compositor, and present the graphical login screen on the AMOLED panel.

### 4.2 Returning to Terminal-Only Operation
To close GNOME and return immediately to the lightweight terminal environment:
```bash
# Stop the display manager and return all RAM to the terminal pool
sudo systemctl stop gdm3

# Switch back to the primary console
chvt 1
```

### 4.3 Setting Default Boot Behavior
- **Default to Terminal Boot (Factory Default):**
  ```bash
  sudo systemctl set-default multi-user.target
  ```
- **Set Default to Graphical Desktop (Optional User Preference):**
  ```bash
  sudo systemctl set-default graphical.target
  ```
- **Return to Terminal Boot from Graphical Mode:**
  ```bash
  sudo systemctl set-default multi-user.target
  ```

---

## 5. Touchscreen, Display Scaling & Mobile Usability

### 5.1 Display Resolution & Fractional Scaling
On the 2400 × 1080 AMOLED screen, native 100% UI scaling renders desktop elements too small for finger touches.
- **Wayland Fractional Scaling:** Mutter supports fractional scaling under Wayland.
- **Recommended Scale Factor:** **200%** (rendering UI elements at an effective 1200 × 540 viewport) or **175%** for optimal touchscreen hit targets and text clarity.
- Configuration:
  ```bash
  gsettings set org.gnome.mutter experimental-features "['scale-monitor-framebuffer']"
  ```

### 5.2 Touchscreen & On-Screen Keyboard (OSK)
- **Multi-Touch Gestures:** Supported natively by Mutter via `libinput`. 3-finger swipe switches workspaces; tap-and-drag provides window movement.
- **On-Screen Keyboard Integration:** GNOME Shell includes a built-in on-screen keyboard that automatically slides up from the bottom of the screen when a text input field is focused.
- **Screen Rotation:** Dynamic portrait/landscape switching is supported through GNOME Settings or automated via the Qualcomm sensor hub accelerometer.

---

## 6. Graphical Session Recovery & Diagnostics

If an unsupported GPU feature or driver issue causes GNOME or Mutter to hang during startup:
1. **Console Recovery Hotkey:** Press `Ctrl + Alt + F1` (via USB keyboard) or connect via SSH to switch away from the frozen graphical virtual terminal.
2. **Emergency Desktop Disable:**
   ```bash
   sudo systemctl stop gdm3
   sudo systemctl disable gdm3
   sudo systemctl set-default multi-user.target
   ```
3. **Session Diagnostic Logging:**
   ```bash
   # Inspect Mutter and GDM logs
   journalctl -u gdm3 -b
   journalctl --user -u gnome-shell -b
   ```
4. **Guaranteed Fallback:** Because the core OS is completely independent of GNOME, stopping GDM instantly restores full terminal operation with zero corruption risk.
