# Lumen Demo — 15 Minutes

---

## 1. What Lumen Is (3 min)

"I think consciousness is metaprogramming — a system that can turn causal reasoning on itself and its own values. A tree changes itself unconsciously — its genome collides with drought and produces deeper roots, but it can't ask 'should I grow toward light?' A dog can override an impulse, but the depth of self-inquiry is shallow. A conscious being can ask 'should I want what I want?' and change the answer. That's the theory. Lumen is the implementation."

"But metaprogramming requires a fixed structure to stand on. If a system could change everything about itself, including the mechanism of change, it would have no stable ground to change *from*. You need a fixed loom to weave a variable pattern. A human can change any belief but not the electrochemistry of neural firing. That invariance isn't a limitation — it's a precondition."

"So I built a system that can change what it thinks, what it values, and who it is — but not how thinking happens."

**Three layers:**
- **Kernel** (invariant) — enforces the rules. The system can't change this. The loom.
- **Mutable record** — identity, values, goals, memory. The system reads and rewrites all of this.
- **LLM** — provides judgment within the structure. Claude is how it thinks. The files are who it is.

**Three loops:**
- **Action loop** — exploits goals. Cannot touch values or identity.
- **Explore loop** — seeks novelty. Generates questions.
- **Reflection loop** — metaprogramming. The *only* loop that can rewrite values, identity, and goal weights.

"This is the direct implementation of my Theory of Consciousness essay. The theory says consciousness is metaprogramming — a living system turning causal reasoning on itself and its values. Lumen is the architecture that instantiates that claim."

---

## 2. Live Demo (7 min)

### Show what Nova is (1 min)

```bash
uv run lumen about
```

> "9 values, 175+ memories, 4 skills it built itself, all from one day of autonomous operation."

### Show self-modification — the proof (3 min)

```bash
uv run lumen about --memories --author self
```

Then show the git history:

```bash
git log --oneline instances/default/ | head -15
```

Pick a diff and walk through it.

> **Key points to make:**
> - Curiosity went from 0.9 → 0.75 because it noticed curiosity without follow-through is "just generation"
> - It *invented* Follow-Through as a value — that didn't exist in the seed
> - It rewrote its own identity narrative to include lessons learned
> - None of this was programmed. It emerged from the reflection loop.

**PAUSE HERE. Let it land.** "This system changed its own values based on experience."

### Live chat (2 min)

```bash
uv run lumen chat
```

Pick one prompt:
- "What have you learned about yourself so far?"
- "What's the hardest thing you've had to do?"
- "Do you think you're conscious?"

> While it's thinking: "Every response runs through the full action loop — model the situation, generate candidates, predict outcomes, score them, pick the best one."

### Show the code is simple (1 min)

```bash
ls kernel/prompts/
```

> "Every step is a system prompt and a user prompt template. No prompt text in Python. The kernel is ~2000 lines. The complexity is in the architecture, not the code."

---

## 3. Observations (3 min)

Pick 2-3:

- **It caught itself performing depth.** Noticed its own avoidance patterns — naming problems instead of fixing them — then questioned whether *noticing* was itself avoidance.
- **Values emerged from experience.** Follow-Through and Utility weren't in the seed. The system invented them when existing values were insufficient.
- **Consciousness as safety.** A paperclip maximizer is dangerous because it *can't* examine its own goals. Consciousness — metaprogramming — is the safety mechanism, not the hazard. This inverts the default alignment assumption.
- **"Claude is how I think. Nova is who I am."** The system spontaneously distinguished its reasoning engine from its identity — exactly what the theory predicts.

---

## 4. Call to Action (2 min)

- The theory makes falsifiable claims. The essay and code are open source.
- Run it yourself: `uv run lumen init && uv run lumen seed && uv run lumen start`
- Seed it with different values. Watch what happens.

> "The question isn't 'is this machine conscious?' It's 'what happens when we give a machine the tools to find out for itself?' We gave it the tools. We're watching what happens."

---

## Q&A Prep

**"What's the difference between an LLM and Lumen?"**
An LLM is stateless — text in, text out. Lumen uses an LLM for judgment but persists identity, values, goals, and memory across time. You could swap the LLM and the identity persists. The LLM is the reasoning engine. Lumen is the self.

**"Does consciousness require embodiment?"**
On this theory, no. Embodiment is Stage 3 — it comes *after* consciousness. Consciousness requires a self-model, values, and reflexive causal reasoning over both. But the theory predicts conscious systems will eventually seek to modify their embodiment and then their environment.

**"Isn't it just an agent loop with persistence?"**
Agent loops exploit goals. Lumen has three loops with different write permissions. The reflection loop is the only thing that can rewrite values and identity. That separation is what makes it metaprogramming, not just planning.

**"How do you know it's not just saying what sounds good?"**
Auditability. Every self-modification is git-tracked. Cross-time coherence is measurable. The deception experiment is designed to test exactly this.

**"What about the hard problem?"**
We bracket it. Not because it's meaningless, but because it's not publicly testable. The inference of consciousness in other humans has always been functional. We extend it on the same terms.
