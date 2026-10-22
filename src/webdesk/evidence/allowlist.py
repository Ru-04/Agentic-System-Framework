"""Vendor documentation allowlist (M1 S2, decision D08; scoped entries from S2-D08 and S2-D09).

Exact lowercase hostnames only, over HTTPS, with no credentials in the URL. The netloc must be the
host alone or the host with the explicit port 443. Any control character, whitespace or non-ASCII
character anywhere in the URL is refused before parsing. Suffix, substring and encoded-host
matches are refused.

Two kinds of entry:
- A host in ``hosts`` permits any path on that host (the Shopify developer and help entries).
- A host in ``scoped`` permits only the path prefixes given for it, matched on a path segment
  boundary, with no query string. Plan documentation and Canadian tax documentation use this, so a
  permitted host cannot be crawled.

The host list and scopes are the working selection recorded on 22 October 2026, and S2-D07 to S2-D09
approve them for the Sprint 2 evaluation. The origin rule (P1) is approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ScopedHost:
    host: str
    path_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class VendorAllowlist:
    hosts: frozenset[str]
    scoped: tuple[ScopedHost, ...] = field(default=())

    def __post_init__(self) -> None:
        names = list(self.hosts) + [entry.host for entry in self.scoped]
        if any(name != name.lower() or not name.strip() for name in names):
            raise ValueError("allowlist hosts must be non-blank lowercase hostnames")
        if set(self.hosts) & {entry.host for entry in self.scoped}:
            raise ValueError("a host cannot be both unscoped and scoped")
        for entry in self.scoped:
            if not entry.path_prefixes or any(not p.startswith("/") for p in entry.path_prefixes):
                raise ValueError("each scoped host needs path prefixes that start with '/'")

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
        netloc = parts.netloc.lower()
        if netloc not in (parts.hostname, f"{parts.hostname}:443"):
            return False
        if parts.hostname in self.hosts:
            return True
        for entry in self.scoped:
            if parts.hostname == entry.host:
                return not parts.query and any(
                    _within(parts.path, prefix) for prefix in entry.path_prefixes
                )
        return False


def _within(path: str, prefix: str) -> bool:
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :]
    return rest == "" or rest[0] in "/."


PROPOSED_SHOPIFY_ALLOWLIST: Final[VendorAllowlist] = VendorAllowlist(
    frozenset({"shopify.dev", "help.shopify.com"})
)

# S2-D08: Shopify plan and pricing documentation only. Validated 22 Oct 2026: /pricing and /plus
# return HTTP 200 on the canonical host. /features redirects into /pos/features, so it is excluded.
# shopify.com redirects to www.shopify.com, so both hosts carry the same scope (flagged for
# decision-maker confirmation).
SHOPIFY_PLAN_SCOPES: Final[tuple[ScopedHost, ...]] = (
    ScopedHost("shopify.com", ("/pricing", "/plus")),
    ScopedHost("www.shopify.com", ("/pricing", "/plus")),
)

# S2-D09: two exact official CRA pages, validated 22 Oct 2026 (the e-commerce page returns HTTP 200;
# the second is the bulletin it links to). Exact paths only: no other canada.ca page is permitted.
CANADA_TAX_SCOPE: Final[ScopedHost] = ScopedHost(
    "www.canada.ca",
    (
        "/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/"
        "charge-collect-specific-situations/e-commerce.html",
        "/en/revenue-agency/services/forms-publications/publications/b-090.html",
    ),
)

SPRINT2_ALLOWLIST: Final[VendorAllowlist] = VendorAllowlist(
    frozenset({"shopify.dev", "help.shopify.com"}),
    scoped=(*SHOPIFY_PLAN_SCOPES, CANADA_TAX_SCOPE),
)
