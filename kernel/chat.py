import uuid
from datetime import datetime

from kernel import data
from kernel.context import compact_history, format_history
from kernel.log import dim
from kernel.loop_action import run_action_loop


def _log(msg: str):
    """Print a dim kernel progress message to stderr."""
    dim(f"  [kernel] {msg}")


class ChatSession:
    """Manages a conversation session.

    Each turn: record user input as external memory -> run the full action loop
    (MODEL -> CANDIDATES -> PREDICT -> DECIDE -> ACT -> RECORD) -> return response.

    Conversation history is maintained for continuity across turns.
    When history grows too long, older turns are compacted into a summary.
    """

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        self.history: list[dict] = []
        self.summary: str = ""

        if session_id:
            # Load existing session
            turns = data.read_conversation(session_id)
            for turn in turns:
                self.history.append({"role": turn.role, "content": turn.content})

        data.create_conversation(self.session_id)

    def turn(self, user_input: str) -> str:
        """Process one user turn through the full action loop."""
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

        # Compact history if it's grown too long
        self.history, self.summary = compact_history(self.history, self.summary)

        # Build conversation history string for context
        conversation_history = format_history(self.history, self.summary)

        # Run the full action loop: MODEL -> CANDIDATES -> PREDICT -> DECIDE -> ACT -> RECORD
        result = run_action_loop(
            situation=f"User said: {user_input}",
            conversation_history=conversation_history,
        )

        response = result.get("response") or "I'm not sure how to respond."

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
