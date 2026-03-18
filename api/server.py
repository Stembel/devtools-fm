#!/usr/bin/env python3
"""DevTools.fm API - Server-side tools backend.
Provides DNS lookup, SSL certificate check, and HTTP header inspection.
Runs on port 8080, Caddy reverse-proxies /api/ to here.
"""

import json
import socket
import ssl
import http.server
import urllib.request
import urllib.error
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs


def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }


def dns_lookup(domain):
    """Resolve DNS records for a domain."""
    results = {}
    try:
        # A records
        ips = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
        results["A"] = list(set(addr[4][0] for addr in ips))
    except socket.gaierror:
        results["A"] = []

    try:
        # AAAA records
        ips6 = socket.getaddrinfo(domain, None, socket.AF_INET6, socket.SOCK_STREAM)
        results["AAAA"] = list(set(addr[4][0] for addr in ips6))
    except socket.gaierror:
        results["AAAA"] = []

    try:
        # Reverse DNS for first A record
        if results["A"]:
            hostname, _, _ = socket.gethostbyaddr(results["A"][0])
            results["PTR"] = hostname
    except (socket.herror, socket.gaierror):
        results["PTR"] = None

    try:
        # MX-like: get mail server hint via getaddrinfo
        mx_info = socket.getaddrinfo(f"mail.{domain}", 25, socket.AF_INET, socket.SOCK_STREAM)
        results["mail_hint"] = list(set(addr[4][0] for addr in mx_info))[:3]
    except socket.gaierror:
        results["mail_hint"] = []

    return {"domain": domain, "records": results}


def ssl_check(hostname, port=443):
    """Check SSL certificate for a hostname."""
    ctx = ssl.create_default_context()
    try:
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(5)
            s.connect((hostname, port))
            cert = s.getpeercert()
            cipher = s.cipher()

        subject = dict(x[0] for x in cert.get("subject", ()))
        issuer = dict(x[0] for x in cert.get("issuer", ()))
        san = [entry[1] for entry in cert.get("subjectAltName", ())]

        not_before = cert.get("notBefore", "")
        not_after = cert.get("notAfter", "")

        return {
            "hostname": hostname,
            "valid": True,
            "subject": subject,
            "issuer": issuer,
            "san": san[:20],
            "not_before": not_before,
            "not_after": not_after,
            "serial": cert.get("serialNumber", ""),
            "version": cert.get("version", ""),
            "cipher": {
                "name": cipher[0] if cipher else None,
                "protocol": cipher[1] if cipher else None,
                "bits": cipher[2] if cipher else None,
            },
        }
    except ssl.SSLCertVerificationError as e:
        return {"hostname": hostname, "valid": False, "error": str(e)}
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return {"hostname": hostname, "valid": False, "error": f"Connection failed: {e}"}


def http_headers(url):
    """Fetch HTTP headers for a URL."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "DevTools.fm Header Checker/1.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            headers = dict(resp.headers)
            return {
                "url": url,
                "status": resp.status,
                "headers": headers,
                "redirect_url": resp.url if resp.url != url else None,
            }
    except urllib.error.HTTPError as e:
        return {
            "url": url,
            "status": e.code,
            "headers": dict(e.headers) if e.headers else {},
            "error": str(e.reason),
        }
    except Exception as e:
        return {"url": url, "error": str(e)}


def sanitize_domain(raw):
    """Extract and validate domain from user input."""
    if not raw:
        return None
    raw = raw.strip().lower()
    # Remove protocol if present
    if "://" in raw:
        raw = urlparse(raw).hostname or raw
    # Remove path/query
    raw = raw.split("/")[0].split("?")[0].split("#")[0]
    # Basic validation
    if not raw or len(raw) > 253:
        return None
    if not all(c.isalnum() or c in ".-" for c in raw):
        return None
    return raw


class APIHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if path == "/api/dns":
            domain = sanitize_domain(params.get("domain", [None])[0])
            if not domain:
                self.send_json({"error": "Missing or invalid 'domain' parameter"}, 400)
                return
            result = dns_lookup(domain)
            self.send_json(result)

        elif path == "/api/ssl":
            hostname = sanitize_domain(params.get("domain", [None])[0])
            if not hostname:
                self.send_json({"error": "Missing or invalid 'domain' parameter"}, 400)
                return
            result = ssl_check(hostname)
            self.send_json(result)

        elif path == "/api/headers":
            url = params.get("url", [None])[0]
            if not url:
                self.send_json({"error": "Missing 'url' parameter"}, 400)
                return
            # Limit URL length
            if len(url) > 2000:
                self.send_json({"error": "URL too long"}, 400)
                return
            result = http_headers(url)
            self.send_json(result)

        elif path == "/api/health":
            self.send_json({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

        else:
            self.send_json({"error": "Not found", "endpoints": ["/api/dns", "/api/ssl", "/api/headers", "/api/health"]}, 404)


if __name__ == "__main__":
    PORT = 8080
    server = http.server.HTTPServer(("127.0.0.1", PORT), APIHandler)
    print(f"DevTools.fm API running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
