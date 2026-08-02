#!/usr/bin/env python3
"""
ZMK Heatmap Generator
Processes keylog data and updates Keymap Drawer SVG & HTML reports
with layer-accurate key, combo, and keycode heat visualization.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

# Add tools directory to sys.path if invoked directly
tools_dir = Path(__file__).parent
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))

from zmk_heatmap_core import parse_keymap_yaml, get_heat_color

def parse_args():
    parser = argparse.ArgumentParser(description="ZMK Heatmap SVG & HTML Generator")
    parser.add_argument("--keylog", "-k", default="keylog.csv", help="Input keylog CSV file (default: keylog.csv)")
    parser.add_argument("--keymap", "-m", default="keymap-drawer/eyelash_corne.yaml", help="Input keymap YAML file")
    parser.add_argument("--svg", "-s", default="keymap-drawer/eyelash_corne.svg", help="Input Keymap Drawer SVG file")
    parser.add_argument("--output-svg", default="heatmap.svg", help="Output Heatmap SVG path (default: heatmap.svg)")
    parser.add_argument("--output-html", default="heatmap.html", help="Output Heatmap HTML report path (default: heatmap.html)")
    parser.add_argument("--title", default="Eyelash Corne Heatmap", help="Heatmap Title")
    return parser.parse_args()

def load_keylog(keylog_path):
    pos_counts = {}
    layer_pos_counts = {}
    combo_counts = {}
    combo_layer_counts = {}
    label_counts = {}
    layer_total_counts = {}
    total_presses = 0

    if not Path(keylog_path).exists():
        print(f"Warning: Keylog file {keylog_path} not found. Generating sample data with combo and layer awareness.")
        sample_keys = [
            (4, 0, "base", "R", "0x15", False, -1, 1500),
            (5, 0, "base", "T", "0x17", False, -1, 1200),
            (11, 0, "base", "Y", "0x1C", False, -1, 1890),
            (12, 0, "base", "U", "0x18", False, -1, 1450),
            (18, 0, "base", "A", "0x04", False, -1, 2450),
            (19, 0, "base", "S/Opt", "0x16", False, -1, 2100),
            (20, 0, "base", "D/Ctrl", "0x07", False, -1, 3100),
            (21, 0, "base", "F/Shift", "0x09", False, -1, 2800),
            (47, 0, "base", "Space", "0x2C", False, -1, 4200),
            (48, 0, "base", "Enter", "0x28", False, -1, 3800),
            (13, 1, "sym", "*", "0x38", False, -1, 850),
            (14, 1, "sym", "(", "0x26", False, -1, 920),
            ("22;23", 0, "base", "HOME (Combo)", "0x4A", True, 1, 650),
            ("24;25", 0, "base", "END (Combo)", "0x4D", True, 2, 580),
            ("23;24", 0, "base", "Backspace (Combo)", "0x2A", True, 3, 1100),
        ]

        for pos, layer, l_name, label, kc, is_combo, combo_idx, count in sample_keys:
            if is_combo:
                combo_counts[combo_idx] = combo_counts.get(combo_idx, 0) + count
                combo_layer_counts[(combo_idx, layer)] = combo_layer_counts.get((combo_idx, layer), 0) + count
            else:
                p = int(pos)
                pos_counts[p] = pos_counts.get(p, 0) + count
                layer_pos_counts[(p, layer)] = layer_pos_counts.get((p, layer), 0) + count

            label_counts[label] = label_counts.get(label, 0) + count
            layer_total_counts[layer] = layer_total_counts.get(layer, 0) + count
            total_presses += count

        return pos_counts, layer_pos_counts, combo_counts, combo_layer_counts, label_counts, layer_total_counts, total_presses

    with open(keylog_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            is_combo = (row.get("is_combo", "false").lower() == "true")
            label = row.get("key_label", "Unknown")
            layer = int(row.get("layer", 0))

            if is_combo:
                combo_idx = int(row.get("combo_index", -1))
                if combo_idx >= 0:
                    combo_counts[combo_idx] = combo_counts.get(combo_idx, 0) + 1
                    combo_layer_counts[(combo_idx, layer)] = combo_layer_counts.get((combo_idx, layer), 0) + 1
            else:
                pos = int(row["position"])
                pos_counts[pos] = pos_counts.get(pos, 0) + 1
                layer_pos_counts[(pos, layer)] = layer_pos_counts.get((pos, layer), 0) + 1

            label_counts[label] = label_counts.get(label, 0) + 1
            layer_total_counts[layer] = layer_total_counts.get(layer, 0) + 1
            total_presses += 1

    return pos_counts, layer_pos_counts, combo_counts, combo_layer_counts, label_counts, layer_total_counts, total_presses

def generate_svg_heatmap(svg_input_path, svg_output_path, pos_counts, layer_pos_counts, combo_counts, combo_layer_counts, layer_names):
    if not Path(svg_input_path).exists():
        print(f"Error: Input SVG {svg_input_path} does not exist.")
        return False

    with open(svg_input_path, "r", encoding="utf-8") as f:
        svg_content = f.read()

    max_key_count = max(layer_pos_counts.values()) if layer_pos_counts else (max(pos_counts.values()) if pos_counts else 1)
    max_combo_count = max(combo_layer_counts.values()) if combo_layer_counts else (max(combo_counts.values()) if combo_counts else 1)

    # Inject SVG Custom Heatmap CSS
    heatmap_style = """
    /* ZMK Heatmap Dynamic Inject Styles */
    rect.key.heat-key, rect.combo.heat-combo {
        transition: fill 0.3s ease, stroke 0.3s ease;
    }
    text.heat-badge {
        font-family: Ubuntu Mono, Consolas, monospace;
        font-size: 9px;
        font-weight: bold;
    }
    g.layer-group {
        transition: opacity 0.3s ease;
    }
    """
    if "</style>" in svg_content:
        svg_content = svg_content.replace("</style>", f"{heatmap_style}\n</style>")

    # Parse layer blocks in SVG: <g transform="..." class="layer-{layer_name}">
    layer_matches = list(re.finditer(r'<g\s+transform="[^"]*"\s+class="layer-([a-zA-Z0-9_-]+)">', svg_content))

    if not layer_matches:
        return _fallback_svg_render(svg_content, svg_output_path, pos_counts, combo_counts, max_key_count, max_combo_count)

    output_parts = []
    first_start = layer_matches[0].start()
    output_parts.append(svg_content[:first_start])

    pattern_key = re.compile(r'<g([^>]+)class="[^"]*keypos-(\d+)[^"]*"[^>]*>(.*?)</g>', re.DOTALL)
    pattern_combo = re.compile(r'<g([^>]+)class="[^"]*combopos-(\d+)[^"]*"[^>]*>(.*?)</g>', re.DOTALL)

    for i, match in enumerate(layer_matches):
        l_name = match.group(1)
        l_idx = layer_names.index(l_name) if (layer_names and l_name in layer_names) else i
        
        start_pos = match.start()
        end_pos = layer_matches[i+1].start() if (i + 1 < len(layer_matches)) else svg_content.rfind("</svg>")
        block_text = svg_content[start_pos:end_pos]

        # Update keys in this layer block
        def update_key_group(m):
            g_tag = m.group(1)
            pos = int(m.group(2))
            inner_content = m.group(3)

            count = layer_pos_counts.get((pos, l_idx), 0)
            colors = get_heat_color(count, max_key_count)

            def update_rect(r_match):
                r_attrs = r_match.group(1)
                new_style = f'fill="{colors["fill"]}" stroke="{colors["stroke"]}" stroke-width="1.8px" style="filter: drop-shadow(0px 0px 4px {colors["glow"]});"'
                return f'<rect {r_attrs} class="key heat-key" {new_style}/>'

            inner_updated = re.sub(r'<rect([^>]+class="key"(?! side)[^>]*)/>', update_rect, inner_content)

            if count > 0:
                badge = f'\n<text x="0" y="21" class="heat-badge" fill="{colors["text"]}" text-anchor="middle">{count:,}</text>'
                inner_updated += badge

            return f'<g{g_tag}class="key keypos-{pos}">{inner_updated}</g>'

        # Update combos in this layer block
        def update_combo_group(m):
            g_tag = m.group(1)
            combo_idx = int(m.group(2))
            inner_content = m.group(3)

            count = combo_layer_counts.get((combo_idx, l_idx), combo_counts.get(combo_idx, 0))
            colors = get_heat_color(count, max_combo_count)

            def update_rect(r_match):
                r_attrs = r_match.group(1)
                new_style = f'fill="{colors["fill"]}" stroke="{colors["stroke"]}" stroke-width="1.8px" style="filter: drop-shadow(0px 0px 4px {colors["glow"]});"'
                return f'<rect {r_attrs} class="combo heat-combo" {new_style}/>'

            inner_updated = re.sub(r'<rect([^>]+class="combo"[^>]*)/>', update_rect, inner_content)

            if count > 0:
                badge = f'\n<text x="0" y="10" class="heat-badge" fill="{colors["text"]}" text-anchor="middle">{count:,}</text>'
                inner_updated += badge

            return f'<g{g_tag}class="combo combopos-{combo_idx}">{inner_updated}</g>'

        mod_block = pattern_key.sub(update_key_group, block_text)
        mod_block = pattern_combo.sub(update_combo_group, mod_block)
        output_parts.append(mod_block)

    last_closing = svg_content.rfind("</svg>")
    output_parts.append(svg_content[last_closing:])

    modified_svg = "".join(output_parts)

    with open(svg_output_path, "w", encoding="utf-8") as f:
        f.write(modified_svg)

    print(f"Heatmap SVG saved to {svg_output_path}")
    return modified_svg

def _fallback_svg_render(svg_content, svg_output_path, pos_counts, combo_counts, max_key_count, max_combo_count):
    pattern_key = re.compile(r'<g([^>]+)class="[^"]*keypos-(\d+)[^"]*"[^>]*>(.*?)</g>', re.DOTALL)
    pattern_combo = re.compile(r'<g([^>]+)class="[^"]*combopos-(\d+)[^"]*"[^>]*>(.*?)</g>', re.DOTALL)

    def update_key_group(match):
        g_tag, pos, inner = match.group(1), int(match.group(2)), match.group(3)
        count = pos_counts.get(pos, 0)
        colors = get_heat_color(count, max_key_count)
        inner = re.sub(r'<rect([^>]+class="key"(?! side)[^>]*)/>', lambda rm: f'<rect {rm.group(1)} class="key heat-key" fill="{colors["fill"]}" stroke="{colors["stroke"]}" stroke-width="1.8px" style="filter: drop-shadow(0px 0px 4px {colors["glow"]});"/>', inner)
        if count > 0:
            inner += f'\n<text x="0" y="21" class="heat-badge" fill="{colors["text"]}" text-anchor="middle">{count:,}</text>'
        return f'<g{g_tag}class="key keypos-{pos}">{inner}</g>'

    def update_combo_group(match):
        g_tag, combo_idx, inner = match.group(1), int(match.group(2)), match.group(3)
        count = combo_counts.get(combo_idx, 0)
        colors = get_heat_color(count, max_combo_count)
        inner = re.sub(r'<rect([^>]+class="combo"[^>]*)/>', lambda rm: f'<rect {rm.group(1)} class="combo heat-combo" fill="{colors["fill"]}" stroke="{colors["stroke"]}" stroke-width="1.8px" style="filter: drop-shadow(0px 0px 4px {colors["glow"]});"/>', inner)
        if count > 0:
            inner += f'\n<text x="0" y="10" class="heat-badge" fill="{colors["text"]}" text-anchor="middle">{count:,}</text>'
        return f'<g{g_tag}class="combo combopos-{combo_idx}">{inner}</g>'

    modified_svg = pattern_key.sub(update_key_group, svg_content)
    modified_svg = pattern_combo.sub(update_combo_group, modified_svg)

    with open(svg_output_path, "w", encoding="utf-8") as f:
        f.write(modified_svg)
    return modified_svg

def generate_html_report(html_output_path, svg_content, pos_counts, layer_pos_counts, combo_counts, label_counts, layer_total_counts, total_presses, layer_names, title):
    unique_keys = len(pos_counts)
    unique_combos = len(combo_counts)
    top_label = max(label_counts, key=label_counts.get) if label_counts else "None"
    top_label_count = label_counts.get(top_label, 0)

    # Layer filter buttons
    layer_buttons = ['<button class="layer-btn active" onclick="filterLayer(\'all\', this)">All Layers</button>']
    for idx, l_name in enumerate(layer_names or ["base"]):
        l_presses = layer_total_counts.get(idx, 0)
        layer_buttons.append(f'<button class="layer-btn" onclick="filterLayer(\'{l_name}\', this)">Layer {idx}: {l_name} ({l_presses:,})</button>')
    buttons_html = "\n".join(layer_buttons)

    # Table rows for key frequency breakdown
    table_rows = []
    sorted_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)
    max_label_count = sorted_labels[0][1] if sorted_labels else 1

    for label, count in sorted_labels:
        pct = (count / total_presses * 100) if total_presses > 0 else 0
        colors = get_heat_color(count, max_label_count)
        is_combo_tag = '<span style="color:#00e5ff; font-size:10px; font-weight:bold;">[COMBO]</span>' if "(Combo)" in label else ""
        table_rows.append(f"""
        <tr>
            <td><strong>{label}</strong> {is_combo_tag}</td>
            <td><span class="badge" style="background:{colors['fill']}; color:{colors['text']}; border:1px solid {colors['stroke']}">{count:,}</span></td>
            <td>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: {pct:.1f}%; background: {colors['stroke']};"></div>
                </div>
            </td>
            <td>{pct:.2f}%</td>
        </tr>
        """)

    table_html = "\n".join(table_rows)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - ZMK Heatmap</title>
    <style>
        :root {{
            --bg-color: #0f1013;
            --card-bg: #16171a;
            --border-color: #27272a;
            --text-main: #f4f4f5;
            --text-muted: #a1a1aa;
            --accent-blue: #00e5ff;
        }}
        body {{
            margin: 0;
            padding: 24px;
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        h1 {{
            margin: 0;
            font-size: 24px;
            color: var(--accent-blue);
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
        }}
        .stat-card .label {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .stat-card .value {{
            font-size: 26px;
            font-weight: bold;
            margin-top: 4px;
            color: #ffffff;
        }}
        .layer-controls {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 16px;
        }}
        .layer-btn {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.2s ease;
        }}
        .layer-btn:hover {{
            border-color: var(--accent-blue);
            color: #ffffff;
        }}
        .layer-btn.active {{
            background: #00e5ff;
            color: #0f1013;
            border-color: #00e5ff;
            box-shadow: 0 0 12px rgba(0, 229, 255, 0.4);
        }}
        .heatmap-container {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow-x: auto;
            margin-bottom: 32px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            position: relative;
        }}
        .heatmap-container svg {{
            max-width: 100%;
            height: auto;
        }}
        .heatmap-tooltip {{
            position: absolute;
            display: none;
            background: #18181b;
            color: #f4f4f5;
            border: 1px solid #00e5ff;
            padding: 8px 12px;
            border-radius: 6px;
            font-family: -apple-system, BlinkMacSystemFont, monospace;
            font-size: 13px;
            pointer-events: none;
            box-shadow: 0 4px 20px rgba(0, 229, 255, 0.4);
            z-index: 9999;
            line-height: 1.4;
        }}
        .stats-section {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            color: var(--text-muted);
            font-size: 13px;
        }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
        }}
        .progress-bar-bg {{
            background: #27272a;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            width: 100%;
        }}
        .progress-bar-fill {{
            height: 100%;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔥 {title}</h1>
            <div style="font-size:14px; color: var(--text-muted);">Layer-Accurate Key & Combo Heatmap Analysis</div>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Keypresses</div>
                <div class="value">{total_presses:,}</div>
            </div>
            <div class="stat-card">
                <div class="label">Unique Key Positions</div>
                <div class="value">{unique_keys}</div>
            </div>
            <div class="stat-card">
                <div class="label">Active Combos</div>
                <div class="value">{unique_combos}</div>
            </div>
            <div class="stat-card">
                <div class="label">Most Active Binding</div>
                <div class="value">{top_label} ({top_label_count:,})</div>
            </div>
        </div>

        <div class="layer-controls">
            {buttons_html}
        </div>

        <div class="heatmap-container" id="svg-host">
            {svg_content}
        </div>

        <div class="stats-section">
            <h2>📊 Resolved Key & Combo Usage Breakdown</h2>
            <table>
                <thead>
                    <tr>
                        <th>Resolved Key / Binding</th>
                        <th>Press Count</th>
                        <th>Usage Frequency</th>
                        <th>Percentage</th>
                    </tr>
                </thead>
                <tbody>
                    {table_html}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function filterLayer(layerName, btnEl) {{
            document.querySelectorAll('.layer-btn').forEach(btn => btn.classList.remove('active'));
            if (btnEl) btnEl.classList.add('active');

            const layers = document.querySelectorAll('g[class*="layer-"]');
            layers.forEach(layer => {{
                if (layerName === 'all' || layer.classList.contains('layer-' + layerName)) {{
                    layer.style.display = 'block';
                    layer.style.opacity = '1.0';
                    layer.style.filter = 'none';
                }} else {{
                    layer.style.display = 'none';
                }}
            }});
        }}

        // Interactive Hover Tooltips for Keycaps & Combos in SVG
        document.addEventListener('DOMContentLoaded', () => {{
            const tooltip = document.createElement('div');
            tooltip.className = 'heatmap-tooltip';
            document.body.appendChild(tooltip);

            document.querySelectorAll('g.key, g.combo').forEach(el => {{
                el.addEventListener('mouseenter', (e) => {{
                    const badge = el.querySelector('.heat-badge');
                    const textEl = el.querySelector('text.tap, text.hold');
                    const label = textEl ? textEl.textContent.trim() : 'Key';
                    const count = badge ? badge.textContent.trim() : '0';

                    let parent = el.parentElement;
                    while (parent && !(parent.className && parent.className.baseVal && parent.className.baseVal.includes('layer-'))) {{
                        parent = parent.parentElement;
                    }}
                    const layerName = (parent && parent.className && parent.className.baseVal) ? parent.className.baseVal.replace('layer-', '') : 'base';

                    tooltip.innerHTML = `<strong>${{label}}</strong><br/>Layer: <span style="color:#a1a1aa">${{layerName}}</span><br/>Presses: <strong style="color:#00e5ff">${{count}}</strong>`;
                    tooltip.style.display = 'block';
                }});

                el.addEventListener('mousemove', (e) => {{
                    tooltip.style.left = (e.pageX + 14) + 'px';
                    tooltip.style.top = (e.pageY + 14) + 'px';
                }});

                el.addEventListener('mouseleave', () => {{
                    tooltip.style.display = 'none';
                }});
            }});
        }});
    </script>
</body>
</html>
"""

    with open(html_output_path, "w", encoding="utf-8") as f:
        f.write(html_template)

    print(f"Interactive Heatmap HTML saved to {html_output_path}")

def main():
    args = parse_args()
    layers, layer_names, combos = parse_keymap_yaml(args.keymap)
    pos_counts, layer_pos_counts, combo_counts, combo_layer_counts, label_counts, layer_total_counts, total_presses = load_keylog(args.keylog)

    print(f"Loaded keylog: {total_presses:,} total presses across {len(pos_counts)} key positions and {len(combo_counts)} combos.")
    svg_content = generate_svg_heatmap(args.svg, args.output_svg, pos_counts, layer_pos_counts, combo_counts, combo_layer_counts, layer_names)
    if svg_content:
        generate_html_report(args.output_html, svg_content, pos_counts, layer_pos_counts, combo_counts, label_counts, layer_total_counts, total_presses, layer_names, args.title)

if __name__ == "__main__":
    main()
