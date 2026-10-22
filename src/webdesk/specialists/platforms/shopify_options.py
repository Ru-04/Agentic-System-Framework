"""Solution option classes and coverage for the Shopify specialist (M1 S2).

The specialist can say which kinds of solution the retrieved evidence mentions:
- NATIVE: configurable inside Shopify with no code, as the evidence describes it.
- APP_OR_EXTENSION: needs an app, app extension or Shopify Function.
- CUSTOM_API: needs custom code against a documented API.

What it cannot say: whether an option is feasible for a given client. Feasibility needs the plan
tier, the store setup and human judgement. No live model is called (D09), and a deterministic
keyword check cannot make that judgement. Feasibility is always reported as not determined.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class OptionClass(StrEnum):
    NATIVE = "native"
    APP_OR_EXTENSION = "app_or_extension"
    CUSTOM_API = "custom_api"


OPTION_LABELS: Final[dict[OptionClass, str]] = {
    OptionClass.NATIVE: "native Shopify configuration",
    OptionClass.APP_OR_EXTENSION: "third-party app or extension",
    OptionClass.CUSTOM_API: "custom code against a documented API",
}

_INDICATORS: Final[dict[OptionClass, tuple[str, ...]]] = {
    OptionClass.NATIVE: (
        "in the shopify admin",
        "built-in",
        "out of the box",
        "theme editor",
        "checkout settings",
    ),
    OptionClass.APP_OR_EXTENSION: (
        "app extension",
        "checkout ui extension",
        "theme app extension",
        "shopify function",
        "customer account ui extension",
        "shopify app",
        "app store",
        "app bridge",
    ),
    OptionClass.CUSTOM_API: (
        "graphql",
        "admin api",
        "storefront api",
        "customer account api",
        "webhook",
        "api version",
        "rate limit",
        "mutation",
    ),
}

FEASIBILITY_STATUS: Final[str] = "not_determined"

FEASIBILITY_UNKNOWN: Final[str] = (
    "feasibility is not determined by this specialist; it needs plan, store and human review "
    "(D07, D09)"
)

PLAN_CLARIFICATION: Final[str] = (
    "CLARIFY: confirm the Shopify plan tier and store setup this requirement assumes"
)


def classify_options(text: str) -> frozenset[OptionClass]:
    lowered = text.lower()
    return frozenset(
        option
        for option, phrases in _INDICATORS.items()
        if any(phrase in lowered for phrase in phrases)
    )


def clarification_for(option: OptionClass) -> str:
    return f"CLARIFY: is a {OPTION_LABELS[option]} acceptable for this requirement?"
