#!/usr/bin/env python3
"""
ZMK Heatmap Core Module
Provides keymap YAML parsing, event processing, combo resolution,
and SVG/HTML heatmap generation.
"""

import re
import csv
import sys
from pathlib import Path

# Regular expressions for ZMK heatmap log format
HM_POS_REGEX = re.compile(r"HM:(\d+),(\d+),(\d+)")
HM_KC_REGEX = re.compile(r"HM:KC:(0x[0-9a-fA-F]+),(0x[0-9a-fA-F]+),(\d+)")

ICON_MAP = {
    "$$mdi:keyboard-tab$$": "Tab",
    "$$mdi:keyboard-esc$$": "ESC",
    "$$mdi:keyboard-return$$": "Enter",
    "$$mdi:keyboard-space$$": "Space",
    "$$mdi:backspace$$": "Backspace",
    "$$mdi:backspace-reverse-outline$$": "Del",
    "$$mdi:apple-keyboard-shift$$": "Shift",
    "$$mdi:apple-keyboard-control$$": "Ctrl",
    "$$mdi:apple-keyboard-option$$": "Alt",
    "$$mdi:apple-keyboard-command$$": "Cmd",
    "$$mdi:arrow-up-bold$$": "Up",
    "$$mdi:arrow-down-bold$$": "Down",
    "$$mdi:arrow-left-bold$$": "Left",
    "$$mdi:arrow-right-bold$$": "Right",
    "$$mdi:bluetooth$$": "BLE",
    "$$mdi:bluetooth-off$$": "BLE Off",
    "$$mdi:bluetooth-connect$$": "BLE Conn",
    "$$mdi:transfer$$": "Trans",
    "$$mdi:minus-circle-outline$$": "None",
}

def clean_label(raw):
    if not raw:
        return "Unknown"
    if isinstance(raw, str):
        s = raw.strip()
        if s in ICON_MAP:
            return ICON_MAP[s]
        for icon, name in ICON_MAP.items():
            s = s.replace(icon, name)
        return s
    elif isinstance(raw, dict):
        tap = clean_label(raw.get("t", ""))
        hold = clean_label(raw.get("h", ""))
        if hold and tap and hold != tap:
            return f"{tap}/{hold}"
        return tap or hold or "Key"
    return str(raw)

def parse_keymap_yaml(filepath):
    if not filepath or not Path(filepath).exists():
        return {}, [], []

    layers = {}
    layer_names = []
    combos = []
    current_layer = None
    in_combos = False
    current_combo = None

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            raw_line = line.rstrip()
            if not raw_line or raw_line.startswith("#"):
                continue

            if raw_line.startswith("layers:"):
                in_combos = False
                continue
            if raw_line.startswith("combos:"):
                in_combos = True
                continue

            if not in_combos:
                m_layer = re.match(r"^  ([a-zA-Z0-9_-]+):$", raw_line)
                if m_layer:
                    current_layer = m_layer.group(1)
                    layers[current_layer] = []
                    layer_names.append(current_layer)
                    continue

                if current_layer and raw_line.startswith("  - "):
                    item = raw_line[4:].strip()
                    if item.startswith("{") and item.endswith("}"):
                        obj = {}
                        for kv in re.findall(r"([a-z]+):\s*('[^']*'|\"[^\"]*\"|[^,}]+)", item):
                            k = kv[0].strip()
                            v = kv[1].strip().strip("'\"")
                            obj[k] = v
                        layers[current_layer].append(clean_label(obj))
                    else:
                        layers[current_layer].append(clean_label(item))
            else:
                if raw_line.startswith("- p:"):
                    if current_combo:
                        combos.append(current_combo)
                    m_p = re.search(r"\[(.*?)\]", raw_line)
                    positions = [int(x.strip()) for x in m_p.group(1).split(",") if x.strip()] if m_p else []
                    current_combo = {"p": sorted(positions), "k": "", "l": []}
                elif current_combo:
                    if "k:" in raw_line:
                        val = raw_line.split("k:", 1)[1].strip().strip("'\"")
                        if val.startswith("{") and val.endswith("}"):
                            obj = {}
                            for kv in re.findall(r"([a-z]+):\s*('[^']*'|\"[^\"]*\"|[^,}]+)", val):
                                obj[kv[0].strip()] = kv[1].strip().strip("'\"")
                            current_combo["k"] = clean_label(obj)
                        else:
                            current_combo["k"] = clean_label(val)
                    elif "l:" in raw_line:
                        m_l = re.search(r"\[(.*?)\]", raw_line)
                        if m_l:
                            current_combo["l"] = [x.strip().strip("'\"") for x in m_l.group(1).split(",") if x.strip()]

        if current_combo:
            combos.append(current_combo)

    return layers, layer_names, combos

def resolve_key_event(pos, layer_idx, layers, layer_names):
    if layer_idx < len(layer_names):
        layer_name = layer_names[layer_idx]
    else:
        layer_name = f"layer_{layer_idx}"

    key_label = "Unknown"
    if layer_name in layers and pos < len(layers[layer_name]):
        key_label = layers[layer_name][pos]

    return layer_name, key_label

def detect_combos(raw_events, combos, layers, layer_names, combo_window_ms=50):
    processed = []
    i = 0
    n = len(raw_events)

    while i < n:
        pos, layer_idx, kc, ts = raw_events[i]
        layer_name = layer_names[layer_idx] if layer_idx < len(layer_names) else f"layer_{layer_idx}"

        j = i + 1
        group = [i]
        positions = [pos]

        while j < n:
            next_pos, next_layer, next_kc, next_ts = raw_events[j]
            if (next_ts - ts) <= combo_window_ms:
                if next_pos not in positions:
                    group.append(j)
                    positions.append(next_pos)
                j += 1
            else:
                break

        sorted_pos = sorted(positions)
        matched_combo_idx = -1
        matched_combo = None

        if len(positions) > 1:
            for idx, combo in enumerate(combos):
                if combo["p"] == sorted_pos:
                    if not combo["l"] or layer_name in combo["l"]:
                        matched_combo_idx = idx
                        matched_combo = combo
                        break

        if matched_combo:
            pos_str = ";".join(str(p) for p in sorted_pos)
            processed.append({
                "position": pos_str,
                "layer": layer_idx,
                "layer_name": layer_name,
                "key_label": f"{matched_combo['k']} (Combo)",
                "keycode": kc or "0x00",
                "is_combo": True,
                "combo_index": matched_combo_idx,
                "timestamp": ts
            })
            i = j
        else:
            layer_name, label = resolve_key_event(pos, layer_idx, layers, layer_names) if layer_names else (layer_name, "Key")
            processed.append({
                "position": str(pos),
                "layer": layer_idx,
                "layer_name": layer_name,
                "key_label": label,
                "keycode": kc or "0x00",
                "is_combo": False,
                "combo_index": -1,
                "timestamp": ts
            })
            i += 1

    return processed

def get_heat_color(count, max_count):
    if max_count == 0 or count == 0:
        return {
            "fill": "#16171a",
            "stroke": "#3c3f47",
            "text": "#52525b",
            "glow": "none"
        }

    ratio = count / max_count

    if ratio < 0.15:
        return {"fill": "#062d38", "stroke": "#00b8d4", "text": "#00e5ff", "glow": "rgba(0, 229, 255, 0.4)"}
    elif ratio < 0.40:
        return {"fill": "#0a3a22", "stroke": "#00e676", "text": "#69f0ae", "glow": "rgba(0, 230, 118, 0.4)"}
    elif ratio < 0.70:
        return {"fill": "#3d3700", "stroke": "#ffea00", "text": "#ffff8d", "glow": "rgba(255, 234, 0, 0.5)"}
    else:
        return {"fill": "#4a1204", "stroke": "#ff3d00", "text": "#ff8a80", "glow": "rgba(255, 61, 0, 0.6)"}
