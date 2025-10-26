#!/usr/bin/env python3
"""
Test script to verify the improved API responses for:
1. AI Cofounder (Assistant) - proper loading state management
2. Design Variants (A/B Testing) - compact, world-class UI responses
"""

import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from features.assistant.service import get_concierge_response
from features.assistant.schemas import ConciergeRequest
from features.testing.service import create_ab_test, get_ab_test_results
from features.testing.schemas import ABTestExperimentRequest
import json


def test_assistant_loading_state():
    """Test that assistant responses include proper loading state fields"""
    print("=" * 60)
    print("TEST 1: AI Cofounder Loading State Management")
    print("=" * 60)
    
    # Test query that should NOT show loading state in response
    request = ConciergeRequest(
        user_id="test_user_123",
        query="Where is the keynote room?",
        context={}
    )
    
    response = get_concierge_response(request)
    
    print(f"\n✅ Query: {request.query}")
    print(f"✅ Response Type: {response.response_type}")
    print(f"✅ Is Processing: {response.is_processing}")
    print(f"✅ Processing Status: {response.processing_status}")
    print(f"✅ Response: {response.response[:50]}...")
    
    # Verify the loading state is false
    assert response.is_processing == False, "is_processing should be False for completed responses"
    assert response.processing_status is None, "processing_status should be None for completed responses"
    
    print("\n✅ PASS: AI Cofounder properly indicates non-processing state")
    print("💡 Frontend should NOT show 'thinking' animation when is_processing=false\n")
    
    return True


def test_compact_variant_design():
    """Test that A/B testing responses include compact, UI-friendly data"""
    print("=" * 60)
    print("TEST 2: Design Variants - Compact UI Response")
    print("=" * 60)
    
    # Create a test experiment request
    request = ABTestExperimentRequest(
        experiment_name="Homepage Recommendation Engine Test",
        description="Testing new transformer-based recommendation model",
        model_variants=[
            ABTestExperimentRequest.ModelVariant(
                name="Control",
                model_id="recommender-v1",
                version="1.2.0",
                traffic=0.5,
                description="Current production model"
            ),
            ABTestExperimentRequest.ModelVariant(
                name="Challenger",
                model_id="recommender-v2",
                version="2.0.0",
                traffic=0.5,
                description="New transformer-based model"
            )
        ]
    )
    
    response = create_ab_test(request)
    
    print(f"\n✅ Experiment Created: {response.experiment_id}")
    print(f"✅ Name: {response.name}")
    print(f"✅ Status: {response.status}")
    
    # Check summary field for compact UI
    print(f"\n📊 Summary (for UI cards):")
    print(json.dumps(response.summary, indent=2))
    
    assert "variant_count" in response.summary, "Summary should include variant_count"
    assert "duration_days" in response.summary, "Summary should include duration_days"
    assert "status_badge" in response.summary, "Summary should include status_badge"
    
    # Check variants are compact
    print(f"\n🎨 Compact Variants (for UI display):")
    for variant in response.variants:
        print(f"  - {variant['name']}: {variant['model']} @ {variant['traffic_pct']}%")
    
    assert len(response.variants) == 2, "Should have 2 variants"
    assert all("name" in v and "model" in v and "traffic_pct" in v for v in response.variants), \
        "Variants should have compact fields"
    
    print("\n✅ PASS: Design Variants use compact, UI-friendly structure")
    print("💡 Frontend can display variants in small cards without clutter\n")
    
    return True


def test_results_with_highlights():
    """Test that experiment results include metric highlights for compact display"""
    print("=" * 60)
    print("TEST 3: Experiment Results - Metric Highlights")
    print("=" * 60)
    
    results = get_ab_test_results("test_experiment_123")
    
    print(f"\n✅ Experiment: {results.experiment_name}")
    print(f"✅ Status: {results.status}")
    print(f"✅ Conclusion: {results.conclusion}")
    
    # Check summary stats
    print(f"\n📊 Summary Stats:")
    print(json.dumps(results.summary_stats, indent=2))
    
    assert "winner_name" in results.summary_stats, "Summary should include winner_name"
    assert "best_improvement" in results.summary_stats, "Summary should include best_improvement"
    
    # Check metric highlights
    print(f"\n🎯 Variant Results with Metric Highlights:")
    for result in results.results:
        print(f"\n  {result.variant_name} {'🏆' if result.is_winner else ''}")
        print(f"    Improvement: {result.improvement_percentage}%")
        print(f"    Top Metrics:")
        for metric in result.metric_highlights:
            print(f"      - {metric['label']}: {metric['display']}")
    
    assert all(len(r.metric_highlights) <= 3 for r in results.results), \
        "Should show max 3 metric highlights for compact UI"
    
    # Check recommendation
    if results.recommendation:
        print(f"\n💡 AI Recommendation:")
        print(f"   {results.recommendation}")
    
    print("\n✅ PASS: Results include metric highlights and recommendations")
    print("💡 Frontend can show concise results without information overload\n")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("ORACLE AI SERVICE - UI INTEGRATION TESTS")
    print("=" * 60 + "\n")
    
    try:
        # Test 1: Assistant loading state
        test_assistant_loading_state()
        
        # Test 2: Compact variant design
        test_compact_variant_design()
        
        # Test 3: Results with highlights
        test_results_with_highlights()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\n📝 Next Steps:")
        print("1. Review UI_INTEGRATION_GUIDE.md for frontend implementation details")
        print("2. Update frontend components to use the new API response structures")
        print("3. Test the UI with the improved loading states and compact designs")
        print()
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
