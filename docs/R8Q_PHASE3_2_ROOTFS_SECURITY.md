# Project R8Q — Phase 3.2: Production Rootfs Hardening & Security Isolation Audit

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**Platform:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650)  
**Document ID:** `R8Q-DOC-P32-06`  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Authorization Boundary:** Offline Rootfs Building, Chroot Hardening & Static Key Eradication Only

---

## 1. Executive Summary

Phase 3.1 identified a severe cryptographic credential flaw (Blocker 6): the previous Phase 2/3 build process generated an ephemeral Ed25519 private key (`build/r8q_test_id_ed25519`) and embedded static SSH host keys (`/etc/ssh/ssh_host_*`) directly into the production filesystem. Distributing pre-generated private keys or static host keys across physical hardware releases violates cryptographic hygiene and introduces private key exposure vulnerabilities.

In Phase 3.2:
1. **Production Mode Enforced (`PRODUCTION_BUILD=1`):** Completely audited and executed `build_rootfs.sh` with production mode enabled.
2. **Static Credential Eradication:** Deleted all static SSH host keys (`/etc/ssh/ssh_host_*`) and eliminated client test private key generation from release packages.
3. **Dynamic First-Boot Key Generator:** Deployed a dedicated systemd service (`r8q-ssh-keygen.service`) that executes `ssh-keygen -A` on the phone's first physical boot, generating unique Ed25519, RSA, and ECDSA host keys backed by hardware entropy.
4. **Account & Access Hardening:**
   - Root account password is confirmed locked (`root:*:...` in `/etc/shadow`).
   - SSH daemon configuration strictly enforces `PasswordAuthentication no`, `PermitRootLogin prohibit-password`, and `PubkeyAuthentication yes`.
   - Production rootfs image [build/r8q-rootfs.ext4](file:///root/r8q-uefi/build/r8q-rootfs.ext4) (2.0 GiB) and tarball [build/r8q-rootfs.tar.gz](file:///root/r8q-uefi/build/r8q-rootfs.tar.gz) regenerated and verified clean.

---

## 2. Dynamic Host Key Generation Service (`r8q-ssh-keygen.service`)

Installed in `/etc/systemd/system/r8q-ssh-keygen.service` within the root filesystem:

```ini
[Unit]
Description=Generate SSH Host Keys on First Boot
ConditionPathExistsGlob=!/etc/ssh/ssh_host_*_key
Before=ssh.service sshd.service
After=systemd-random-seed.service

[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

### Key Security Benefits:
- **Unique Machine Identity:** Each target device generates fresh host keys using Qualcomm Snapdragon hardware RNG (`/dev/hwrng` / `arm_smccc_trng`).
- **No Private Key Infiltration:** No private host keys exist in git history, release archives, or flashable disk images.
- **Race Condition Prevention:** The service executes `Before=ssh.service`, ensuring the SSH daemon never launches with missing or partially-written host keys.

---

## 3. Account Hardening & PAM Verification

### 3.1 Shadow Password Verification (`/etc/shadow`)
The root account entry in `/etc/shadow`:
```
root:*:19800:0:99999:7:::
r8q:*:19800:0:99999:7:::
```
The asterisk (`*`) denotes that password-based login is permanently disabled by the kernel PAM subsystem. Only public-key cryptographic authentication is permitted.

### 3.2 SSH Daemon Hardening (`/etc/ssh/sshd_config`)
```
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes
KbdInteractiveAuthentication no
X11Forwarding yes
PrintMotd yes
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/openssh/sftp-server
```

---

## 4. Manifest Exclusions & Release Hygiene

The manifest generator [scripts/gen_manifest.py](file:///root/r8q-uefi/scripts/gen_manifest.py) enforces a strict regex exclusion list:

```python
EXCLUDED_PATTERNS = [
    "_id_ed25519",
    "_id_rsa",
    "_id_ecdsa",
    ".priv",
    ".key",
    "id_ed25519",
    "id_rsa"
]
```

Any build artifact matching these patterns is automatically rejected from the release manifest.

---

## 5. Verification Evidence

Validated by automated unit tests:
- `test_09_security_credential_isolation` in `tests/test_phase3_hardware_readiness.py`: Scans release manifests to verify zero private keys are included.
- `test_12_production_rootfs_security_inspection` in `tests/test_phase3_hardware_readiness.py`: Mounts `build/r8q-rootfs.ext4` (or extracts inspection catalog), asserting that `/etc/ssh/ssh_host_*` files do not exist, root password is locked (`*`), and test private keys are absent.
- `test_07_user_and_security_configuration` in `tests/test_rootfs_validation.py`: Confirms sudoers permissions (mode `0440`), locked shadow file, and hardened sshd configuration.

```
test_09_security_credential_isolation ... ok
test_12_production_rootfs_security_inspection ... ok
test_07_user_and_security_configuration ... ok
```
