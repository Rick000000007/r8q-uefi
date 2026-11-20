#!/usr/bin/env python3
"""
Project R8Q UEFI: Android Boot Image v2 Packaging Tool (Proof-of-Concept)
Packages the compiled R8Q UEFI binary into a standard Android Boot Image v2.
Operates purely on files in /root/r8q-uefi/build.
DOES NOT flash or write to any device partition.
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

def package_boot_img(kernel_path, output_path, cmdline=""):
    if not os.path.exists(kernel_path):
        print(f"ERROR: Kernel file {kernel_path} not found.")
        sys.exit(1)

    with open(kernel_path, "rb") as f:
        kernel_data = f.read()

    # Verify if payload already contains 64-byte ARM64 Linux Kernel Image Header
    # If not (e.g. raw EDK II FD), prepend the compliant 64-byte ARM64 header wrapper
    has_arm64_header = False
    if len(kernel_data) >= 64 and kernel_data[56:60] == b"ARMd":
        has_arm64_header = True

    if not has_arm64_header:
        print("[PACKAGER] Prepending 64-byte ARM64 Linux Kernel Header wrapper to payload...")
        # code0: b +64 (branch forward 16 instructions = 64 bytes: 0x14000010)
        code0 = 0x14000010
        code1 = 0x00000000
        text_offset = 0x80000 # 512 KiB alignment
        total_image_size = len(kernel_data) + 64
        flags = 0x0A          # Little-endian, 4KB page size
        arm64_magic = b"ARMd" # 0x644D5241 ("ARM\x64")

        arm64_hdr = bytearray(64)
        struct.pack_into(
            "<IIQQQ24s4sI",
            arm64_hdr, 0,
            code0, code1,
            text_offset,
            total_image_size,
            flags,
            b"\x00" * 24,
            arm64_magic,
            0
        )
        kernel_data = bytes(arm64_hdr) + kernel_data

    kernel_size = len(kernel_data)
    ramdisk_data = b"" # Empty or stub ramdisk for proof-of-concept
    ramdisk_size = len(ramdisk_data)

    # Offsets matching Samsung Galaxy S20 FE 5G SM8250 baseline
    kernel_addr = 0x8000
    ramdisk_addr = 0x1000000
    second_addr = 0x0
    tags_addr = 0x100

    # Android Boot Header v2 (1660 bytes total)
    # Magic (8B)
    # kernel_size (4B), kernel_addr (4B)
    # ramdisk_size (4B), ramdisk_addr (4B)
    # second_size (4B), second_addr (4B)
    # tags_addr (4B), page_size (4B)
    # header_version (4B)
    # os_version (4B)
    # name (16B)
    # cmdline (512B)
    # id (32B)
    # extra_cmdline (1024B)
    # recovery_dtbo_size (4B), recovery_dtbo_offset (8B), header_size (4B)
    # dtb_size (4B), dtb_addr (8B)

    cmdline_bytes = cmdline.encode("ascii")[:512].ljust(512, b"\x00")
    extra_cmdline_bytes = b"\x00" * 1024
    name_bytes = b"R8Q_UEFI".ljust(16, b"\x00")
    sha = hashlib.sha1(kernel_data + ramdisk_data).digest().ljust(32, b"\x00")

    header = bytearray(BOOT_PAGE_SIZE)
    struct.pack_into(
        "<8s9II16s512s32s1024sIQIIQ",
        header, 0,
        BOOT_MAGIC,
        kernel_size, kernel_addr,
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
        0, 0        # dtb_size, dtb_addr
    )

    with open(output_path, "wb") as out:
        out.write(header)
        out.write(kernel_data)
        # Pad kernel to page size
        pad = align(kernel_size, BOOT_PAGE_SIZE) - kernel_size
        if pad > 0:
            out.write(b"\x00" * pad)

    total_bytes = os.path.getsize(output_path)
    print(f"[SUCCESS] Boot Image packaged cleanly: {output_path}")
    print(f"  Header Version: {BOOT_HEADER_VERSION}")
    print(f"  Page Size:      {BOOT_PAGE_SIZE} bytes")
    print(f"  Kernel Size:    {kernel_size} bytes ({kernel_size/(1024*1024):.2f} MiB)")
    print(f"  Total Image:    {total_bytes} bytes ({total_bytes/(1024*1024):.2f} MiB)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: package_boot_img.py <kernel.bin> <output.img> [cmdline]")
        sys.exit(1)
    k_path = sys.argv[1]
    o_path = sys.argv[2]
    cmd = sys.argv[3] if len(sys.argv) > 3 else "console=tty0 clk_ignore_unused pd_ignore_unused"
    package_boot_img(k_path, o_path, cmd)
