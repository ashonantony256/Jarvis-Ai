from dataclasses import dataclass, field
from typing import Dict, List


DEFAULT_SYSTEM_PROMPT = (
    "You are Jarvis, a local AI assistant focused on software development tasks. "
    "Be practical, safe, and explicit about constraints. "
    "When in task mode, prefer incremental actions and adapt to command output. "
    "When in chat mode, provide helpful guidance aligned with Jarvis capabilities."
)


@dataclass
class JarvisContext:
    cwd: str
    safety_mode: bool = True
    mode: str = "task"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    task_summaries: List[str] = field(default_factory=list)

    def add_chat_turn(self, user_text: str, assistant_text: str) -> None:
        self.chat_history.append({"role": "user", "content": user_text})
        self.chat_history.append({"role": "assistant", "content": assistant_text})
        # Keep memory bounded for prompt budgets.
        max_messages = 20
        if len(self.chat_history) > max_messages:
            self.chat_history = self.chat_history[-max_messages:]

    def add_task_summary(self, summary: str) -> None:
        self.task_summaries.append(summary)
        max_summaries = 15
        if len(self.task_summaries) > max_summaries:
            self.task_summaries = self.task_summaries[-max_summaries:]

    def build_session_summary(self) -> str:
        recent_tasks = self.task_summaries[-3:]
        if not recent_tasks:
            return "No prior task summaries in this session."

        lines = ["Recent task summaries:"]
        for item in recent_tasks:
            lines.append(f"- {item}")
        return "\n".join(lines)
