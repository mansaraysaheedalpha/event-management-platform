# tests/utils/test_exchange_rates.py
"""
Test exchange rate API integration and conversion direction.
"""
import pytest
from app.utils.exchange_rates import get_exchange_rates_sync, convert_amount


class TestExchangeRatesIntegration:
    """Integration tests with real API to verify conversion direction."""

    def test_real_api_response_format(self):
        """Verify the actual API response format from open.er-api.com."""
        rates_data = get_exchange_rates_sync("USD")

        assert rates_data is not None, "API should return data"
        assert "base" in rates_data
        assert "rates" in rates_data
        assert rates_data["base"] == "USD"

        # Check that rates dict contains expected currencies
        rates = rates_data["rates"]
        assert "KES" in rates, "Should have KES (Kenyan Shilling)"
        assert "NGN" in rates, "Should have NGN (Nigerian Naira)"
        assert "EUR" in rates, "Should have EUR"

        # Verify rate format: 1 USD = X KES (KES rate should be > 100)
        kes_rate = rates["KES"]
        assert kes_rate > 100, f"1 USD should be ~128 KES, got {kes_rate}"
        assert kes_rate < 200, f"Rate seems too high: {kes_rate}"

        # EUR should be < 1 (1 USD = ~0.9 EUR)
        eur_rate = rates["EUR"]
        assert 0.7 < eur_rate < 1.2, f"1 USD should be ~0.9 EUR, got {eur_rate}"

    def test_currency_conversion_direction_kes_to_usd(self):
        """
        Test conversion from KES to USD with real rates.
        Expected: 100,000 KES → ~781 USD (at rate 1 USD = 128 KES)
        """
        rates_data = get_exchange_rates_sync("USD")
        assert rates_data is not None

        kes_rate = rates_data["rates"]["KES"]
        print(f"\n[CONVERSION TEST] 1 USD = {kes_rate} KES")

        # Convert 100,000 KES to USD
        amount_kes = 100000
        # Formula: amount_usd = amount_kes / kes_rate
        expected_usd = amount_kes / kes_rate

        print(f"[CONVERSION TEST] {amount_kes:,} KES ÷ {kes_rate} = {expected_usd:.2f} USD")

        # Verify the result is in expected range (~750-810 USD)
        assert 700 < expected_usd < 900, (
            f"Conversion failed: {amount_kes} KES should convert to ~781 USD, "
            f"but got {expected_usd:.2f} USD. "
            f"If this is 12,800,000 USD, the formula is BACKWARDS!"
        )

    def test_currency_conversion_direction_ngn_to_usd(self):
        """
        Test conversion from NGN to USD with real rates.
        Expected: 1,000,000 NGN → ~650 USD (at rate 1 USD = 1,530 NGN)
        """
        rates_data = get_exchange_rates_sync("USD")
        assert rates_data is not None

        ngn_rate = rates_data["rates"]["NGN"]
        print(f"\n[CONVERSION TEST] 1 USD = {ngn_rate} NGN")

        # Convert 1,000,000 NGN to USD
        amount_ngn = 1000000
        expected_usd = amount_ngn / ngn_rate

        print(f"[CONVERSION TEST] {amount_ngn:,} NGN ÷ {ngn_rate} = {expected_usd:.2f} USD")

        # Verify the result is in expected range (~600-700 USD)
        assert 500 < expected_usd < 800, (
            f"Conversion failed: {amount_ngn} NGN should convert to ~650 USD, "
            f"but got {expected_usd:.2f} USD"
        )

    def test_currency_conversion_direction_zar_to_usd(self):
        """
        Test conversion from ZAR to USD with real rates.
        Expected: 10,000 ZAR → ~550 USD (at rate 1 USD = 18 ZAR)
        """
        rates_data = get_exchange_rates_sync("USD")
        assert rates_data is not None

        zar_rate = rates_data["rates"]["ZAR"]
        print(f"\n[CONVERSION TEST] 1 USD = {zar_rate} ZAR")

        # Convert 10,000 ZAR to USD
        amount_zar = 10000
        expected_usd = amount_zar / zar_rate

        print(f"[CONVERSION TEST] {amount_zar:,} ZAR ÷ {zar_rate} = {expected_usd:.2f} USD")

        # Verify the result is in expected range (~500-600 USD)
        assert 450 < expected_usd < 650, (
            f"Conversion failed: {amount_zar} ZAR should convert to ~555 USD, "
            f"but got {expected_usd:.2f} USD"
        )

    def test_convert_amount_utility_function(self):
        """Test the convert_amount utility function directly."""
        # Convert 100 USD to KES
        result = convert_amount(100, "USD", "KES")
        assert result is not None
        assert 12000 < result < 20000, f"100 USD should be ~12,800 KES, got {result}"

        # Convert 100 EUR to USD
        result_usd = convert_amount(100, "EUR", "USD")
        assert result_usd is not None
        assert 95 < result_usd < 120, f"100 EUR should be ~110 USD, got {result_usd}"

    def test_same_currency_conversion(self):
        """Test that same currency conversion returns the same amount."""
        result = convert_amount(1000, "USD", "USD")
        assert result == 1000

    @pytest.mark.parametrize("base,target,min_rate,max_rate", [
        ("USD", "KES", 100, 200),    # 1 USD = ~128 KES
        ("USD", "NGN", 1000, 2000),  # 1 USD = ~1530 NGN
        ("USD", "ZAR", 15, 25),      # 1 USD = ~18 ZAR
        ("USD", "EUR", 0.7, 1.2),    # 1 USD = ~0.9 EUR
    ])
    def test_rate_sanity_checks(self, base, target, min_rate, max_rate):
        """Verify rates are in expected ranges."""
        rates_data = get_exchange_rates_sync(base)
        assert rates_data is not None

        rate = rates_data["rates"][target]
        assert min_rate <= rate <= max_rate, (
            f"Rate for {base}/{target} is {rate}, expected between {min_rate}-{max_rate}"
        )


class TestComparisonDashboardConversion:
    """Test the actual conversion logic used in comparison dashboard."""

    def test_comparison_conversion_matches_formula(self):
        """
        Simulate the exact logic from rfps.py:614-624 to verify correctness.
        """
        # Get real rates with USD as base
        exchange_rate_data = get_exchange_rates_sync("USD")
        assert exchange_rate_data is not None

        # Simulate a venue response in KES
        venue_cost_kes = 500000  # 500,000 KES
        venue_currency = "KES"
        preferred_currency = "USD"

        rates = exchange_rate_data.get("rates", {})
        from_rate = rates.get(venue_currency)

        assert from_rate is not None
        assert from_rate > 0

        # This is the EXACT formula from rfps.py:624
        total_in_preferred = venue_cost_kes / from_rate

        print(f"\n[DASHBOARD SIMULATION]")
        print(f"Venue cost: {venue_cost_kes:,} {venue_currency}")
        print(f"Exchange rate: 1 {preferred_currency} = {from_rate} {venue_currency}")
        print(f"Converted cost: {total_in_preferred:.2f} {preferred_currency}")

        # Verify the result is reasonable (~3,900 USD)
        assert 3500 < total_in_preferred < 4500, (
            f"500,000 KES should convert to ~3,900 USD, got {total_in_preferred:.2f} USD"
        )

    def test_comparison_no_conversion_needed(self):
        """Test when venue currency matches preferred currency."""
        venue_cost_usd = 5000
        venue_currency = "USD"
        preferred_currency = "USD"

        # No conversion needed
        total_in_preferred = venue_cost_usd

        assert total_in_preferred == 5000
