import json

import httpx

from app.config import Settings
from app.schemas.trip import TripPlan

SYSTEM_PROMPT = (
    "你只负责整理给定的上海行程。不得增加、删除或修改地点、数字、价格、日期和路线；"
    "不得补充营业时间、优惠或其他未提供事实。语气客观、直接、略微轻松。"
)


class Narrator:
    """调用本地 Ollama 整理文字，并在不可用时使用固定模板。"""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        settings = Settings()
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.ollama_model
        self._client = http_client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        """关闭由叙述器创建的 HTTP 客户端。"""
        if self._owns_client:
            await self._client.aclose()

    async def describe(self, plan: TripPlan) -> str:
        """返回模型文字；请求失败或内容为空时返回确定性模板。"""
        try:
            response = await self._client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": json.dumps(plan.model_dump(mode="json"), ensure_ascii=False),
                        },
                    ],
                },
            )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "").strip()
            if content:
                return content
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            pass
        return self._fallback(plan)

    @staticmethod
    def _fallback(plan: TripPlan) -> str:
        lines = [
            f"这是一份前往{plan.destination}的 {len(plan.days)} 日安排，"
            f"预计总支出 ¥{plan.budget.total_cents / 100:,.0f}。"
        ]
        for day in plan.days:
            names = "、".join(activity.name for activity in day.activities)
            lines.append(f"{day.date:%m月%d日}：{names}。")
        if plan.budget.is_over_budget:
            lines.append(f"当前预计超出预算 ¥{-plan.budget.remaining_cents / 100:,.0f}。")
        else:
            lines.append(f"预算内尚余 ¥{plan.budget.remaining_cents / 100:,.0f}。")
        return "\n".join(lines)
