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
    with open(dtb_path, "rb") as f:
        dtb_data = f.read()

    # 1. Construct 64-byte ARM64 Linux Header Wrapper for the compound kernel
    # code0: b +64 (branch forward 64 bytes = 0x14000010)
    code0 = 0x14000010
    code1 = 0x00000000
    text_offset = 0x80000  # 512 KiB alignment
    total_compound_size = 64 + len(fd_data) + len(kernel_data)
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

    # Compound kernel payload: [64B Wrapper] + [4.00 MiB R8Q_EFI.fd] + [46.03 MiB build/Image]
    compound_kernel = bytes(arm64_hdr) + fd_data + kernel_data
    compound_kernel_size = len(compound_kernel)

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

    with open(output_path, "wb") as out:
        # 1. Header (Page 0)
        out.write(header)
        
        # 2. Compound Kernel Payload
        out.write(compound_kernel)
        pad_kernel = align(compound_kernel_size, BOOT_PAGE_SIZE) - compound_kernel_size
        if pad_kernel > 0:
            out.write(b"\x00" * pad_kernel)

        # 3. Ramdisk Payload
        out.write(initrd_data)
        pad_ramdisk = align(ramdisk_size, BOOT_PAGE_SIZE) - ramdisk_size
        if pad_ramdisk > 0:
            out.write(b"\x00" * pad_ramdisk)

        # 4. DTB Payload
        out.write(dtb_data)
        pad_dtb = align(dtb_size, BOOT_PAGE_SIZE) - dtb_size
        if pad_dtb > 0:
            out.write(b"\x00" * pad_dtb)

    total_bytes = os.path.getsize(output_path)
    print("=================================================================")
    print("   PROJECT R8Q: COMPLETE COMPOUND BOOT IMAGE GENERATOR")
    print("   Target: Samsung Galaxy S20 FE 5G (SM-G781B / r8q / SM8250)")
    print("=================================================================")
    print(f"[SUCCESS] Complete compound boot image built: {output_path}")
    print(f"  Container Format:      Android Boot Image Header v{BOOT_HEADER_VERSION}")
    print(f"  Page Size:             {BOOT_PAGE_SIZE} bytes")
    print(f"  Compound Kernel Size:  {compound_kernel_size} bytes ({compound_kernel_size/(1024*1024):.2f} MiB)")
    print(f"    - Wrapper Header:    64 bytes")
    print(f"    - R8Q_EFI.fd Volume: {len(fd_data)} bytes ({len(fd_data)/(1024*1024):.2f} MiB)")
    print(f"    - Linux Kernel Image:{len(kernel_data)} bytes ({len(kernel_data)/(1024*1024):.2f} MiB)")
    print(f"  Ramdisk Size:          {ramdisk_size} bytes ({ramdisk_size/(1024*1024):.2f} MiB)")
    print(f"  DTB Size:              {dtb_size} bytes ({dtb_size/1024:.1f} KiB)")
    print(f"  Total Container Size:  {total_bytes} bytes ({total_bytes/(1024*1024):.2f} MiB)")
    print(f"  Headroom in sda24:     {(82739200 - total_bytes)/(1024*1024):.2f} MiB remaining in recovery partition")

if __name__ == "__main__":
    build_complete_boot_image()
