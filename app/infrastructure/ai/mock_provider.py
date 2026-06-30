class MockAIProvider:
    def generate(self, prompt: str) -> tuple[str, dict[str, int]]:
        response = f"mock-response: {prompt[:64]}"
        usage = {
            "prompt_tokens": max(1, len(prompt.split())),
            "completion_tokens": 12,
            "total_tokens": max(1, len(prompt.split())) + 12,
        }
        return response, usage

