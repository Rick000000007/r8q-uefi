#!/usr/bin/env python3
"""
Project R8Q UEFI: Complete Self-Contained Android Boot Image v2 Packager
Bundles R8Q EDK II Firmware Volume, Linux ARM64 EFI Stub Kernel,
Rescue Initramfs, and R8Q Device Tree Blob into a single boot container.
Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)
"""

import os
import sys
import struct
import hashlib
import subprocess

BOOT_MAGIC = b"ANDROID!"
BOOT_PAGE_SIZE = 4096
BOOT_HEADER_VERSION = 2

def align(size, page_size):
    return (size + page_size - 1) & ~(page_size - 1)

def build_complete_boot_image():
    project_root = "/root/r8q-uefi"
    fd_path = os.path.join(project_root, "build/R8Q_EFI.fd")
    kernel_path = os.path.join(project_root, "build/Image")
    initrd_path = os.path.join(project_root, "build/initramfs.img")
    # Check for mainline DTB first, fall back to vendor dump if absent
    mainline_dtb = os.path.join(project_root, "build/sm8250-samsung-r8q.dtb")
    if os.path.exists(mainline_dtb):
        dtb_path = mainline_dtb
    else:
        dtb_path = os.path.join(project_root, "build/r8q.dtb")
    output_path = os.path.join(project_root, "build/r8q-uefi-boot-complete.img")

    for p in [fd_path, kernel_path, initrd_path, dtb_path]:
        if not os.path.exists(p):
            print(f"ERROR: Missing required input file: {p}")
            sys.exit(1)

    with open(fd_path, "rb") as f:
        fd_data = f.read()
    with open(kernel_path, "rb") as f:
        kernel_data = f.read()
    with open(initrd_path, "rb") as f:
        initrd_data = f.read()

    # Pre-patch DTB /chosen node with authoritative Linux ARM64 boot parameters
    # Sets console, earlycon, initramfs destination buffer (0xA4400000 - 0xA46CF9EA), and rootfs mount
    initrd_start = 0xA4400000
    initrd_end = initrd_start + len(initrd_data)
    bootargs_str = "console=tty0 console=ttyMSM0,115200n8 earlycon=msm_geni_serial,0xa90000 clk_ignore_unused pd_ignore_unused initcall_debug loglevel=8 root=/dev/ram0 rw init=/init"

    subprocess.run(["fdtput", "-t", "s", dtb_path, "/chosen", "bootargs", bootargs_str], check=True)
    subprocess.run(["fdtput", "-p", "-t", "x", dtb_path, "/chosen", "linux,initrd-start", "0x0", f"0x{initrd_start:x}"], check=True)
    subprocess.run(["fdtput", "-p", "-t", "x", dtb_path, "/chosen", "linux,initrd-end", "0x0", f"0x{initrd_end:x}"], check=True)

    with open(dtb_path, "rb") as f:
        dtb_data = f.read()

    # 1. Construct 64-byte ARM64 Linux Header Wrapper for the Compound Firmware + Kernel Payload
    # code0: b +64 (branch forward 64 bytes = 0x14000010)
    code0 = 0x14000010
    code1 = 0x00000000
    text_offset = 0x80000  # 512 KiB alignment
    compound_payload = fd_data + kernel_data
    total_compound_size = 64 + len(compound_payload)
    flags = 0x0A           # Little-endian, 4KB page size
    arm64_magic = b"ARM\x64"

    arm64_hdr = bytearray(64)
    struct.pack_into(
        "<IIQQQ24s4sI",
        arm64_hdr, 0,
        code0, code1,
        text_offset,
        total_compound_size,
        flags,
        b"\x00" * 24,
        arm64_magic,
        0
    )

    # Compound kernel payload: [64B Wrapper] + [4.00 MiB R8Q_EFI.fd] + [16.02 MiB Image]
    # Staged by ABL into high System RAM (0xA0160000), completely outside TrustZone (0x80B00000).
    compound_kernel = bytes(arm64_hdr) + compound_payload
    compound_kernel_size = len(compound_kernel)

    # Critical Safety Ceiling Assertions:
    MAX_COMPOUND_PAYLOAD_CEILING = 25 * 1024 * 1024  # 25 MiB ceiling for compound kernel
    if compound_kernel_size > MAX_COMPOUND_PAYLOAD_CEILING:
        raise ValueError(
            f"SAFETY VIOLATION: Compound kernel size {compound_kernel_size} bytes exceeds "
            f"safety ceiling ({MAX_COMPOUND_PAYLOAD_CEILING} bytes)!"
        )

    ramdisk_size = len(initrd_data)
    dtb_size = len(dtb_data)

    # Offsets matching Qualcomm SM8250 / Samsung ABL baseline
    kernel_addr = 0x00008000
    ramdisk_addr = 0x01000000
    second_addr = 0x00000000
    tags_addr = 0x00000100
    dtb_addr = 0x0000000001F00000

    cmdline_str = "console=tty0 clk_ignore_unused pd_ignore_unused root=/dev/mmcblk0p2 rw rootwait init=/init"
    cmdline_bytes = cmdline_str.encode("ascii")[:512].ljust(512, b"\x00")
    extra_cmdline_bytes = b"\x00" * 1024
    name_bytes = b"R8Q_COMPOUND".ljust(16, b"\x00")

    # SHA1 checksum of kernel + ramdisk
    sha = hashlib.sha1(compound_kernel + initrd_data).digest().ljust(32, b"\x00")

    # Android Boot Header v2 (1660 bytes total struct)
    header = bytearray(BOOT_PAGE_SIZE)
    struct.pack_into(
        "<8s9II16s512s32s1024sIQIIQ",
        header, 0,
        BOOT_MAGIC,
        compound_kernel_size, kernel_addr,
        ramdisk_size, ramdisk_addr,
        0, second_addr,
        tags_addr, BOOT_PAGE_SIZE,
        BOOT_HEADER_VERSION,
        0, # os_version
        name_bytes,
        cmdline_bytes,
        sha,
        extra_cmdline_bytes,
        0, 0, 1660, # recovery_dtbo_size, recovery_dtbo_offset, header_size
        dtb_size, dtb_addr
    )

    # Calculate and verify exact page-aligned component offsets
    header_offset = 0
    kernel_offset = BOOT_PAGE_SIZE
    kernel_end_raw = kernel_offset + compound_kernel_size
    pad_kernel = align(compound_kernel_size, BOOT_PAGE_SIZE) - compound_kernel_size
    ramdisk_offset = kernel_end_raw + pad_kernel
    ramdisk_end_raw = ramdisk_offset + ramdisk_size
    pad_ramdisk = align(ramdisk_size, BOOT_PAGE_SIZE) - ramdisk_size
    dtb_offset = ramdisk_end_raw + pad_ramdisk
    dtb_end_raw = dtb_offset + dtb_size
    pad_dtb = align(dtb_size, BOOT_PAGE_SIZE) - dtb_size
    expected_total_size = dtb_end_raw + pad_dtb

    # Assert exact expected component layout geometry
    assert kernel_offset == 0x1000, f"Kernel start must be 0x1000, got 0x{kernel_offset:x}"
    assert ramdisk_offset == align(kernel_end_raw, BOOT_PAGE_SIZE), f"Ramdisk offset 0x{ramdisk_offset:x} must be page-aligned to kernel end"
    assert ramdisk_end_raw <= dtb_offset, f"Ramdisk raw end 0x{ramdisk_end_raw:x} exceeds DTB offset 0x{dtb_offset:x}"
    assert dtb_offset == align(ramdisk_end_raw, BOOT_PAGE_SIZE), f"DTB offset 0x{dtb_offset:x} must be page-aligned to ramdisk end"
    assert dtb_end_raw <= expected_total_size, f"DTB raw end 0x{dtb_end_raw:x} exceeds total size 0x{expected_total_size:x}"
    assert expected_total_size == align(dtb_end_raw, BOOT_PAGE_SIZE), f"Total image size 0x{expected_total_size:x} must be page-aligned"

    with open(output_path, "wb") as out:
        # 1. Header (Page 0)
        out.write(header)
        
        # 2. Compound Kernel Payload
        out.write(compound_kernel)
        if pad_kernel > 0:
            out.write(b"\x00" * pad_kernel)

        # 3. Ramdisk Payload
        out.write(initrd_data)
        if pad_ramdisk > 0:
            out.write(b"\x00" * pad_ramdisk)

        # 4. DTB Payload
        out.write(dtb_data)
        if pad_dtb > 0:
            out.write(b"\x00" * pad_dtb)

    total_bytes = os.path.getsize(output_path)
    assert total_bytes == expected_total_size, f"File size mismatch: {total_bytes} != {expected_total_size}"

    MAX_SDA24_CAPACITY = 82694144  # Exactly 161,512 sectors * 512 bytes on physical UFS storage
    if total_bytes > MAX_SDA24_CAPACITY:
        os.remove(output_path)
        raise ValueError(
            f"CRITICAL SAFETY OVERRUN: Output boot image size {total_bytes} bytes exceeds "
            f"exact physical capacity of recovery partition sda24 ({MAX_SDA24_CAPACITY} bytes)! "
            f"Staging this image would overwrite {total_bytes - MAX_SDA24_CAPACITY} bytes into "
            f"sda25 (keyrefuge), causing permanent cryptographic bricking of hardware Knox keys."
        )

    print("=================================================================")
    print("   PROJECT R8Q: COMPLETE COMPOUND BOOT IMAGE GENERATOR")
    print("   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)")
    print("=================================================================")
    print(f"[SUCCESS] Complete compound boot image built: {output_path}")
    print(f"  Container Format:      Android Boot Image Header v{BOOT_HEADER_VERSION}")
    print(f"  Page Size:             {BOOT_PAGE_SIZE} bytes")
    print(f"  Component Layout Offsets (Page-Aligned):")
    print(f"    - Header (Page 0):   0x00000000 - 0x00000FFF (4,096 bytes)")
    print(f"    - Kernel Payload:    0x{kernel_offset:08X} - 0x{kernel_end_raw:08X} ({compound_kernel_size} bytes)")
    print(f"      ├─ Wrapper Header: 64 bytes (0x00001000 - 0x0000103F)")
    print(f"      ├─ R8Q_EFI.fd:     {len(fd_data)} bytes (0x00001040 - 0x0040103F)")
    print(f"      └─ Linux Image:    {len(kernel_data)} bytes (0x00401040 - 0x0140403F)")
    print(f"      └─ Zero Padding:   {pad_kernel} bytes (0x{kernel_end_raw:08X} - 0x{ramdisk_offset:08X})")
    print(f"    - Ramdisk Payload:   0x{ramdisk_offset:08X} - 0x{ramdisk_end_raw:08X} ({ramdisk_size} bytes)")
    print(f"      └─ Zero Padding:   {pad_ramdisk} bytes (0x{ramdisk_end_raw:08X} - 0x{dtb_offset:08X})")
    print(f"    - DTB Payload:       0x{dtb_offset:08X} - 0x{dtb_end_raw:08X} ({dtb_size} bytes)")
    print(f"      └─ Zero Padding:   {pad_dtb} bytes (0x{dtb_end_raw:08X} - 0x{expected_total_size:08X})")
    print(f"  Total Container Size:  {total_bytes} bytes (0x{total_bytes:08X} / {total_bytes/(1024*1024):.2f} MiB)")
    print(f"  Headroom in sda24:     {(MAX_SDA24_CAPACITY - total_bytes)/(1024*1024):.2f} MiB remaining before sda25 boundary")

if __name__ == "__main__":
    build_complete_boot_image()
