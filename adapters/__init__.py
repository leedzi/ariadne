"""
平台适配器模块
支持多平台（微信、QQ等）的统一接口
"""

from .base import PlatformAdapter, Message, User
from .qq_adapter import QQAdapter
from .wechat_adapter import WeChatAdapter

__all__ = [
    'PlatformAdapter',
    'Message',
    'User',
    'QQAdapter',
    'WeChatAdapter'
]