class MockAIProvider:
    def generate(self, prompt: str, max_completion_tokens: int) -> tuple[str, dict[str, int]]:
        if "[fail]" in prompt:
            raise RuntimeError("mock AI failure")

        prompt_tokens = max(1, len(prompt.split()))
        extra_completion = 4 if "[over]" in prompt else 0
        completion_tokens = max_completion_tokens + extra_completion
        response = f"mock-response: {prompt[:64]}"
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        return response, usage
