**Candidates to score:**
{{candidates}}

**Values (with weights):**
{{values}}

**Active Goals (with weights):**
{{goals}}

**Available Skills:**
{{skills}}

Score each candidate using B=MAP and select the best action.

```json
{
  "scores": [
    {
      "action": "action description",
      "M": 0.0,
      "A": 0.0,
      "P": 0.0,
      "B": 0.0,
      "rationale": "why these scores"
    }
  ],
  "selected": {
    "action": "selected action description",
    "skill": "skill to invoke or respond",
    "response": "if responding directly, the response text",
    "prediction": "predicted outcome"
  }
}
```