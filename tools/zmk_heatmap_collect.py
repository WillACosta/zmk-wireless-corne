#!/usr/bin/env python3
"""
ZMK Heatmap Data Collector
Listens to live serial logging or parses log files, resolving keycodes,
active layers, and combos using keymap definitions.
"""

import argparse
import csv
import sys
import re
import time
from pathlib import Path

# Add tools directory to sys.path if invoked directly
tools_dir = Path(__file__).parent
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))

from zmk_heatmap_core import (
    HM_POS_REGEX,
    HM_KC_REGEX,
    parse_keymap_yaml,
    detect_combos,
    resolve_key_event
)

def parse_args():
    parser = argparse.ArgumentParser(description="ZMK Heatmap Data Collector")
    parser.add_argument("--keymap", "-m", default="keymap-drawer/eyelash_corne.yaml", help="Path to keymap YAML file")
    parser.add_argument("--port", "-p", help="Serial port (e.g. /dev/tty.usbmodem14101 or COM3)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--input", "-i", help="Input raw log file to parse instead of live serial")
    parser.add_argument("--output", "-o", default="keylog.csv", help="Output CSV file (default: keylog.csv)")
    parser.add_argument("--combo-window", type=int, default=50, help="Combo detection time window in ms (default: 50)")
    return parser.parse_args()

def collect_from_file(file_path, output_path, layers, layer_names, combos, combo_window):
    print(f"Parsing ZMK log file: {file_path}")
    raw_events = []
    last_kc = "0x00"

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m_kc = HM_KC_REGEX.search(line)
            if m_kc:
                last_kc = m_kc.group(2)
                continue

            m_pos = HM_POS_REGEX.search(line)
            if m_pos:
                pos = int(m_pos.group(1))
                layer = int(m_pos.group(2))
                ts = int(m_pos.group(3))
                raw_events.append((pos, layer, last_kc, ts))
                last_kc = "0x00"

    processed = detect_combos(raw_events, combos, layers, layer_names, combo_window)

    with open(output_path, "w", newline="", encoding="utf-8") as f_out:
        fieldnames = ["position", "layer", "layer_name", "key_label", "keycode", "is_combo", "combo_index", "timestamp"]
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(processed)

    print(f"Processed {len(processed)} events into {output_path}.")
    
    # Summary
    key_counts = {}
    combo_counts = {}
    for ev in processed:
        label = ev["key_label"]
        if ev["is_combo"]:
            combo_counts[label] = combo_counts.get(label, 0) + 1
        else:
            key_counts[label] = key_counts.get(label, 0) + 1

    print("\nTop Regular Key Actuations:")
    for k, c in sorted(key_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {k:20s}: {c} presses")

    if combo_counts:
        print("\nTop Combo Actuations:")
        for k, c in sorted(combo_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {k:20s}: {c} actuations")

def collect_from_serial(port, baud, output_path, layers, layer_names, combos, combo_window):
    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        print("Error: pyserial is required for live serial monitoring.")
        print("Install it with: pip install pyserial")
        sys.exit(1)

    if not port:
        ports = list(serial.tools.list_ports.comports())
        zmk_ports = [p.device for p in ports if "usbmodem" in p.device.lower() or "ttyACM" in p.device]
        if zmk_ports:
            port = zmk_ports[0]
            print(f"Auto-detected ZMK serial port: {port}")
        else:
            if ports:
                print("Available serial ports:")
                for p in ports:
                    print(f"  {p.device} - {p.description}")
                port = ports[0].device
                print(f"Using port: {port}")
            else:
                print("Error: No serial ports found. Please connect your ZMK keyboard or specify --input.")
                sys.exit(1)

    print(f"Connecting to ZMK board on {port} @ {baud} baud...")
    raw_events = []
    last_kc = "0x00"

    try:
        ser = serial.Serial(port, baud, timeout=1)
        print("Listening for keypresses... Press Ctrl+C to stop.\n")

        while True:
            line = ser.readline().decode("utf-8", errors="ignore")
            if not line:
                continue

            m_kc = HM_KC_REGEX.search(line)
            if m_kc:
                last_kc = m_kc.group(2)
                continue

            m_pos = HM_POS_REGEX.search(line)
            if m_pos:
                pos = int(m_pos.group(1))
                layer = int(m_pos.group(2))
                ts = int(m_pos.group(3))
                raw_events.append((pos, layer, last_kc, ts))
                last_kc = "0x00"
                
                processed = detect_combos(raw_events, combos, layers, layer_names, combo_window)
                latest = processed[-1]
                print(f"\r[Live] Key: {latest['key_label']:15s} | Layer: {latest['layer_name']:6s} | Total: {len(processed)}", end="", flush=True)

    except KeyboardInterrupt:
        print(f"\nStopped live collection. Saving {len(raw_events)} events...")
        processed = detect_combos(raw_events, combos, layers, layer_names, combo_window)
        with open(output_path, "w", newline="", encoding="utf-8") as f_out:
            fieldnames = ["position", "layer", "layer_name", "key_label", "keycode", "is_combo", "combo_index", "timestamp"]
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(processed)
        print(f"Saved to {output_path}")

def main():
    args = parse_args()
    layers, layer_names, combos = parse_keymap_yaml(args.keymap)
    if layer_names:
        print(f"Loaded keymap: {len(layer_names)} layers ({', '.join(layer_names)}), {len(combos)} combos.")
    
    if args.input:
        collect_from_file(args.input, args.output, layers, layer_names, combos, args.combo_window)
    else:
        collect_from_serial(args.port, args.baud, args.output, layers, layer_names, combos, args.combo_window)

if __name__ == "__main__":
    main()
