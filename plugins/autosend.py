"""
自动主动消息插件 - QQ版
使用NoneBot2的APScheduler实现定时主动发送消息功能
"""

from nonebot import require, get_bot, on_command
from nonebot.adapters.onebot.v11 import Bot, PrivateMessageEvent
from nonebot.log import logger
from datetime import datetime, time as dt_time
import random
import os
import asyncio
from typing import Optional

# 导入APScheduler支持
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

try:
    from data.config import config
    from src.services.ai.llm_service import LLMService
    from modules.memory.memory_service import MemoryService
    from plugins.emoji import process_emotion_tags, create_emoji_messages
    from plugins.smart_emoji import GlobalEmojiSelector
    from modules.recognition.context_recognition.service import ContextRecognitionService
except ImportError as e:
    logger.warning(f"[AutoSend] 导入模块失败: {e}")
    config = None
    LLMService = None
    MemoryService = None
    process_emotion_tags = None
    create_emoji_messages = None
    GlobalEmojiSelector = None
    ContextRecognitionService = None


class AutoSendManager:
    """自动发送消息管理器"""
    
    def __init__(self):
        self.enabled = False
        self.listen_list = []
        self.min_hours = 2.0
        self.max_hours = 6.0
        self.quiet_start = "23:00"
        self.quiet_end = "07:00"
        self.auto_message_content = ""
        self.job_id = "auto_send_message_job"
        
        # AI服务
        self.llm_service = None
        self.memory_service = None
        self.context_recognition = None
        self.emoji_selector = None
        self.current_avatar = None
        self.root_dir = os.getcwd()
        
        # 加载配置
        self._load_config()
        
        # 初始化AI服务
        self._init_ai_services()
    
    def _load_config(self):
        """从配置文件加载设置"""
        if not config:
            logger.warning("[AutoSend] 配置文件未加载，使用默认配置")
            return
        
        try:
            # 加载监听列表（从config.user.listen_list直接读取）
            self.listen_list = getattr(config.user, 'listen_list', [])
            
            # 加载自动消息配置（从config.behavior.auto_message直接读取）
            auto_msg_config = config.behavior.auto_message
            self.enabled = auto_msg_config.enabled
            self.auto_message_content = auto_msg_config.content.strip()
            self.min_hours = auto_msg_config.min_hours
            self.max_hours = auto_msg_config.max_hours
            
            # 加载安静时间配置
            quiet_time_config = config.behavior.quiet_time
            self.quiet_start = quiet_time_config.start
            self.quiet_end = quiet_time_config.end
            
            logger.info(f"[AutoSend] 配置加载成功 - 启用: {self.enabled}, 监听用户数: {len(self.listen_list)}")
            logger.info(f"[AutoSend] 监听列表: {self.listen_list}")
            logger.info(f"[AutoSend] 消息内容: {self.auto_message_content[:50] if self.auto_message_content else '使用默认'}")
            logger.info(f"[AutoSend] 时间间隔: {self.min_hours}-{self.max_hours}小时")
        except Exception as e:
            logger.error(f"[AutoSend] 加载配置失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _init_ai_services(self):
        """初始化AI服务"""
        if not config or not LLMService or not MemoryService:
            logger.warning("[AutoSend] AI服务未配置，将直接发送系统指令")
            return
        
        try:
            # 获取配置
            api_key = config.llm.api_key
            base_url = config.llm.base_url
            model = config.llm.model
            max_token = config.llm.max_tokens
            temperature = config.llm.temperature
            max_groups = config.behavior.context.max_groups
            self.current_avatar = os.path.basename(config.behavior.context.avatar_dir)
            
            # 初始化LLM服务
            self.llm_service = LLMService(
                api_key=api_key,
                base_url=base_url,
                model=model,
                max_token=max_token,
                temperature=temperature,
                max_groups=max_groups
            )
            
            # 初始化记忆服务
            self.memory_service = MemoryService(
                root_dir=self.root_dir,
                api_key=api_key,
                base_url=base_url,
                model=model,
                max_token=max_token,
                temperature=temperature,
                max_groups=max_groups
            )
            
            # 初始化情境识别服务
            if ContextRecognitionService:
                try:
                    self.context_recognition = ContextRecognitionService(self.llm_service)
                    logger.info("[AutoSend] 情境识别服务初始化成功")
                except Exception as e:
                    logger.warning(f"[AutoSend] 情境识别服务初始化失败: {e}")
            
            # 初始化智能表情选择器
            if GlobalEmojiSelector:
                try:
                    emoji_dir = os.path.join(self.root_dir, "data", "avatars", self.current_avatar, "emoji")
                    self.emoji_selector = GlobalEmojiSelector(emoji_dir)
                    logger.info("[AutoSend] 智能表情选择器初始化成功")
                except Exception as e:
                    logger.warning(f"[AutoSend] 智能表情选择器初始化失败: {e}")
            
            logger.info("[AutoSend] AI服务初始化成功")
        except Exception as e:
            logger.error(f"[AutoSend] AI服务初始化失败: {e}")
            self.llm_service = None
            self.memory_service = None
    
    def _load_avatar_prompt(self, avatar_name: str) -> str:
        """加载角色设定"""
        try:
            avatar_path = os.path.join(self.root_dir, "data", "avatars", avatar_name, "avatar.md")
            if os.path.exists(avatar_path):
                with open(avatar_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"[AutoSend] 加载角色设定失败: {e}")
        return "你是一个友好的AI助手。"
    
    async def _generate_ai_response(self, user_id: str, system_prompt: str, instruction: str) -> Optional[str]:
        """使用AI生成回复"""
        if not self.llm_service or not self.memory_service:
            logger.warning("[AutoSend] AI服务未初始化，无法生成回复")
            return None
        
        try:
            avatar_name = self.current_avatar
            
            # 初始化该用户的记忆文件
            self.memory_service.initialize_memory_files(avatar_name, user_id)
            
            # ✅ 获取核心记忆（长记忆） - 保留
            core_memory = self.memory_service.get_core_memory(avatar_name, user_id)
            core_memory_prompt = f"# 核心记忆\n{core_memory}" if core_memory else ""
            if core_memory:
                logger.info(f"[AutoSend] ✅ 已加载核心记忆（长记忆）")
            
            # ✅ 修复：主动消息总是强制从记忆文件读取最新对话（短记忆）
            # 移除缓存判断条件，确保每次都读取最新的对话历史
            recent_context = self.memory_service.get_recent_context(avatar_name, user_id)
            if recent_context:
                logger.info(f"[AutoSend] ✅ 从记忆加载了 {len(recent_context)//2} 轮历史对话（短记忆）")
                # 同时更新LLM的上下文缓存，保持一致性
                self.llm_service.chat_contexts[user_id] = recent_context
            else:
                logger.warning(f"[AutoSend] ⚠️ 未找到用户 {user_id} 的历史对话记录")
            
            # ✅ 调用LLM生成回复（包含人设system_prompt、长记忆core_memory、短记忆recent_context）
            response = self.llm_service.get_response(
                message=instruction,
                user_id=user_id,
                system_prompt=system_prompt,  # 人设
                previous_context=recent_context,  # 短记忆
                core_memory=core_memory_prompt  # 长记忆
            )
            
            # 保存到记忆系统（统一使用简化标记）
            if response:
                self.memory_service.add_conversation(
                    avatar_name=avatar_name,
                    user_message="[主动消息]",  # ✅ 统一使用简化标记
                    bot_reply=response,
                    user_id=user_id
                )
                logger.debug(f"[AutoSend] 已保存对话到记忆系统（标记: [主动消息]）")
            
            return response
            
        except Exception as e:
            logger.error(f"[AutoSend] AI生成回复失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _send_split_message(self, bot: Bot, user_id: int, message: str):
        """按$分割并发送消息，支持表情处理和智能情境表情"""
        try:
            # 按$分割消息
            message_parts = message.split('$') if '$' in message else [message]
            
            for msg_part in message_parts:
                if not msg_part.strip():
                    continue
                
                # 处理表情标签
                if process_emotion_tags and create_emoji_messages:
                    clean_text, emoji_paths = await process_emotion_tags(msg_part)
                    
                    if clean_text:
                        await bot.send_private_msg(user_id=user_id, message=clean_text)
                        await asyncio.sleep(0.5)
                    
                    if emoji_paths:
                        emoji_messages = await create_emoji_messages(emoji_paths)
                        for emoji_msg in emoji_messages:
                            await bot.send_private_msg(user_id=user_id, message=emoji_msg)
                            await asyncio.sleep(0.3)
                else:
                    # 如果表情处理不可用，直接发送
                    await bot.send_private_msg(user_id=user_id, message=msg_part)
                    await asyncio.sleep(0.5)
            
            logger.debug(f"[AutoSend] 已分割发送 {len(message_parts)} 条消息")
            
            # 🎨 智能情境表情：分析主动消息内容并发送相关表情
            await self._send_context_emoji(bot, user_id, message)
            
        except Exception as e:
            logger.error(f"[AutoSend] 分割发送消息失败: {e}")
            # 降级：直接发送整条消息
            try:
                await bot.send_private_msg(user_id=user_id, message=message)
            except Exception as e2:
                logger.error(f"[AutoSend] 发送消息完全失败: {e2}")
    
    async def _send_context_emoji(self, bot: Bot, user_id: int, message: str):
        """分析消息内容并发送智能情境表情"""
        if not self.context_recognition or not self.emoji_selector:
            logger.debug("[AutoSend] 智能表情服务未初始化，跳过")
            return
        
        try:
            logger.info("[AutoSend] 🤖 开始分析主动消息的情境...")
            
            # 调用情境识别（只分析Bot消息，用户消息传空）
            result = await self.context_recognition.recognize("", message)
            
            if not result or not result.get('should_send_emoji'):
                logger.info("[AutoSend] ❌ 未检测到需要发送表情的情境")
                return
            
            context_type = result.get('context_type')
            context_name = result.get('context_name')
            keywords = result.get('keywords', [])
            
            logger.info(f"[AutoSend] 📊 检测到情境: {context_type}/{context_name}, 关键词: {keywords}")
            
            # 使用智能表情选择器（select_best_emoji会自动选择最佳匹配）
            emoji_path = self.emoji_selector.select_best_emoji(keywords, context_name)
            
            if emoji_path:
                logger.info(f"[AutoSend] ✅ 找到匹配表情: {emoji_path}")
                if create_emoji_messages:
                    emoji_messages = await create_emoji_messages([emoji_path])
                    for emoji_msg in emoji_messages:
                        await asyncio.sleep(0.5)
                        await bot.send_private_msg(user_id=user_id, message=emoji_msg)
                    logger.info(f"[AutoSend] 🎉 已发送智能情境表情")
            else:
                logger.info(f"[AutoSend] ❌ 未找到匹配的表情")
                
        except Exception as e:
            logger.error(f"[AutoSend] 智能表情处理失败: {e}")
            import traceback
            traceback.print_exc()
    
    def is_quiet_time(self) -> bool:
        """检查当前是否在安静时间段内"""
        try:
            current_time = datetime.now().time()
            quiet_start = datetime.strptime(self.quiet_start, "%H:%M").time()
            quiet_end = datetime.strptime(self.quiet_end, "%H:%M").time()
            
            if quiet_start <= quiet_end:
                return quiet_start <= current_time <= quiet_end
            else:
                # 跨夜的情况
                return current_time >= quiet_start or current_time <= quiet_end
        except Exception as e:
            logger.error(f"[AutoSend] 检查安静时间出错: {e}")
            return False
    
    def get_random_interval_seconds(self) -> int:
        """获取随机间隔时间（秒）"""
        min_seconds = int(self.min_hours * 3600)
        max_seconds = int(self.max_hours * 3600)
        return random.randint(min_seconds, max_seconds)
    
    async def send_auto_message(self):
        """发送自动消息"""
        if not self.enabled:
            logger.debug("[AutoSend] 自动消息功能未启用")
            return
        
        if self.is_quiet_time():
            logger.info("[AutoSend] 当前处于安静时间，跳过自动发送")
            return
        
        if not self.listen_list:
            logger.warning("[AutoSend] 监听列表为空，无法发送自动消息")
            return
        
        try:
            # 获取Bot实例
            bot = get_bot()
            
            # 随机选择一个用户
            target_user_id = random.choice(self.listen_list)
            
            # 准备系统指令
            if self.auto_message_content:
                instruction = self.auto_message_content
                logger.info(f"[AutoSend] 使用配置的自定义指令")
            else:
                instruction = "请你作为当前角色，完全根据上下文（包括时间、记忆和人设），主动向用户发起一段符合情境的对话。"
                logger.info(f"[AutoSend] 使用默认指令让AI自行发挥")
            
            # 如果AI服务可用，生成自然对话
            if self.llm_service and self.current_avatar:
                logger.info(f"[AutoSend] 正在使用AI生成自然对话...")
                
                # 加载角色设定
                system_prompt = self._load_avatar_prompt(self.current_avatar)
                
                # 生成AI回复
                ai_response = await self._generate_ai_response(
                    user_id=target_user_id,
                    system_prompt=system_prompt,
                    instruction=instruction
                )
                
                if ai_response:
                    # 按$分割消息并发送
                    await self._send_split_message(bot, int(target_user_id), ai_response)
                    logger.info(f"[AutoSend] 成功向用户 {target_user_id} 发送AI生成的主动消息")
                else:
                    logger.warning(f"[AutoSend] AI生成失败，跳过本次发送")
            else:
                # 降级：直接发送系统指令（也需要分割）
                logger.warning(f"[AutoSend] AI服务不可用，直接发送系统指令")
                await self._send_split_message(bot, int(target_user_id), instruction)
                logger.info(f"[AutoSend] 成功向用户 {target_user_id} 发送系统指令")
            
        except Exception as e:
            logger.error(f"[AutoSend] 发送自动消息失败: {e}")
            import traceback
            traceback.print_exc()
    
    def start_scheduler(self):
        """启动定时任务"""
        if not self.enabled:
            logger.info("[AutoSend] 自动消息功能未启用，不启动定时任务")
            return
        
        # 计算下次执行的间隔
        interval_seconds = self.get_random_interval_seconds()
        interval_hours = interval_seconds / 3600
        
        logger.info(f"[AutoSend] 启动自动消息定时任务，首次执行间隔: {interval_hours:.2f}小时")
        
        # 先移除已存在的任务
        try:
            if scheduler.get_job(self.job_id):
                scheduler.remove_job(self.job_id)
        except Exception:
            pass
        
        # 定义任务函数
        async def auto_send_job():
            await self.send_auto_message()
            
            # 重新调度下一次执行（使用新的随机间隔）
            new_interval = self.get_random_interval_seconds()
            new_hours = new_interval / 3600
            logger.info(f"[AutoSend] 下次自动消息将在 {new_hours:.2f}小时 后发送")
            
            # 更新任务间隔
            try:
                job = scheduler.get_job(self.job_id)
                if job:
                    scheduler.reschedule_job(
                        self.job_id,
                        trigger='interval',
                        seconds=new_interval
                    )
            except Exception as e:
                logger.error(f"[AutoSend] 重新调度任务失败: {e}")
        
        # 添加动态间隔的定时任务（不使用装饰器）
        scheduler.add_job(
            auto_send_job,
            trigger="interval",
            seconds=interval_seconds,
            id=self.job_id,
            replace_existing=True
        )
    
    def stop_scheduler(self):
        """停止定时任务"""
        try:
            if scheduler.get_job(self.job_id):
                scheduler.remove_job(self.job_id)
                logger.info("[AutoSend] 已停止自动消息定时任务")
        except Exception as e:
            logger.error(f"[AutoSend] 停止定时任务失败: {e}")
    
    def reschedule_timer(self):
        """重新调度定时器（用于用户对话后重置）"""
        if not self.enabled:
            return
        
        try:
            # 计算新的随机间隔
            new_interval = self.get_random_interval_seconds()
            new_hours = new_interval / 3600
            
            # 获取现有任务
            job = scheduler.get_job(self.job_id)
            if job:
                # 重新调度
                scheduler.reschedule_job(
                    self.job_id,
                    trigger='interval',
                    seconds=new_interval
                )
                logger.info(f"[AutoSend] ⏰ 用户对话后重置定时器，下次主动消息将在 {new_hours:.2f}小时 后发送")
            else:
                # 如果任务不存在，重新启动
                logger.warning("[AutoSend] 定时任务不存在，重新启动")
                self.start_scheduler()
        except Exception as e:
            logger.error(f"[AutoSend] 重新调度定时器失败: {e}")


# 创建全局管理器实例
auto_send_manager = AutoSendManager()

# 启动命令
start_autosend = on_command("start_autosend", aliases={"启动自动消息"}, priority=5)
stop_autosend = on_command("stop_autosend", aliases={"停止自动消息"}, priority=5)
autosend_status = on_command("autosend_status", aliases={"自动消息状态"}, priority=5)


@start_autosend.handle()
async def handle_start_autosend(bot: Bot, event: PrivateMessageEvent):
    """启动自动消息"""
    user_id = str(event.get_user_id())
    
    # 检查权限（可选：只允许管理员操作）
    # if user_id not in admin_list:
    #     await bot.send(event, "权限不足")
    #     return
    
    auto_send_manager.enabled = True
    auto_send_manager.start_scheduler()
    await bot.send(event, "✅ 自动消息功能已启动")


@stop_autosend.handle()
async def handle_stop_autosend(bot: Bot, event: PrivateMessageEvent):
    """停止自动消息"""
    user_id = str(event.get_user_id())
    
    # 检查权限（可选：只允许管理员操作）
    # if user_id not in admin_list:
    #     await bot.send(event, "权限不足")
    #     return
    
    auto_send_manager.enabled = False
    auto_send_manager.stop_scheduler()
    await bot.send(event, "❌ 自动消息功能已停止")


@autosend_status.handle()
async def handle_autosend_status(bot: Bot, event: PrivateMessageEvent):
    """查看自动消息状态"""
    status = "启用" if auto_send_manager.enabled else "禁用"
    
    status_text = f"""
📤 自动消息状态

🔘 功能状态: {status}
👥 监听用户数: {len(auto_send_manager.listen_list)}
⏰ 发送间隔: {auto_send_manager.min_hours}-{auto_send_manager.max_hours}小时
🌙 安静时间: {auto_send_manager.quiet_start}-{auto_send_manager.quiet_end}
📝 消息内容: {'已配置' if auto_send_manager.auto_message_content else '使用默认'}

💡 命令:
/start_autosend - 启动自动消息
/stop_autosend - 停止自动消息
    """.strip()
    
    await bot.send(event, status_text)


# 在Bot启动时自动启动定时任务
from nonebot import get_driver

driver = get_driver()


@driver.on_startup
async def start_auto_send_on_startup():
    """Bot启动时自动启动自动消息功能"""
    try:
        logger.info(f"[AutoSend] 🚀 Bot启动，检查自动消息功能...")
        logger.info(f"[AutoSend] - enabled: {auto_send_manager.enabled}")
        logger.info(f"[AutoSend] - listen_list: {auto_send_manager.listen_list}")
        logger.info(f"[AutoSend] - min_hours: {auto_send_manager.min_hours}")
        logger.info(f"[AutoSend] - max_hours: {auto_send_manager.max_hours}")
        
        if auto_send_manager.enabled:
            auto_send_manager.start_scheduler()
            logger.info("[AutoSend] ✅ Bot启动时自动启动自动消息功能")
        else:
            logger.warning("[AutoSend] ⚠️ 自动消息功能未启用（enabled=False）")
    except Exception as e:
        logger.error(f"[AutoSend] ❌ Bot启动时初始化失败: {e}")
        import traceback
        traceback.print_exc()


@driver.on_shutdown
async def stop_auto_send_on_shutdown():
    """Bot关闭时停止自动消息功能"""
    auto_send_manager.stop_scheduler()
    logger.info("[AutoSend] Bot关闭时停止自动消息功能")


# 导出
__all__ = ['AutoSendManager', 'auto_send_manager']

__plugin_name__ = "autosend"
__plugin_usage__ = "自动主动消息功能，定时随机向用户发送消息"
__plugin_version__ = "1.0.0"