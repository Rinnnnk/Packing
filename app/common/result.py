# -*- coding: utf-8 -*-
"""
result.py - 统一 JsonResult 响应包装类
"""
import time
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field

T = TypeVar("T")


class JsonResult(BaseModel, Generic[T]):
    code: int = Field(default=200, description="状态码: 200-成功, 400-业务/防呆拦截, 500-系统异常")
    message: str = Field(default="操作成功", description="响应提示信息")
    data: Optional[T] = Field(default=None, description="业务数据")
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000), description="响应时间戳")

    @classmethod
    def success(cls, data: Optional[T] = None, message: str = "操作成功") -> "JsonResult[T]":
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, message: str = "操作失败", code: int = 400) -> "JsonResult[None]":
        return cls(code=code, message=message, data=None)