# IPTV Playlist & EPG Filter

Fetches a large IPTV provider playlist and EPG, filters them down to a curated set of channel groups, and writes smaller output files ready to be served locally.

## How it works

The provider supplies a full M3U playlist (~335k channels, ~80 MB) and an XMLTV EPG (~108 MB). Running `filter.py` fetches both, keeps only the groups listed in `config.yaml`, and writes two files to `output/`:

- `output/playlist.m3u` — filtered M3U with the `url-tvg` header pointing at the local EPG URL
- `output/epg.xml` — filtered XMLTV containing only programme data for kept channels

The playlist header embeds the local EPG URL so IPTV apps that auto-derive the EPG from the playlist URL pick it up without manual configuration.

## Files

| File | Purpose |
|---|---|
| `filter.py` | Main script: fetch, filter, write |
| `config.yaml` | Whitelist of `group-title` values to keep; also sets `local_epg_url` |
| `.env` | Provider credentials (gitignored — copy `.env.example`) |
| `output/` | Generated files (gitignored) |

## Usage

```sh
# One-time setup
pip install -r requirements.txt
cp .env.example .env   # fill in PROVIDER_M3U_URL and PROVIDER_EPG_URL

# Discover available groups
python filter.py --list-groups

# Generate filtered playlist and EPG
python filter.py
```

## Configuration

Edit `config.yaml` to control which groups are kept and where the output will be served:

```yaml
local_epg_url: "http://nas:8080/epg.xml"

keep_groups:
  - "UK | SPORTS"
  - "NL | NETHERLANDS"
  # ...

keep_channels: []   # individual channel names, if needed
```

## Deployment (QNAP NAS)

The `output/` directory is served over HTTP on port 8080. A scheduled task (cron) runs `filter.py` weekly to refresh both files. Point your IPTV app at:

- Playlist: `http://nas:8080/playlist.m3u`
- EPG: `http://nas:8080/epg.xml` (or leave it implicit — the playlist header sets it)
