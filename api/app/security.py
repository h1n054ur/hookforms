"""SSRF protection for webhook forwarding."""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_BLOCKED_HOSTNAMES = {
    "localhost",
    "postgres",
    "redis",
    "api",
    "worker",
    "cloudflared",
    "nginx",
    "metadata",
    "metadata.google.internal",
}


def _is_ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in _BLOCKED_NETWORKS)
    except ValueError:
        return True


def is_safe_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL"

    if parsed.scheme not in ("http", "https"):
        return False, f"Scheme '{parsed.scheme}' not allowed. Use http or https."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL has no hostname"

    if hostname.lower() in _BLOCKED_HOSTNAMES:
        return False, f"Hostname '{hostname}' is not allowed"

    try:
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in addr_infos:
            if _is_ip_blocked(sockaddr[0]):
                return False, "URL resolves to private/reserved IP address"
    except socket.gaierror:
        return False, "Cannot resolve hostname"

    return True, ""


class SSRFSafeTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        hostname = request.url.host
        if hostname:
            if hostname.lower() in _BLOCKED_HOSTNAMES:
                raise httpx.ConnectError(f"Blocked hostname: {hostname}")
            try:
                addr_infos = socket.getaddrinfo(
                    hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
                )
                for family, _, _, _, sockaddr in addr_infos:
                    if _is_ip_blocked(sockaddr[0]):
                        raise httpx.ConnectError(f"DNS resolved to blocked IP for {hostname}")
            except socket.gaierror:
                raise httpx.ConnectError(f"Cannot resolve hostname: {hostname}")
        return await super().handle_async_request(request)


def safe_http_client(
    timeout: float = 15,
    follow_redirects: bool = True,
    **kwargs,
) -> httpx.AsyncClient:
    transport = SSRFSafeTransport()
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=follow_redirects,
        transport=transport,
        **kwargs,
    )
