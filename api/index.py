from flask import Flask, request, jsonify
import requests
import os
import socket
from urllib.parse import quote

app = Flask(__name__)

IPINFO_TOKEN = os.getenv("IPINFO_TOKEN", "YOUR_IPINFO_TOKEN")
IPAPI_KEY = os.getenv("IPAPI_KEY", "YOUR_IPAPI_KEY")


def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def get_reverse_dns(ip):
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return host
    except Exception:
        return None


def parse_ipinfo(data):
    loc = data.get("loc", "")
    lat, lon = None, None
    if "," in loc:
        parts = loc.split(",", 1)
        lat, lon = parts[0], parts[1]

    return {
        "provider": "ipinfo",
        "raw": data,
        "normalized": {
            "ip": data.get("ip"),
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country"),
            "continent": data.get("continent"),
            "postal": data.get("postal"),
            "timezone": data.get("timezone"),
            "coordinates": {
                "latitude": lat,
                "longitude": lon
            },
            "asn": data.get("asn") or data.get("as"),
            "org": data.get("org"),
            "hostname": data.get("hostname"),
            "privacy": data.get("privacy"),
            "company": data.get("company"),
            "carrier": data.get("carrier"),
        }
    }


def parse_ipapi(data):
    return {
        "provider": "ipapi",
        "raw": data,
        "normalized": {
            "ip": data.get("ip"),
            "type": data.get("type"),
            "city": data.get("city"),
            "region": data.get("region_name"),
            "country": data.get("country_name"),
            "country_code": data.get("country_code"),
            "continent": data.get("continent_name"),
            "continent_code": data.get("continent_code"),
            "postal": data.get("zip"),
            "timezone": safe_get(data, "time_zone", "id"),
            "timezone_offset": safe_get(data, "time_zone", "gmt_offset"),
            "coordinates": {
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude")
            },
            "currency": {
                "code": safe_get(data, "currency", "code"),
                "name": safe_get(data, "currency", "name"),
                "symbol": safe_get(data, "currency", "symbol")
            },
            "language": data.get("location", {}).get("languages"),
            "connection": data.get("connection"),
            "security": data.get("security"),
        }
    }


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "name": "Advanced IP Info API",
        "routes": {
            "/api/myip": "Get requester public IP",
            "/api/ip?ip=8.8.8.8": "Get advanced IP details",
            "/api/ip?ip=8.8.8.8&provider=ipinfo": "Force IPinfo",
            "/api/ip?ip=8.8.8.8&provider=ipapi": "Force ipapi"
        }
    })


@app.route("/api/myip")
def myip():
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=10)
        r.raise_for_status()
        ip = r.json().get("ip")

        return jsonify({
            "success": True,
            "ip": ip,
            "request_meta": {
                "remote_addr": request.remote_addr,
                "user_agent": request.headers.get("User-Agent"),
                "forwarded_for": request.headers.get("X-Forwarded-For")
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/ip")
def ip_lookup():
    ip = request.args.get("ip", "").strip()
    provider = request.args.get("provider", "").strip().lower()

    if not ip:
        return jsonify({
            "success": False,
            "error": "Missing ip parameter"
        }), 400

    reverse_dns = get_reverse_dns(ip)

    try:
        if provider in ("", "ipinfo"):
            url = f"https://ipinfo.io/{quote(ip)}/json"
            params = {}
            if IPINFO_TOKEN and IPINFO_TOKEN != "YOUR_IPINFO_TOKEN":
                params["token"] = IPINFO_TOKEN

            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            provider_data = parse_ipinfo(r.json())

        elif provider == "ipapi":
            if not IPAPI_KEY or IPAPI_KEY == "YOUR_IPAPI_KEY":
                return jsonify({
                    "success": False,
                    "error": "IPAPI_KEY not configured"
                }), 500

            url = f"http://api.ipapi.com/{quote(ip)}"
            params = {"access_key": IPAPI_KEY}
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            provider_data = parse_ipapi(r.json())

        else:
            return jsonify({
                "success": False,
                "error": "Unsupported provider. Use ipinfo or ipapi"
            }), 400

        return jsonify({
            "success": True,
            "query": ip,
            "reverse_dns": reverse_dns,
            "request_meta": {
                "user_agent": request.headers.get("User-Agent"),
                "origin": request.headers.get("Origin"),
                "referer": request.headers.get("Referer")
            },
            "data": provider_data
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "query": ip,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
