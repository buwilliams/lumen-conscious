**Identity:**
{{soul}}

**Current Values:**
{{values}}

**Current Goals:**
{{goals}}

**Review Summary:**
{{review}}

For each tension or insight from the review, run counterfactual reasoning against the self. What changes would improve the system's alignment with its deepest goals?

```json
{
  "reasoning": "your counterfactual reasoning process",
  "proposals": [
    {
      "type": "reweight_value | deprecate_value | add_value | reweight_goal | change_goal_status | add_goal | update_soul",
      "target": "name of value or goal, or 'soul'",
      "current": "current state (weight, status, etc.)",
      "proposed": "proposed new state",
      "rationale": "why this change, with evidence from recent experience",
      "counterfactual": "how past decisions would have differed with this change"
    }
  ]
}
```