#!/usr/bin/env python3
"""
IPTV playlist and EPG filter.

Usage:
  python filter.py --list-groups   # fetch playlist and print all group-title values
  python filter.py                 # filter playlist + EPG and write to output/
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import requests
import yaml

ENV_FILE = Path(__file__).parent / ".env"
CONFIG_FILE = Path(__file__).parent / "config.yaml"
OUTPUT_DIR = Path(__file__).parent / "output"


def load_env():
    if not ENV_FILE.exists():
        sys.exit(f"Missing {ENV_FILE} — copy .env.example and fill in credentials.")
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def load_config():
    if not CONFIG_FILE.exists():
        sys.exit(f"Missing {CONFIG_FILE} — run --list-groups first, then create config.yaml.")
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def fetch(url, label):
    print(f"Fetching {label}...", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        content = r.content
        print(f"{len(content) // 1024} KB")
        return content
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


def parse_m3u(raw: bytes):
    """Return list of (attrs_dict, stream_url) tuples, one per channel."""
    text = raw.decode("utf-8", errors="replace")
    channels = []
    extinf_re = re.compile(r'#EXTINF:-?\d+([^,]*),(.*)')
    attr_re = re.compile(r'([\w-]+)="([^"]*)"')

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            m = extinf_re.match(line)
            if m:
                attrs = dict(attr_re.findall(m.group(1)))
                attrs["_display_name"] = m.group(2).strip()
                # next non-empty line is the stream URL
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                url = lines[i].strip() if i < len(lines) else ""
                channels.append((attrs, url))
        i += 1
    return channels


def list_groups(channels):
    groups = defaultdict(int)
    for attrs, _ in channels:
        g = attrs.get("group-title", "(no group)")
        groups[g] += 1
    print(f"\n{'GROUP':60s}  CHANNELS")
    print("-" * 70)
    for g, count in sorted(groups.items(), key=lambda x: x[0].lower()):
        print(f"{g:60s}  {count}")
    print(f"\nTotal groups: {len(groups)}, Total channels: {sum(groups.values())}")


def filter_m3u(channels, keep_groups, keep_channels):
    keep_groups_lower = {g.lower() for g in keep_groups}
    keep_channels_lower = {c.lower() for c in keep_channels}
    kept = []
    for attrs, url in channels:
        g = attrs.get("group-title", "")
        name = attrs.get("_display_name", "")
        if g.lower() in keep_groups_lower or name.lower() in keep_channels_lower:
            kept.append((attrs, url))
    return kept


def write_m3u(channels, path: Path, local_epg_url: str):
    lines = [f'#EXTM3U url-tvg="{local_epg_url}"']
    for attrs, url in channels:
        display = attrs.pop("_display_name", "")
        attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        attrs["_display_name"] = display  # restore
        lines.append(f"#EXTINF:-1 {attr_str},{display}")
        lines.append(url)
    path.write_text("\n".join(lines), encoding="utf-8")


def filter_epg(raw: bytes, kept_tvg_ids: set):
    root = ET.fromstring(raw)
    to_remove_channels = [ch for ch in root.findall("channel") if ch.get("id") not in kept_tvg_ids]
    to_remove_progs = [p for p in root.findall("programme") if p.get("channel") not in kept_tvg_ids]
    for el in to_remove_channels:
        root.remove(el)
    for el in to_remove_progs:
        root.remove(el)
    return root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-groups", action="store_true", help="Print all group-title values and exit")
    args = parser.parse_args()

    env = load_env()
    m3u_url = env.get("PROVIDER_M3U_URL")
    epg_url = env.get("PROVIDER_EPG_URL")

    if not m3u_url:
        sys.exit("PROVIDER_M3U_URL not set in .env")

    raw_m3u = fetch(m3u_url, "M3U playlist")
    channels = parse_m3u(raw_m3u)

    if args.list_groups:
        list_groups(channels)
        return

    cfg = load_config()
    keep_groups = cfg.get("keep_groups", [])
    keep_channels = cfg.get("keep_channels", [])
    local_epg_url = cfg.get("local_epg_url", "http://localhost:8080/epg.xml")

    kept = filter_m3u(channels, keep_groups, keep_channels)
    kept_tvg_ids = {attrs.get("tvg-id", "") for attrs, _ in kept} - {""}
    print(f"Kept {len(kept)} / {len(channels)} channels across {len(kept_tvg_ids)} tvg-ids")

    OUTPUT_DIR.mkdir(exist_ok=True)
    playlist_path = OUTPUT_DIR / "pl.m3u"
    write_m3u(kept, playlist_path, local_epg_url)
    print(f"Written: {playlist_path} ({playlist_path.stat().st_size // 1024} KB)")

    if epg_url:
        raw_epg = fetch(epg_url, "EPG XML")
        epg_root = filter_epg(raw_epg, kept_tvg_ids)
        epg_path = OUTPUT_DIR / "epg.xml"
        tree = ET.ElementTree(epg_root)
        ET.indent(tree, space="  ")
        tree.write(str(epg_path), encoding="utf-8", xml_declaration=True)
        print(f"Written: {epg_path} ({epg_path.stat().st_size // 1024} KB)")
    else:
        print("PROVIDER_EPG_URL not set — skipping EPG filtering")


if __name__ == "__main__":
    main()
