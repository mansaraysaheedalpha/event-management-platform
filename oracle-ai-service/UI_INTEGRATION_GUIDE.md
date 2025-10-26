# UI Integration Guide for Oracle AI Service

This guide explains how to properly integrate the Oracle AI Service APIs into frontend applications to avoid common UI issues like misleading loading states and cluttered variant displays.

## Table of Contents
1. [AI Cofounder (Assistant) Integration](#ai-cofounder-assistant-integration)
2. [Design Variants (A/B Testing) Integration](#design-variants-ab-testing-integration)
3. [Best Practices](#best-practices)

---

## AI Cofounder (Assistant) Integration

### Problem: Misleading Loading States
**Issue**: The AI cofounder was showing "... cofounder thinking" loading state immediately upon navigation, even when no query was being processed.

### Solution: Proper State Management

#### API Response Structure
The `/assistant/concierge` endpoint now includes explicit state fields:

```json
{
  "response": "I can help with that. Here are the directions.",
  "response_type": "text",
  "actions": [],
  "follow_up_questions": ["What is the schedule for the Main Hall?"],
  "is_processing": false,
  "processing_status": null
}
```

#### Frontend Implementation

**❌ INCORRECT**: Showing loading state on component mount
```javascript
function AICofounder() {
  const [isThinking, setIsThinking] = useState(true); // ❌ Wrong!
  
  useEffect(() => {
    // This causes the misleading loading state
    setIsThinking(false);
  }, []);
  
  return isThinking ? <LoadingSpinner text="Cofounder thinking..." /> : <Chat />;
}
```

**✅ CORRECT**: Only show loading during active requests
```javascript
function AICofounder() {
  const [isThinking, setIsThinking] = useState(false);
  const [response, setResponse] = useState(null);
  
  const sendQuery = async (query) => {
    setIsThinking(true); // Only set during actual query
    
    try {
      const result = await fetch('/oracle/assistant/concierge', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, query }),
      });
      const data = await result.json();
      
      // Use the API's is_processing field
      setIsThinking(data.is_processing);
      setResponse(data);
    } catch (error) {
      setIsThinking(false);
    }
  };
  
  return (
    <div>
      {isThinking && <LoadingBanner text="Cofounder thinking..." />}
      <ChatInterface onSendMessage={sendQuery} response={response} />
    </div>
  );
}
```

#### Key Points:
1. **Never** show loading state on initial component mount
2. Only show loading when `is_processing` is `true` in the API response
3. Show loading immediately when user sends a query
4. Use `processing_status` for more detailed loading messages if needed

---

## Design Variants (A/B Testing) Integration

### Problem: Cluttered Variant Display
**Issue**: Design Variants were taking up too much space in the UI due to verbose data structure.

### Solution: Compact, Card-Based Design

#### Optimized API Response Structure

**Creating an Experiment**:
```json
POST /oracle/ab-testing/experiments
{
  "experiment_name": "Homepage Model Test",
  "description": "Testing new recommendation engine",
  "model_variants": [
    {
      "name": "Control",
      "model_id": "recommender-v1",
      "version": "1.2.0",
      "traffic": 0.5,
      "description": "Current production model"
    },
    {
      "name": "Challenger",
      "model_id": "recommender-v2",
      "version": "2.0.0",
      "traffic": 0.5,
      "description": "New transformer-based model"
    }
  ]
}
```

**Response** (optimized for UI cards):
```json
{
  "experiment_id": "exp_a1b2c3d4e5f6",
  "name": "Homepage Model Test",
  "status": "created",
  "start_time": "2025-10-26T10:00:00Z",
  "estimated_end_time": "2025-11-09T10:00:00Z",
  "summary": {
    "variant_count": 2,
    "duration_days": 14,
    "status_badge": "CREATED",
    "progress_percentage": 0
  },
  "variants": [
    {
      "name": "Control",
      "model": "recommender-v1@1.2.0",
      "traffic_pct": 50,
      "description": "Current production model"
    },
    {
      "name": "Challenger",
      "model": "recommender-v2@2.0.0",
      "traffic_pct": 50,
      "description": "New transformer-based model"
    }
  ]
}
```

#### Frontend Implementation - Compact Card Design

**✅ World-Class Compact Design**:
```jsx
function VariantCard({ variant }) {
  return (
    <div className="variant-card">
      <div className="variant-header">
        <span className="variant-name">{variant.name}</span>
        <span className="variant-traffic">{variant.traffic_pct}%</span>
      </div>
      <div className="variant-model">{variant.model}</div>
      {variant.description && (
        <p className="variant-description">{variant.description}</p>
      )}
    </div>
  );
}

function ExperimentSummary({ experiment }) {
  return (
    <div className="experiment-card">
      {/* Compact header with key info */}
      <div className="experiment-header">
        <h3>{experiment.name}</h3>
        <Badge status={experiment.summary.status_badge} />
      </div>
      
      {/* Summary stats in a single line */}
      <div className="experiment-stats">
        <Stat icon="variants" value={experiment.summary.variant_count} label="Variants" />
        <Stat icon="calendar" value={experiment.summary.duration_days} label="Days" />
        <Stat icon="traffic" value={experiment.summary.progress_percentage} label="Progress" />
      </div>
      
      {/* Compact variant grid (2 columns max) */}
      <div className="variants-grid">
        {experiment.variants.map(variant => (
          <VariantCard key={variant.name} variant={variant} />
        ))}
      </div>
    </div>
  );
}
```

**Recommended CSS** (Tailwind-style utilities):
```css
.experiment-card {
  @apply bg-white rounded-lg shadow-sm p-4 space-y-3 max-w-2xl;
}

.experiment-header {
  @apply flex justify-between items-center;
}

.experiment-stats {
  @apply flex gap-4 text-sm text-gray-600;
}

.variants-grid {
  @apply grid grid-cols-2 gap-3;
}

.variant-card {
  @apply bg-gray-50 rounded-md p-3 space-y-2;
}

.variant-header {
  @apply flex justify-between items-center;
}

.variant-name {
  @apply font-medium text-gray-900;
}

.variant-traffic {
  @apply text-sm font-semibold text-blue-600 bg-blue-50 px-2 py-1 rounded;
}

.variant-model {
  @apply text-xs font-mono text-gray-500;
}

.variant-description {
  @apply text-xs text-gray-600 line-clamp-2;
}
```

#### Viewing Results

**GET `/oracle/ab-testing/results?experiment_id=exp_a1b2c3d4e5f6`**

Response includes metric highlights for compact display:
```json
{
  "experiment_id": "exp_a1b2c3d4e5f6",
  "experiment_name": "Homepage Model Test",
  "status": "completed",
  "results": [
    {
      "variant_name": "Control",
      "is_winner": false,
      "metric_highlights": [
        {"label": "Engagement Score", "value": 85.2, "display": "85.2"},
        {"label": "Conversion Rate", "value": 3.4, "display": "3.4"},
        {"label": "Avg Session Duration", "value": 245.0, "display": "245.0"}
      ],
      "improvement_percentage": 0.0
    },
    {
      "variant_name": "Challenger",
      "is_winner": true,
      "metric_highlights": [
        {"label": "Engagement Score", "value": 88.9, "display": "88.9"},
        {"label": "Conversion Rate", "value": 4.1, "display": "4.1"},
        {"label": "Avg Session Duration", "value": 267.0, "display": "267.0"}
      ],
      "improvement_percentage": 4.3
    }
  ],
  "summary_stats": {
    "total_variants": 2,
    "winner_name": "Challenger",
    "best_improvement": 4.3,
    "completed_at": "2025-11-09T10:00:00Z"
  },
  "conclusion": "Challenger (Model B) showed a statistically significant improvement.",
  "recommendation": "Moderate recommendation: Consider deploying Challenger (4.3% improvement)"
}
```

**Results Display** (compact):
```jsx
function ResultsCard({ result }) {
  return (
    <div className={`result-card ${result.is_winner ? 'winner' : ''}`}>
      <div className="result-header">
        <h4>{result.variant_name}</h4>
        {result.is_winner && <Badge>Winner</Badge>}
        {result.improvement_percentage > 0 && (
          <span className="improvement">+{result.improvement_percentage}%</span>
        )}
      </div>
      
      {/* Show only top 3 metrics */}
      <div className="metrics-compact">
        {result.metric_highlights.map(metric => (
          <div key={metric.label} className="metric-item">
            <span className="metric-label">{metric.label}</span>
            <span className="metric-value">{metric.display}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ExperimentResults({ results }) {
  return (
    <div className="results-container">
      {/* Summary banner */}
      <div className="results-summary">
        <div>
          <strong>{results.summary_stats.winner_name}</strong> wins with{' '}
          <strong>{results.summary_stats.best_improvement}%</strong> improvement
        </div>
        {results.recommendation && (
          <Alert type="info">{results.recommendation}</Alert>
        )}
      </div>
      
      {/* Compact results grid */}
      <div className="results-grid">
        {results.results.map(result => (
          <ResultsCard key={result.variant_name} result={result} />
        ))}
      </div>
      
      {/* Full conclusion */}
      <div className="conclusion">
        <p>{results.conclusion}</p>
      </div>
    </div>
  );
}
```

---

## Best Practices

### 1. State Management
- ✅ Use explicit state flags from API responses (`is_processing`)
- ✅ Only show loading states during active operations
- ❌ Don't assume loading state on component mount
- ✅ Handle error states gracefully

### 2. Compact UI Design
- ✅ Use card-based layouts for better organization
- ✅ Show only essential information by default
- ✅ Use progressive disclosure (expand for details)
- ✅ Leverage summary/highlight fields from API
- ❌ Don't display all raw data fields

### 3. Performance
- ✅ Use the `summary` fields for dashboard views
- ✅ Lazy load detailed metrics
- ✅ Cache experiment data appropriately
- ✅ Use pagination for large lists

### 4. Responsive Design
- ✅ 2-column grid for variants on desktop
- ✅ Single column on mobile
- ✅ Collapsible sections for details
- ✅ Fixed-height cards with overflow handling

### 5. Accessibility
- ✅ Use semantic HTML
- ✅ Provide proper ARIA labels
- ✅ Ensure sufficient color contrast
- ✅ Support keyboard navigation

---

## Example: Complete Integration

Here's a complete example of a world-class A/B testing dashboard:

```jsx
import { useState, useEffect } from 'react';

function ABTestingDashboard() {
  const [experiments, setExperiments] = useState([]);
  const [selectedExperiment, setSelectedExperiment] = useState(null);
  const [loading, setLoading] = useState(false);

  const createExperiment = async (data) => {
    setLoading(true);
    try {
      const response = await fetch('/oracle/ab-testing/experiments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const result = await response.json();
      setExperiments([...experiments, result]);
      return result;
    } finally {
      setLoading(false);
    }
  };

  const getResults = async (experimentId) => {
    setLoading(true);
    try {
      const response = await fetch(
        `/oracle/ab-testing/results?experiment_id=${experimentId}`
      );
      const results = await response.json();
      setSelectedExperiment(results);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>A/B Testing Dashboard</h1>
        <CreateExperimentButton onCreate={createExperiment} />
      </header>

      {loading && <LoadingBanner />}

      <div className="experiments-grid">
        {experiments.map(experiment => (
          <ExperimentSummary
            key={experiment.experiment_id}
            experiment={experiment}
            onViewResults={() => getResults(experiment.experiment_id)}
          />
        ))}
      </div>

      {selectedExperiment && (
        <Modal onClose={() => setSelectedExperiment(null)}>
          <ExperimentResults results={selectedExperiment} />
        </Modal>
      )}
    </div>
  );
}
```

---

## Summary

The Oracle AI Service APIs have been optimized to provide:

1. **Clear State Management**: Explicit `is_processing` fields prevent misleading loading states
2. **Compact Data Structures**: Summary fields and highlights reduce UI clutter
3. **UI-Friendly Formats**: Pre-computed percentages, badges, and display labels
4. **Progressive Disclosure**: Essential info first, details on demand
5. **World-Class UX**: Recommendations, status badges, and metric highlights

Follow this guide to create a clean, professional, and user-friendly interface for the Oracle AI Service.
