"""Vendor documentation allowlist (M1 S2, decision D08).

Exact lowercase hostnames only, over HTTPS, with no credentials in the URL. The netloc must be the
host alone or the host with the explicit port 443. Any control character, whitespace or non-ASCII
character anywhere in the URL is refused before parsing. Suffix, substring and encoded-host
matches are refused.

The entries below are the working selection recorded on 22 October 2026. The origin rule (P1) is
approved. The host list is not yet a formal approval of official vendor domains under D08, and the
decision-maker must confirm it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit


@dataclass(frozen=True)
class VendorAllowlist:
    hosts: frozenset[str]

    def __post_init__(self) -> None:
        if any(host != host.lower() or not host.strip() for host in self.hosts):
            raise ValueError("allowlist hosts must be non-blank lowercase hostnames")

    def permits(self, url: str) -> bool:
        if not url.isascii() or any(ord(ch) <= 0x20 or ord(ch) == 0x7F for ch in url):
            return False
        try:
            parts = urlsplit(url)
        except ValueError:
            return False
        if parts.scheme != "https" or not parts.hostname:
            return False
        if parts.username is not None or parts.password is not None:
            return False
        if parts.hostname not in self.hosts:
            return False
        netloc = parts.netloc.lower()
        return netloc in (parts.hostname, f"{parts.hostname}:443")


PROPOSED_SHOPIFY_ALLOWLIST: Final[VendorAllowlist] = VendorAllowlist(
    frozenset({"shopify.dev", "help.shopify.com"})
)
