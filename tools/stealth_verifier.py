#!/usr/bin/env python3
"""
stealth_verifier.py — Проверка невидимости инфраструктуры.

Сканирует собственные сервисы с точки зрения атакующего:
  - Открытые порты
  - Утечки заголовков (Server, X-Powered-By)
  - Fingerprinting через timing-анализ
  - TLS-конфигурация

Usage:
    python tools/stealth_verifier.py --target 127.0.0.1 --ports 80,443,8000,8080
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import ssl
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [STEALTH] %(message)s")
logger = logging.getLogger("stealth_verifier")

LEAK_HEADERS = [
    "server",
    "x-powered-by",
    "x-aspnet-version",
    "x-generator",
    "x-drupal-cache",
    "x-runtime",
    "via",
]


@dataclass
class PortResult:
    port: int
    state: str  # open | closed | filtered
    service_banner: str = ""
    response_time_ms: float = 0.0


@dataclass
class HeaderAuditResult:
    url: str
    leaked_headers: dict = field(default_factory=dict)
    missing_security_headers: list = field(default_factory=list)
    score: float = 0.0  # 0 = fully exposed, 100 = fully stealth


@dataclass
class TLSResult:
    port: int
    protocol: str = ""
    cipher: str = ""
    cert_cn: str = ""
    cert_expired: bool = False
    supports_tls13: bool = False


@dataclass
class StealthReport:
    target: str
    timestamp: str = ""
    port_scan: list = field(default_factory=list)
    header_audits: list = field(default_factory=list)
    tls_checks: list = field(default_factory=list)
    overall_score: float = 0.0
    verdict: str = ""


def scan_port(host: str, port: int, timeout: float = 2.0) -> PortResult:
    """TCP connect scan with banner grab."""
    start = time.monotonic()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        elapsed = (time.monotonic() - start) * 1000
        banner = ""
        try:
            sock.settimeout(1.0)
            banner = sock.recv(1024).decode("utf-8", errors="replace").strip()[:200]
        except (socket.timeout, OSError):
            pass
        finally:
            sock.close()
        return PortResult(port=port, state="open", service_banner=banner, response_time_ms=round(elapsed, 2))
    except (ConnectionRefusedError, OSError):
        elapsed = (time.monotonic() - start) * 1000
        return PortResult(port=port, state="closed", response_time_ms=round(elapsed, 2))
    except socket.timeout:
        return PortResult(port=port, state="filtered", response_time_ms=timeout * 1000)


def audit_http_headers(url: str, timeout: float = 5.0) -> HeaderAuditResult:
    """Check response headers for information leakage."""
    result = HeaderAuditResult(url=url)
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True, verify=False)
        headers_lower = {k.lower(): v for k, v in resp.headers.items()}

        for h in LEAK_HEADERS:
            if h in headers_lower:
                result.leaked_headers[h] = headers_lower[h]

        required_security = [
            "x-content-type-options",
            "x-frame-options",
            "content-security-policy",
            "referrer-policy",
            "permissions-policy",
        ]
        for h in required_security:
            if h not in headers_lower:
                result.missing_security_headers.append(h)

        # Score: 100 - penalties
        penalties = len(result.leaked_headers) * 15 + len(result.missing_security_headers) * 10
        result.score = max(0.0, 100.0 - penalties)

    except Exception as e:
        logger.warning("HTTP audit failed for %s: %s", url, e)
        result.score = -1  # unreachable

    return result


def check_tls(host: str, port: int = 443) -> Optional[TLSResult]:
    """Inspect TLS configuration."""
    result = TLSResult(port=port)
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.create_connection((host, port), timeout=3), server_hostname=host) as s:
            result.protocol = s.version() or "unknown"
            cipher_info = s.cipher()
            result.cipher = cipher_info[0] if cipher_info else "unknown"
            cert = s.getpeercert()
            if cert:
                subject = dict(x[0] for x in cert.get("subject", ()))
                result.cert_cn = subject.get("commonName", "")
            result.supports_tls13 = "TLSv1.3" in (result.protocol or "")
        return result
    except Exception as e:
        logger.warning("TLS check failed for %s:%d: %s", host, port, e)
        return None


def run_stealth_audit(target: str, ports: list[int]) -> StealthReport:
    """Full stealth audit pipeline."""
    report = StealthReport(target=target, timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"))

    # 1. Port scan
    logger.info("Сканирование портов %s...", target)
    for port in ports:
        result = scan_port(target, port)
        report.port_scan.append(asdict(result))
        if result.state == "open":
            logger.info("  Порт %d: OPEN (%.1fms) banner=%s", port, result.response_time_ms, result.service_banner or "—")
        else:
            logger.info("  Порт %d: %s", port, result.state)

    # 2. HTTP header audit on open ports
    open_ports = [r["port"] for r in report.port_scan if r["state"] == "open"]
    for port in open_ports:
        scheme = "https" if port in (443, 8443) else "http"
        url = f"{scheme}://{target}:{port}/"
        audit = audit_http_headers(url)
        report.header_audits.append(asdict(audit))

    # 3. TLS check on 443/8443
    for port in [p for p in open_ports if p in (443, 8443)]:
        tls = check_tls(target, port)
        if tls:
            report.tls_checks.append(asdict(tls))

    # 4. Overall score
    scores = [a["score"] for a in report.header_audits if a["score"] >= 0]
    report.overall_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    if report.overall_score >= 90:
        report.verdict = "STEALTH: Инфраструктура хорошо замаскирована"
    elif report.overall_score >= 60:
        report.verdict = "PARTIAL: Обнаружены утечки заголовков"
    else:
        report.verdict = "EXPOSED: Инфраструктура видна, требуется маскировка"

    return report



def timing_analysis(host: str, port: int, samples: int = 10) -> dict:
    """Detect service fingerprinting via response time variance."""
    times = []
    for _ in range(samples):
        start = time.monotonic()
        try:
            sock = socket.create_connection((host, port), timeout=2)
            sock.close()
        except Exception:
            pass
        elapsed = (time.monotonic() - start) * 1000
        times.append(elapsed)
        time.sleep(0.1)

    if not times:
        return {"port": port, "avg_ms": 0, "std_ms": 0, "fingerprintable": False}

    avg = sum(times) / len(times)
    variance = sum((t - avg) ** 2 for t in times) / len(times)
    std = variance ** 0.5

    return {
        "port": port,
        "avg_ms": round(avg, 2),
        "std_ms": round(std, 2),
        "samples": samples,
        "fingerprintable": std < 5.0,  # Low variance = consistent = fingerprintable
    }


def check_dns_leaks(host: str) -> dict:
    """Check if DNS reveals internal infrastructure."""
    import socket as _sock
    result = {"host": host, "leaks": []}
    try:
        fqdn = _sock.getfqdn(host)
        if fqdn != host and "internal" in fqdn.lower():
            result["leaks"].append(f"FQDN reveals internal name: {fqdn}")
        
        # Reverse DNS
        try:
            reverse = _sock.gethostbyaddr(host)
            if reverse[0] and reverse[0] != host:
                hostname = reverse[0]
                # Check for revealing hostnames
                revealing_keywords = ["prod", "staging", "db", "redis", "api", "admin"]
                for kw in revealing_keywords:
                    if kw in hostname.lower():
                        result["leaks"].append(f"Reverse DNS reveals role: {hostname}")
                        break
        except _sock.herror:
            pass
    except Exception as e:
        logger.debug("DNS check error: %s", e)

    return result



def main():
    parser = argparse.ArgumentParser(description="Infrastructure stealth verifier")
    parser.add_argument("--target", required=True, help="Target IP or hostname")
    parser.add_argument("--ports", default="80,443,8000,8080,3000,5000", help="Comma-separated ports")
    parser.add_argument("--output", default="/tmp/stealth_report.json", help="Output JSON path")
    args = parser.parse_args()

    ports = [int(p.strip()) for p in args.ports.split(",")]
    report = run_stealth_audit(args.target, ports)

    report_dict = asdict(report)
    with open(args.output, "w") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    logger.info("═══ ВЕРДИКТ: %s (Score: %.1f/100) ═══", report.verdict, report.overall_score)
    logger.info("Отчёт: %s", args.output)


if __name__ == "__main__":
    main()
