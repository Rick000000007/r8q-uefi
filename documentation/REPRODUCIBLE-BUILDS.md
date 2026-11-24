# Project R8Q — Reproducible Builds Engineering Specification

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Architecture:** ARM64 / AArch64  
**Reproducibility Standard:** Bit-Exact Determinism (`SOURCE_DATE_EPOCH=315532800`)  
**Document Revision:** 1.0.0  
**Status:** Approved Technical Standard  

---

## 1. Engineering Definition of Reproducibility

A build is **reproducible** if, given identical source code and build instructions, any independent build system (local developer workstation, virtual machine, or remote GitHub Actions runner) produces **bit-exact identical binary outputs** verified by cryptographic hash (`SHA-256`).

In Project R8Q, bit-exact reproducibility guarantees:
1. **Security & Auditability:** Verifies that distribution binaries contain zero undisclosed patches, injected code, or local workstation artifacts.
2. **Authoritative CI:** GitHub Actions and local workstations produce identical release archives.
3. **Validation Confidence:** Automated tests can assert exact checksums across distributed environments.

---

## 2. Sources of Non-Determinism & Remediations

Standard build pipelines introduce non-deterministic variance through five primary vectors:

| Non-Determinism Vector | Standard Behavior | Project R8Q Deterministic Remediation |
|---|---|---|
| **Timestamps in Tar/Gzip** | Records current wall-clock mtime | Fixed epoch: `SOURCE_DATE_EPOCH=315532800` (1980-01-01 00:00:00 UTC) |
| **Gzip Header Timestamp** | Writes current timestamp into header | Normalized: `gzip.GzipFile(..., mtime=0.0)` |
| **Filesystem Traversal Order** | Non-deterministic inode order | Alphabetical sorting of all paths (`payloads.sort()`, `dirs_needed`) |
| **File Ownership & Modes** | Host runner UID/GID (e.g. 1001) | Normalized: `uid=0, gid=0, uname='', gname='', mode=0o644 / 0o755` |
| **PE32+ EFI Application Time** | Build timestamp in PE/COFF header | Deterministic linker flags and GenFw zero-timestamp normalization |
| **Ext4 Directory Indexing** | Variable hash seed / time | Superblock initialized with fixed UUID and normalized inode dates |

---

## 3. Implementation Details

### 3.1 Reproducible Full System Packager (`scripts/package_full_system.py`)

The full system archive `R8Q-Debian12-Full-System.tar.gz` packages 17 distinct component payloads.

```python
FIXED_EPOCH = 315532800  # 1980-01-01 00:00:00 UTC

# Payloads sorted alphabetically by archive path
payloads.sort(key=lambda x: x[1])

with open(out_tar, 'wb') as f_out:
    with gzip.GzipFile(filename='', mode='wb', fileobj=f_out, mtime=0.0) as gz_out:
        with tarfile.open(mode='w', fileobj=gz_out) as tar:
            for d in dirs_needed:
                ti = tarfile.TarInfo(name=d)
                ti.type = tarfile.DIRTYPE
                ti.mode = 0o755
                ti.mtime = FIXED_EPOCH
                ti.uid = 0
                ti.gid = 0
                ti.uname = ''
                ti.gname = ''
                tar.addfile(ti)

            for src_rel, arc_path in payloads:
                size = os.path.getsize(full_src)
                ti = tarfile.TarInfo(name=arc_path)
                ti.type = tarfile.REGTYPE
                ti.size = size
                ti.mode = 0o644
                ti.mtime = FIXED_EPOCH
                ti.uid = 0
                ti.gid = 0
                tar.addfile(ti, f_in)
```

### 3.2 Compound Boot Image Layout Determinism (`scripts/package_complete_boot_img.py`)
- Android Boot Image v2 header written with deterministic struct packing.
- Exact 4,096-byte page alignment for each component:
  - Header: Offset `0x00000000` (4,096 B)
  - Compound Kernel: Offset `0x00001000` (64 B Wrapper + 4.00 MiB FD + 16.02 MiB Image)
  - Ramdisk: Page-aligned immediately after kernel payload
  - DTB: Page-aligned immediately after ramdisk payload
- Padding bytes explicitly written as zeros (`b"\x00"`).

### 3.3 Recovery Installer ZIP Determinism (`scripts/package_recovery_zip.py`)
- Uses `zipfile.ZipInfo` with normalized date tuple `(1980, 1, 1, 0, 0, 0)`.
- Enforces `compress_type=zipfile.ZIP_DEFLATED`.

---

## 4. Cryptographic Baseline Verification

Every build must produce the exact cryptographic digest recorded in `SHA256SUMS`:

```
cd R8Q-DEBIAN12-RELEASE
sha256sum -c SHA256SUMS
```

All 10 release components must pass without mismatch. Any discrepancy halts the release pipeline immediately.
