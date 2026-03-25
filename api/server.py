#!/usr/bin/env python3
"""DevTools.fm API - Server-side tools backend.
Provides DNS lookup, SSL certificate check, HTTP header inspection,
WHOIS lookup, redirect chain tracing, and comprehensive website grading.
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
from html.parser import HTMLParser
import threading


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


# ---------------------------------------------------------------------------
# Website Grader - comprehensive site analysis
# ---------------------------------------------------------------------------

class SEOHTMLParser(HTMLParser):
    """Lightweight HTML parser to extract SEO-relevant tags."""

    def __init__(self):
        super().__init__()
        self.title = None
        self.meta_description = None
        self.has_h1 = False
        self.h1_count = 0
        self.has_canonical = False
        self.has_viewport = False
        self.has_robots_meta = False
        self.robots_content = None
        self.has_og_title = False
        self.has_og_description = False
        self.has_lang = False
        self.lang_value = None
        self.img_count = 0
        self.img_without_alt = 0
        self._in_title = False
        self._title_parts = []
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = {k.lower(): v for k, v in attrs}

        if tag == "html":
            lang = attrs_dict.get("lang", "")
            if lang:
                self.has_lang = True
                self.lang_value = lang

        if tag == "title":
            self._in_title = True
            self._title_parts = []

        if tag == "h1":
            self.has_h1 = True
            self.h1_count += 1
            self._in_h1 = True

        if tag == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")

            if name == "description":
                self.meta_description = content
            if name == "viewport":
                self.has_viewport = True
            if name == "robots":
                self.has_robots_meta = True
                self.robots_content = content
            if prop == "og:title":
                self.has_og_title = True
            if prop == "og:description":
                self.has_og_description = True

        if tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            if rel == "canonical":
                self.has_canonical = True

        if tag == "img":
            self.img_count += 1
            if not attrs_dict.get("alt"):
                self.img_without_alt += 1

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_parts).strip()
        if tag == "h1":
            self._in_h1 = False


def _score_to_grade(score):
    """Convert a numeric score (0-100) to a letter grade."""
    if score >= 97:
        return "A+"
    elif score >= 93:
        return "A"
    elif score >= 90:
        return "A-"
    elif score >= 87:
        return "B+"
    elif score >= 83:
        return "B"
    elif score >= 80:
        return "B-"
    elif score >= 77:
        return "C+"
    elif score >= 73:
        return "C"
    elif score >= 70:
        return "C-"
    elif score >= 67:
        return "D+"
    elif score >= 63:
        return "D"
    elif score >= 60:
        return "D-"
    else:
        return "F"


def _fetch_page(url, timeout=15):
    """Fetch a page and return (response_time_ms, status_code, headers_dict, body_text, final_url).
    Returns None tuple values on failure."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    start = time.time()
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent",
                        "Mozilla/5.0 (compatible; ZeroKit.dev WebsiteGrader/1.0; +https://zerokit.dev)")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = round((time.time() - start) * 1000)
            headers = {k: v for k, v in resp.headers.items()}
            body = resp.read(120000).decode("utf-8", errors="ignore")
            return elapsed_ms, resp.status, headers, body, resp.url
    except urllib.error.HTTPError as e:
        elapsed_ms = round((time.time() - start) * 1000)
        headers = {k: v for k, v in e.headers.items()} if e.headers else {}
        body = ""
        try:
            body = e.read(120000).decode("utf-8", errors="ignore")
        except Exception:
            pass
        return elapsed_ms, e.code, headers, body, url
    except Exception as e:
        elapsed_ms = round((time.time() - start) * 1000)
        return elapsed_ms, None, {}, "", url


def _check_https_redirect(url):
    """Check if HTTP version redirects to HTTPS."""
    parsed = urlparse(url if "://" in url else "https://" + url)
    hostname = parsed.hostname
    http_url = f"http://{hostname}/"

    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        req = urllib.request.Request(http_url, method="HEAD")
        req.add_header("User-Agent", "ZeroKit.dev WebsiteGrader/1.0")
        resp = opener.open(req, timeout=8)
        return {"redirects_to_https": False, "status": resp.status}
    except urllib.error.HTTPError as e:
        location = e.headers.get("Location", "") if e.headers else ""
        redirects = location.startswith("https://")
        return {"redirects_to_https": redirects, "status": e.code, "location": location}
    except Exception as e:
        return {"redirects_to_https": False, "error": str(e)}


def website_grade(url):
    """Run comprehensive website grading across multiple categories."""
    if not url:
        return {"error": "Missing URL"}

    # Normalise
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    if not hostname:
        return {"error": "Invalid URL"}

    # ------------------------------------------------------------------
    # 1. Fetch page (gives us response time, headers, body)
    # ------------------------------------------------------------------
    response_time_ms, status_code, headers, body, final_url = _fetch_page(url)

    site_down = status_code is None or status_code >= 500

    # ------------------------------------------------------------------
    # 2. SSL check (threaded for speed)
    # ------------------------------------------------------------------
    ssl_result = {}
    ssl_thread_result = [None]

    def _ssl_worker():
        ssl_thread_result[0] = ssl_check(hostname)

    ssl_thread = threading.Thread(target=_ssl_worker)
    ssl_thread.start()

    # ------------------------------------------------------------------
    # 3. HTTPS redirect check (threaded)
    # ------------------------------------------------------------------
    https_redirect_result = [None]

    def _https_worker():
        https_redirect_result[0] = _check_https_redirect(url)

    https_thread = threading.Thread(target=_https_worker)
    https_thread.start()

    # ------------------------------------------------------------------
    # 4. Parse HTML for SEO
    # ------------------------------------------------------------------
    seo_parser = SEOHTMLParser()
    try:
        seo_parser.feed(body)
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Wait for threaded checks
    # ------------------------------------------------------------------
    ssl_thread.join(timeout=12)
    https_thread.join(timeout=12)
    ssl_result = ssl_thread_result[0] or {"valid": False, "error": "SSL check timed out"}
    https_redirect = https_redirect_result[0] or {"redirects_to_https": False, "error": "Check timed out"}

    # ------------------------------------------------------------------
    # CATEGORY 1: Performance (20%)
    # ------------------------------------------------------------------
    if response_time_ms is not None and not site_down:
        if response_time_ms < 200:
            perf_score = 100
        elif response_time_ms < 500:
            perf_score = 90
        elif response_time_ms < 1000:
            perf_score = 75
        elif response_time_ms < 2000:
            perf_score = 60
        elif response_time_ms < 3000:
            perf_score = 40
        else:
            perf_score = 20
    else:
        perf_score = 0

    perf_details = {
        "response_time_ms": response_time_ms,
        "status_code": status_code,
    }

    # ------------------------------------------------------------------
    # CATEGORY 2: Security Headers (25%)
    # ------------------------------------------------------------------
    SECURITY_HEADERS = [
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "X-XSS-Protection",
    ]

    # Normalise header lookup (case-insensitive)
    headers_lower = {k.lower(): v for k, v in headers.items()}

    sec_present = {}
    sec_missing = []
    for h in SECURITY_HEADERS:
        val = headers_lower.get(h.lower())
        if val:
            sec_present[h] = val
        else:
            sec_missing.append(h)

    total_sec_headers = len(SECURITY_HEADERS)
    found_sec = len(sec_present)
    sec_score = round((found_sec / total_sec_headers) * 100) if total_sec_headers else 0

    sec_details = {
        "headers_present": sec_present,
        "headers_missing": sec_missing,
        "found": found_sec,
        "total": total_sec_headers,
    }

    # ------------------------------------------------------------------
    # CATEGORY 3: SSL / HTTPS (20%)
    # ------------------------------------------------------------------
    ssl_score = 0
    ssl_details = {}

    ssl_valid = ssl_result.get("valid", False)
    if ssl_valid:
        ssl_score += 50  # Valid cert = 50 points

        # Check expiry - bonus points for long validity
        not_after = ssl_result.get("not_after", "")
        days_remaining = None
        if not_after:
            try:
                expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                now = datetime.utcnow()
                days_remaining = (expiry - now).days
                if days_remaining > 30:
                    ssl_score += 20
                elif days_remaining > 7:
                    ssl_score += 10
                # else near-expiry, no bonus
            except Exception:
                ssl_score += 10  # Can't parse but cert is valid

        # Check cipher strength
        cipher_info = ssl_result.get("cipher", {})
        bits = cipher_info.get("bits")
        if bits and bits >= 256:
            ssl_score += 10
        elif bits and bits >= 128:
            ssl_score += 5

        ssl_details["valid"] = True
        ssl_details["days_remaining"] = days_remaining
        ssl_details["cipher"] = cipher_info
        ssl_details["issuer"] = ssl_result.get("issuer", {})
    else:
        ssl_details["valid"] = False
        ssl_details["error"] = ssl_result.get("error", "Unknown SSL error")

    # HTTPS redirect bonus
    if https_redirect.get("redirects_to_https"):
        ssl_score += 20
        ssl_details["https_redirect"] = True
    else:
        ssl_details["https_redirect"] = False

    ssl_score = min(100, ssl_score)

    # ------------------------------------------------------------------
    # CATEGORY 4: SEO Basics (20%)
    # ------------------------------------------------------------------
    seo_checks = {}
    seo_score = 0
    seo_max = 0

    # Title tag (15 pts)
    seo_max += 15
    if seo_parser.title:
        title_len = len(seo_parser.title)
        if 10 <= title_len <= 70:
            seo_score += 15
            seo_checks["title"] = {"present": True, "value": seo_parser.title[:100], "length": title_len, "optimal": True}
        else:
            seo_score += 8
            seo_checks["title"] = {"present": True, "value": seo_parser.title[:100], "length": title_len, "optimal": False,
                                    "note": "Title should be 10-70 characters"}
    else:
        seo_checks["title"] = {"present": False}

    # Meta description (15 pts)
    seo_max += 15
    if seo_parser.meta_description:
        desc_len = len(seo_parser.meta_description)
        if 50 <= desc_len <= 160:
            seo_score += 15
            seo_checks["meta_description"] = {"present": True, "length": desc_len, "optimal": True}
        else:
            seo_score += 8
            seo_checks["meta_description"] = {"present": True, "length": desc_len, "optimal": False,
                                                "note": "Description should be 50-160 characters"}
    else:
        seo_checks["meta_description"] = {"present": False}

    # H1 tag (15 pts)
    seo_max += 15
    if seo_parser.has_h1:
        if seo_parser.h1_count == 1:
            seo_score += 15
            seo_checks["h1"] = {"present": True, "count": 1, "optimal": True}
        else:
            seo_score += 8
            seo_checks["h1"] = {"present": True, "count": seo_parser.h1_count, "optimal": False,
                                 "note": f"Found {seo_parser.h1_count} H1 tags, should have exactly 1"}
    else:
        seo_checks["h1"] = {"present": False}

    # Canonical URL (10 pts)
    seo_max += 10
    if seo_parser.has_canonical:
        seo_score += 10
        seo_checks["canonical"] = {"present": True}
    else:
        seo_checks["canonical"] = {"present": False}

    # Viewport meta (10 pts)
    seo_max += 10
    if seo_parser.has_viewport:
        seo_score += 10
        seo_checks["viewport"] = {"present": True}
    else:
        seo_checks["viewport"] = {"present": False}

    # Lang attribute (10 pts)
    seo_max += 10
    if seo_parser.has_lang:
        seo_score += 10
        seo_checks["lang_attribute"] = {"present": True, "value": seo_parser.lang_value}
    else:
        seo_checks["lang_attribute"] = {"present": False}

    # Open Graph tags (10 pts)
    seo_max += 10
    if seo_parser.has_og_title and seo_parser.has_og_description:
        seo_score += 10
        seo_checks["open_graph"] = {"present": True}
    elif seo_parser.has_og_title or seo_parser.has_og_description:
        seo_score += 5
        seo_checks["open_graph"] = {"partial": True, "note": "Missing og:title or og:description"}
    else:
        seo_checks["open_graph"] = {"present": False}

    # Image alt tags (15 pts)
    seo_max += 15
    if seo_parser.img_count > 0:
        alt_ratio = 1 - (seo_parser.img_without_alt / seo_parser.img_count)
        img_score = round(alt_ratio * 15)
        seo_score += img_score
        seo_checks["image_alt_tags"] = {
            "total_images": seo_parser.img_count,
            "missing_alt": seo_parser.img_without_alt,
            "coverage": f"{round(alt_ratio * 100)}%",
        }
    else:
        seo_score += 15  # No images = no issue
        seo_checks["image_alt_tags"] = {"total_images": 0, "note": "No images found"}

    seo_score_pct = round((seo_score / seo_max) * 100) if seo_max else 0

    # ------------------------------------------------------------------
    # CATEGORY 5: Availability (15%)
    # ------------------------------------------------------------------
    if site_down:
        avail_score = 0
    elif status_code and 200 <= status_code < 300:
        avail_score = 100
    elif status_code and 300 <= status_code < 400:
        avail_score = 90  # Redirect — acceptable
    elif status_code and 400 <= status_code < 500:
        avail_score = 30  # Client error
    else:
        avail_score = 0

    avail_details = {
        "status_code": status_code,
        "response_time_ms": response_time_ms,
        "is_up": not site_down,
        "final_url": final_url,
    }

    # ------------------------------------------------------------------
    # OVERALL SCORE (weighted)
    # ------------------------------------------------------------------
    overall_score = round(
        perf_score * 0.20 +
        sec_score * 0.25 +
        ssl_score * 0.20 +
        seo_score_pct * 0.20 +
        avail_score * 0.15
    )
    overall_grade = _score_to_grade(overall_score)

    # ------------------------------------------------------------------
    # RECOMMENDATIONS
    # ------------------------------------------------------------------
    recommendations = []

    # Performance recs
    if response_time_ms and response_time_ms > 1000:
        recommendations.append("Improve server response time (currently {0}ms, aim for under 500ms)".format(response_time_ms))
    if response_time_ms and response_time_ms > 3000:
        recommendations.append("Critical: Response time over 3 seconds will cause users to leave")

    # Security recs
    if "Strict-Transport-Security" in sec_missing:
        recommendations.append("Add Strict-Transport-Security (HSTS) header to enforce HTTPS")
    if "Content-Security-Policy" in sec_missing:
        recommendations.append("Add Content-Security-Policy header to prevent XSS and injection attacks")
    if "X-Frame-Options" in sec_missing:
        recommendations.append("Add X-Frame-Options header to prevent clickjacking")
    if "X-Content-Type-Options" in sec_missing:
        recommendations.append("Add X-Content-Type-Options: nosniff to prevent MIME-type sniffing")
    if "Referrer-Policy" in sec_missing:
        recommendations.append("Add Referrer-Policy header to control referrer information")
    if "Permissions-Policy" in sec_missing:
        recommendations.append("Add Permissions-Policy header to control browser features")

    # SSL recs
    if not ssl_valid:
        recommendations.append("Fix SSL certificate - your site is not secure for visitors")
    elif ssl_details.get("days_remaining") is not None and ssl_details["days_remaining"] < 30:
        recommendations.append("SSL certificate expires in {0} days - renew soon".format(ssl_details["days_remaining"]))
    if not https_redirect.get("redirects_to_https"):
        recommendations.append("Set up HTTP to HTTPS redirect to ensure all traffic is encrypted")

    # SEO recs
    if not seo_parser.title:
        recommendations.append("Add a <title> tag - essential for search engine rankings")
    elif seo_parser.title and (len(seo_parser.title) < 10 or len(seo_parser.title) > 70):
        recommendations.append("Optimize title tag length (currently {0} chars, aim for 10-70)".format(len(seo_parser.title)))
    if not seo_parser.meta_description:
        recommendations.append("Add a meta description - improves click-through rates from search results")
    if not seo_parser.has_h1:
        recommendations.append("Add an H1 heading - important for SEO and accessibility")
    elif seo_parser.h1_count > 1:
        recommendations.append("Use only one H1 tag per page (found {0})".format(seo_parser.h1_count))
    if not seo_parser.has_canonical:
        recommendations.append("Add a canonical URL to prevent duplicate content issues")
    if not seo_parser.has_viewport:
        recommendations.append("Add a viewport meta tag for mobile responsiveness")
    if not seo_parser.has_lang:
        recommendations.append("Add a lang attribute to the <html> tag for accessibility and SEO")
    if not (seo_parser.has_og_title and seo_parser.has_og_description):
        recommendations.append("Add Open Graph meta tags (og:title, og:description) for better social sharing")
    if seo_parser.img_count > 0 and seo_parser.img_without_alt > 0:
        recommendations.append("Add alt text to {0} image(s) for accessibility and SEO".format(seo_parser.img_without_alt))

    # Availability recs
    if site_down:
        recommendations.append("Your website appears to be down - check your server immediately")

    # ------------------------------------------------------------------
    # Build response
    # ------------------------------------------------------------------
    # Detect technologies from headers
    tech_hints = []
    server_header = headers_lower.get("server", "")
    if server_header:
        tech_hints.append({"name": server_header, "category": "Server"})
    powered_by = headers_lower.get("x-powered-by", "")
    if powered_by:
        tech_hints.append({"name": powered_by, "category": "Framework"})

    return {
        "url": url,
        "final_url": final_url,
        "hostname": hostname,
        "grade": overall_grade,
        "score": overall_score,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "categories": {
            "performance": {
                "score": perf_score,
                "grade": _score_to_grade(perf_score),
                "weight": "20%",
                "details": perf_details,
            },
            "security": {
                "score": sec_score,
                "grade": _score_to_grade(sec_score),
                "weight": "25%",
                "details": sec_details,
            },
            "ssl": {
                "score": ssl_score,
                "grade": _score_to_grade(ssl_score),
                "weight": "20%",
                "details": ssl_details,
            },
            "seo": {
                "score": seo_score_pct,
                "grade": _score_to_grade(seo_score_pct),
                "weight": "20%",
                "details": seo_checks,
            },
            "availability": {
                "score": avail_score,
                "grade": _score_to_grade(avail_score),
                "weight": "15%",
                "details": avail_details,
            },
        },
        "recommendations": recommendations,
        "technologies": tech_hints,
    }


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

        elif path == "/api/grade":
            url = params.get("url", [None])[0]
            if not url:
                self.send_json({"error": "Missing 'url' parameter"}, 400)
                return
            if len(url) > 2000:
                self.send_json({"error": "URL too long"}, 400)
                return
            result = website_grade(url)
            self.send_json(result)

        elif path == "/api/health":
            self.send_json({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

        else:
            self.send_json({"error": "Not found", "endpoints": ["/api/dns", "/api/ssl", "/api/headers", "/api/whois", "/api/redirect", "/api/status", "/api/email-validate", "/api/tech-detect", "/api/grade", "/api/health"]}, 404)


if __name__ == "__main__":
    PORT = 8080
    server = http.server.HTTPServer(("127.0.0.1", PORT), APIHandler)
    print(f"DevTools.fm API running on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
