#!/bin/sh
set -e
cd /app
mkdir -p output

echo "[epg] Running initial filter..."
python filter.py || echo "[epg] Initial run failed, will retry on schedule"

# Weekly cron: Sunday 03:00
echo "0 3 * * 0 cd /app && python filter.py >> /proc/1/fd/1 2>&1" > /etc/crontabs/root
crond

echo "[epg] Serving output/ on :8181"
cd output
exec python -m http.server 8181
