"""
Thompson Sampling for Intervention Selection

Implements multi-armed bandit algorithm to learn which interventions work best
in different contexts. Uses Bayesian approach with Beta distributions.

Key Concepts:
- Each intervention type (POLL, CHAT_PROMPT, etc.) is an "arm"
- Track successes (α) and failures (β) per intervention type per context
- Sample from Beta(α, β) to balance exploration vs exploitation
- Context includes: anomaly type, engagement level, time of day, session size
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class InterventionType(str, Enum):
    POLL = "POLL"
    CHAT_PROMPT = "CHAT_PROMPT"
    NOTIFICATION = "NOTIFICATION"
    GAMIFICATION = "GAMIFICATION"


class AnomalyType(str, Enum):
    SUDDEN_DROP = "SUDDEN_DROP"
    GRADUAL_DECLINE = "GRADUAL_DECLINE"
    MASS_EXIT = "MASS_EXIT"
    LOW_ENGAGEMENT = "LOW_ENGAGEMENT"


@dataclass
class ContextKey:
    """
    Defines the context for Thompson Sampling.
    Interventions are tracked separately per context.
    """
    anomaly_type: AnomalyType
    engagement_bucket: str  # 'critical', 'low', 'medium'
    session_size_bucket: str  # 'small', 'medium', 'large'

    def to_string(self) -> str:
        return f"{self.anomaly_type}_{self.engagement_bucket}_{self.session_size_bucket}"


@dataclass
class InterventionStats:
    """Statistics for a single intervention type in a specific context"""
    intervention_type: InterventionType
    context: ContextKey
    alpha: float  # Successes + 1 (prior)
    beta: float   # Failures + 1 (prior)
    total_attempts: int
    last_updated: datetime

    @property
    def success_rate(self) -> float:
        """Expected success rate (mean of Beta distribution)"""
        return self.alpha / (self.alpha + self.beta)

    @property
    def confidence_interval(self) -> Tuple[float, float]:
        """95% credible interval for success rate"""
        # Using Beta distribution quantiles
        from scipy.stats import beta as beta_dist
        dist = beta_dist(self.alpha, self.beta)
        return (dist.ppf(0.025), dist.ppf(0.975))

    def sample(self) -> float:
        """Sample from Beta(α, β) for Thompson Sampling"""
        return np.random.beta(self.alpha, self.beta)


class ThompsonSampling:
    """
    Thompson Sampling for intervention selection.

    Learns which interventions work best in different contexts by:
    1. Maintaining Beta distributions for each intervention-context pair
    2. Sampling from these distributions to select interventions
    3. Updating distributions based on outcomes

    Usage:
        ts = ThompsonSampling()

        # Select intervention
        context = ts.create_context(anomaly_type, engagement_score, active_users)
        intervention = ts.select_intervention(context)

        # After execution, update with outcome
        ts.update(context, intervention, success=True, reward=0.15)
    """

    def __init__(self, alpha_prior: float = 1.0, beta_prior: float = 1.0):
        """
        Initialize Thompson Sampling.

        Args:
            alpha_prior: Prior successes (default 1.0 = uniform prior)
            beta_prior: Prior failures (default 1.0 = uniform prior)
        """
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior

        # Statistics storage: {context_key: {intervention_type: InterventionStats}}
        self.stats: Dict[str, Dict[InterventionType, InterventionStats]] = {}

        logger.info(f"ThompsonSampling initialized with prior α={alpha_prior}, β={beta_prior}")

    def create_context(
        self,
        anomaly_type: AnomalyType,
        engagement_score: float,
        active_users: int
    ) -> ContextKey:
        """
        Create context key from current session state.

        Args:
            anomaly_type: Type of anomaly detected
            engagement_score: Current engagement score (0-100)
            active_users: Number of active users

        Returns:
            ContextKey for looking up intervention statistics
        """
        # Bucket engagement score
        if engagement_score < 30:
            engagement_bucket = 'critical'
        elif engagement_score < 50:
            engagement_bucket = 'low'
        else:
            engagement_bucket = 'medium'

        # Bucket session size
        if active_users < 10:
            session_size_bucket = 'small'
        elif active_users < 50:
            session_size_bucket = 'medium'
        else:
            session_size_bucket = 'large'

        return ContextKey(
            anomaly_type=anomaly_type,
            engagement_bucket=engagement_bucket,
            session_size_bucket=session_size_bucket
        )

    def select_intervention(
        self,
        context: ContextKey,
        available_interventions: Optional[List[InterventionType]] = None
    ) -> Tuple[InterventionType, float]:
        """
        Select intervention using Thompson Sampling.

        Args:
            context: Current context
            available_interventions: List of available interventions (default: all)

        Returns:
            Tuple of (selected_intervention, sampled_value)
        """
        if available_interventions is None:
            available_interventions = list(InterventionType)

        context_key = context.to_string()

        # Initialize context if first time
        if context_key not in self.stats:
            self._initialize_context(context_key, context)

        # Sample from Beta distributions for each intervention
        samples = {}
        for intervention_type in available_interventions:
            stats = self.stats[context_key][intervention_type]
            samples[intervention_type] = stats.sample()

        # Select intervention with highest sample
        selected = max(samples.items(), key=lambda x: x[1])

        logger.info(
            f"Thompson Sampling selected {selected[0]} (sample={selected[1]:.3f}) "
            f"for context {context_key}"
        )
        logger.debug(f"All samples: {samples}")

        return selected

    def update(
        self,
        context: ContextKey,
        intervention_type: InterventionType,
        success: bool,
        reward: Optional[float] = None
    ):
        """
        Update intervention statistics after execution.

        Args:
            context: Context in which intervention was executed
            intervention_type: Type of intervention that was executed
            success: Whether intervention was successful
            reward: Optional reward signal (engagement delta, 0-1 scale)
        """
        context_key = context.to_string()

        if context_key not in self.stats:
            self._initialize_context(context_key, context)

        stats = self.stats[context_key][intervention_type]

        # Update Beta distribution parameters
        if success:
            # If reward provided, use it to scale the update
            if reward is not None:
                stats.alpha += reward
            else:
                stats.alpha += 1.0
        else:
            stats.beta += 1.0

        stats.total_attempts += 1
        stats.last_updated = datetime.utcnow()

        logger.info(
            f"Updated {intervention_type} in context {context_key}: "
            f"α={stats.alpha:.2f}, β={stats.beta:.2f}, "
            f"success_rate={stats.success_rate:.3f}"
        )

    def get_stats(
        self,
        context: ContextKey,
        intervention_type: InterventionType
    ) -> Optional[InterventionStats]:
        """Get statistics for specific intervention-context pair"""
        context_key = context.to_string()
        if context_key not in self.stats:
            return None
        return self.stats[context_key].get(intervention_type)

    def get_all_stats(self, context: ContextKey) -> Dict[InterventionType, InterventionStats]:
        """Get all statistics for a context"""
        context_key = context.to_string()
        if context_key not in self.stats:
            self._initialize_context(context_key, context)
        return self.stats[context_key]

    def get_best_intervention(
        self,
        context: ContextKey
    ) -> Tuple[InterventionType, float]:
        """
        Get intervention with highest expected success rate (no sampling).
        Useful for "exploit" mode or reporting.

        Returns:
            Tuple of (best_intervention, success_rate)
        """
        context_key = context.to_string()
        if context_key not in self.stats:
            self._initialize_context(context_key, context)

        best = max(
            self.stats[context_key].items(),
            key=lambda x: x[1].success_rate
        )

        return (best[0], best[1].success_rate)

    def _initialize_context(self, context_key: str, context: ContextKey):
        """Initialize statistics for a new context"""
        self.stats[context_key] = {}

        for intervention_type in InterventionType:
            self.stats[context_key][intervention_type] = InterventionStats(
                intervention_type=intervention_type,
                context=context,
                alpha=self.alpha_prior,
                beta=self.beta_prior,
                total_attempts=0,
                last_updated=datetime.utcnow()
            )

        logger.info(f"Initialized new context: {context_key}")

    def export_stats(self) -> Dict:
        """Export all statistics for persistence/analysis"""
        export = {}
        for context_key, context_stats in self.stats.items():
            export[context_key] = {}
            for intervention_type, stats in context_stats.items():
                export[context_key][intervention_type.value] = {
                    'alpha': stats.alpha,
                    'beta': stats.beta,
                    'total_attempts': stats.total_attempts,
                    'success_rate': stats.success_rate,
                    'confidence_interval': stats.confidence_interval,
                    'last_updated': stats.last_updated.isoformat()
                }
        return export

    def import_stats(self, data: Dict):
        """Import statistics from persistence"""
        for context_key, context_data in data.items():
            # Parse context from key
            parts = context_key.split('_')
            if len(parts) != 3:
                logger.warning(f"Invalid context key format: {context_key}")
                continue

            context = ContextKey(
                anomaly_type=AnomalyType(parts[0]),
                engagement_bucket=parts[1],
                session_size_bucket=parts[2]
            )

            self.stats[context_key] = {}

            for intervention_str, stats_data in context_data.items():
                intervention_type = InterventionType(intervention_str)
                self.stats[context_key][intervention_type] = InterventionStats(
                    intervention_type=intervention_type,
                    context=context,
                    alpha=stats_data['alpha'],
                    beta=stats_data['beta'],
                    total_attempts=stats_data['total_attempts'],
                    last_updated=datetime.fromisoformat(stats_data['last_updated'])
                )

        logger.info(f"Imported statistics for {len(self.stats)} contexts")


# Global Thompson Sampling instance
_thompson_sampling_instance: Optional[ThompsonSampling] = None


def get_thompson_sampling() -> ThompsonSampling:
    """Get or create global Thompson Sampling instance"""
    global _thompson_sampling_instance
    if _thompson_sampling_instance is None:
        _thompson_sampling_instance = ThompsonSampling()
    return _thompson_sampling_instance
