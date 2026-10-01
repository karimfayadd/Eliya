#!/usr/bin/env bash
set -e

# Enable IP forwarding so MITM doesn't cut target's internet
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sysctl -w net.ipv4.ip_forward=1 2>/dev/null || true
fi

echo ""
echo " Starting Eliya..."
echo " Dashboard → http://127.0.0.1:7331"
echo ""

# Run as root / sudo for raw socket access
if [[ "$EUID" -ne 0 ]]; then
    echo " [!] Re-running with sudo (scapy needs raw sockets)..."
    exec sudo python3 "$(dirname "$0")/eliya.py" --traffic "$@"
else
    python3 "$(dirname "$0")/eliya.py" --traffic "$@"
fi
