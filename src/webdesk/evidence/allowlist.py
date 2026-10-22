"""Vendor documentation allowlist (M1 S2, decision D08; scoped entries from S2-D08 and S2-D09).

Exact lowercase hostnames only, over HTTPS, with no credentials in the URL. The netloc must be the
host alone or the host with the explicit port 443. Any control character, whitespace or non-ASCII
character anywhere in the URL is refused before parsing. Suffix, substring and encoded-host
matches are refused.

Two kinds of entry:
- A host in ``hosts`` permits any path on that host (the Shopify developer and help entries).
- A host in ``scoped`` permits only the paths given for it. A prefix entry permits its path and
  paths beneath it on a segment boundary. An exact entry permits only that path, with no children.
  Scoped hosts also refuse query strings, percent-encoding, backslashes and dot segments, so a
  permitted path cannot be walked out of its scope (QA4-01, QA4-02).

Scope values: the host list and scopes are the working selection recorded on 22 October 2026, and
S2-D07 to S2-D09 approve them for the Sprint 2 evaluation. The origin rule (P1) is approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ScopedHost:
    host: str
    paths: tuple[str, ...]
    exact: bool = False


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
            if not entry.paths or any(not p.startswith("/") for p in entry.paths):
                raise ValueError("each scoped host needs paths that start with '/'")
            if any(_unsafe_path(p) for p in entry.paths):
                raise ValueError("scoped paths must not contain dot segments or encoding")

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
                if parts.query or _unsafe_path(parts.path):
                    return False
                return any(_matches(parts.path, p, entry.exact) for p in entry.paths)
        return False


def _unsafe_path(path: str) -> bool:
    # Percent-encoding, backslashes, and dot segments are refused outright. They can make a path
    # look like it is inside a scope while the server resolves it elsewhere.
    if "%" in path or "\\" in path:
        return True
    return any(segment in (".", "..") for segment in path.split("/"))


def _matches(path: str, scoped_path: str, exact: bool) -> bool:
    if exact:
        return path == scoped_path
    if not path.startswith(scoped_path):
        return False
    rest = path[len(scoped_path) :]
    return rest == "" or rest[0] in "/."


PROPOSED_SHOPIFY_ALLOWLIST: Final[VendorAllowlist] = VendorAllowlist(
    frozenset({"shopify.dev", "help.shopify.com"})
)

# S2-D08: Shopify plan and pricing documentation only. Directory-style prefixes. /features is
# excluded because it redirects into /pos/features. shopify.com redirects to www.shopify.com, so
# both hosts carry the same scope (flagged for decision-maker confirmation). Note: the plan pages
# returned HTTP 403 to the fetch client when last attempted (see the evaluation record).
SHOPIFY_PLAN_SCOPES: Final[tuple[ScopedHost, ...]] = (
    ScopedHost("shopify.com", ("/pricing", "/plus")),
    ScopedHost("www.shopify.com", ("/pricing", "/plus")),
)

# S2-D09: two exact official CRA pages. The e-commerce page returned HTTP 200 and the bulletin it
# links to returned HTTP 200 when validated. Exact paths only, with no children.
CANADA_TAX_SCOPE: Final[ScopedHost] = ScopedHost(
    "www.canada.ca",
    (
        "/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/"
        "charge-collect-specific-situations/e-commerce.html",
        "/en/revenue-agency/services/forms-publications/publications/b-090.html",
    ),
    exact=True,
)

SPRINT2_ALLOWLIST: Final[VendorAllowlist] = VendorAllowlist(
    frozenset({"shopify.dev", "help.shopify.com"}),
    scoped=(*SHOPIFY_PLAN_SCOPES, CANADA_TAX_SCOPE),
)
