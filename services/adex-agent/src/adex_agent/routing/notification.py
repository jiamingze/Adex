"""Semantic user notification preferences; never inferred from a model answer's wording."""

import asyncio
import json
from decimal import Decimal, InvalidOperation
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from adex_kernel.text import strip_json_fence


class NotificationCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=1000)
    operator: Literal["semantic", "lt", "lte", "gt", "gte", "eq"] = "semantic"
    threshold: str = Field(default="", max_length=50)
    unit: str = Field(default="", max_length=40)

    @model_validator(mode="after")
    def valid(self):
        if self.operator != "semantic":
            try:
                if not Decimal(self.threshold).is_finite() or not self.unit.strip():
                    raise ValueError()
            except (InvalidOperation, ValueError):
                raise ValueError("Numeric condition needs a finite threshold and explicit unit") from None
        elif self.threshold or self.unit:
            raise ValueError("Semantic condition has no numeric operands")
        return self


class NotificationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notification_policy: Literal["EVERY_RUN", "CHANGES_ONLY", "CONDITION_MET"] = "EVERY_RUN"
    notification_condition: NotificationCondition | None = None
    clarification: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def valid(self):
        if not self.clarification and (self.notification_policy == "CONDITION_MET") != (
            self.notification_condition is not None
        ):
            raise ValueError("Condition and policy must agree")
        return self


async def notification_plan(runtime, owner, key, text):
    prompt = (
        "NOTIFICATION_PLAN_V1: 只解释用户的通知偏好，返回JSON："
        '{"notification_policy":"EVERY_RUN|CHANGES_ONLY|CONDITION_MET","notification_condition":null}。'
        "要求满足某条件、低于/高于阈值或仅有重要变化才通知，使用CONDITION_MET，条件对象为"
        '{"description":"完整条件与对象","operator":"semantic|lt|lte|gt|gte|eq","threshold":"十进制阈值字符串","unit":"单位"}。'
        "数字比较用对应算符和明确单位，如CNY/g、USD/oz；禁止擅自转换币种、猜测黄金品种、报价口径或不明阈值。"
        "非数字、多条件或连续次数条件operator=semantic且threshold/unit为空字符串，完整保留条件，不可简化成单个阈值。仅指内容有更新可用CHANGES_ONLY。"
        "不满足条件时可回会话但不能通知。不含通知限制时EVERY_RUN。"
        '信息不足只返回{"clarification":"需要补充的问题"}。不得执行或承诺创建任务。'
    )
    try:
        async with asyncio.timeout(25):
            output = ""
            async for event in runtime.invoke(
                "notification-plan:" + str(key),
                owner,
                [{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            ):
                if event["type"] == "completed":
                    output = event["content"]
        return NotificationPlan.model_validate(json.loads(strip_json_fence(output))).model_dump(
            exclude_none=True
        )
    except (ValueError, TypeError, TimeoutError):
        return {"clarification": "未能确认通知条件，请补充监控对象、触发条件和检查频率；尚未创建任务。"}
