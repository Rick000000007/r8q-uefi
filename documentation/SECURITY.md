# Project R8Q — Security Architecture & Hardening Specification

**Target Platform:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Document Revision:** 3.0.0 (Cryptographic Isolation & Zero-Insecure-Default Policy)  
**Status:** Approved Security Architecture  

---

## 1. Absolute Protection of Cryptographic Keystore (`sda25`)

Partition `sda25` (`keyrefuge`) on UFS LUN0 holds the hardware-bound Knox certificates, TrustZone attestation credentials, and disk encryption master keys. Compromising, erasing, or writing to this partition would permanently damage the phone's cryptographic attestation.

### 1.1 Multi-Layer Defense-in-Depth Architecture

```
+---------------------------------------------------------------------------------+
|                         SDA25 PROTECTION DEFENSE-IN-DEPTH                       |
+---------------------------------------------------------------------------------+

Layer 1: CI/CD & Build Pipeline Guarantee
├── Pre-commit grep checks for sda25 write commands in source code
└── Zero block access during cloud compilation

Layer 2: Partition Headroom Boundary Verification
├── sda24 capacity: 82,694,144 Bytes (~78.86 MiB)
├── R8Q payload size: 24,461,312 Bytes (~23.33 MiB)
└── Headroom safety margin: +58,232,832 Bytes (+55.53 MiB) of pure unwritten clearance

Layer 3: Installer Preflight Script Guard (update-binary)
├── Resolves destination block device realpath
├── Rejects match against '*sda25*', '*keyrefuge*', or raw '/dev/block/sda'
└── Aborts immediately with error code 3 if keystore is targeted

Layer 4: UEFI Hardware Block Write Filter (StorageProtectionDxe)
├── Intercepts all EFI_BLOCK_IO_PROTOCOL and EFI_STORAGE_SECURITY_COMMAND_PROTOCOL requests
└── Immediately returns EFI_WRITE_PROTECTED on access to protected LUN0 ranges
```

---

## 2. Authentication, Userspace & Credential Hardening

In strict compliance with modern security engineering principles, Project R8Q enforces a **Zero-Insecure-Default-Credential Policy**:

1. **Elimination of Legacy Passwords:**
   - Insecure default credentials (such as `toor` / `root`, `r8q` / `r8q`, or `admin`) are strictly eradicated.
2. **Locked Root Account:**
   - In `/etc/shadow`, the root account is explicitly locked:
     `root:*:19712:0:99999:7:::`
   - Direct password login to root is prohibited.
3. **Administrative User Account (`r8q`):**
   - Non-root user `r8q` (`uid=1000, gid=1000`) is provisioned for daily system administration.
   - Account password is protected with salted SHA-512 cryptographic hashing:
     `$6$qemuR8Qsec$E7Xk6JqKq2V0bN5gW...`
4. **Sudoers Role-Based Delegation:**
   - Administrative commands are executed via sudo (`/etc/sudoers.d/r8q`), with file permissions restricted to `0440`.

---

## 3. Network & OpenSSH Server Hardening

The Debian 12 native rootfs includes a hardened OpenSSH server daemon configuration (`/etc/ssh/sshd_config`):

```ini
# Project R8Q Hardened OpenSSH Configuration
Port 22
AddressFamily any
PermitRootLogin prohibit-password
PubkeyAuthentication yes
PasswordAuthentication no
PermitEmptyPasswords no
ChallengeResponseAuthentication no
AuthorizedKeysFile .ssh/authorized_keys
Subsystem sftp /usr/lib/openssh/sftp-server
```

### 3.1 Host Key Lifecycle & Isolation
- **Production Mode:** In production builds (`PRODUCTION_BUILD=1`), all pre-generated test host keys and authorized keys are eradicated.
- **Dynamic First-Boot Provisioning:** A dedicated systemd unit (`r8q-ssh-keygen.service`) automatically invokes `ssh-keygen -A` during the first physical boot to generate unique, locally generated Ed25519, RSA, and ECDSA host keys on the device.
- **Virtual QEMU Testing Isolation:** Ephemeral test keys generated for automated testing are restricted strictly to virtualized emulators and are never bundled into release tarballs.

---

## 4. Verification and Readback Guarantees

Every installation script implements strict readback verification:
1. Calculates SHA-256 of payload prior to writing.
2. Writes payload using atomic page-aligned blocks (`bs=4096 conv=fsync`).
3. Reads back written blocks directly from storage and computes readback SHA-256 digest.
4. Requires bit-for-bit hash equality before reporting success.
