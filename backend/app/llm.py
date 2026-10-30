"""Provider interface. To add another provider, implement LLMProvider and change get_llm()."""
from functools import lru_cache
from typing import Iterator, Protocol

from .config import GEMINI_API_KEY, GEMINI_MODEL

# Events yielded by stream():
#   ("text", str) | ("tool_call", name, args_dict) | ("usage", prompt_tokens, completion_tokens)


class LLMProvider(Protocol):
    def stream(self, system: str, user: str, tools: list[dict] | None = None,
               force_tool: bool = False) -> Iterator[tuple]: ...

    def complete(self, system: str, user: str) -> str: ...


class GeminiProvider:
    def __init__(self):
        from google import genai
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL

    def stream(self, system, user, tools=None, force_tool=False):
        from google.genai import types
        cfg = {"system_instruction": system, "temperature": 0.2}
        if tools:
            decls = [types.FunctionDeclaration(name=t["name"], description=t["description"],
                                               parameters_json_schema=t["parameters"]) for t in tools]
            cfg["tools"] = [types.Tool(function_declarations=decls)]
            cfg["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
            if force_tool:
                cfg["tool_config"] = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="ANY"))
        prompt_tokens = completion_tokens = 0
        for chunk in self.client.models.generate_content_stream(
                model=self.model, contents=user, config=types.GenerateContentConfig(**cfg)):
            um = chunk.usage_metadata
            if um:
                prompt_tokens = um.prompt_token_count or prompt_tokens
                completion_tokens = um.candidates_token_count or completion_tokens
            for cand in chunk.candidates or []:
                parts = cand.content.parts if cand.content and cand.content.parts else []
                for part in parts:
                    if part.function_call:
                        yield ("tool_call", part.function_call.name, dict(part.function_call.args or {}))
                    elif part.text:
                        yield ("text", part.text)
        yield ("usage", prompt_tokens, completion_tokens)

    def complete(self, system, user):
        from google.genai import types
        r = self.client.models.generate_content(
            model=self.model, contents=user,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0))
        return r.text or ""


@lru_cache(maxsize=1)
def get_llm() -> LLMProvider:
    return GeminiProvider()
