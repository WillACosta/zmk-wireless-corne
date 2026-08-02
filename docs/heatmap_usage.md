# ZMK Heatmap Module - Usage & Integration Guide

This guide explains how to enable, collect data from, and generate keypress heatmaps using the **ZMK Heatmap** module and tooling integrated into this repository.

---

## 1. Firmware Setup & Configuration

### Enabling in this Repository (Eyelash Corne)
The module is included in `zephyr/module.yml` and enabled in `config/eyelash_corne.conf`:

```properties
# === Heatmap Generator ===
CONFIG_ZMK_HEATMAP=y
```

When enabled, your keyboard logs matrix positions, layer changes, and resolved keycodes over USB serial (CDC ACM):
- Position Event: `HM:<position>,<layer>,<timestamp_ms>`
- Keycode Event: `HM:KC:<usage_page>,<keycode>,<timestamp_ms>`

---

## 2. CLI Tooling: `zmk-heatmap`

A human-readable CLI tool `zmk-heatmap` is available in the repository root for both data collection and SVG/HTML report generation.

### Commands Overview

```bash
# 1. Collect live data or parse log files with keymap awareness
./zmk-heatmap collect --keymap=keymap-drawer/eyelash_corne.yaml

# 2. Generate SVG heatmap & interactive HTML report
./zmk-heatmap generate
```

---

## 3. Data Collection (`zmk-heatmap collect`)

The collector parses incoming logs, cross-referencing your `keymap.yaml` file to resolve physical positions to true key bindings (e.g. distinguishing `ESC` on layer 0 from `Delete` or `!` on layer 1) and detecting multi-key combo actuations.

### Option A: Live USB Serial Monitoring
Connect your keyboard via USB and run:

```bash
./zmk-heatmap collect --keymap=keymap-drawer/eyelash_corne.yaml
```
- Auto-detects your ZMK serial port (`/dev/tty.usbmodem*` or `COM*`).
- Displays live feedback as keys and combos are actuated.
- Saves enriched dataset into `keylog.csv`.

### Option B: Offline Log Ingestion
If you captured logs via `cat`, `hid_listen`, or terminal logs:

```bash
./zmk-heatmap collect --input=raw.log --keymap=keymap-drawer/eyelash_corne.yaml --output=keylog.csv
```

### Enriched Dataset Format (`keylog.csv`)
```csv
position,layer,layer_name,key_label,keycode,is_combo,combo_index,timestamp
13,0,base,ESC/Shift,0x0029,False,-1,10450
13,1,sym,*,0x0038,False,-1,10820
22;23,0,base,HOME (Combo),0x004A,True,1,11200
```

---

## 4. Heatmap Generation (`zmk-heatmap generate`)

The generator parses `keylog.csv` and renders both single-key position heatmaps and combo actuation heatmaps onto Keymap Drawer vector layouts.

```bash
./zmk-heatmap generate \
  --keylog=keylog.csv \
  --keymap=keymap-drawer/eyelash_corne.yaml \
  --svg=keymap-drawer/eyelash_corne.svg \
  --output-svg=heatmap.svg \
  --output-html=heatmap.html
```

### Generated Artifacts
1. **`heatmap.svg`**: High-resolution vector layout styled with heat intensity fills (`Cool Cyan -> Emerald Green -> Yellow -> Hot Red`) on both key shapes (`keypos-{N}`) and combo elements (`combopos-{M}`).
2. **`heatmap.html`**: Self-contained interactive report with summary cards, SVG layout viewer, and a breakdown of resolved key & combo usage statistics.
