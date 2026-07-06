#!/bin/zsh
# Serve RideCompare on the LAN so your phone can reach it.
PORT=4880
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")
echo ""
echo "  RideCompare running:"
echo "    Mac:    http://localhost:$PORT"
echo "    Phone:  http://$IP:$PORT   (same Wi-Fi network)"
echo ""
echo "  On iPhone: open the phone URL in Safari → Share → Add to Home Screen"
echo ""
cd "$(dirname "$0")"
exec python3 -m http.server "$PORT" --bind 0.0.0.0
