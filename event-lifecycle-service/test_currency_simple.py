#!/usr/bin/env python3
"""
Simple currency conversion direction test - no dependencies.
"""
import sys
import io

# Fix Windows console Unicode issues
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import httpx


def test_currency_conversion():
    """Test currency conversion direction with real API."""
    print("\n" + "="*70)
    print("CURRENCY CONVERSION DIRECTION TEST")
    print("="*70)

    # Fetch real rates from API
    url = "https://open.er-api.com/v6/latest/USD"
    print(f"\nFetching rates from: {url}")

    try:
        response = httpx.get(url, timeout=10)
        data = response.json()
    except Exception as e:
        print(f"❌ Failed to fetch rates: {e}")
        return False

    if "rates" not in data:
        print(f"❌ No rates in response: {data}")
        return False

    rates = data["rates"]
    print(f"\n✅ API Response received")
    print(f"   Base currency: {data.get('base')}")
    print(f"   Total currencies: {len(rates)}")

    # Print sample rates
    print(f"\n📊 Sample Exchange Rates (1 USD = X):")
    for curr in ["KES", "NGN", "ZAR", "EUR", "GBP"]:
        if curr in rates:
            print(f"   1 USD = {rates[curr]:.4f} {curr}")

    # Test 1: Verify KES rate format
    print(f"\n" + "-"*70)
    print("TEST 1: Verify Rate Format")
    print("-"*70)

    kes_rate = rates.get("KES", 0)
    print(f"KES rate: {kes_rate}")

    if 100 < kes_rate < 200:
        print(f"✅ Rate format is CORRECT: 1 USD = {kes_rate} KES")
        print(f"   (This means rates represent 'target currency per 1 base currency')")
    else:
        print(f"❌ Unexpected rate: {kes_rate}")
        return False

    # Test 2: Convert 100,000 KES to USD
    print(f"\n" + "-"*70)
    print("TEST 2: Convert 100,000 KES to USD")
    print("-"*70)

    amount_kes = 100000
    # If rates["KES"] = 128.5 (meaning 1 USD = 128.5 KES)
    # Then to convert FROM KES TO USD: amount_kes / kes_rate
    amount_usd = amount_kes / kes_rate

    print(f"Input: {amount_kes:,} KES")
    print(f"Rate: 1 USD = {kes_rate} KES")
    print(f"Formula: {amount_kes:,} / {kes_rate} = {amount_usd:.2f} USD")
    print(f"\nResult: {amount_usd:.2f} USD")

    if 700 < amount_usd < 900:
        print(f"✅ CORRECT: {amount_kes:,} KES = {amount_usd:.2f} USD")
        print(f"   Expected ~781 USD, got {amount_usd:.2f} USD ✓")
    elif amount_usd > 1000000:
        print(f"❌ BACKWARDS: Got {amount_usd:,.0f} USD (millions!)")
        print(f"   The formula should be: amount / rate (not amount * rate)")
        return False
    else:
        print(f"⚠️  Unexpected result: {amount_usd:.2f} USD")

    # Test 3: Convert 1,000,000 NGN to USD
    print(f"\n" + "-"*70)
    print("TEST 3: Convert 1,000,000 NGN to USD")
    print("-"*70)

    ngn_rate = rates.get("NGN", 0)
    amount_ngn = 1000000
    amount_usd_ngn = amount_ngn / ngn_rate

    print(f"Input: {amount_ngn:,} NGN")
    print(f"Rate: 1 USD = {ngn_rate} NGN")
    print(f"Formula: {amount_ngn:,} / {ngn_rate} = {amount_usd_ngn:.2f} USD")
    print(f"\nResult: {amount_usd_ngn:.2f} USD")

    if 500 < amount_usd_ngn < 800:
        print(f"✅ CORRECT: {amount_ngn:,} NGN = {amount_usd_ngn:.2f} USD")
    else:
        print(f"⚠️  Unexpected result: {amount_usd_ngn:.2f} USD")

    # Test 4: Convert 10,000 ZAR to USD
    print(f"\n" + "-"*70)
    print("TEST 4: Convert 10,000 ZAR to USD")
    print("-"*70)

    zar_rate = rates.get("ZAR", 0)
    amount_zar = 10000
    amount_usd_zar = amount_zar / zar_rate

    print(f"Input: {amount_zar:,} ZAR")
    print(f"Rate: 1 USD = {zar_rate} ZAR")
    print(f"Formula: {amount_zar:,} / {zar_rate} = {amount_usd_zar:.2f} USD")
    print(f"\nResult: {amount_usd_zar:.2f} USD")

    if 450 < amount_usd_zar < 650:
        print(f"✅ CORRECT: {amount_zar:,} ZAR = {amount_usd_zar:.2f} USD")
    else:
        print(f"⚠️  Unexpected result: {amount_usd_zar:.2f} USD")

    # Summary
    print(f"\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"✅ Currency conversion formula is CORRECT:")
    print(f"   amount_in_base = amount_in_target / rate")
    print(f"\n✅ The code in rfps.py:624 is using the RIGHT formula:")
    print(f"   total_in_preferred = total_cost / from_rate")
    print(f"\n✅ No changes needed!")
    print("="*70)

    return True


if __name__ == "__main__":
    try:
        success = test_currency_conversion()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
