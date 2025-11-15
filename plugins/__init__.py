"""
NoneBot2插件模块
包含所有QQ Bot的功能插件
"""

from nonebot import require

# 加载调度器插件（用于定时任务）
require("nonebot_plugin_apscheduler")

__all__ = []