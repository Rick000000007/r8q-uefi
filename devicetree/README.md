# Downstream Device Tree Evidence

This directory contains one file, `r8q-live.dts`, which is **evidence**, not a
build input.

## What the file is

`r8q-live.dts` is a 35,733-line decompiled downstream Samsung/vendor device
tree for the captured `r8q` unit. Its top-level identity is:

| Property | Value |
|---|---|
| `model` | `Samsung R8Q EUR PROJECT - R8 REV04 (board-id,08)` |
| `compatible` | `qcom,kona-mtp`, `qcom,kona`, `qcom,mtp` |
| `qcom,msm-id` | `<0x164 0x20001>` |
| `qcom,board-id` | `<0x08 0x08>` |
| `/memory` | `0x80000000 + 0x3BB00000`, `0xC0000000 + 0x1C0000000` |

It is not the upstream Linux `sm8250-samsung-r8q.dts`. The upstream file only
adds firmware names and a model string; the downstream file contains the
Samsung panel, touch, charger, PMIC, UFS, USB, PCIe, WLAN, TSENS, and
reserved-memory descriptions.

## Provenance status

**Provenance is not established.** The capture method, date, firmware version,
and chain of custody are unknown. The content is consistent with a DTB read
from a booted vendor system, but that is an inference, not a recorded fact.
The file must not be described as an official Samsung or Qualcomm source.

## Sanitization

The following values in `/chosen/bootargs` were replaced with `REDACTED` before
this file was committed:

| Original field | Reason |
|---|---|
| `androidboot.serialno` | Device serial number |
| `androidboot.ap_serial` | Application-processor serial |
| `androidboot.em.did` | Device identity value |
| `signoff` | Vendor sign-off value |

The bootloader build string (`androidboot.bootloader=G781BXXSIHYJ4`), model
(`SM-G781B`), region/carrier codes, and `androidboot.dram_info` were retained
because they describe firmware/variant state rather than a personal identifier.
A future capture should re-check for IMEI, MAC addresses, calibration data, and
any new `androidboot.*serial*` fields before publication.

Current file identity:

```text
size:    1,234,551 bytes
lines:   35,733
sha256:  9b71666f5ccf53b9c70d587b9befa002c0aa2f1db3420a79084d9b6857ed91c8
```

## Validation

The file parses with the host `dtc`:

```bash
dtc -I dts -O dtb -o /tmp/r8q-live.dtb devicetree/r8q-live.dts
```

This exits 0 but emits warnings. The warnings observed on 2026-11-20 were:

- `gpios_property` warnings where a decompiled GPIO cell is not a phandle
  reference;
- a missing `#interrupt-cells` property on the `max77705` interrupt provider;
- alias names that are not lowercase or do not contain only `-`.

These are properties of the decompiled vendor tree and its bindings. They are
not proof of a hardware fault, and they must not be "fixed" in the evidence
file. If a cleaned DTS is needed for a build, create a separate derivative and
document every change.

## How to use it

- Cite it as `V-R8Q-FDT` in `docs/VERIFICATION_LEDGER.md`.
- Treat every value as evidence for the **captured unit**, not for every
  `r8q` variant.
- Re-read the live FDT on the target before using an address, size, panel,
  touch controller, charger, or partition mapping.
- Never copy a carveout into a static UEFI memory map without checking the live
  `/reserved-memory` map.
- Never use this file as the firmware's build-time DTB. The firmware must
  validate and patch the live FDT it receives.

## Redistribution

The file may be subject to Samsung or Qualcomm licensing terms. Do not
redistribute it outside this repository until the provenance and licensing
status have been reviewed. The sanitized identifiers reduce privacy risk but do
not establish a redistribution right.
