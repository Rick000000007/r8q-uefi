#!/bin/sh
# Project R8Q — POSIX / TWRP-Compatible Shared Shell Helpers
# Designed to run cleanly under BusyBox ash, Android mksh, dash, and GNU bash
# with zero python3 or bash-specific extensions required.

r8q_detect_sh() {
    if [ -n "${R8Q_SH_BIN:-}" ] && [ -x "${R8Q_SH_BIN}" ]; then
        printf '%s\n' "$R8Q_SH_BIN"
        return 0
    fi
    for cand in /sbin/sh /system/bin/sh /bin/sh; do
        if [ -x "$cand" ]; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    if command -v sh >/dev/null 2>&1; then
        command -v sh
        return 0
    fi
    return 1
}

r8q_filesize() {
    wc -c < "$1" | tr -d ' \t\r\n'
}

r8q_hex_slice() {
    _file="$1"
    _offset="$2"
    _count="$3"
    dd if="$_file" bs=1 skip="$_offset" count="$_count" 2>/dev/null | od -An -tx1 -v | tr -d ' \t\r\n'
}

r8q_u16le() {
    _hex="$(r8q_hex_slice "$1" "$2" 2)"
    [ "${#_hex}" -eq 4 ] || return 1
    awk -v h="$_hex" 'BEGIN {
        b0 = substr(h, 1, 2); b1 = substr(h, 3, 2);
        printf "%u\n", strtonum_hex(b1 b0)
    }
    function strtonum_hex(s,    i, c, v, n) {
        s = tolower(s); n = 0;
        for (i = 1; i <= length(s); i++) {
            c = index("0123456789abcdef", substr(s, i, 1)) - 1;
            n = n * 16 + c;
        }
        return n;
    }'
}

r8q_u32le() {
    _hex="$(r8q_hex_slice "$1" "$2" 4)"
    [ "${#_hex}" -eq 8 ] || return 1
    awk -v h="$_hex" 'BEGIN {
        b0 = substr(h, 1, 2); b1 = substr(h, 3, 2);
        b2 = substr(h, 5, 2); b3 = substr(h, 7, 2);
        printf "%.0f\n", hexval(b3 b2 b1 b0)
    }
    function hexval(s,    i, c, n) {
        s = tolower(s); n = 0;
        for (i = 1; i <= length(s); i++) {
            c = index("0123456789abcdef", substr(s, i, 1)) - 1;
            n = n * 16 + c;
        }
        return n;
    }'
}

r8q_u32be() {
    _hex="$(r8q_hex_slice "$1" "$2" 4)"
    [ "${#_hex}" -eq 8 ] || return 1
    awk -v h="$_hex" 'BEGIN {
        printf "%.0f\n", hexval(h)
    }
    function hexval(s,    i, c, n) {
        s = tolower(s); n = 0;
        for (i = 1; i <= length(s); i++) {
            c = index("0123456789abcdef", substr(s, i, 1)) - 1;
            n = n * 16 + c;
        }
        return n;
    }'
}

r8q_free_bytes() {
    _dir="$1"
    _df_out="$(df -kP "$_dir" 2>/dev/null || df -k "$_dir" 2>/dev/null || true)"
    _avail_bytes="$(printf '%s\n' "$_df_out" | awk 'NR > 1 && NF >= 4 { avail=$(NF-2) } END { if (avail ~ /^[0-9]+$/) printf "%.0f\n", avail * 1024 }')"
    if [ -z "$_avail_bytes" ]; then
        _df_out="$(df -k 2>/dev/null || true)"
        _avail_bytes="$(printf '%s\n' "$_df_out" | awk 'NR > 1 && NF >= 4 { avail=$(NF-2) } END { if (avail ~ /^[0-9]+$/) printf "%.0f\n", avail * 1024 }')"
    fi
    printf '%s\n' "$_avail_bytes"
}
