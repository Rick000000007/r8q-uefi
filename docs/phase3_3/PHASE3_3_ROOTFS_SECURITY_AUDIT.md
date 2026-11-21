# Project R8Q — Phase 3.3: Production Rootfs Security Audit

**Target Device:** Samsung Galaxy S20 FE 5G (`SM-G781B` / `r8q`)  
**SoC:** Qualcomm Snapdragon 865 (`SM8250` / Kona / Adreno 650)  
**Document ID:** `R8Q-DOC-P33-07-SEC`  
**Baseline Commit:** [`4e62ec4`](file:///root/r8q-uefi) (*"feat(phase3.2): architecture remediation, memory decoupling, native kernel 7.2.15 & full validation suite"*)  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Workstream Verdict:** **CONDITIONAL PASS**  

---

## 1. Executive Summary

This audit evaluated the security posture of the production native Linux root filesystem ([build/r8q-rootfs.ext4](file:///root/r8q-uefi/build/r8q-rootfs.ext4)) and its staging root tree (`/tmp/r8q_rootfs_staging`), covering cryptographic key generation, authentication policies, privilege escalation configurations, and system service permissions.

The audit verified that:
1. Static Ed25519 test keys (`r8q_test_id_ed25519`) and pre-bundled host keys (`/etc/ssh/ssh_host_*`) have been eradicated from the production release image.
2. Root account password authentication is locked (`root:*:...` in `/etc/shadow`).
3. Fresh SSH host keys are dynamically generated on first physical boot using Qualcomm hardware RNG via `r8q-ssh-keygen.service`.

However, two security vulnerabilities were identified:
1. **Total Network SSH Lockout (`P33-ROOTFS-SEC-01`):** `/etc/ssh/sshd_config` disables password authentication (`PasswordAuthentication no`), while both `/root/.ssh/authorized_keys` and `/home/r8q/.ssh/authorized_keys` are shipped empty. The device is completely unreachable via SSH on first boot.
2. **Hardcoded User Hash & Passwordless Sudo (`P33-ROOTFS-SEC-02`):** The non-root user `r8q` is configured with a static hardcoded SHA-512 salt and hash in [scripts/build_rootfs.sh](file:///root/r8q-uefi/scripts/build_rootfs.sh), and granted unauthenticated, passwordless root privilege escalation (`r8q ALL=(ALL:ALL) NOPASSWD: ALL`).

---

## 2. Authentication & Account Policy Audit

### 2.1 Password Database (`/etc/shadow`)
```text
root:*:19712:0:99999:7:::
daemon:*:19712:0:99999:7:::
bin:*:19712:0:99999:7:::
...
r8q:$6$qemuR8Qsec$E7Xk6JqKq2V0bN5gW.t0L5/zZ3.QzP8A6X9lM1vB4yC7dE0fG3hI6jK9lM2oP5rS8uV1xY4zA7cD0fG3hI6jK:19712:0:99999:7:::
```
- **Root Account:** Status `LOCKED` (`*`). Root cannot log in via password over console or SSH.
- **User Account (`r8q`):** Configured with SHA-512 hash using static salt `qemuR8Qsec`.

### 2.2 Sudo Privilege Configuration
Inspection of `/tmp/r8q_rootfs_staging/etc/sudoers.d/r8q`:
```text
r8q ALL=(ALL:ALL) NOPASSWD: ALL
```
User `r8q` is granted complete unauthenticated root access without password prompt.

---

## 3. SSH Service & Key Management Audit

### 3.1 Daemon Configuration (`/etc/ssh/sshd_config`)
```text
Port 22
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
ChallengeResponseAuthentication no
UsePAM yes
X11Forwarding yes
PrintMotd no
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/openssh/sftp-server
```

### 3.2 Dynamic First-Boot Host Key Generation
Inspection of `/tmp/r8q_rootfs_staging/etc/systemd/system/r8q-ssh-keygen.service`:
```ini
[Unit]
Description=Generate Unique SSH Host Keys on First Boot
Before=ssh.service
ConditionFileNotEmpty=!/etc/ssh/ssh_host_ed25519_key

[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```
- This service executes `/usr/bin/ssh-keygen -A` if no host keys exist, generating fresh Ed25519, RSA, and ECDSA host keys using the Linux kernel entropy pool fed by Snapdragon 865 hardware RNG (`qcom-rng`).

---

## 4. Audit Findings

### Finding P33-ROOTFS-SEC-01: Total Network SSH Lockout by Default on First Boot
* **Finding ID:** `P33-ROOTFS-SEC-01`
* **Severity:** **MEDIUM**
* **Affected Component:** `/etc/ssh/sshd_config`, `/root/.ssh/authorized_keys`, `/home/r8q/.ssh/authorized_keys`
* **Evidence:**
  `PasswordAuthentication no` is set in `sshd_config`. Both `/root/.ssh/authorized_keys` and `/home/r8q/.ssh/authorized_keys` are empty.
* **Reproduction Procedure:**
  Execute automated test:
  ```bash
  python3 -m unittest tests.test_phase3_3_independent_audit.TestPhase33IndependentAudit.test_audit_05_rootfs_ssh_lockout_condition
  ```
* **Engineering Impact:**
  On physical hardware boot, the device will initialize SSH successfully, but will reject 100% of incoming connection attempts because no password authentication is permitted and no public keys are authorized. An operator will have zero network management access unless a USB UART cable is physically attached.
* **Recommended Remediation:**
  During rootfs generation (or before staging), require the operator to inject their public SSH key (`id_ed25519.pub`) into `/home/r8q/.ssh/authorized_keys` and `/root/.ssh/authorized_keys`.
* **Verification Result:**
  Verified lockout condition via `test_audit_05_rootfs_ssh_lockout_condition`.

---

### Finding P33-ROOTFS-SEC-02: Hardcoded Static User Password Hash and Unauthenticated Passwordless Sudo
* **Finding ID:** `P33-ROOTFS-SEC-02`
* **Severity:** **MEDIUM**
* **Affected Component:** [scripts/build_rootfs.sh](file:///root/r8q-uefi/scripts/build_rootfs.sh), `/etc/sudoers.d/r8q`, `/etc/shadow`
* **Evidence:**
  In `scripts/build_rootfs.sh`:
  ```bash
  SECURE_R8Q_HASH='$6$qemuR8Qsec$E7Xk6JqKq2V0bN5gW.t0L5/zZ3.QzP8A6X9lM1vB4yC7dE0fG3hI6jK9lM2oP5rS8uV1xY4zA7cD0fG3hI6jK'
  ```
  In `/etc/sudoers.d/r8q`:
  ```text
  r8q ALL=(ALL:ALL) NOPASSWD: ALL
  ```
* **Reproduction Procedure:**
  Execute automated test:
  ```bash
  python3 -m unittest tests.test_phase3_3_independent_audit.TestPhase33IndependentAudit.test_audit_06_rootfs_hardcoded_user_hash_and_nopasswd_sudo
  ```
* **Engineering Impact:**
  Any compromised local process running as `r8q` can immediately obtain root privileges without password verification. Furthermore, shipping a hardcoded password hash in source code compromises credentials across all deployed devices.
* **Recommended Remediation:**
  1. Remove `NOPASSWD: ALL` from `/etc/sudoers.d/r8q` for production deployments.
  2. Implement an interactive or cloud-init first-boot password initialization prompt.
* **Verification Result:**
  Verified via `test_audit_06_rootfs_hardcoded_user_hash_and_nopasswd_sudo`.
