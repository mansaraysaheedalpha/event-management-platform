# app/features/testing/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class VariantStatus(str, Enum):
    """Status of a variant in the experiment"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ABTestExperimentRequest(BaseModel):
    class ModelVariant(BaseModel):
        """Compact variant configuration for A/B testing"""
        name: str = Field(..., description="Short, descriptive variant name", max_length=50)
        model_id: str = Field(..., description="Unique model identifier")
        version: str = Field(..., description="Model version (semver format recommended)")
        traffic: float = Field(..., ge=0, le=1, description="Traffic allocation (0.0 to 1.0)")
        description: Optional[str] = Field(None, max_length=200, description="Brief variant description")
        
        # Compact display properties for UI
        @property
        def display_label(self) -> str:
            """Returns a compact display label for UI"""
            return f"{self.name} • {self.version}"
        
        @property
        def traffic_percentage(self) -> int:
            """Returns traffic as percentage for better UI display"""
            return int(self.traffic * 100)

    experiment_name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    model_variants: List[ModelVariant] = Field(..., min_items=2, max_items=10)


class ABTestExperimentResponse(BaseModel):
    """Optimized response with summary data for compact UI display"""
    experiment_id: str
    name: str
    status: str
    start_time: datetime
    estimated_end_time: datetime
    
    # Compact summary for UI cards
    summary: Dict[str, Any] = Field(
        default_factory=lambda: {},
        description="Compact experiment summary for dashboard cards"
    )
    
    # Detailed variant information
    variants: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Variant configurations"
    )
    
    # Dashboard link
    dashboard_url: str = "https://your-analytics-platform.com/ab-test/dashboard"
    
    @classmethod
    def create_with_summary(
        cls,
        experiment_id: str,
        name: str,
        status: str,
        start_time: datetime,
        estimated_end_time: datetime,
        variants: List[Dict[str, Any]]
    ):
        """Factory method to create response with computed summary"""
        duration_days = (estimated_end_time - start_time).days
        return cls(
            experiment_id=experiment_id,
            name=name,
            status=status,
            start_time=start_time,
            estimated_end_time=estimated_end_time,
            variants=variants,
            summary={
                "variant_count": len(variants),
                "duration_days": duration_days,
                "status_badge": status.upper(),
                "progress_percentage": 0,  # Can be computed based on time elapsed
            }
        )


class ABTestResultsResponse(BaseModel):
    """Optimized results with metric highlights for compact UI display"""
    
    class VariantResult(BaseModel):
        """Compact variant result with key metrics"""
        variant_name: str
        is_winner: bool
        status: VariantStatus = VariantStatus.COMPLETED
        
        # Performance metrics - structured for easy UI rendering
        metrics: Dict[str, float] = Field(
            default_factory=dict,
            description="Key performance metrics"
        )
        
        # Compact metric highlights for UI cards
        metric_highlights: List[Dict[str, Any]] = Field(
            default_factory=list,
            description="Top 3 metrics for card display"
        )
        
        # Comparison data
        improvement_percentage: Optional[float] = Field(
            None,
            description="Percentage improvement over control"
        )
        
        @classmethod
        def create_with_highlights(
            cls,
            variant_name: str,
            is_winner: bool,
            metrics: Dict[str, float],
            improvement: Optional[float] = None
        ):
            """Factory method to create result with metric highlights"""
            # Select top 3 metrics for highlights
            sorted_metrics = sorted(
                metrics.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:3]
            
            highlights = [
                {
                    "label": metric_name.replace("_", " ").title(),
                    "value": value,
                    "display": f"{value:.1f}"
                }
                for metric_name, value in sorted_metrics
            ]
            
            return cls(
                variant_name=variant_name,
                is_winner=is_winner,
                metrics=metrics,
                metric_highlights=highlights,
                improvement_percentage=improvement
            )

    experiment_id: str
    experiment_name: str
    status: str
    results: List[VariantResult]
    conclusion: str
    
    # Summary statistics for quick overview
    summary_stats: Dict[str, Any] = Field(
        default_factory=lambda: {},
        description="Summary statistics for dashboard overview"
    )
    
    # Recommendation based on results
    recommendation: Optional[str] = Field(
        None,
        description="AI-generated recommendation based on results"
    )
    
    @classmethod
    def create_with_stats(
        cls,
        experiment_id: str,
        experiment_name: str,
        status: str,
        results: List[VariantResult],
        conclusion: str
    ):
        """Factory method to create response with computed statistics"""
        winner = next((r for r in results if r.is_winner), None)
        
        stats = {
            "total_variants": len(results),
            "winner_name": winner.variant_name if winner else "None",
            "best_improvement": max(
                (r.improvement_percentage for r in results if r.improvement_percentage),
                default=0
            ),
            "completed_at": datetime.now().isoformat()
        }
        
        recommendation = None
        if winner:
            improvement = winner.improvement_percentage or 0
            if improvement > 10:
                recommendation = f"Strong recommendation: Deploy {winner.variant_name} ({improvement:.1f}% improvement)"
            elif improvement > 5:
                recommendation = f"Moderate recommendation: Consider deploying {winner.variant_name} ({improvement:.1f}% improvement)"
            else:
                recommendation = f"Weak signal: {winner.variant_name} shows minimal improvement ({improvement:.1f}%)"
        
        return cls(
            experiment_id=experiment_id,
            experiment_name=experiment_name,
            status=status,
            results=results,
            conclusion=conclusion,
            summary_stats=stats,
            recommendation=recommendation
        )
