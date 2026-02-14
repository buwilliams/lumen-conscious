import uuid
from datetime import datetime

from kernel import data
from kernel.loops import run_action_loop


class ChatSession:
    """Manages a conversation session.

    Each turn: record user input as external memory → pass it as the situation
    to the action loop → the action loop runs its full cycle (THINK → DECIDE →
    ACT → RECORD) → return whatever the loop produces.

    Conversation history is maintained for continuity across turns.
    """

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        self.history: list[dict] = []

        if session_id:
            # Load existing session
            turns = data.read_conversation(session_id)
            for turn in turns:
                self.history.append({"role": turn.role, "content": turn.content})

        data.create_conversation(self.session_id)

    def turn(self, user_input: str) -> str:
        """Process one user turn through the action loop."""
        # Record user input as external memory
        data.append_memory(data.make_memory(
            author="external",
            weight=0.7,
            situation="chat",
            description=f"User said: {user_input}",
        ))

        # Store conversation turn
        data.append_turn(self.session_id, data.ConversationTurn(
            role="user",
            content=user_input,
            timestamp=datetime.now().isoformat(),
        ))
        self.history.append({"role": "user", "content": user_input})

        # Build conversation history string for context
        conversation_history = self._format_history()

        # Run the action loop with user input as the situation
        result = run_action_loop(
            situation=f"User said: {user_input}",
            conversation_history=conversation_history,
        )

        response = result.get("response") or result.get("result") or "I'm not sure how to respond."

        # Record response as self memory
        data.append_memory(data.make_memory(
            author="self",
            weight=0.6,
            situation="chat",
            description=f"Responded: {response[:500]}",
        ))

        # Store assistant turn
        data.append_turn(self.session_id, data.ConversationTurn(
            role="assistant",
            content=response,
            timestamp=datetime.now().isoformat(),
        ))
        self.history.append({"role": "assistant", "content": response})

        return response

    def _format_history(self) -> str:
        """Format conversation history for inclusion in prompts."""
        if not self.history:
            return ""
        lines = ["\n**Conversation History:**"]
        for turn in self.history[-20:]:  # Last 20 turns max
            role = "User" if turn["role"] == "user" else "Lumen"
            lines.append(f"{role}: {turn['content']}")
        return "\n".join(lines)
