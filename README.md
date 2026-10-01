<div align="center">

```
 _____  _ _
| ____|| (_)_   _  __ _
|  _|  | | | | | |/ _` |
| |___ | | | |_| | (_| |
|_____|_|_|\__, |\__,_|
           |___/
```

# Eliya — Live Network Asset Intelligence

**Discover every device. Monitor all traffic. Control your network.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](https://github.com/karimfayadd/eliya)
[![License](https://img.shields.io/badge/License-Eliya%20v1.0-orange)](LICENSE)
[![Stars](https://img.shields.io/github/stars/karimfayadd/eliya?style=social)](https://github.com/karimfayadd/eliya)

</div>

---

## What is Eliya?

Eliya is a **network asset intelligence tool** with a real-time visual graph dashboard. It combines passive monitoring, active scanning, and MITM-grade interception into a single Python script with a sleek dark-themed web UI — no external databases, no agents, no bloat.

Think of it as **Wireshark + NetCut + Nmap** — but visual, controllable from a browser, and built for red-teamers and network defenders alike.

---

## Features

### Discovery
| Feature | Description |
|---|---|
| **ARP Scan** | Multi-method: scapy Layer-2 ARP, ping sweep + OS ARP table, mDNS, SSDP/UPnP — all in parallel |
| **Camera / IoT Detection** | OUI fingerprinting for 40+ vendors: Hikvision, Dahua, Reolink, Nest, Ring, Wyze, Roku, Samsung TV, Xbox, PlayStation, and more |
| **HTTP Banner Grab** | Pulls `Server` header + page title from ports 80/443/8080/8443 |
| **Nmap Integration** | Import any nmap XML; full service version + OS detection |
| **Reverse DNS** | Background hostname resolution with NetBIOS fallback on Windows |

### Monitoring
| Feature | Description |
|---|---|
| **Live Traffic Monitor** | Per-device bandwidth (↓/↑ KB/s) via scapy packet sniffer |
| **DNS Snooping** | Logs every DNS query from every device in real time |
| **TLS SNI Extraction** | Reads HTTPS hostnames from ClientHello — no decryption needed |
| **Live Network Monitor** | Background re-scan on interval; alerts on new/disappeared devices |

### Interception (MITM)
| Feature | Description |
|---|---|
| **Passive MITM** | Transparent ARP interception — device keeps internet, all traffic flows through you |
| **Full HTTP URL Capture** | TCP stream reassembly extracts method + full path + query string + Referer from every request including keep-alive connections |
| **DNS Spoofing** | Intercept DNS queries and redirect any domain to your custom URL or HTML page |
| **Wildcard Rules** | `*.ads.com` catches all subdomains |
| **HTTP Redirect Server** | Built-in socket server (port 80 / 8080 fallback) serves 302 redirects or custom HTML to spoofed victims |

### Control
| Feature | Description |
|---|---|
| **Cut Internet** | ARP spoof to drop a device's internet — one click, reversible |
| **Restore Internet** | Sends corrective ARP to heal the victim's ARP table |
| **Per-Device Control Tab** | Manage MITM, cut/restore, and DNS spoof rules per device |

### Dashboard
| Feature | Description |
|---|---|
| **Cytoscape.js Graph** | Interactive force-directed network map with device shapes + color by type |
| **Real-time WebSocket** | All events (scan, traffic, MITM, DNS) pushed live to the browser |
| **Tabbed Details Panel** | Info / Traffic / Websites / Control per device |
| **Sidebar Speed Badges** | ↓/↑ KB/s shown inline per device |
| **Filter Bar** | All / Online / Offline / Cams 📷 / IoT / ⚠ Risk |
| **Dark Theme** | GitHub-style dark UI — easy on the eyes during long sessions |

---

## Requirements

### Windows
- Python 3.10+
- **[Npcap](https://npcap.com/)** — raw socket driver required by scapy (install before running)
- Run as **Administrator**

### Linux
- Python 3.10+
- Run as **root** (`sudo`) — required for raw socket access
- IP forwarding enabled automatically by `run.sh`

### macOS
- Python 3.10+
- Run as **root** (`sudo python3 eliya.py`)

---

## Installation

```bash
git clone https://github.com/karimfayadd/eliya.git
cd eliya
pip install -r requirements.txt
```

> **Windows only:** install [Npcap](https://npcap.com/) before running.

---

## Quick Start

### Windows
```
Double-click run.bat
```
Or from an elevated command prompt:
```cmd
python eliya.py --traffic
```

### Linux / macOS
```bash
chmod +x run.sh
./run.sh
```

Then open **http://127.0.0.1:7331** in your browser.

---

## CLI Reference

```
python eliya.py [OPTIONS]
```

| Flag | Description |
|---|---|
| `--traffic` | Enable live traffic monitor + DNS snooping at startup |
| `--arp-scan NETWORK` | Run ARP scan immediately (e.g. `192.168.1.0/24`) |
| `--monitor NETWORK` | Start continuous background re-scan |
| `--interval N` | Re-scan interval in seconds (default: 30) |
| `--import-xml FILE` | Import nmap XML scan results |
| `--scan TARGET` | Run nmap scan against target at startup |
| `--host HOST` | Bind address (default: `127.0.0.1`) |
| `--port PORT` | Dashboard port (default: `7331`) |
| `--no-browser` | Don't auto-open the browser |
| `--db FILE` | Custom SQLite database path |
| `--version` | Print version and exit |

---

## API Reference

```
GET  /api/graph                  — Full network graph (nodes + edges)
GET  /api/assets                 — All discovered assets
GET  /api/assets/{ip}            — Asset detail + ports + DNS log + events
GET  /api/traffic                — Current per-IP bandwidth speeds
POST /api/traffic/start          — Start traffic monitor
POST /api/traffic/stop           — Stop traffic monitor
GET  /api/dns                    — All DNS log entries
GET  /api/dns/{ip}               — DNS log for a specific device
POST /api/arp-scan               — Trigger ARP scan {"network":"192.168.1.0/24"}
POST /api/scan                   — Trigger nmap scan {"target":"192.168.1.0/24"}
POST /api/ssdp                   — Trigger SSDP/UPnP discovery
POST /api/control/cut/{ip}       — Cut device's internet access
POST /api/control/restore/{ip}   — Restore device's internet access
GET  /api/control/status         — Cut IPs + gateway info
POST /api/mitm/start/{ip}        — Start passive MITM on device
POST /api/mitm/stop/{ip}         — Stop passive MITM on device
GET  /api/mitm/status            — Currently intercepted IPs
GET  /api/mitm/log/{ip}          — Captured connections log
GET  /api/spoof/rules            — List DNS spoof rules
POST /api/spoof/rules            — Add rule {"domain":"example.com","redirect":"http://..."}
DELETE /api/spoof/rules/{domain} — Remove spoof rule
POST /api/monitor/start          — Start live monitor {"network":"...","interval":30}
POST /api/monitor/stop           — Stop live monitor
GET  /api/events                 — Event log
DELETE /api/assets/{ip}          — Delete asset
DELETE /api/clear                — Clear all data
WS   /ws                         — WebSocket for real-time events
```

---

## WebSocket Events

Events pushed in real time to all connected browser tabs:

| Event | Payload |
|---|---|
| `asset_up` | `{ip, mac, vendor, hostname}` |
| `device_joined` | `{ip, mac, vendor}` |
| `device_left` | `{ip}` |
| `device_cut` | `{ip}` |
| `device_restored` | `{ip}` |
| `traffic_update` | `{speeds: {ip: {in, out, bi, bo}}}` |
| `scan_done` | `{scan_id, count}` |
| `mitm_started` | `{ip}` |
| `mitm_stopped` | `{ip}` |
| `mitm_live` | `{ip, proto, domain, method, path, referer, url, dst, dport, ts}` |
| `dns_spoofed` | `{ip, domain, to, rule, ts}` |
| `spoof_updated` | `{rules}` |

---

## Important Notes

- **HTTPS sites**: DNS spoofing still intercepts the DNS query, but the browser will show a TLS certificate error when connecting to port 443. Full HTTPS interception requires SSL MITM with a trusted CA certificate on the target device.
- **DNS-over-HTTPS (DoH)**: Browsers using DoH (Firefox, Chrome on some configs) bypass local DNS — their encrypted DNS queries go directly to `1.1.1.1` or `8.8.8.8` over HTTPS and are invisible to this tool.
- **Admin / root required**: scapy needs raw socket access. On Windows, run as Administrator. On Linux/macOS, run as root.

---

## Legal

This tool is for use only on networks and systems you own or have **explicit written authorization** to test. Unauthorized use is illegal and entirely your responsibility.

See [LICENSE](LICENSE) for full terms.

---

## Author

Built by **Karim Fayad** · [github.com/karimfayadd](https://github.com/karimfayadd)
