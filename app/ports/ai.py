from typing import Protocol


class AIProvider(Protocol):
    def generate(self, prompt: str) -> tuple[str, dict[str, int]]:
        ...

