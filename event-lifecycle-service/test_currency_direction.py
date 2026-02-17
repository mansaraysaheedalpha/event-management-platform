#!/usr/bin/env python3
"""
Standalone test to verify currency conversion direction.
Run this script directly to test with real API.
"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app.utils.exchange_rates import get_exchange_rates_sync, convert_amount


def test_api_response_format():
    """Test 1: Verify the actual API response format."""
    print("\n" + "="*70)
    print("TEST 1: Verify API Response Format")
    print("="*70)

    rates_data = get_exchange_rates_sync("USD")

    if not rates_data:
        print("❌ FAILED: API returned no data")
        return False

    print(f"✅ API returned data: base={rates_data['base']}")
    print(f"   Fetched at: {rates_data.get('fetched_at')}")

    rates = rates_data["rates"]

    # Check key currencies
    for curr in ["KES", "NGN", "ZAR", "EUR", "GBP"]:
        if curr in rates:
            print(f"   1 USD = {rates[curr]:.4f} {curr}")
        else:
            print(f"   ⚠️  {curr} not found in rates")

    # Verify KES rate is in expected range
    kes_rate = rates.get("KES", 0)
    if 100 < kes_rate < 200:
        print(f"\n✅ KES rate is reasonable: {kes_rate:.2f}")
        print(f"   (Expected ~128 for 1 USD = 128 KES)")
        return True
    else:
        print(f"\n❌ KES rate seems wrong: {kes_rate}")
        return False


def test_kes_to_usd_conversion():
    """Test 2: Convert 100,000 KES to USD."""
    print("\n" + "="*70)
    print("TEST 2: Convert 100,000 KES to USD")
    print("="*70)

    rates_data = get_exchange_rates_sync("USD")
    if not rates_data:
        print("❌ FAILED: No rate data")
        return False

    kes_rate = rates_data["rates"]["KES"]
    amount_kes = 100000

    # Current formula: amount_usd = amount_kes / kes_rate
    amount_usd = amount_kes / kes_rate

    print(f"Amount in KES: {amount_kes:,}")
    print(f"Exchange rate: 1 USD = {kes_rate:.4f} KES")
    print(f"Formula: {amount_kes:,} KES ÷ {kes_rate:.4f} = {amount_usd:.2f} USD")
    print(f"\nResult: {amount_usd:.2f} USD")

    # Expected: ~781 USD (if rate is ~128)
    if 700 < amount_usd < 900:
        print(f"✅ CORRECT: Result is in expected range (700-900 USD)")
        return True
    elif amount_usd > 1000000:
        print(f"❌ BACKWARDS: Got {amount_usd:,.2f} USD (millions!)")
        print(f"   This means the formula is INVERTED")
        return False
    else:
        print(f"⚠️  UNEXPECTED: Got {amount_usd:.2f} USD")
        return False


def test_ngn_to_usd_conversion():
    """Test 3: Convert 1,000,000 NGN to USD."""
    print("\n" + "="*70)
    print("TEST 3: Convert 1,000,000 NGN to USD")
    print("="*70)

    rates_data = get_exchange_rates_sync("USD")
    if not rates_data:
        print("❌ FAILED: No rate data")
        return False

    ngn_rate = rates_data["rates"]["NGN"]
    amount_ngn = 1000000

    amount_usd = amount_ngn / ngn_rate

    print(f"Amount in NGN: {amount_ngn:,}")
    print(f"Exchange rate: 1 USD = {ngn_rate:.4f} NGN")
    print(f"Formula: {amount_ngn:,} NGN ÷ {ngn_rate:.4f} = {amount_usd:.2f} USD")
    print(f"\nResult: {amount_usd:.2f} USD")

    if 500 < amount_usd < 800:
        print(f"✅ CORRECT: Result is in expected range (500-800 USD)")
        return True
    else:
        print(f"❌ UNEXPECTED: Got {amount_usd:.2f} USD")
        return False


def test_zar_to_usd_conversion():
    """Test 4: Convert 10,000 ZAR to USD."""
    print("\n" + "="*70)
    print("TEST 4: Convert 10,000 ZAR to USD")
    print("="*70)

    rates_data = get_exchange_rates_sync("USD")
    if not rates_data:
        print("❌ FAILED: No rate data")
        return False

    zar_rate = rates_data["rates"]["ZAR"]
    amount_zar = 10000

    amount_usd = amount_zar / zar_rate

    print(f"Amount in ZAR: {amount_zar:,}")
    print(f"Exchange rate: 1 USD = {zar_rate:.4f} ZAR")
    print(f"Formula: {amount_zar:,} ZAR ÷ {zar_rate:.4f} = {amount_usd:.2f} USD")
    print(f"\nResult: {amount_usd:.2f} USD")

    if 450 < amount_usd < 650:
        print(f"✅ CORRECT: Result is in expected range (450-650 USD)")
        return True
    else:
        print(f"❌ UNEXPECTED: Got {amount_usd:.2f} USD")
        return False


def test_convert_amount_function():
    """Test 5: Test the convert_amount utility function."""
    print("\n" + "="*70)
    print("TEST 5: Test convert_amount() Utility Function")
    print("="*70)

    # Test 100 USD to KES
    result_kes = convert_amount(100, "USD", "KES")
    print(f"100 USD → {result_kes} KES")

    if result_kes and 12000 < result_kes < 20000:
        print(f"✅ CORRECT: 100 USD converts to ~12,800 KES")
    else:
        print(f"❌ FAILED: Expected ~12,800 KES, got {result_kes}")
        return False

    # Test 100 EUR to USD
    result_usd = convert_amount(100, "EUR", "USD")
    print(f"100 EUR → {result_usd} USD")

    if result_usd and 95 < result_usd < 120:
        print(f"✅ CORRECT: 100 EUR converts to ~110 USD")
        return True
    else:
        print(f"❌ FAILED: Expected ~110 USD, got {result_usd}")
        return False


def main():
    """Run all tests."""
    print("\n" + "🔍" * 35)
    print("CURRENCY CONVERSION DIRECTION VERIFICATION")
    print("🔍" * 35)

    tests = [
        ("API Response Format", test_api_response_format),
        ("KES → USD Conversion", test_kes_to_usd_conversion),
        ("NGN → USD Conversion", test_ngn_to_usd_conversion),
        ("ZAR → USD Conversion", test_zar_to_usd_conversion),
        ("convert_amount() Function", test_convert_amount_function),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ Test '{name}' raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    print(f"\n{passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 All tests passed! Currency conversion direction is CORRECT.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review the conversion logic.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
