**What was predicted:**
{{prediction}}

**Expected outcome score:** {{expected_outcome}}

**What actually happened:**
{{outcome}}

Rate the actual outcome on the -1.0 to +1.0 scale, then compute the signed prediction error.

```json
{
  "outcome_score": 0.0,
  "prediction_error": 0.0,
  "surprise": "what was unexpected, if anything",
  "learning": "what this reveals about the world model"
}
```

- outcome_score: -1.0 (worst) to +1.0 (best) — how well did this actually go?
- prediction_error: outcome_score minus expected_outcome (positive = better than expected, negative = worse than expected)
