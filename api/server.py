#!/usr/bin/env python3
"""DevTools.fm API - Server-side tools backend.
Provides DNS lookup, SSL certificate check, HTTP header inspection,
WHOIS lookup, and redirect chain tracing.
Runs on port 8080, Caddy reverse-proxies /api/ to here.
"""

import json
import re
import socket
import ssl
import subprocess
import time
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


def whois_lookup(domain):
    """Run WHOIS lookup for a domain."""
    try:
        result = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=15
        )
        raw = result.stdout
        if not raw.strip():
            return {"domain": domain, "error": "No WHOIS data returned"}

        # Parse key fields
        parsed = {}
        field_map = {
            "domain name": "domain_name",
            "registrar": "registrar",
            "creation date": "created",
            "updated date": "updated",
            "registry expiry date": "expires",
            "registrar whois server": "whois_server",
            "name server": "nameservers",
            "registrant organization": "registrant_org",
            "registrant country": "registrant_country",
            "registrant state/province": "registrant_state",
            "dnssec": "dnssec",
        }
        nameservers = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("%") or line.startswith("#"):
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                key_lower = key.strip().lower()
                val = val.strip()
                if key_lower in field_map:
                    field = field_map[key_lower]
                    if field == "nameservers":
                        nameservers.append(val.lower())
                    else:
                        parsed[field] = val
        if nameservers:
            parsed["nameservers"] = list(set(nameservers))

        return {"domain": domain, "parsed": parsed, "raw": raw[:4000]}
    except subprocess.TimeoutExpired:
        return {"domain": domain, "error": "WHOIS lookup timed out"}
    except FileNotFoundError:
        return {"domain": domain, "error": "whois command not found on server"}
    except Exception as e:
        return {"domain": domain, "error": str(e)}


def redirect_trace(url, max_redirects=10):
    """Follow HTTP redirects and return the full chain."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    chain = []
    current_url = url

    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # Don't follow redirects automatically

    opener = urllib.request.build_opener(NoRedirectHandler)

    for i in range(max_redirects):
        try:
            req = urllib.request.Request(current_url, method="GET")
            req.add_header("User-Agent", "DevTools.fm Redirect Checker/1.0")
            resp = opener.open(req, timeout=10)
            chain.append({
                "step": i + 1,
                "url": current_url,
                "status": resp.status,
                "status_text": "OK",
                "headers": {k: v for k, v in list(resp.headers.items())[:20]},
            })
            break  # No redirect, we're done
        except urllib.error.HTTPError as e:
            location = e.headers.get("Location", "")
            chain.append({
                "step": i + 1,
                "url": current_url,
                "status": e.code,
                "status_text": str(e.reason),
                "location": location,
                "headers": {k: v for k, v in list(e.headers.items())[:20]},
            })
            if e.code in (301, 302, 303, 307, 308) and location:
                # Resolve relative URLs
                if location.startswith("/"):
                    p = urlparse(current_url)
                    location = f"{p.scheme}://{p.netloc}{location}"
                current_url = location
            else:
                break
        except Exception as e:
            chain.append({
                "step": i + 1,
                "url": current_url,
                "error": str(e),
            })
            break

    return {
        "original_url": url,
        "final_url": current_url,
        "total_redirects": len(chain) - 1 if len(chain) > 1 else 0,
        "chain": chain,
    }


def website_status(url):
    """Check if a website is up and measure response time."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    start = time.time()
    try:
        hostname = urlparse(url).hostname
        ip = socket.gethostbyname(hostname) if hostname else None
    except socket.gaierror:
        ip = None

    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "DevTools.fm Status Checker/1.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = time.time() - start
            return {
                "url": url,
                "status": "up",
                "status_code": resp.status,
                "response_time_ms": round(elapsed * 1000),
                "ip": ip,
                "server": resp.headers.get("Server", ""),
                "content_type": resp.headers.get("Content-Type", ""),
            }
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start
        return {
            "url": url,
            "status": "up" if e.code < 500 else "error",
            "status_code": e.code,
            "response_time_ms": round(elapsed * 1000),
            "ip": ip,
            "reason": str(e.reason),
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "url": url,
            "status": "down",
            "response_time_ms": round(elapsed * 1000),
            "ip": ip,
            "error": str(e),
        }


def email_validate(email):
    """Validate email address - syntax check + MX record lookup."""
    email = email.strip().lower()

    # Syntax check
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return {"email": email, "valid": False, "reason": "Invalid email syntax"}

    _, domain = email.rsplit("@", 1)

    # MX record check
    try:
        result = subprocess.run(
            ["dig", "+short", "MX", domain],
            capture_output=True, text=True, timeout=10
        )
        mx_lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        mx_records = []
        for line in mx_lines:
            parts = line.split()
            if len(parts) >= 2:
                mx_records.append({"priority": int(parts[0]), "server": parts[1].rstrip(".")})

        if not mx_records:
            # Fallback: check A record
            a_result = subprocess.run(
                ["dig", "+short", "A", domain],
                capture_output=True, text=True, timeout=10
            )
            a_records = [l.strip() for l in a_result.stdout.strip().split("\n") if l.strip()]
            if not a_records:
                return {"email": email, "valid": False, "domain": domain,
                        "reason": "Domain has no MX or A records - cannot receive email",
                        "mx_records": [], "a_records": []}
            return {"email": email, "valid": True, "domain": domain,
                    "mx_records": [], "a_records": a_records,
                    "note": "No MX records but domain has A records (may accept mail)"}

        return {"email": email, "valid": True, "domain": domain, "mx_records": mx_records}
    except subprocess.TimeoutExpired:
        return {"email": email, "domain": domain, "error": "DNS lookup timed out"}
    except Exception as e:
        return {"email": email, "domain": domain, "error": str(e)}


def tech_detect(url):
    """Detect web technologies from response headers and HTML content."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "DevTools.fm Tech Detector/1.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            headers = dict(resp.headers)
            body = resp.read(60000).decode("utf-8", errors="ignore")

            techs = []

            # Server
            server = headers.get("Server", "")
            if server:
                techs.append({"name": server, "category": "Server", "source": "Server header"})

            # Framework
            powered_by = headers.get("X-Powered-By", "")
            if powered_by:
                techs.append({"name": powered_by, "category": "Framework", "source": "X-Powered-By header"})

            # CDN / Platform
            if headers.get("CF-Ray"):
                techs.append({"name": "Cloudflare", "category": "CDN", "source": "CF-Ray header"})
            if headers.get("X-Vercel-Id") or headers.get("X-Vercel-Cache"):
                techs.append({"name": "Vercel", "category": "Platform", "source": "X-Vercel header"})
            if headers.get("X-Amz-Cf-Id") or headers.get("X-Amz-Cf-Pop"):
                techs.append({"name": "Amazon CloudFront", "category": "CDN", "source": "CloudFront header"})
            if "netlify" in headers.get("Server", "").lower() or headers.get("X-NF-Request-ID"):
                techs.append({"name": "Netlify", "category": "Platform", "source": "Netlify header"})
            if headers.get("X-GitHub-Request-Id"):
                techs.append({"name": "GitHub Pages", "category": "Platform", "source": "GitHub header"})
            if headers.get("Fly-Request-Id"):
                techs.append({"name": "Fly.io", "category": "Platform", "source": "Fly header"})

            # CMS from HTML
            if "wp-content" in body or "wp-includes" in body:
                techs.append({"name": "WordPress", "category": "CMS", "source": "HTML content"})
            if "Drupal.settings" in body or "drupal.js" in body:
                techs.append({"name": "Drupal", "category": "CMS", "source": "HTML content"})
            if "Joomla" in body or "/media/jui/" in body:
                techs.append({"name": "Joomla", "category": "CMS", "source": "HTML content"})
            if "shopify" in body.lower() and ("cdn.shopify.com" in body or "Shopify.theme" in body):
                techs.append({"name": "Shopify", "category": "E-Commerce", "source": "HTML content"})

            # JS Frameworks
            if '="__next' in body or "__NEXT_DATA__" in body:
                techs.append({"name": "Next.js", "category": "Framework", "source": "HTML content"})
            if "__NUXT__" in body or "/_nuxt/" in body:
                techs.append({"name": "Nuxt.js", "category": "Framework", "source": "HTML content"})
            if "data-reactroot" in body or "_reactListening" in body:
                techs.append({"name": "React", "category": "Library", "source": "HTML content"})
            if "ng-version" in body or "ng-app" in body:
                techs.append({"name": "Angular", "category": "Framework", "source": "HTML content"})
            if "__vue" in body or "data-v-" in body:
                techs.append({"name": "Vue.js", "category": "Framework", "source": "HTML content"})
            if "__svelte" in body or "svelte-" in body:
                techs.append({"name": "Svelte", "category": "Framework", "source": "HTML content"})
            if "gatsby" in body.lower() and ("gatsby-" in body or "___gatsby" in body):
                techs.append({"name": "Gatsby", "category": "Framework", "source": "HTML content"})

            # Analytics
            if "google-analytics.com" in body or "gtag(" in body or "googletagmanager.com" in body:
                techs.append({"name": "Google Analytics", "category": "Analytics", "source": "HTML content"})
            if "hotjar.com" in body:
                techs.append({"name": "Hotjar", "category": "Analytics", "source": "HTML content"})
            if "plausible.io" in body:
                techs.append({"name": "Plausible", "category": "Analytics", "source": "HTML content"})
            if "clarity.ms" in body:
                techs.append({"name": "Microsoft Clarity", "category": "Analytics", "source": "HTML content"})

            # CSS Frameworks
            if "tailwindcss" in body.lower() or "tailwind" in body.lower():
                techs.append({"name": "Tailwind CSS", "category": "CSS Framework", "source": "HTML content"})
            if "bootstrap" in body.lower() and ("bootstrap.min" in body or "bootstrap.css" in body):
                techs.append({"name": "Bootstrap", "category": "CSS Framework", "source": "HTML content"})

            # Security headers
            security = {}
            for h in ["Strict-Transport-Security", "Content-Security-Policy",
                       "X-Frame-Options", "X-Content-Type-Options", "X-XSS-Protection",
                       "Permissions-Policy", "Referrer-Policy"]:
                if headers.get(h):
                    security[h] = headers[h]

            return {
                "url": url,
                "technologies": techs,
                "security_headers": security,
                "total_detected": len(techs),
            }
    except urllib.error.HTTPError as e:
        return {"url": url, "error": f"HTTP {e.code}: {e.reason}"}
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

        elif path == "/api/whois":
            domain = sanitize_domain(params.get("domain", [None])[0])
            if not domain:
                self.send_json({"error": "Missing or invalid 'domain' parameter"}, 400)
                return
            result = whois_lookup(domain)
            self.send_json(result)

        elif path == "/api/redirect":
            url = params.get("url", [None])[0]
            if not url:
                self.send_json({"error": "Missing 'url' parameter"}, 400)
                return
            if len(url) > 2000:
                self.send_json({"error": "URL too long"}, 400)
                return
            result = redirect_trace(url)
            self.send_json(result)

        elif path == "/api/status":
            url = params.get("url", [None])[0]
            if not url:
                self.send_json({"error": "Missing 'url' parameter"}, 400)
                return
            if len(url) > 2000:
                self.send_json({"error": "URL too long"}, 400)
                return
            result = website_status(url)
            self.send_json(result)

        elif path == "/api/email-validate":
            email = params.get("email", [None])[0]
            if not email:
                self.send_json({"error": "Missing 'email' parameter"}, 400)
                return
            if len(email) > 320:
                self.send_json({"error": "Email too long"}, 400)
                return
            result = email_validate(email)
            self.send_json(result)

        elif path == "/api/tech-detect":
            url = params.get("url", [None])[0]
            if not url:
                self.send_json({"error": "Missing 'url' parameter"}, 400)
                return
            if len(url) > 2000:
                self.send_json({"error": "URL too long"}, 400)
                return
            result = tech_detect(url)
            self.send_json(result)

        elif path == "/api/health":
            self.send_json({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

        else:
            self.send_json({"error": "Not found", "endpoints": ["/api/dns", "/api/ssl", "/api/headers", "/api/whois", "/api/redirect", "/api/status", "/api/email-validate", "/api/tech-detect", "/api/health"]}, 404)


if __name__ == "__main__":
    PORT = 8080
    server = http.server.HTTPServer(("127.0.0.1", PORT), APIHandler)
    print(f"DevTools.fm API running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
