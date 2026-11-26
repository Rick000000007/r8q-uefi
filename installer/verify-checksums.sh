#!/bin/sh
# Project R8Q — Unified Package Cryptographic Checksum & Payload Completeness Verifier
# Pure POSIX / BusyBox-compatible implementation (no python3 or bash required).
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=scripts/lib-common.sh
. "$SCRIPT_DIR/scripts/lib-common.sh"

MANIFEST_JSON="$SCRIPT_DIR/manifests/MANIFEST.json"
CHECKSUM_FILE="$SCRIPT_DIR/manifests/SHA256SUMS"

if [ ! -f "$MANIFEST_JSON" ]; then
    echo "[ERROR] Missing manifest file: $MANIFEST_JSON" >&2
    exit 1
fi
if [ ! -f "$CHECKSUM_FILE" ]; then
    echo "[ERROR] Missing checksum manifest: $CHECKSUM_FILE" >&2
    exit 1
fi

echo "[VERIFY-CHECKSUMS] Checking every payload and manifest entry in $SCRIPT_DIR..."

TMP_WORK="$(mktemp -d "${TMPDIR:-/tmp}/r8q_sum_XXXXXX")"
trap 'rm -rf "$TMP_WORK"' EXIT INT TERM

PARSED_MANIFEST="$TMP_WORK/manifest_files.tsv"
PARSED_SHA="$TMP_WORK/sha_entries.tsv"
REQ_GROUPS="$TMP_WORK/required_groups.txt"

cat << 'EOF' > "$REQ_GROUPS"
install.sh
uninstall-or-rollback.sh
verify-device.sh
verify-checksums.sh
config/device.conf
config/partition-map.conf
config/boot.conf
payload/firmware/R8Q_EFI.fd
payload/firmware/r8q-uefi-boot-complete.img
payload/boot-manager/BootManager.efi
payload/setup/Setup.efi
payload/uefi/Shell.efi
payload/uefi/LinuxBoot.efi
payload/esp/esp.img
payload/esp/startup.nsh
payload/kernel/Image
payload/dtb/sm8250-samsung-r8q.dtb
payload/dtb/r8q.dtb
payload/initramfs/initramfs.img
payload/debian-rootfs/r8q-rootfs.ext4.gz
payload/debian-rootfs/r8q-rootfs.tar.gz
manifests/MANIFEST.json
INSTALL.md
VERSION
EOF

# Parse MANIFEST.json "files" array safely into: path<TAB>size_bytes<TAB>sha256
awk '
BEGIN { in_files=0; path=""; size=""; sha=""; count=0 }
/"files"[[:space:]]*:[[:space:]]*\[/ { in_files=1; next }
in_files {
    if ($0 ~ /^[[:space:]]*\]/) {
        in_files=0;
        next;
    }
    if (match($0, /"path"[[:space:]]*:[[:space:]]*"[^"]*"/)) {
        s = substr($0, RSTART, RLENGTH);
        sub(/^"path"[[:space:]]*:[[:space:]]*"/, "", s);
        sub(/"$/, "", s);
        path = s;
    }
    if (match($0, /"size_bytes"[[:space:]]*:[[:space:]]*[0-9]+/)) {
        s = substr($0, RSTART, RLENGTH);
        sub(/^"size_bytes"[[:space:]]*:[[:space:]]*/, "", s);
        size = s;
    }
    if (match($0, /"sha256"[[:space:]]*:[[:space:]]*"[0-9a-fA-F]+"/)) {
        s = substr($0, RSTART, RLENGTH);
        sub(/^"sha256"[[:space:]]*:[[:space:]]*"/, "", s);
        sub(/"$/, "", s);
        sha = tolower(s);
    }
    if ($0 ~ /\}/ && path != "") {
        printf "%s\t%s\t%s\n", path, size, sha;
        count++;
        path=""; size=""; sha="";
    }
}
END {
    if (count == 0) {
        print "[ERROR] MANIFEST.json has no declared files" > "/dev/stderr";
        exit 1;
    }
}
' "$MANIFEST_JSON" > "$PARSED_MANIFEST"

# Parse and validate SHA256SUMS syntax into: path<TAB>sha256
awk '
{
    raw = $0;
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", raw);
    if (raw == "") next;
    line_no++;
    sha = raw;
    sub(/[[:space:]].*$/, "", sha);
    rest = raw;
    sub(/^[^[:space:]]+[[:space:]]+/, "", rest);
    sub(/^\*/, "", rest);
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", rest);
    if (length(sha) != 64 || sha ~ /[^0-9a-fA-F]/ || rest == "") {
        printf "[ERROR] Malformed SHA256SUMS line %d: %s\n", NR, $0 > "/dev/stderr";
        exit 1;
    }
    printf "%s\t%s\n", rest, tolower(sha);
}
' "$CHECKSUM_FILE" > "$PARSED_SHA"

# Verify step scripts 01..11 exist uniquely in MANIFEST.json
i=1
while [ "$i" -le 11 ]; do
    prefix=$(printf 'scripts/%02d-' "$i")
    match_count=$(awk -F '\t' -v pfx="$prefix" 'index($1, pfx) == 1 { c++ } END { print c+0 }' "$PARSED_MANIFEST")
    if [ "$match_count" -ne 1 ]; then
        echo "[ERROR] Missing or ambiguous step script $(printf '%02d' "$i") in MANIFEST.json (count=$match_count)" >&2
        exit 1
    fi
    i=$((i + 1))
done

# Verify every mandatory file is present in SHA256SUMS and MANIFEST.json
awk -F '\t' '
FILENAME == ARGV[1] { sha_paths[$1] = $2; next }
FILENAME == ARGV[2] { man_paths[$1] = 1; next }
FILENAME == ARGV[3] {
    req = $1;
    if (!(req in sha_paths)) {
        printf "[ERROR] Missing mandatory package file in SHA256SUMS: %s\n", req > "/dev/stderr";
        exit 1;
    }
    if (req != "manifests/MANIFEST.json" && !(req in man_paths)) {
        printf "[ERROR] Missing mandatory package file in MANIFEST.json: %s\n", req > "/dev/stderr";
        exit 1;
    }
    next;
}
END {
    for (p in man_paths) {
        if (!(p in sha_paths)) {
            printf "[ERROR] Files in MANIFEST.json missing from SHA256SUMS: %s\n", p > "/dev/stderr";
            exit 1;
        }
    }
}
' "$PARSED_SHA" "$PARSED_MANIFEST" "$REQ_GROUPS"

# Compute SHA-256 and exact byte size for every file declared in SHA256SUMS
verified=0
while IFS='	' read -r rel expected_sha; do
    [ -n "$rel" ] || continue
    full_path="$SCRIPT_DIR/$rel"
    if [ ! -f "$full_path" ]; then
        echo "[ERROR] Missing payload file: $rel" >&2
        exit 1
    fi
    size="$(r8q_filesize "$full_path")"
    if [ -z "$size" ] || [ "$size" -eq 0 ]; then
        echo "[ERROR] Zero-byte file detected: $rel" >&2
        exit 1
    fi
    actual_sha="$(sha256sum "$full_path" | awk '{print tolower($1)}')"
    if [ "$actual_sha" != "$expected_sha" ]; then
        echo "[ERROR] Checksum mismatch for $rel: expected $expected_sha, got $actual_sha" >&2
        exit 1
    fi
    man_line="$(awk -F '\t' -v p="$rel" '$1 == p { print $2 "\t" $3; exit }' "$PARSED_MANIFEST")"
    if [ -n "$man_line" ]; then
        man_size="$(printf '%s' "$man_line" | awk -F '\t' '{print $1}')"
        man_sha="$(printf '%s' "$man_line" | awk -F '\t' '{print $2}')"
        if [ "$man_sha" != "$actual_sha" ] || [ "$man_size" != "$size" ]; then
            echo "[ERROR] MANIFEST.json metadata mismatch for $rel" >&2
            exit 1
        fi
    fi
    verified=$((verified + 1))
done < "$PARSED_SHA"

echo "[PASS] Verified SHA-256 digests and sizes for all $verified files in package."
