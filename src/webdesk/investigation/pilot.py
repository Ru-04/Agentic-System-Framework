"""Controlled read-only retrieval pilot (WDS approval, 28 October 2026).

Two pages only: the WooCommerce Store API products reference and the BigCommerce product read page.
Each page is fetched through the Sprint 2 vendor opener, which does not follow redirects and uses
no proxy. Each page is then passed to the investigation engine, which decides what it supports.

A page is cited only when it states the requested version. The version used here for the BigCommerce
page is the API path version shown on that page (v3). The WooCommerce page states no version, so it
cannot be cited for any version.
"""

from __future__ import annotations

import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import partial
from typing import IO, Final, cast

from webdesk.evidence.http_vendor import Opener, build_vendor_opener
from webdesk.investigation.engine import Capability, ClaimKind, Edition, investigate
from webdesk.investigation.retrieval import FetchRecord, RetrievalOutcome, retrieve_approved_pages
from webdesk.specialists.authorization import AuthorityContext, execute_verified

PILOT_WORKSPACE: Final[str] = "ws-pilot"
PILOT_SPECIALIST_ID: Final[str] = "pilot-retrieval"
# One pilot run is one request, so one operator decision covers both cases.
PILOT_REQUEST_ID: Final[str] = "pilot-run-2026-10-28"
PILOT_ACTIONS: Final[frozenset[str]] = frozenset({"read_evidence"})
# The pilot identifies itself. The default urllib agent is refused by a vendor (HTTP 403).
PILOT_USER_AGENT: Final[str] = "WebDesk-pilot/1.0 (read-only; WDS approval 28 Oct 2026)"


def pilot_opener(url: str, timeout: float) -> IO[bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": PILOT_USER_AGENT})  # noqa: S310
    # https only; the boundary check runs before any call, and redirects are refused in the opener.
    return cast(IO[bytes], build_vendor_opener().open(request, timeout=timeout))


@dataclass(frozen=True)
class PilotCase:
    name: str
    source_id: str
    platform: str
    edition: Edition
    url: str
    capability: Capability
    page_version: str | None
    requested_version: str | None


PILOT_CASES: Final[tuple[PilotCase, ...]] = (
    PilotCase(
        name="woocommerce_store_api_products",
        source_id="woocommerce_docs",
        platform="woocommerce",
        edition=Edition.NOT_APPLICABLE,
        url="https://developer.woocommerce.com/docs/apis/store-api/resources-endpoints/products/",
        capability=Capability(
            "product variation pricing",
            "woocommerce",
            Edition.NOT_APPLICABLE,
            ClaimKind.FEATURE,
            ("variation", "price"),
        ),
        page_version=None,
        requested_version=None,
    ),
    PilotCase(
        name="bigcommerce_get_product",
        source_id="bigcommerce_docs_product_page",
        platform="bigcommerce",
        edition=Edition.NOT_APPLICABLE,
        url=(
            "https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/"
            "get-product"
        ),
        capability=Capability(
            "product catalog read",
            "bigcommerce",
            Edition.NOT_APPLICABLE,
            ClaimKind.FEATURE,
            ("product", "catalog"),
        ),
        page_version="v3",
        requested_version="v3",
    ),
)


@dataclass(frozen=True)
class PilotResult:
    case: str
    fetch: tuple[dict[str, object], ...]
    outcome: str
    citations: tuple[str, ...]
    unknowns: tuple[str, ...]
    refusals: tuple[str, ...]


def run_pilot(opener: Opener, authority: AuthorityContext) -> tuple[PilotResult, ...]:
    """Run each pilot case once, each under a verified operator decision.

    The pilot never creates authority. ``authority`` is supplied by the trusted operator workflow,
    and each case's retrieval runs only through ``execute_verified``. A missing, expired, revoked or
    mismatched decision raises ``AuthorizationDenied`` before any request is made.
    """
    results: list[PilotResult] = []
    for case in PILOT_CASES:
        outcome = execute_verified(
            authority,
            workspace_id=PILOT_WORKSPACE,
            specialist_id=PILOT_SPECIALIST_ID,
            request_id=PILOT_REQUEST_ID,
            requested_actions=PILOT_ACTIONS,
            operation=partial(_retrieve, case, opener, authority.now),
        )
        finding = investigate(
            case.capability,
            outcome.pages,
            workspace_id=PILOT_WORKSPACE,
            requested_version=case.requested_version,
            operator_confirmed=True,
        )
        results.append(
            PilotResult(
                case=case.name,
                fetch=tuple(_fetch_dict(record) for record in outcome.records),
                outcome=finding.outcome.value,
                citations=tuple(c.url for c in finding.citations),
                unknowns=tuple(finding.unknowns),
                refusals=finding.refusals,
            )
        )
    return tuple(results)


def _retrieve(case: PilotCase, opener: Opener, now: datetime) -> RetrievalOutcome:
    """The retrieval call. It runs only inside ``execute_verified``."""
    return retrieve_approved_pages(
        platform=case.platform,
        edition=case.edition,
        urls=[case.url],
        workspace_id=PILOT_WORKSPACE,
        version=case.page_version,
        opener=opener,
        source_id=case.source_id,
        now=now,
    )


def _fetch_dict(record: FetchRecord) -> dict[str, object]:
    data = asdict(record)
    data["status"] = record.status.value
    data["retrieved_at"] = record.retrieved_at.isoformat() if record.retrieved_at else None
    return data
