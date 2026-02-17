**Recent Memories (since last reflection):**
{{memories}}

**Recent Prediction Errors:**
{{prediction_errors}}

**Cycles Since Last Reflection:**
{{cycles_since_reflection}}

**Reflection Cycle Interval:**
{{reflection_interval}}

**Prediction Error Threshold:**
{{prediction_error_threshold}}

Evaluate whether to trigger reflection. Check each condition:
1. Any prediction error with absolute value above {{prediction_error_threshold}}?
2. Any value tensions in recent actions?
3. Any goals completed or stale?
4. Has it been {{reflection_interval}} or more cycles since last reflection?
5. Any explicit request for self-examination?

```json
{
  "should_reflect": true,
  "triggers": ["list of trigger conditions that fired"],
  "rationale": "why reflection should or should not happen"
}
```
