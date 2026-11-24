# Project R8Q — CI/CD Failure Triage & Troubleshooting Matrix

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Pipeline:** GitHub Actions Modular CI/CD  
**Document Revision:** 1.0.0  
**Status:** Operational Troubleshooting Guide  

---

## 1. Quick Triage Matrix

| Stage | Symptom / Error Message | Root Cause | Immediate Resolution |
|---|---|---|---|
| **BaseTools** | `FileNotFoundError: SemLock` / `No such file or directory` in `synchronize.py` | GitHub Actions container lacks `/dev/shm` tmpfs mount | Ensure `mkdir -p /dev/shm && mount -t tmpfs tmpfs /dev/shm` executes before EDK II build |
| **Firmware** | `aarch64-linux-gnu-gcc: command not found` | Cross-compiler missing on x86_64 host runner | Add `sudo apt-get install -y gcc-aarch64-linux-gnu` |
| **Firmware** | `build: command not found` | EDK II BaseTools not added to `$PATH` | Export `PATH="$EDK_TOOLS_PATH/BinWrappers/PosixLike:$PATH"` |
| **BootMgr** | `error: '/*' within comment` | Nested C comment syntax in application source | Clean source comments; do not nest `/*` inside block comments |
| **BootMgr** | `error: 'EFI_BACKGROUND_LIGHTCYAN' undeclared` | Non-standard UEFI text attribute | Replace with standard `EFI_BACKGROUND_CYAN` |
| **Kernel** | `dtc: command not found` | Device tree compiler missing | Install `device-tree-compiler` via apt |
| **Initramfs**| `bin/busybox: cannot execute binary file: Exec format error` | Host x86_64 BusyBox copied instead of ARM64 | Use `BUSYBOX_ARM64` multiarch package or stage pre-verified binary |
| **ESP** | `ESP size does not match expected (268435456 bytes)` | Geometry mismatch during disk image creation | Verify `dd if=/dev/zero of=esp.img bs=1M count=256` and exact FAT32 offsets |
| **Complete**| `SAFETY VIOLATION: Compound kernel exceeds safety ceiling` | Compound payload exceeds 25 MiB ceiling | Check `R8Q_EFI.fd` and `Image` sizes; assert kernel compression |
| **Complete**| `CRITICAL SAFETY OVERRUN: Output boot image exceeds sda24` | Total boot image exceeds 82,694,144 bytes (`sda24`) | Strip unused kernel drivers; assert +55.53 MiB safety margin |
| **Recovery**| `sda25 protection missing!` | Updater script lacks boundary guard assertions | Check `META-INF/com/google/android/update-binary` contains `sda25` hazard block |
| **Release** | `CRITICAL FAILURE: Unauthorized physical flashing command detected` | Source code contains raw `dd of=/dev/sd*` or `fastboot flash` | Remove destructive physical block device commands |
| **Test** | `PE header offset mismatch` / `pe_offset > 512` | GenFw placed PE header at offset > 512 bytes | Read 4096 bytes minimum when inspecting PE/COFF MZ header |

---

## 2. Detailed Root-Cause Analyses & Remedies

### 2.1 EDK II Shared Memory (`/dev/shm`) Missing
- **Symptoms:**
  ```
  Traceback (most recent call last):
    File "/root/r8q-uefi/edk2/BaseTools/Source/Python/build/build.py", line 47, in <module>
      from multiprocessing import Lock, Semaphore
    ...
  FileNotFoundError: [Errno 2] No such file or directory
  ```
- **Root Cause:** Standard minimal containers and some CI runners do not mount POSIX shared memory (`/dev/shm`). Python's `multiprocessing` module requires `/dev/shm` to allocate semaphores (`SemLock`).
- **Remedy:** Prepend every EDK II build job with:
  ```bash
  sudo mkdir -p /dev/shm
  sudo chmod 1777 /dev/shm
  sudo mount -t tmpfs tmpfs /dev/shm || true
  ```

### 2.2 Cross-Compilation Toolchain Prefix on x86_64 Runners
- **Symptoms:** EDK II attempts to invoke host `gcc` when building target AArch64 code, leading to invalid machine architecture errors (`x86_64` instead of `AArch64`).
- **Remedy:** Ensure the target toolchain prefix is explicitly exported:
  ```bash
  export GCC5_AARCH64_PREFIX=aarch64-linux-gnu-
  export ARCH=arm64
  export CROSS_COMPILE=aarch64-linux-gnu-
  ```

### 2.3 Partition Boundary Hazard (`sda24` vs `sda25`)
- **Symptoms:** CI fails with:
  ```
  ValueError: CRITICAL SAFETY OVERRUN: Output boot image size X bytes exceeds exact physical capacity of recovery partition sda24 (82694144 bytes)!
  ```
- **Hazard:** Partition `sda24` on Samsung Galaxy S20 FE 5G is exactly 82,694,144 bytes (161,512 sectors * 512 bytes). The next sequential partition is `sda25` (`keyrefuge`), which holds cryptographic Knox hardware keys. An overflow into `sda25` causes irreversible hardware bricking.
- **Remedy:** Do not increase kernel or initramfs payload sizes beyond the 25 MiB ceiling. Ensure `r8q-uefi-boot-complete.img` remains under 26 MiB, preserving **+55.53 MiB** of safety margin.

### 2.4 Ext4 Rootfs Superblock Magic Verification Failure
- **Symptoms:** `ext4 magic: b'\x00\x00' != b'\x53\xef'`.
- **Root Cause:** The ext4 superblock is located at byte offset **1024** from the start of the partition. The two-byte magic number `0xEF53` (`b'\x53\xef'` little-endian) is located at offset `0x38` inside the superblock (absolute byte offset `1024 + 56 = 1080`).
- **Remedy:** Read at least 2048 bytes from the uncompressed rootfs image and check `header[1024+0x38:1024+0x3A] == b'\x53\xef'`.
