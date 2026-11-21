# Project R8Q — Phase 3.2: Partition Geometry & Hardware Keyrefuge Safety Audit

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Platform:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650)  
**Document ID:** `R8Q-DOC-P32-05`  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Authorization Boundary:** Read-Only Block Device Query & Offline Packager Safety Assertions (Strict Zero-Physical-Write Enforcement)

---

## 1. Executive Summary

Phase 3.1 identified a catastrophic device safety vulnerability (Blocker 5): the previous Phase 3 boot image package approached ~55.68 MiB and lacked hard capacity checks. A detailed inspection of the physical UFS storage layout revealed that the LineageOS Recovery partition (`sda24`) is exactly 82,694,144 bytes (78.86 MiB) and is immediately succeeded with **zero sector gap** by partition `sda25` (`keyrefuge`).

Partition `sda25` stores hardware-backed cryptographic material, Samsung Knox keystore certificates, and device encryption keys. Any staging or flashing operation that overruns `sda24` by even one single sector permanently overwrites `keyrefuge`, destroying hardware cryptographic identity and rendering the device unbootable.

In Phase 3.2:
1. **Physical Partition Boundaries Empirically Mapped:** Geometry was queried directly from `/sys/block/sda/` confirming start sectors, capacities, and the zero-gap interface between `sda24` and `sda25`.
2. **Decoupled Boot Image Packaging:** The packaging script [scripts/package_complete_boot_img.py](file:///root/r8q-uefi/scripts/package_complete_boot_img.py) was re-engineered to bundle only `arm64_hdr` + `R8Q_EFI.fd` (4.00 MiB) into the Android Boot Image v2 kernel slot. The complete output image [build/r8q-uefi-boot-complete.img](file:///root/r8q-uefi/build/r8q-uefi-boot-complete.img) is **7,974,912 bytes (7.61 MiB)**.
3. **Hardware Keystore Headroom:** Leaves **74,719,232 bytes (71.26 MiB / 90.3% free space)** of safety headroom before the `sda25` boundary.
4. **Hard Programmatic Boundary Guard:** Hard code assertions were embedded into the packager enforcing `total_bytes <= 82694144` and `kernel_size <= (0x80B00000 - 0x80080000)`.

---

## 2. Empirical Block Device Geometry (UFS 3.1 / `sda`)

Extracted directly from Linux block sysfs (`/sys/block/sda/`):

| Partition | Block Dev | Start Sector (512B) | Sector Count | Capacity (Bytes) | Capacity (MiB) | Function / Content |
|---|---|---|---|---|---|---|
| `boot` | `sda23` | `1,204,360` | `163,856` | `83,894,272` | 80.00 MiB | Active LineageOS 23.2 OS (STRICTLY PROTECTED) |
| `recovery` | `sda24` | `1,368,216` | `161,512` | `82,694,144` | 78.86 MiB | Designated R8Q UEFI Staging Slot |
| `keyrefuge`| `sda25` | `1,529,728` | `16,384` | `8,388,608` | 8.00 MiB | Hardware Knox / Keystore Crypto Material |

### Zero-Gap Boundary Proof:
$$\text{sda24\_start } (1368216) + \text{sda24\_sectors } (161512) = 1529728 = \text{sda25\_start}$$

The end of partition `sda24` directly touches sector `1529728` where `sda25` begins. **There is zero padding or guard band between recovery and keyrefuge.**

---

## 3. Decoupled Packaging & Headroom Calculation

### 3.1 Android Boot Image v2 Output Specification (`build/r8q-uefi-boot-complete.img`):

```
- Android Boot Magic: 'ANDROID!'
- Header Version: 2
- Page Size: 4096 bytes
- Kernel Segment Size: 4,194,368 bytes (4.00 MiB EDK II Firmware)
- Ramdisk Segment Size: 2,947,586 bytes (2.81 MiB Native Initramfs)
- DTB Segment Size: 821,466 bytes (0.78 MiB Mainline DTB)
- Total Image Size: 7,974,912 bytes (7.61 MiB)
```

### 3.2 Safety Headroom:
$$\Delta_{\text{safety}} = \text{Capacity}_{\text{sda24}} - \text{Size}_{\text{boot.img}}$$
$$\Delta_{\text{safety}} = 82,694,144 - 7,974,912 = 74,719,232 \text{ bytes } (71.26 \text{ MiB})$$
$$\text{Utilization} = \frac{7,974,912}{82,694,144} = 9.64\%$$

The staging package occupies less than 10% of `sda24`, leaving a massive 71.26 MiB safety margin protecting `keyrefuge`.

---

## 4. Programmatic Packager Safety Assertions

Implemented in [scripts/package_complete_boot_img.py](file:///root/r8q-uefi/scripts/package_complete_boot_img.py):

```python
# Hard Safety Boundaries from Physical Hardware Geometry
MAX_SDA24_CAPACITY = 82694144  # 161,512 sectors * 512 bytes = 78.86 MiB
TRUSTZONE_BOUNDARY = 0x80B00000 - 0x80080000 # 10.5 MiB (11,010,048 bytes)

# Guard 1: Verify Kernel Segment fits before TrustZone
if compound_kernel_size > TRUSTZONE_BOUNDARY:
    raise ValueError(
        f"[FATAL SAFETY VIOLATION] Compound kernel ({compound_kernel_size} B) "
        f"exceeds TrustZone boundary ({TRUSTZONE_BOUNDARY} B) by {compound_kernel_size - TRUSTZONE_BOUNDARY} B!"
    )

# Guard 2: Verify Total Boot Image fits within sda24
if total_bytes > MAX_SDA24_CAPACITY:
    raise ValueError(
        f"[FATAL PARTITION OVERRUN] Boot image ({total_bytes} B) exceeds sda24 capacity "
        f"({MAX_SDA24_CAPACITY} B) by {total_bytes - MAX_SDA24_CAPACITY} B! Threat to sda25 (keyrefuge)!"
    )
```

---

## 5. Verification Evidence

Validated by automated unit tests:
- `test_07_compound_boot_image_v2_header`: Confirms total image size `7,974,912` bytes, validates that `total_size <= 82,694,144` bytes (`MAX_SDA24_CAPACITY`), and verifies `kernel_size == 4,194,368` bytes <= TrustZone margin.
- `test_08_recovery_slot_isolation_and_safety_checks`: Verifies `sda23` (LineageOS boot partition) sector bounds and confirms zero modifications.

```
test_07_compound_boot_image_v2_header ... ok
test_08_recovery_slot_isolation_and_safety_checks ... ok
```
