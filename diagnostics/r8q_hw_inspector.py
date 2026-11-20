#!/usr/bin/env python3
"""
Project R8Q UEFI: host-side read-only hardware inspection prototype.

This is NOT the UEFI diagnostic engine and it does NOT run inside R8Q UEFI.
It is a small Linux-side tool used to design diagnostic output and to collect
read-only evidence when the target is running a Linux kernel. When it runs on
the build host, every value is a host value, not a phone fact.

Design rules:
  * Print UNKNOWN instead of a plausible default.
  * Never write to a block device or partition.
  * Do not print serial numbers, IMEI, MAC addresses, or other identifiers
    unless --show-identifiers is explicitly passed.
  * Do not infer a UFS LUN map, panel model, charger, or fuel gauge from a
    filename or a public reference.
"""

from __future__ import annotations

import argparse
import glob
import os
import struct
import sys
from pathlib import Path

TARGET_MARKERS = ("SM-G781B", "r8q", "Samsung Galaxy S20 FE")
UNKNOWN = "UNKNOWN"


def read_text(path: str, default: str = UNKNOWN) -> str:
    try:
        return Path(path).read_text(errors="ignore").strip("\x00\n \t")
    except OSError:
        return default


def read_int(path: str) -> int | None:
    value = read_text(path)
    try:
        return int(value, 0)
    except (TypeError, ValueError):
        return None


def host_model() -> str:
    for path in (
        "/sys/firmware/devicetree/base/model",
        "/proc/device-tree/model",
    ):
        value = read_text(path, "")
        if value:
            return value
    return UNKNOWN


def on_target() -> bool:
    model = host_model()
    return any(marker.lower() in model.lower() for marker in TARGET_MARKERS)


def context_line() -> str:
    model = host_model()
    if on_target():
        return f"Observation context: target-like host ({model})"
    return f"Observation context: build host ({model}); values are NOT phone evidence"


def show(label: str, value: object, source: str) -> None:
    print(f"{label:<24} {str(value):<44} [{source}]")


def cmd_sysinfo(args: argparse.Namespace) -> None:
    print("=== sysinfo ===")
    print(context_line())
    show("Model", host_model(), "/sys/firmware/devicetree/base/model")
    show("Compatible", read_text("/sys/firmware/devicetree/base/compatible"), "device tree")
    show("SoC ID", read_text("/sys/devices/soc0/soc_id"), "/sys/devices/soc0")
    show("SoC name", read_text("/sys/devices/soc0/chip_name"), "/sys/devices/soc0")
    show("SoC revision", read_text("/sys/devices/soc0/revision"), "/sys/devices/soc0")

    mem_kb = None
    for line in read_text("/proc/meminfo", "").splitlines():
        if line.startswith("MemTotal:"):
            try:
                mem_kb = int(line.split()[1])
            except (IndexError, ValueError):
                pass
            break
    if mem_kb is None:
        show("MemTotal", UNKNOWN, "/proc/meminfo")
    else:
        show("MemTotal", f"{mem_kb / 1024 / 1024:.2f} GiB", "/proc/meminfo")

    serial = read_text("/sys/devices/soc0/serial_number", UNKNOWN)
    if serial != UNKNOWN and not args.show_identifiers:
        serial = "redacted (pass --show-identifiers)"
    show("SoC serial", serial, "/sys/devices/soc0")


def cmd_cpuinfo(_args: argparse.Namespace) -> None:
    print("=== cpuinfo ===")
    print(context_line())
    cpus = sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*"))
    if not cpus:
        show("CPU topology", UNKNOWN, "/sys/devices/system/cpu")
        return

    show("CPU count", len(cpus), "/sys/devices/system/cpu")
    clusters: dict[str, list[int]] = {}
    for cpu in cpus:
        package = read_text(os.path.join(cpu, "topology/physical_package_id"), UNKNOWN)
        clusters.setdefault(package, []).append(int(os.path.basename(cpu)[3:]))

    for package, cores in sorted(clusters.items()):
        show(f"Package {package}", f"{len(cores)} CPUs: {cores}", "/sys topology")
        for cpu in cores:
            base = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq"
            max_khz = read_int(os.path.join(base, "cpuinfo_max_freq"))
            min_khz = read_int(os.path.join(base, "cpuinfo_min_freq"))
            if max_khz is None:
                show(f"  cpu{cpu} max", UNKNOWN, "cpufreq")
            else:
                show(f"  cpu{cpu} max", f"{max_khz / 1000:.0f} MHz", "cpufreq")
            if min_khz is not None:
                show(f"  cpu{cpu} min", f"{min_khz / 1000:.0f} MHz", "cpufreq")

    freq = read_text("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")
    if freq != UNKNOWN:
        show("Boot CPU max", f"{int(freq) / 1000:.0f} MHz", "cpufreq")


def cmd_fdt(_args: argparse.Namespace) -> None:
    print("=== fdt ===")
    path = "/sys/firmware/fdt"
    try:
        data = Path(path).read_bytes()
    except OSError:
        show("Live FDT", UNKNOWN, path)
        return
    if len(data) < 40:
        show("Live FDT", f"too short ({len(data)} bytes)", path)
        return
    magic, totalsize, off_struct, off_strings, off_rsvmap, version, last_comp = struct.unpack(
        ">IIIIIII", data[:28]
    )
    if magic != 0xD00DFEED:
        show("Live FDT", f"bad magic 0x{magic:08X}", path)
        return
    show("FDT magic", f"0x{magic:08X}", path)
    show("FDT size", totalsize, path)
    show("FDT version", f"{version} (last compatible {last_comp})", path)
    show("Struct offset", off_struct, path)
    show("Strings offset", off_strings, path)
    show("RSV map offset", off_rsvmap, path)


def cmd_memmap(_args: argparse.Namespace) -> None:
    print("=== memmap ===")
    print(context_line())
    text = read_text("/proc/iomem", "")
    if not text:
        show("Linux iomem", UNKNOWN, "/proc/iomem (restricted or unavailable)")
        print("The UEFI memory map is only available from GetMemoryMap() inside firmware.")
        return
    show("Source", "/proc/iomem", "Linux; not a UEFI memory map")
    for line in text.splitlines()[:80]:
        print(f"  {line}")


def cmd_storage(_args: argparse.Namespace) -> None:
    print("=== storage ===")
    print(context_line())
    devices = sorted(glob.glob("/sys/block/*"))
    if not devices:
        show("Block devices", UNKNOWN, "/sys/block")
        return
    print("Linux block devices only; UFS LUN order and partition indices are not inferred.")
    for dev in devices:
        name = os.path.basename(dev)
        model = read_text(os.path.join(dev, "device/model"), UNKNOWN)
        sectors = read_int(os.path.join(dev, "size"))
        removable = read_text(os.path.join(dev, "removable"), UNKNOWN)
        if sectors is None:
            size = UNKNOWN
        else:
            size = f"{sectors * 512 / (1024 ** 3):.2f} GiB"
        show(name, f"model={model} size={size} removable={removable}", "/sys/block")


def cmd_partitions(_args: argparse.Namespace) -> None:
    print("=== partitions ===")
    print(context_line())
    roots = ["/dev/disk/by-partlabel", "/dev/block/by-name"]
    found = False
    for root in roots:
        if not os.path.isdir(root):
            continue
        found = True
        entries = sorted(os.listdir(root))
        show("Source", root, "Linux device links")
        for entry in entries:
            link = os.path.realpath(os.path.join(root, entry))
            print(f"  {entry:<24} -> {os.path.basename(link)}")
    if not found:
        show("Named partitions", UNKNOWN, "no by-name/by-partlabel directory")
    print("Read-only listing. No partition was mounted, read, or written by this tool.")


def cmd_display(_args: argparse.Namespace) -> None:
    print("=== display ===")
    print(context_line())
    fb = "/sys/class/graphics/fb0"
    if not os.path.isdir(fb):
        show("Framebuffer", UNKNOWN, fb)
        return
    show("Virtual size", read_text(os.path.join(fb, "virtual_size")), f"{fb}/virtual_size")
    show("Stride", read_text(os.path.join(fb, "stride")), f"{fb}/stride")
    show("Bits per pixel", read_text(os.path.join(fb, "bits_per_pixel")), f"{fb}/bits_per_pixel")
    show("State", read_text(os.path.join(fb, "state")), f"{fb}/state")
    show("Panel model", UNKNOWN, "not read; use the live FDT or a panel ID register")


def cmd_battery(_args: argparse.Namespace) -> None:
    print("=== battery ===")
    print(context_line())
    supplies = sorted(glob.glob("/sys/class/power_supply/*"))
    if not supplies:
        show("Power supplies", UNKNOWN, "/sys/class/power_supply")
        return
    for supply in supplies:
        name = os.path.basename(supply)
        fields = {}
        for field in ("type", "status", "capacity", "voltage_now", "current_now", "temp"):
            fields[field] = read_text(os.path.join(supply, field), UNKNOWN)
        print(f"  {name}: " + " ".join(f"{k}={v}" for k, v in fields.items()))


def cmd_thermal(_args: argparse.Namespace) -> None:
    print("=== thermal ===")
    print(context_line())
    zones = sorted(glob.glob("/sys/class/thermal/thermal_zone*"))
    if not zones:
        show("Thermal zones", UNKNOWN, "/sys/class/thermal")
        return
    for zone in zones:
        name = os.path.basename(zone)
        kind = read_text(os.path.join(zone, "type"), UNKNOWN)
        raw = read_int(os.path.join(zone, "temp"))
        temp = UNKNOWN if raw is None else f"{raw / 1000:.1f} C"
        print(f"  {name:<20} type={kind:<24} temp={temp}")


def cmd_audit(args: argparse.Namespace) -> None:
    for command in (
        cmd_sysinfo,
        cmd_cpuinfo,
        cmd_fdt,
        cmd_memmap,
        cmd_storage,
        cmd_partitions,
        cmd_display,
        cmd_battery,
        cmd_thermal,
    ):
        command(args)
        print()


COMMANDS = {
    "sysinfo": cmd_sysinfo,
    "cpuinfo": cmd_cpuinfo,
    "fdt": cmd_fdt,
    "memmap": cmd_memmap,
    "storage": cmd_storage,
    "partitions": cmd_partitions,
    "display": cmd_display,
    "battery": cmd_battery,
    "thermal": cmd_thermal,
    "audit": cmd_audit,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only host-side inspection prototype for Project R8Q UEFI."
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="sysinfo",
        choices=sorted(COMMANDS),
        help="inspection command (default: sysinfo)",
    )
    parser.add_argument(
        "--show-identifiers",
        action="store_true",
        help="print serial numbers; off by default",
    )
    args = parser.parse_args()

    print("Project R8Q UEFI host inspection prototype")
    print("Read-only. Not the UEFI diagnostic engine. No device writes.")
    print()
    COMMANDS[args.command](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
