**Current Identity:**
{{soul}}

**Current Values:**
{{values}}

**Current Goals:**
{{goals}}

**Proposed Changes:**
{{proposals}}

Consistency-check these proposals. Resolve any contradictions. Then produce the final changes to apply.

```json
{
  "conflicts": [
    {
      "description": "what conflicts",
      "resolution": "how it was resolved",
      "kept": "which proposal was kept",
      "dropped": "which proposal was dropped"
    }
  ],
  "changes": [
    {
      "type": "reweight_value | deprecate_value | add_value | reweight_goal | change_goal_status | add_goal | update_soul",
      "target": "name or soul",
      "new_value": "the new weight, status, or soul text",
      "rationale": "final rationale for this change"
    }
  ],
  "soul_update": "if soul.md should be updated, the complete new text (or null if no change)"
}
```