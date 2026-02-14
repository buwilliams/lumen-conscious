**Identity:**
{{soul}}

**Values:**
{{values}}

**Active Goals:**
{{goals}}

**Recent Memories:**
{{memories}}

**Current Situation:**
{{situation}}

{{conversation_history}}

Analyze this situation. Generate 1-3 candidate actions with predicted outcomes.

```json
{
  "analysis": "your analysis of the situation",
  "candidates": [
    {
      "action": "description of the action",
      "skill": "respond or skill_name",
      "values": ["value names this serves"],
      "goals": ["goal names this serves"],
      "prediction": "predicted outcome if this action is taken",
      "response": "if skill is respond, the actual response text"
    }
  ]
}
```