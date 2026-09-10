"""Unit tests for utility_provider_tools.py.

These exercise the mock data and pure tool logic directly - no AWS credentials
or network access required.

Run with:
    pip install -r requirements-dev.txt
    pytest
"""

from utility_provider_tools import find_providers, get_promotions, estimate_monthly_budget


# --- find_providers ---------------------------------------------------


def test_find_providers_by_zip_code():
    result = find_providers(zip_code="78701")
    assert "Austin, TX" in result
    assert "Austin Water" in result
    assert "Google Fiber" in result


def test_find_providers_by_city_and_state():
    result = find_providers(city="Chicago", state="IL")
    assert "Chicago, IL" in result
    assert "ComEd" in result


def test_find_providers_filters_by_service_type():
    result = find_providers(zip_code="78701", service_type="internet")
    assert "Internet:" in result
    assert "Water:" not in result
    assert "Gas:" not in result
    assert "Electricity:" not in result


def test_find_providers_flags_active_promotions():
    result = find_providers(zip_code="78701", service_type="electricity")
    assert "Austin Energy" in result
    assert "active promotion available" in result


def test_find_providers_unknown_location():
    result = find_providers(zip_code="00000")
    assert "No coverage data found" in result


def test_find_providers_requires_location():
    result = find_providers()
    assert "Please provide" in result


def test_find_providers_rejects_invalid_service_type():
    result = find_providers(zip_code="78701", service_type="cable")
    assert "Unknown service type" in result


# --- get_promotions ----------------------------------------------------


def test_get_promotions_by_exact_provider_name():
    result = get_promotions(provider_name="Google Fiber")
    assert "$10/mo off" in result
    assert "expires 2026-11-30" in result


def test_get_promotions_no_match_for_provider():
    result = get_promotions(provider_name="Nonexistent ISP")
    assert "No active promotion found" in result


def test_get_promotions_filtered_by_service_type():
    result = get_promotions(service_type="electricity")
    assert "TXU Energy" in result
    assert "Austin Energy" in result
    # Should not include an internet-only promotion.
    assert "Google Fiber" not in result


def test_get_promotions_with_no_filter_lists_everything():
    result = get_promotions()
    assert "Current promotions:" in result
    assert "Google Fiber" in result
    assert "TXU Energy" in result


# --- estimate_monthly_budget --------------------------------------------


def test_estimate_monthly_budget_applies_promo_discount():
    result = estimate_monthly_budget(
        water_provider="Austin Water",
        gas_provider="Texas Gas Service",
        electricity_provider="Austin Energy",
        internet_provider="Google Fiber",
    )
    # 58 + 40 + (85-5) + (70-10) = 238
    assert "$238.00/mo" in result
    assert "$80.00/mo" in result  # electricity net after promo
    assert "$60.00/mo" in result  # internet net after promo


def test_estimate_monthly_budget_no_promo_provider():
    result = estimate_monthly_budget(water_provider="Austin Water")
    assert "$58.00/mo" in result
    assert "promo" not in result.split("Estimated total")[0].lower()


def test_estimate_monthly_budget_unknown_provider():
    result = estimate_monthly_budget(internet_provider="Definitely Not A Real ISP")
    assert "no rate data found" in result
    assert "$0.00/mo" in result


def test_estimate_monthly_budget_service_mismatch():
    # "Austin Water" is a water provider, not gas.
    result = estimate_monthly_budget(gas_provider="Austin Water")
    assert "not gas" in result
    assert "Skipped" in result


def test_estimate_monthly_budget_requires_at_least_one_provider():
    result = estimate_monthly_budget()
    assert "Please provide at least one provider" in result
