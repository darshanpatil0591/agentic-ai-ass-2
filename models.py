from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    username: str
    role: str
    student_id: str | None = None


@dataclass(frozen=True)
class AgentResult:
    answer: str
    latency_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    tools: tuple[str, ...]

