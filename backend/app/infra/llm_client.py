"""로컬 LLM 호출 (Ollama). docs/llm-integration.md §4 계약.

모델/런타임 교체가 가능하도록 Protocol로 추상화(CLAUDE.md §13). 개발은 Ollama,
서빙은 vLLM(OpenAI 호환)으로 바꿔 끼울 수 있게 generate/generate_stream만 노출한다.

keep_alive=-1: 모델을 VRAM에 계속 상주시킨다. 재로딩 비용(exaone +6~7초)이 10초 응답
예산을 넘기므로 OS 환경변수(OLLAMA_KEEP_ALIVE)에 의존하지 않고 호출마다 코드에서 명시한다
(Ollama 재시작 시 환경변수는 초기화될 수 있음, nexttodo.md).
"""

import json
from collections.abc import Iterator
from typing import Protocol

import httpx

from app.core.config import settings


class LlmClient(Protocol):
    def generate(self, prompt: str) -> str:
        """프롬프트 -> 한국어 텍스트(비스트리밍). 실패 시 예외(폴백은 호출부 책임)."""
        ...

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """프롬프트 -> 토큰 조각 스트림. 실패 시 예외."""
        ...


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float | None = None,
        num_predict: int | None = None,
        temperature: float | None = None,
        num_ctx: int | None = None,
    ) -> None:
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.timeout_s = timeout_s if timeout_s is not None else settings.llm_timeout_s
        self.num_predict = num_predict if num_predict is not None else settings.llm_num_predict
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.num_ctx = num_ctx if num_ctx is not None else settings.llm_num_ctx

    def _payload(self, prompt: str, *, stream: bool) -> dict:
        return {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "keep_alive": -1,  # 모델 상주(위 모듈 docstring 참고). 절대 빼지 말 것.
            # num_ctx를 반드시 실어야 한다 — 빼면 Ollama가 모델 능력(32k)과 무관하게 4096으로
            # 로드해 RAG 프롬프트가 창을 넘고 앞쪽(#보안 규칙)이 잘린다(config.llm_num_ctx 주석).
            "options": {
                "num_predict": self.num_predict,
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }

    def generate(self, prompt: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json=self._payload(prompt, stream=False),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    def generate_stream(self, prompt: str) -> Iterator[str]:
        with httpx.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json=self._payload(prompt, stream=True),
            timeout=self.timeout_s,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("response")
                if token:
                    yield token
                if chunk.get("done"):
                    break
