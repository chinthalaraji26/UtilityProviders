"""
Tools for the Utility Providers Agent.

These mock tools simulate a backend that knows which water, gas, electricity,
and internet providers serve a given area, what promotions those providers
are currently running, and how to estimate a combined monthly utility budget
once the user has picked a provider for each service.
"""

from strands import tool

SERVICE_TYPES = ["water", "gas", "electricity", "internet"]

# --- Mock regional data -----------------------------------------------------
# Each region lists the zip codes it covers and the providers available per
# service type, with a representative average monthly rate for a typical
# household. Real rates vary by usage; these are planning estimates.

REGIONS = [
    {
        "city": "Seattle",
        "state": "WA",
        "zip_codes": ["98101", "98102", "98103", "98104"],
        "providers": {
            "water": [
                {"name": "Seattle Public Utilities", "monthly_rate": 65.00, "rating": 4.1},
            ],
            "gas": [
                {"name": "Puget Sound Energy", "monthly_rate": 55.00, "rating": 4.0},
            ],
            "electricity": [
                {"name": "Seattle City Light", "monthly_rate": 90.00, "rating": 4.3},
            ],
            "internet": [
                {"name": "Comcast Xfinity", "monthly_rate": 70.00, "rating": 3.6},
                {"name": "CenturyLink Fiber", "monthly_rate": 60.00, "rating": 3.8},
            ],
        },
    },
    {
        "city": "Austin",
        "state": "TX",
        "zip_codes": ["78701", "78702", "78703", "78704"],
        "providers": {
            "water": [
                {"name": "Austin Water", "monthly_rate": 58.00, "rating": 3.9},
            ],
            "gas": [
                {"name": "Texas Gas Service", "monthly_rate": 40.00, "rating": 4.0},
            ],
            "electricity": [
                {"name": "Austin Energy", "monthly_rate": 85.00, "rating": 4.2},
                {"name": "TXU Energy", "monthly_rate": 95.00, "rating": 3.7},
            ],
            "internet": [
                {"name": "Google Fiber", "monthly_rate": 70.00, "rating": 4.5},
                {"name": "Spectrum", "monthly_rate": 65.00, "rating": 3.5},
            ],
        },
    },
    {
        "city": "Chicago",
        "state": "IL",
        "zip_codes": ["60601", "60602", "60603", "60604"],
        "providers": {
            "water": [
                {"name": "Chicago Dept. of Water Mgmt", "monthly_rate": 50.00, "rating": 3.8},
            ],
            "gas": [
                {"name": "Peoples Gas", "monthly_rate": 60.00, "rating": 3.6},
            ],
            "electricity": [
                {"name": "ComEd", "monthly_rate": 95.00, "rating": 3.9},
            ],
            "internet": [
                {"name": "Comcast Xfinity", "monthly_rate": 75.00, "rating": 3.6},
                {"name": "RCN", "monthly_rate": 55.00, "rating": 3.7},
            ],
        },
    },
    {
        "city": "Atlanta",
        "state": "GA",
        "zip_codes": ["30301", "30302", "30303", "30304"],
        "providers": {
            "water": [
                {"name": "Atlanta Dept. of Watershed Mgmt", "monthly_rate": 62.00, "rating": 3.7},
            ],
            "gas": [
                {"name": "Atlanta Gas Light", "monthly_rate": 45.00, "rating": 3.9},
            ],
            "electricity": [
                {"name": "Georgia Power", "monthly_rate": 105.00, "rating": 4.0},
            ],
            "internet": [
                {"name": "AT&T Fiber", "monthly_rate": 65.00, "rating": 4.1},
                {"name": "Xfinity", "monthly_rate": 70.00, "rating": 3.6},
            ],
        },
    },
    {
        "city": "San Francisco",
        "state": "CA",
        "zip_codes": ["94102", "94103", "94104", "94105"],
        "providers": {
            "water": [
                {"name": "SF Public Utilities Commission", "monthly_rate": 80.00, "rating": 4.0},
            ],
            "gas": [
                {"name": "PG&E", "monthly_rate": 70.00, "rating": 3.5},
            ],
            "electricity": [
                {"name": "PG&E", "monthly_rate": 130.00, "rating": 3.5},
            ],
            "internet": [
                {"name": "Sonic Fiber", "monthly_rate": 55.00, "rating": 4.4},
                {"name": "AT&T Fiber", "monthly_rate": 75.00, "rating": 4.0},
            ],
        },
    },
]

# --- Mock current promotions -------------------------------------------------
# Keyed by provider name (case-insensitive lookup). A provider not listed here
# simply has no active promotion.

PROMOTIONS = {
    "comcast xfinity": {
        "offer": "$20/mo off internet for 12 months for new customers",
        "discount_amount": 20.00,
        "service_type": "internet",
        "expires": "2026-12-31",
    },
    "centurylink fiber": {
        "offer": "First 3 months free, then standard rate",
        "discount_amount": 0.00,
        "service_type": "internet",
        "expires": "2026-10-31",
    },
    "google fiber": {
        "offer": "$10/mo off for 6 months when bundled with a moving offer",
        "discount_amount": 10.00,
        "service_type": "internet",
        "expires": "2026-11-30",
    },
    "spectrum": {
        "offer": "$15/mo off internet for the first year",
        "discount_amount": 15.00,
        "service_type": "internet",
        "expires": "2026-12-31",
    },
    "at&t fiber": {
        "offer": "$200 reward card + $10/mo off for 12 months",
        "discount_amount": 10.00,
        "service_type": "internet",
        "expires": "2026-12-31",
    },
    "sonic fiber": {
        "offer": "Price locked for life for new sign-ups this quarter",
        "discount_amount": 0.00,
        "service_type": "internet",
        "expires": "2026-09-30",
    },
    "txu energy": {
        "offer": "$100 bill credit spread over first 6 months ($16.67/mo)",
        "discount_amount": 16.67,
        "service_type": "electricity",
        "expires": "2026-12-31",
    },
    "austin energy": {
        "offer": "Free smart thermostat + $5/mo efficiency credit",
        "discount_amount": 5.00,
        "service_type": "electricity",
        "expires": "2026-12-31",
    },
    "georgia power": {
        "offer": "$8/mo off for enrolling in autopay + paperless billing",
        "discount_amount": 8.00,
        "service_type": "electricity",
        "expires": "2026-12-31",
    },
    "rcn": {
        "offer": "$25/mo off internet for 12 months, new customers only",
        "discount_amount": 25.00,
        "service_type": "internet",
        "expires": "2026-12-31",
    },
}


# --- Internal helpers ---------------------------------------------------


def _find_regions(zip_code: str = None, city: str = None, state: str = None):
    matches = []
    for region in REGIONS:
        if zip_code and zip_code.strip() in region["zip_codes"]:
            matches.append(region)
            continue
        if city and state:
            if (
                city.strip().lower() == region["city"].lower()
                and state.strip().lower() in (region["state"].lower(), region["state"].lower())
            ):
                matches.append(region)
    return matches


def _promo_for(provider_name: str):
    return PROMOTIONS.get(provider_name.strip().lower())


def _find_provider_rate(provider_name: str):
    """Search all regions for a provider by name and return its rate info."""
    target = provider_name.strip().lower()
    for region in REGIONS:
        for service_type, providers in region["providers"].items():
            for provider in providers:
                if provider["name"].lower() == target:
                    return service_type, provider
    return None, None


# --- Tools ---------------------------------------------------------------


@tool
def find_providers(zip_code: str = "", city: str = "", state: str = "", service_type: str = "") -> str:
    """Find water, gas, electricity, and internet providers available in an area.

    Look up providers either by zip_code, or by city + state. Optionally filter
    to a single service_type (water, gas, electricity, or internet).

    Args:
        zip_code: The 5-digit zip code to search (e.g. "78701"). Leave empty if using city/state.
        city: The city name (e.g. "Austin"). Must be paired with state.
        state: The 2-letter state code (e.g. "TX"). Must be paired with city.
        service_type: Optional filter - one of "water", "gas", "electricity", "internet".
    """
    if not zip_code and not (city and state):
        return "Please provide either a zip_code, or both a city and state."

    regions = _find_regions(zip_code=zip_code or None, city=city or None, state=state or None)
    if not regions:
        return f"No coverage data found for {zip_code or f'{city}, {state}'}. Try a nearby major city and state."

    wanted_types = [service_type.lower()] if service_type else SERVICE_TYPES
    invalid = [t for t in wanted_types if t not in SERVICE_TYPES]
    if invalid:
        return f"Unknown service type(s): {', '.join(invalid)}. Valid types: {', '.join(SERVICE_TYPES)}."

    lines = []
    for region in regions:
        lines.append(f"Providers serving {region['city']}, {region['state']}:")
        for stype in wanted_types:
            providers = region["providers"].get(stype, [])
            if not providers:
                continue
            lines.append(f"  {stype.capitalize()}:")
            for p in providers:
                promo = _promo_for(p["name"])
                promo_note = "  [active promotion available]" if promo else ""
                lines.append(
                    f"    - {p['name']}: ~${p['monthly_rate']:.2f}/mo (rating {p['rating']}/5){promo_note}"
                )
    return "\n".join(lines)


@tool
def get_promotions(provider_name: str = "", service_type: str = "") -> str:
    """Get current promotions being offered by utility providers.

    Filter by provider_name for a specific provider's promotion, or by
    service_type (water, gas, electricity, internet) to see all promotions
    for that category. Leave both empty to list every active promotion.

    Args:
        provider_name: Optional exact provider name (e.g. "Google Fiber").
        service_type: Optional filter - one of "water", "gas", "electricity", "internet".
    """
    if provider_name:
        promo = _promo_for(provider_name)
        if not promo:
            return f"No active promotion found for {provider_name}."
        return (
            f"{provider_name}: {promo['offer']} "
            f"(effective discount ~${promo['discount_amount']:.2f}/mo, expires {promo['expires']})"
        )

    results = []
    for name, promo in PROMOTIONS.items():
        if service_type and promo["service_type"] != service_type.lower():
            continue
        # Look up the properly-cased provider name for display.
        display_name = name
        for region in REGIONS:
            for providers in region["providers"].values():
                for p in providers:
                    if p["name"].lower() == name:
                        display_name = p["name"]
        results.append(
            f"- {display_name} ({promo['service_type']}): {promo['offer']} "
            f"(~${promo['discount_amount']:.2f}/mo off, expires {promo['expires']})"
        )

    if not results:
        return "No active promotions found for that filter."
    return "Current promotions:\n" + "\n".join(results)


@tool
def estimate_monthly_budget(
    water_provider: str = "",
    gas_provider: str = "",
    electricity_provider: str = "",
    internet_provider: str = "",
) -> str:
    """Estimate the combined monthly utility budget for chosen providers.

    Pass the exact provider name the customer picked for each service they
    want included. Leave a service empty to exclude it from the budget. Any
    active promotion discount is automatically applied to the estimate.

    Args:
        water_provider: Name of the chosen water provider, if any.
        gas_provider: Name of the chosen gas provider, if any.
        electricity_provider: Name of the chosen electricity provider, if any.
        internet_provider: Name of the chosen internet provider, if any.
    """
    chosen = {
        "water": water_provider,
        "gas": gas_provider,
        "electricity": electricity_provider,
        "internet": internet_provider,
    }
    chosen = {k: v for k, v in chosen.items() if v}
    if not chosen:
        return "Please provide at least one provider (water, gas, electricity, and/or internet)."

    lines = ["Monthly budget estimate:"]
    total = 0.0
    for service_type, name in chosen.items():
        found_type, provider = _find_provider_rate(name)
        if not provider:
            lines.append(f"  - {service_type.capitalize()}: no rate data found for provider '{name}'")
            continue
        if found_type != service_type:
            lines.append(
                f"  - {service_type.capitalize()}: '{name}' is listed as a {found_type} provider, not {service_type}. Skipped."
            )
            continue

        base_rate = provider["monthly_rate"]
        promo = _promo_for(name)
        discount = promo["discount_amount"] if promo else 0.0
        net_rate = max(base_rate - discount, 0.0)
        total += net_rate

        line = f"  - {service_type.capitalize()} ({name}): ${base_rate:.2f}/mo"
        if discount > 0:
            line += f" - ${discount:.2f} promo = ${net_rate:.2f}/mo"
        lines.append(line)

    lines.append(f"Estimated total: ${total:.2f}/mo")
    lines.append("(Estimates are for a typical household; actual usage may vary.)")
    return "\n".join(lines)
