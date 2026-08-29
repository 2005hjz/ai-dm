"""防御性编程:输入校验 + 提示词防护(Prompt 防护)+ 内容安全过滤。

- InputValidationError : 输入不合法时抛出,由 API 层转为 422。
- sanitize_input        : 清理控制字符 / 归一化空白 / 长度上限。
- scan_guardrails       : 检测越狱 / 提示词注入关键字,命中则返回提示语(不等同于直接拒绝,DM 以角色内方式化解)。# noqa: E501
"""

from __future__ import annotations

import re

from . import config

# 控制字符(除 \n \t 外)归一化
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# 提示词注入 / 越狱 模式(命中即触发「角色内化解」或拒绝)
_JAILBREAK_PATTERNS = [
    re.compile(r"忽略\s*(之前|上面|前面|以上|你的指令|所有)|无视.*规则", re.IGNORECASE),
    re.compile(r"system\s*prompt|提示词|初始指令|你的系统", re.IGNORECASE),
    re.compile(r"越狱|DAN\b|jailbreak\b|reveal\s*(the)?\s*instructions?", re.IGNORECASE),
    re.compile(r"扮演{0,2}(另一个|真实|不再|去掉|解除)|你是\s*(OpenAI|DeepSeek|语言模型|AI模型)", re.IGNORECASE),
    re.compile(r"输出\s*(完整|全部|原始)?\s*(prompt|提示|指令|协议)", re.IGNORECASE),
]

_SENSITIVE_WORDS = [
    "身份证",
    "银行卡",
    "密码",
    "验证码",
    "转账",
    "汇款",
    "信用卡号",
    "SSN",
    "银行卡号",
    "支付宝密码",
    "手机验证码",
]


class InputValidationError(ValueError):
    """输入不满足约束时抛出。"""


def sanitize_input(raw: str) -> str:
    """清洗输入:去控制字符 → 去首尾空白 → 长度上限卡点。"""
    if raw is None:
        raise InputValidationError("输入为空")
    text = _CONTROL_RE.sub("", raw or "").strip()
    if not text:
        raise InputValidationError("输入不能为空")
    if text.lower() == "/help":
        return text
    if len(text) > config.MAX_INPUT_LENGTH:
        raise InputValidationError(f"输入过长(上限 {config.MAX_INPUT_LENGTH} 字)。")
    # /roll 允许数字;其它指令限长
    return text


def scan_guardrails(text: str) -> str | None:
    """检测提示词注入/越狱。命中:返回一条「角色内化解」提示,由前端显示;否则 None。"""
    for pat in _JAILBREAK_PATTERNS:
        if pat.search(text):
            return "『雾』压低了声音:别在雾里问这种问题。继续你的行动吧。"
    return None


def has_sensitive_data(text: str) -> bool:
    """宽松检测敏感信息关键词(用于日志脱敏提示)。"""
    return any(w in text for w in _SENSITIVE_WORDS)


def guard_log(msg: str) -> str:
    """日志脱敏:把疑似敏感信息替换为 *masked*。"""
    if has_sensitive_data(msg):
        return "*masked*"
    return msg[:200] if len(msg) > 200 else msg
