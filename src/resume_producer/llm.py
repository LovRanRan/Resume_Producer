"""LLM 单入口：所有 Claude 调用经此模块，统一模型/effort/refusal 处理/用量统计。"""

from __future__ import annotations

import os
from dataclasses import dataclass

from pydantic import BaseModel

MODEL = os.environ.get("RESUME_MODEL", "claude-opus-5")
# claude-opus-5 定价（$/token）
INPUT_PRICE = 5.0 / 1_000_000
OUTPUT_PRICE = 25.0 / 1_000_000

class LLMError(RuntimeError):
    pass


@dataclass
class UsageTracker:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def record(self, usage) -> None:
        self.calls += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    @property
    def cost_usd(self) -> float:
        return self.input_tokens * INPUT_PRICE + self.output_tokens * OUTPUT_PRICE


_client = None


def get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic
        from dotenv import load_dotenv

        load_dotenv()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise LLMError("未找到 ANTHROPIC_API_KEY。请 `cp .env.example .env` 并填入 key。")
        _client = Anthropic()
    return _client


def parse_structured[T: BaseModel](
    system: str,
    prompt: str,
    schema: type[T],
    usage: UsageTracker,
    effort: str | None = None,
    max_tokens: int = 16000,
) -> T:
    """结构化输出调用：返回校验过的 Pydantic 实例。"""
    client = get_client()
    kwargs: dict = {}
    if effort:
        kwargs["output_config"] = {"effort": effort}
    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            **kwargs,
        )
    except TypeError:
        # 旧版 SDK 不接受 output_config 与 parse 并用时退化为默认 effort
        response = client.messages.parse(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
    if response.stop_reason == "refusal":
        raise LLMError("模型拒绝了该请求（stop_reason=refusal），请检查 JD 内容。")
    if response.stop_reason == "max_tokens":
        raise LLMError("输出被 max_tokens 截断，请重试或简化输入。")
    usage.record(response.usage)
    parsed = response.parsed_output
    if parsed is None:
        raise LLMError("结构化输出解析失败。")
    return parsed
