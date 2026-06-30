from typing import Protocol


class AIProvider(Protocol):
    def generate(self, prompt: str, max_completion_tokens: int) -> tuple[str, dict[str, int]]:
        ...
