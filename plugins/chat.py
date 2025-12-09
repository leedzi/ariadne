"""
聊天插件
处理用户对话，集成AI服务和记忆系统
完整支持：核心记忆、短期记忆、自动总结、内容生成
"""

from nonebot import on_message, on_command
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger
from typing import Optional, Dict, List
import asyncio
import os
import time
import random
import json

# 导入现有的服务
try:
    from src.services.ai.llm_service import LLMService
    from modules.memory.memory_service import MemoryService
    from modules.memory.content_generator import ContentGenerator
    from adapters.qq_adapter import QQAdapter
    from plugins.emoji import process_emotion_tags, create_emoji_messages
    from plugins.smart_emoji import GlobalEmojiSelector
    from modules.recognition.reminder_request_recognition.service import ReminderRecognitionService
    from modules.recognition.context_recognition.service import ContextRecognitionService
    from data.config import config
    logger.info("[ChatPlugin] 所有模块导入成功")
except Exception as e:
    logger.error(f"导入服务失败，请检查项目结构: {e}")
    import traceback
    traceback.print_exc()
    LLMService = None
    MemoryService = None
    ContentGenerator = None
    QQAdapter = None
    process_emotion_tags = None
    create_emoji_messages = None
    GlobalEmojiSelector = None
    ReminderRecognitionService = None
    ContextRecognitionService = None
    config = None

# Database不是必需的，单独导入
try:
    from src.services.database import Session, ChatMessage
    Database = Session  # 使用Session作为Database的替代
except Exception:
    Database = None
    logger.debug("[ChatPlugin] 数据库模块未加载（可选）")


# 创建聊天处理器（优先级最低，确保命令先执行）
chat_handler = on_message(priority=10, block=False)

# 创建命令处理器（优先级更高，且block=True阻止消息继续传播）
# 移除中文别名，防止误触发
help_cmd = on_command("help", priority=5, block=True)
status_cmd = on_command("status", priority=5, block=True)
mem_cmd = on_command("mem", priority=5, block=True)
reset_cmd = on_command("reset", priority=5, block=True)
clear_cmd = on_command("clear", priority=5, block=True)
context_cmd = on_command("context", priority=5, block=True)
refresh_memory_cmd = on_command("refresh_memory", priority=5, block=True)
toggle_recognition_cmd = on_command("toggle_recognition", priority=5, block=True)

# 内容生成命令（block=True阻止消息继续传播）
# 移除中文别名，防止误触发
diary_cmd = on_command("diary", priority=5, block=True)
state_cmd = on_command("state", priority=5, block=True)
letter_cmd = on_command("letter", priority=5, block=True)
list_cmd = on_command("list", priority=5, block=True)
pyq_cmd = on_command("pyq", priority=5, block=True)
gift_cmd = on_command("gift", priority=5, block=True)
shopping_cmd = on_command("shopping", priority=5, block=True)


class ChatPlugin:
    """聊天插件类 - 完整集成记忆系统"""
    
    def __init__(self):
        # 安全初始化适配器
        if QQAdapter:
            self.adapter = QQAdapter()
        else:
            self.adapter = None
            logger.error("[ChatPlugin] QQAdapter未能加载")
        self.llm_service = None
        self.database = None
        self.memory_service = None
        self.content_generator = None
        self.reminder_recognition = None
        self.context_recognition = None
        self.emoji_selector = None
        self._initialized = False
        
        # 获取项目根目录
        self.root_dir = os.getcwd()
        
        # 当前使用的角色名
        self.current_avatar = None
        
        # 状态文件路径
        self.state_file = os.path.join(self.root_dir, "data", "recognition_state.json")
        
        # 消息队列系统
        self.message_queues: Dict[str, Dict] = {}
        self.queue_tasks: Dict[str, asyncio.Task] = {}
        self.QUEUE_TIMEOUT = 10  # 默认10秒
        self.MAX_QUEUE_WAIT = 120  # 最长等待时间2分钟（用于图片识别）
        
        # 图片识别状态追踪
        self.image_recognition_status: Dict[str, bool] = {}  # {queue_key: is_recognizing}
        
        # 智能表情控制参数
        self.emoji_cooldowns: Dict[str, float] = {}  # {user_id: last_send_time}
        self.EMOJI_PROBABILITY = 0.3  # 30%概率
        self.EMOJI_COOLDOWN = 300  # 5分钟冷却（300秒）
        
        # 功能开关状态 - 从文件加载
        self._load_recognition_state()
    
    def _load_recognition_state(self):
        """从文件加载识别功能的开关状态"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.recognition_enabled = state.get('recognition_enabled', True)
                    self.emoji_recognition_enabled = state.get('emoji_recognition_enabled', True)
                    logger.info(f"[ChatPlugin] 已加载识别状态: 意图识别={self.recognition_enabled}, 表情识别={self.emoji_recognition_enabled}")
            else:
                # 默认状态
                self.recognition_enabled = True
                self.emoji_recognition_enabled = True
                logger.info("[ChatPlugin] 使用默认识别状态（全部开启）")
        except Exception as e:
            logger.error(f"[ChatPlugin] 加载识别状态失败: {e}，使用默认状态")
            self.recognition_enabled = True
            self.emoji_recognition_enabled = True
    
    def _save_recognition_state(self):
        """保存识别功能的开关状态到文件"""
        try:
            # 确保data目录存在
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            
            state = {
                'recognition_enabled': self.recognition_enabled,
                'emoji_recognition_enabled': self.emoji_recognition_enabled
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[ChatPlugin] 已保存识别状态到文件")
        except Exception as e:
            logger.error(f"[ChatPlugin] 保存识别状态失败: {e}")
    
    async def initialize(self):
        """初始化插件和所有服务"""
        if self._initialized:
            return
        
        try:
            # 初始化适配器
            if self.adapter:
                await self.adapter.initialize()
                logger.info("[ChatPlugin] 适配器初始化成功")
            else:
                logger.warning("[ChatPlugin] 适配器未加载，跳过初始化")
            
            # 加载配置
            try:
                # 检查config是否可用
                if config is None:
                    raise ValueError("config模块未成功导入")
                
                # 获取AI配置
                api_key = config.llm.api_key
                base_url = config.llm.base_url
                model = config.llm.model
                max_token = config.llm.max_tokens  # 注意是max_tokens不是max_token
                temperature = config.llm.temperature
                max_groups = config.behavior.context.max_groups  # 从behavior.context获取
                
                # 获取当前角色
                self.current_avatar = os.path.basename(config.behavior.context.avatar_dir)
                logger.info(f"[ChatPlugin] 当前角色: {self.current_avatar}")
                
                # 加载消息队列超时配置
                try:
                    self.QUEUE_TIMEOUT = config.behavior.message_queue.timeout
                    logger.info(f"[ChatPlugin] 消息队列超时: {self.QUEUE_TIMEOUT}秒")
                except:
                    self.QUEUE_TIMEOUT = 10
                    logger.warning(f"[ChatPlugin] 使用默认消息队列超时: 10秒")
                
            except Exception as e:
                logger.error(f"[ChatPlugin] 加载配置失败: {e}")
                # 使用默认配置
                api_key = os.getenv("OPENAI_API_KEY", "")
                base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                model = os.getenv("OPENAI_MODEL", "gpt-4")
                max_token = 2000
                temperature = 0.7
                max_groups = 10
                self.current_avatar = "default"
            
            # 初始化LLM服务
            if LLMService:
                self.llm_service = LLMService(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    max_token=max_token,
                    temperature=temperature,
                    max_groups=max_groups
                )
                logger.info("[ChatPlugin] LLM服务初始化成功")
            
            # 初始化记忆服务
            if MemoryService:
                self.memory_service = MemoryService(
                    root_dir=self.root_dir,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    max_token=max_token,
                    temperature=temperature,
                    max_groups=max_groups
                )
                logger.info("[ChatPlugin] 记忆服务初始化成功")
            
            # 初始化内容生成服务
            if ContentGenerator:
                self.content_generator = ContentGenerator(
                    root_dir=self.root_dir,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    max_token=max_token,
                    temperature=temperature
                )
                logger.info("[ChatPlugin] 内容生成服务初始化成功")
            
            # 初始化提醒意图识别服务
            if ReminderRecognitionService and self.llm_service:
                try:
                    self.reminder_recognition = ReminderRecognitionService(self.llm_service)
                    logger.info("[ChatPlugin] 提醒意图识别服务初始化成功")
                except Exception as e:
                    logger.warning(f"[ChatPlugin] 提醒意图识别服务初始化失败: {e}")
            
            # 初始化情境识别服务
            if ContextRecognitionService and self.llm_service:
                try:
                    self.context_recognition = ContextRecognitionService(self.llm_service)
                    logger.info("[ChatPlugin] 情境识别服务初始化成功")
                except Exception as e:
                    logger.warning(f"[ChatPlugin] 情境识别服务初始化失败: {e}")
            
            # 初始化智能表情选择器
            if GlobalEmojiSelector:
                try:
                    emoji_dir = os.path.join(self.root_dir, "data", "avatars", self.current_avatar, "emoji")
                    self.emoji_selector = GlobalEmojiSelector(emoji_dir)
                    logger.info("[ChatPlugin] 智能表情选择器初始化成功")
                except Exception as e:
                    logger.warning(f"[ChatPlugin] 智能表情选择器初始化失败: {e}")
            
            # 初始化数据库（如果需要）
            if Database:
                try:
                    self.database = Database()
                    logger.info("[ChatPlugin] 数据库服务初始化成功")
                except Exception as e:
                    logger.warning(f"[ChatPlugin] 数据库初始化失败: {e}")
            
            self._initialized = True
            logger.info("[ChatPlugin] 聊天插件初始化完成")
            
        except Exception as e:
            logger.error(f"[ChatPlugin] 初始化失败: {e}")
    
    async def process_message(self, bot: Bot, event: Event, custom_content: str = None, image_paths: list = None) -> Optional[str]:
        """
        处理消息并生成回复（集成完整记忆系统）
        
        Args:
            bot: Bot实例
            event: 事件对象
            custom_content: 自定义消息内容（用于队列合并后的消息）
            image_paths: 图片路径列表
        """
        try:
            # 检查适配器
            if not self.adapter:
                logger.error("[ChatPlugin] 适配器未初始化")
                return None
            
            # 解析消息
            message = self.adapter.parse_message_from_event(event)
            
            user_id = message.user_id
            user_name = message.user_name
            # 使用自定义内容或原始内容
            content = custom_content if custom_content else message.content
            avatar_name = self.current_avatar
            
            logger.info(f"[ChatPlugin] 收到消息 - 用户:{user_name}({user_id}), 内容:{content[:50]}")
            
            # 检查是否需要回复
            if not await self._should_reply(message, event):
                return None
            
            # 初始化该用户的记忆文件
            if self.memory_service:
                self.memory_service.initialize_memory_files(avatar_name, user_id)
            
            # 获取核心记忆
            core_memory = ""
            if self.memory_service:
                core_memory = self.memory_service.get_core_memory(avatar_name, user_id)
                core_memory_prompt = f"# 核心记忆\n{core_memory}" if core_memory else ""
                logger.debug(f"[ChatPlugin] 核心记忆长度: {len(core_memory)}")
            else:
                core_memory_prompt = ""
            
            # 获取最近对话上下文
            recent_context = []
            if self.memory_service and self.llm_service and user_id not in self.llm_service.chat_contexts:
                recent_context = self.memory_service.get_recent_context(avatar_name, user_id)
                if recent_context:
                    logger.info(f"[ChatPlugin] 从记忆加载了 {len(recent_context)//2} 轮历史对话")
            
            # 读取角色设定
            system_prompt = self._load_avatar_prompt(avatar_name)
            
            # 处理图片数据
            image_data = None
            if image_paths:
                try:
                    # 仅处理第一张图片
                    import base64
                    from PIL import Image
                    import io
                    
                    img_path = image_paths[0]
                    # 简单读取并编码
                    with open(img_path, "rb") as f:
                        # 简单的压缩逻辑
                        with Image.open(f) as img:
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            buffer = io.BytesIO()
                            img.save(buffer, format="JPEG", quality=80)
                            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    logger.info(f"[ChatPlugin] 已加载并编码图片: {img_path}")
                except Exception as e:
                    logger.error(f"[ChatPlugin] 图片处理失败: {e}")

            # 调用LLM生成回复
            response = await self._generate_response(
                user_id=user_id,
                content=content,
                system_prompt=system_prompt,
                previous_context=recent_context,
                core_memory=core_memory_prompt,
                image_data=image_data
            )
            
            # 保存到记忆系统
            if self.memory_service and response:
                self.memory_service.add_conversation(
                    avatar_name=avatar_name,
                    user_message=content,
                    bot_reply=response,
                    user_id=user_id
                )
                logger.debug(f"[ChatPlugin] 已保存对话到记忆系统")
            
            # 检测提醒意图
            await self._check_reminder_intent(bot, event, content, user_id)
            
            # 检测情境并发送表情（如果适用）
            await self._check_context_and_send_emoji(bot, event, content, response)
            
            # 用户对话后，重置主动消息定时器
            await self._reset_autosend_timer(user_id)
            
            return response
            
        except Exception as e:
            logger.error(f"[ChatPlugin] 处理消息失败: {e}")
            return None
    
    def _load_avatar_prompt(self, avatar_name: str) -> str:
        """加载角色设定"""
        try:
            avatar_path = os.path.join(self.root_dir, "data", "avatars", avatar_name, "avatar.md")
            if os.path.exists(avatar_path):
                with open(avatar_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"[ChatPlugin] 加载角色设定失败: {e}")
        
        return "你是一个友好的AI助手。"
    
    async def _should_reply(self, message, event) -> bool:
        """判断是否应该回复此消息"""
        # 私聊消息总是回复
        if isinstance(event, PrivateMessageEvent):
            return True
        
        # 群消息：完全禁用聊天功能（只保留命令，命令由单独的handler处理）
        if isinstance(event, GroupMessageEvent):
            logger.debug(f"[ChatPlugin] 群聊消息已忽略（群聊聊天功能已禁用）")
            return False
        
        return False
    
    async def _generate_response(
        self,
        user_id: str,
        content: str,
        system_prompt: str,
        previous_context: list = None,
        core_memory: str = None,
        image_data: str = None
    ) -> str:
        """生成AI回复"""
        try:
            if self.llm_service:
                response = self.llm_service.get_response(
                    message=content,
                    user_id=user_id,
                    system_prompt=system_prompt,
                    previous_context=previous_context,
                    core_memory=core_memory,
                    image_data=image_data
                )
                return response
            else:
                return "AI服务暂未配置。"
        except Exception as e:
            logger.error(f"[ChatPlugin] 生成回复失败: {e}")
            return "抱歉，我遇到了一些问题，请稍后再试。"
    
    async def _check_reminder_intent(self, bot: Bot, event: Event, content: str, user_id: str):
        """检测并处理提醒意图"""
        if not self.reminder_recognition:
            return
            
        # 检查意图识别开关
        if not self.recognition_enabled:
            logger.debug("[ChatPlugin] 意图识别已关闭，跳过检测")
            return
        
        try:
            # 调用意图识别
            result = self.reminder_recognition.recognize(content)
            
            # 如果不包含提醒意图
            if result == "NOT_TIME_RELATED":
                return
            
            # 如果检测到提醒任务
            if isinstance(result, list) and len(result) > 0:
                logger.info(f"[ChatPlugin] 检测到 {len(result)} 个提醒任务")
                
                # 导入提醒服务
                try:
                    from plugins.reminder import plugin as reminder_plugin
                    
                    # 为每个任务创建提醒
                    for task in result:
                        target_time = task.get('target_time')
                        reminder_content = task.get('reminder_content', content)
                        
                        # 转换时间格式
                        from datetime import datetime
                        try:
                            remind_time = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
                            
                            # 添加提醒（传入datetime对象，不是时间戳）
                            success = await reminder_plugin.add_reminder(
                                user_id=user_id,
                                content=reminder_content,
                                remind_time=remind_time,
                                is_group=isinstance(event, GroupMessageEvent),
                                group_id=str(event.group_id) if isinstance(event, GroupMessageEvent) else None
                            )
                            
                            if success:
                                logger.info(f"[ChatPlugin] 已自动创建提醒: {target_time} - {reminder_content}")
                                await bot.send(event, f"✅ 好的，我会在 {target_time} 提醒你：{reminder_content}")
                            else:
                                logger.warning(f"[ChatPlugin] 创建提醒失败，请检查提醒服务状态")
                        except ValueError as e:
                            logger.error(f"[ChatPlugin] 时间格式解析失败: {e}")
                        except Exception as e:
                            logger.error(f"[ChatPlugin] 创建提醒异常: {e}")
                            import traceback
                            traceback.print_exc()
                
                except ImportError:
                    logger.warning("[ChatPlugin] 提醒插件未加载，无法自动创建提醒")
                except Exception as e:
                    logger.error(f"[ChatPlugin] 创建提醒失败: {e}")
                    
        except Exception as e:
            logger.error(f"[ChatPlugin] 意图识别失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def _check_context_and_send_emoji(self, bot: Bot, event: Event, user_message: str, bot_reply: str):
        """检测情境并发送智能表情（20%概率 + 2分钟冷却）- 增强日志版"""
        if not self.context_recognition or not self.emoji_selector:
            logger.info("[SmartEmoji] ❌ 服务未初始化")
            return
            
        # 检查表情包识别开关
        if not self.emoji_recognition_enabled:
            logger.debug("[SmartEmoji] 表情包识别已关闭，跳过检测")
            return
        
        try:
            user_id = str(event.get_user_id())
            current_time = time.time()
            
            logger.info(f"[SmartEmoji] 开始检测情境 - 用户:{user_id}")
            
            # 🔥 冷却时间检查
            if user_id in self.emoji_cooldowns:
                elapsed = current_time - self.emoji_cooldowns[user_id]
                if elapsed < self.EMOJI_COOLDOWN:
                    remaining = int(self.EMOJI_COOLDOWN - elapsed)
                    logger.info(f"[SmartEmoji] ⏰ 冷却中，还需等待 {remaining} 秒 → 本次不发送")
                    return
                else:
                    logger.info(f"[SmartEmoji] ✅ 冷却已结束（已过 {int(elapsed)} 秒）")
            else:
                logger.info(f"[SmartEmoji] ✅ 首次检测，无冷却限制")
            
            # 调用情境识别（双向分析用户消息和Bot回复）
            logger.info(f"[SmartEmoji] 🤖 调用AI识别情境...")
            result = await self.context_recognition.recognize(user_message, bot_reply)
            
            # 检查是否应该发送表情
            if not result:
                logger.info("[SmartEmoji] ❌ AI识别返回空 → 本次不发送")
                return
            
            should_send = result.get('should_send_emoji')
            has_context = result.get('has_context')
            context_type = result.get('context_type')
            context_name = result.get('context_name')
            keywords = result.get('keywords', [])
            confidence = result.get('confidence', 0)
            reason = result.get('reason', '无')
            
            logger.info(f"[SmartEmoji] 📊 识别结果:")
            logger.info(f"  - 有情境: {has_context}")
            logger.info(f"  - 类型: {context_type}")
            logger.info(f"  - 名称: {context_name}")
            logger.info(f"  - 关键词: {keywords}")
            logger.info(f"  - 置信度: {confidence}")
            logger.info(f"  - 应发送: {should_send}")
            logger.info(f"  - 原因: {reason}")
            
            if not should_send:
                logger.info("[SmartEmoji] ❌ AI判断不应发送表情 → 本次不发送")
                return
            
            # 🎲 概率控制（20%）
            random_value = random.random()
            if random_value > self.EMOJI_PROBABILITY:
                logger.info(f"[SmartEmoji] 🎲 概率控制: {random_value:.2f} > {self.EMOJI_PROBABILITY} → 本次不发送")
                return
            else:
                logger.info(f"[SmartEmoji] 🎲 概率通过: {random_value:.2f} <= {self.EMOJI_PROBABILITY} → 继续")
            
            # 使用智能表情选择器（select_best_emoji会自动选择最佳匹配）
            logger.info(f"[SmartEmoji] 🔍 搜索匹配表情: 关键词={keywords}, 情境={context_name}")
            emoji_path = self.emoji_selector.select_best_emoji(keywords, context_name)
            
            if emoji_path:
                logger.info(f"[SmartEmoji] ✅ 找到表情: {emoji_path}")
                # 发送表情
                if create_emoji_messages:
                    emoji_messages = await create_emoji_messages([emoji_path])
                    for emoji_msg in emoji_messages:
                        await asyncio.sleep(0.5)  # 稍微延迟，让文本消息先发出
                        await bot.send(event, emoji_msg)
                        logger.info(f"[SmartEmoji] 🎉 已发送情境表情")
                    
                    # ✅ 更新冷却时间
                    self.emoji_cooldowns[user_id] = current_time
                    logger.info(f"[SmartEmoji] ⏰ 已更新冷却时间，{self.EMOJI_COOLDOWN}秒后可再次发送")
            else:
                logger.info(f"[SmartEmoji] ❌ 未找到匹配的表情: {keywords} → 本次不发送")
                
        except Exception as e:
            logger.error(f"[SmartEmoji] 💥 情境表情处理失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def _reset_autosend_timer(self, user_id: str):
        """用户对话后，重置主动消息定时器"""
        try:
            # 导入autosend管理器
            from plugins.autosend import auto_send_manager
            
            # 检查该用户是否在监听列表中
            if user_id in auto_send_manager.listen_list:
                # 重新调度定时任务
                auto_send_manager.reschedule_timer()
                logger.info(f"[ChatPlugin] ✅ 用户 {user_id} 对话后已重置主动消息定时器")
        except Exception as e:
            logger.debug(f"[ChatPlugin] 重置主动消息定时器失败: {e}")
    
    def _get_queue_key(self, user_id: str, group_id: str = None) -> str:
        """生成队列键值"""
        if group_id:
            return f"{group_id}_{user_id}"
        return user_id
    
    async def _add_to_message_queue(self, bot: Bot, event: Event, message_content: str):
        """添加消息到队列"""
        try:
            user_id = str(event.get_user_id())
            group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else None
            queue_key = self._get_queue_key(user_id, group_id)
            
            current_time = time.time()
            
            # 检查事件中是否包含图片路径（由ImagePlugin传递）
            image_paths = getattr(event, 'image_paths', [])
            
            if queue_key not in self.message_queues:
                # 创建新队列
                self.message_queues[queue_key] = {
                    'messages': [message_content],
                    'image_paths': image_paths, # 保存图片路径
                    'bot': bot,
                    'event': event,
                    'last_update': current_time,
                    'created_at': current_time  # 记录队列创建时间
                }
                logger.info(f"[MessageQueue] 创建新队列 - 用户: {user_id}")
            else:
                # 添加到现有队列
                self.message_queues[queue_key]['messages'].append(message_content)
                if image_paths:
                    self.message_queues[queue_key].setdefault('image_paths', []).extend(image_paths)
                self.message_queues[queue_key]['last_update'] = current_time
                logger.info(f"[MessageQueue] 追加消息 - 用户: {user_id}, 当前消息数: {len(self.message_queues[queue_key]['messages'])}")
            
            # 取消现有任务
            if queue_key in self.queue_tasks:
                self.queue_tasks[queue_key].cancel()
            
            # 创建新的异步任务
            self.queue_tasks[queue_key] = asyncio.create_task(
                self._delayed_process_queue(queue_key)
            )
            logger.debug(f"[MessageQueue] 设置延迟任务 - {self.QUEUE_TIMEOUT}秒后处理")
                
        except Exception as e:
            logger.error(f"[MessageQueue] 添加消息到队列失败: {e}")
            import traceback
            traceback.print_exc()
    
    def set_image_recognizing(self, queue_key: str, is_recognizing: bool):
        """设置图片识别状态"""
        self.image_recognition_status[queue_key] = is_recognizing
        if is_recognizing:
            logger.info(f"[MessageQueue] 🖼️ 标记队列 {queue_key} 正在识别图片，将暂停超时")
        else:
            logger.info(f"[MessageQueue] ✅ 队列 {queue_key} 图片识别完成，恢复队列处理")
            if queue_key in self.image_recognition_status:
                del self.image_recognition_status[queue_key]
    
    async def _delayed_process_queue(self, queue_key: str):
        """延迟处理队列 - 支持图片识别等待"""
        try:
            start_time = time.time()
            
            # 第一阶段：等待初始超时时间
            await asyncio.sleep(self.QUEUE_TIMEOUT)
            
            # 第二阶段：检查是否有图片正在识别
            while queue_key in self.image_recognition_status and self.image_recognition_status[queue_key]:
                elapsed = time.time() - start_time
                
                # 检查是否超过最长等待时间（2分钟）
                if elapsed >= self.MAX_QUEUE_WAIT:
                    logger.warning(f"[MessageQueue] ⏰ 队列 {queue_key} 等待超时（{self.MAX_QUEUE_WAIT}秒），强制处理")
                    break
                
                # 继续等待1秒，然后再次检查
                logger.debug(f"[MessageQueue] 🖼️ 等待图片识别中...已等待 {int(elapsed)}秒")
                await asyncio.sleep(1)
            
            # 处理队列
            await self._process_message_queue(queue_key)
            
        except asyncio.CancelledError:
            logger.debug(f"[MessageQueue] 队列任务被取消: {queue_key}")
        except Exception as e:
            logger.error(f"[MessageQueue] 延迟处理失败: {e}")
    
    async def _process_message_queue(self, queue_key: str):
        """处理消息队列"""
        try:
            if queue_key not in self.message_queues:
                return
            
            queue_data = self.message_queues.pop(queue_key)
            if queue_key in self.queue_tasks:
                self.queue_tasks.pop(queue_key)
            
            messages = queue_data['messages']
            bot = queue_data['bot']
            event = queue_data['event']
            
            image_paths = queue_data.get('image_paths', [])
            
            # 过滤掉纯URL消息（如果存在图片）
            filtered_messages = []
            if image_paths:
                for msg in messages:
                    if msg.strip().startswith(('http://', 'https://')) and ' ' not in msg.strip():
                        continue
                    filtered_messages.append(msg)
            else:
                filtered_messages = messages

            # 合并消息
            combined_message = "；".join(filtered_messages)
            logger.info(f"[MessageQueue] 处理队列 - 消息数: {len(messages)}, 图片数: {len(image_paths)}, 合并后: {combined_message[:50]}...")
            
            # 处理合并后的消息
            response = await self.process_message(bot, event, combined_message, image_paths=image_paths)
            
            if response:
                await asyncio.sleep(0.5)
                
                # 按$分割消息
                message_parts = response.split('$') if '$' in response else [response]
                
                for msg_part in message_parts:
                    if not msg_part.strip():
                        continue
                    
                    # 处理表情标签
                    if process_emotion_tags and create_emoji_messages:
                        clean_text, emoji_paths = await process_emotion_tags(msg_part)
                        
                        if clean_text:
                            await bot.send(event, clean_text)
                            await asyncio.sleep(0.5)
                        
                        if emoji_paths:
                            emoji_messages = await create_emoji_messages(emoji_paths)
                            for emoji_msg in emoji_messages:
                                await bot.send(event, emoji_msg)
                                await asyncio.sleep(0.3)
                    else:
                        await bot.send(event, msg_part)
                        await asyncio.sleep(0.5)
                
                logger.info(f"[MessageQueue] 已发送回复")
                
        except Exception as e:
            logger.error(f"[MessageQueue] 处理队列失败: {e}")


# 创建全局插件实例
plugin = ChatPlugin()


# Bot启动时自动初始化插件
from nonebot import get_driver

driver = get_driver()

@driver.on_startup
async def init_chat_plugin():
    """Bot启动时初始化Chat插件"""
    logger.info("[ChatPlugin] 🚀 Bot启动，开始初始化Chat插件...")
    await plugin.initialize()
    logger.info("[ChatPlugin] ✅ Chat插件启动初始化完成")


@chat_handler.handle()
async def handle_message(bot: Bot, event: Event):
    """处理所有消息 - 使用消息队列"""
    # 启动时已完成初始化，无需再次检查
    
    # 检查是否需要回复
    message = plugin.adapter.parse_message_from_event(event)
    if not await plugin._should_reply(message, event):
        return
    
    # 获取消息内容
    content = message.content
    
    # 添加到消息队列（而不是立即处理）
    await plugin._add_to_message_queue(bot, event, content)
    logger.debug(f"[ChatPlugin] 消息已加入队列")


@help_cmd.handle()
async def handle_help(bot: Bot, event: Event):
    """处理帮助命令（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    
    help_text = """
🤖 QQ Bot 使用说明

📝 基础功能：
- 私聊：直接发送消息即可对话
- 群聊：已禁用所有功能

🧠 记忆管理：
/mem - 查看当前记忆状态
/reset - 重置短期记忆
/clear - 清空长期记忆总结
/context - 清空对话上下文
/refresh_memory - 强制刷新长期记忆总结
/toggle_recognition - 开启/关闭意图和表情识别

📚 内容生成：
/diary - 生成角色日记
/state - 查看角色状态
/letter - 角色给你写的信
/list - 角色的备忘录
/pyq - 角色的朋友圈
/gift - 角色想送的礼物
/shopping - 角色的购物清单

🎨 系统命令：
/help - 显示此帮助信息
/status - 查看Bot状态

💡 提示：
- 支持多轮对话和上下文记忆
- 自动智能总结对话内容
- 支持图片识别功能
    """.strip()
    
    await bot.send(event, help_text)


@status_cmd.handle()
async def handle_status(bot: Bot, event: Event):
    """处理状态命令（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    status_text = f"""
📊 Bot 状态信息

✅ 运行状态：正常
🤖 Bot ID：{bot.self_id}
🔌 适配器：OneBot V11
👤 当前角色：{plugin.current_avatar}
🧠 LLM服务：{'已连接' if plugin.llm_service else '未配置'}
💾 记忆服务：{'已连接' if plugin.memory_service else '未配置'}
📝 内容生成：{'已连接' if plugin.content_generator else '未配置'}
💿 数据库：{'已连接' if plugin.database else '未配置'}

⏰ 运行时间：在线中
📈 处理消息：正常
    """.strip()
    
    await bot.send(event, status_text)


@mem_cmd.handle()
async def handle_memory(bot: Bot, event: Event):
    """查看记忆状态（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.memory_service:
        await bot.send(event, "记忆服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    try:
        # 获取核心记忆
        core_memory = plugin.memory_service.get_core_memory(avatar_name, user_id)
        
        # 获取最近对话
        recent_context = plugin.memory_service.get_recent_context(avatar_name, user_id, context_size=5)
        
        memory_text = f"""
🧠 记忆状态

📚 核心记忆：
{core_memory if core_memory else '暂无核心记忆'}

💬 最近对话轮数：{len(recent_context) // 2}轮
        """.strip()
        
        await bot.send(event, memory_text)
    except Exception as e:
        logger.error(f"获取记忆失败: {e}")
        await bot.send(event, f"获取记忆失败: {str(e)}")


# 内容生成命令处理器
@diary_cmd.handle()
async def handle_diary(bot: Bot, event: Event):
    """生成日记（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.content_generator:
        await bot.send(event, "内容生成服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    await bot.send(event, "正在生成日记，请稍候...")
    
    try:
        diary = plugin.content_generator.generate_diary(avatar_name, user_id)
        await bot.send(event, diary)
    except Exception as e:
        logger.error(f"生成日记失败: {e}")
        await bot.send(event, f"生成日记失败: {str(e)}")


@state_cmd.handle()
async def handle_state(bot: Bot, event: Event):
    """生成状态栏（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.content_generator:
        await bot.send(event, "内容生成服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    try:
        state = plugin.content_generator.generate_state(avatar_name, user_id)
        await bot.send(event, state)
    except Exception as e:
        await bot.send(event, f"生成状态栏失败: {str(e)}")


@letter_cmd.handle()
async def handle_letter(bot: Bot, event: Event):
    """生成信件（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.content_generator:
        await bot.send(event, "内容生成服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    await bot.send(event, "正在生成信件，请稍候...")
    
    try:
        letter = plugin.content_generator.generate_letter(avatar_name, user_id)
        await bot.send(event, letter)
    except Exception as e:
        await bot.send(event, f"生成信件失败: {str(e)}")


@list_cmd.handle()
async def handle_list(bot: Bot, event: Event):
    """生成备忘录（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.content_generator:
        await bot.send(event, "内容生成服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    try:
        memo_list = plugin.content_generator.generate_list(avatar_name, user_id)
        await bot.send(event, memo_list)
    except Exception as e:
        await bot.send(event, f"生成备忘录失败: {str(e)}")


@pyq_cmd.handle()
async def handle_pyq(bot: Bot, event: Event):
    """生成朋友圈（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.content_generator:
        await bot.send(event, "内容生成服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    try:
        pyq = plugin.content_generator.generate_pyq(avatar_name, user_id)
        await bot.send(event, pyq)
    except Exception as e:
        await bot.send(event, f"生成朋友圈失败: {str(e)}")


@gift_cmd.handle()
async def handle_gift(bot: Bot, event: Event):
    """生成礼物（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.content_generator:
        await bot.send(event, "内容生成服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    try:
        gift = plugin.content_generator.generate_gift(avatar_name, user_id)
        await bot.send(event, gift)
    except Exception as e:
        await bot.send(event, f"生成礼物失败: {str(e)}")


@shopping_cmd.handle()
async def handle_shopping(bot: Bot, event: Event):
    """生成购物清单（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.content_generator:
        await bot.send(event, "内容生成服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    try:
        shopping = plugin.content_generator.generate_shopping(avatar_name, user_id)
        await bot.send(event, shopping)
    except Exception as e:
        await bot.send(event, f"生成购物清单失败: {str(e)}")

@reset_cmd.handle()
async def handle_reset(bot: Bot, event: Event):
    """重置短期记忆（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.memory_service:
        await bot.send(event, "记忆服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    try:
        import json
        # 重置短期记忆文件
        short_memory_path = plugin.memory_service._get_short_memory_path(avatar_name, user_id)
        if os.path.exists(short_memory_path):
            with open(short_memory_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        await bot.send(event, f"已重置 {avatar_name} 的短期记忆")
    except Exception as e:
        logger.error(f"重置短期记忆失败: {e}")
        await bot.send(event, f"重置短期记忆失败: {str(e)}")


@clear_cmd.handle()
async def handle_clear(bot: Bot, event: Event):
    """清空核心记忆（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.memory_service:
        await bot.send(event, "记忆服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    try:
        import json
        from datetime import datetime
        # 清空核心记忆文件
        core_memory_path = plugin.memory_service._get_core_memory_path(avatar_name, user_id)
        if os.path.exists(core_memory_path):
            initial_core_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "content": ""
            }
            with open(core_memory_path, "w", encoding="utf-8") as f:
                json.dump(initial_core_data, f, ensure_ascii=False, indent=2)
        await bot.send(event, f"已清空 {avatar_name} 的核心记忆")
    except Exception as e:
        logger.error(f"清空核心记忆失败: {e}")
        await bot.send(event, f"清空核心记忆失败: {str(e)}")


@context_cmd.handle()
async def handle_context(bot: Bot, event: Event):
    """清空对话上下文（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.llm_service:
        await bot.send(event, "LLM服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    
    try:
        plugin.llm_service.clear_history(user_id)
        await bot.send(event, "已清空对话上下文")
    except Exception as e:
        logger.error(f"清空对话上下文失败: {e}")
        await bot.send(event, f"清空对话上下文失败: {str(e)}")


@refresh_memory_cmd.handle()
async def handle_refresh_memory(bot: Bot, event: Event):
    """强制刷新长期记忆总结（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    # 启动时已完成初始化
    
    if not plugin.memory_service:
        await bot.send(event, "记忆服务未初始化")
        return
    
    user_id = str(event.get_user_id())
    avatar_name = plugin.current_avatar
    
    await bot.send(event, "正在刷新长期记忆总结，请稍候...")
    
    try:
        # 获取最近对话上下文
        context = plugin.memory_service.get_recent_context(avatar_name, user_id)
        
        if not context or len(context) < 2:
            await bot.send(event, "对话历史不足，无法生成记忆总结")
            return
        
        # 强制更新长期记忆总结（核心记忆）
        if plugin.memory_service.update_core_memory(avatar_name, user_id, context):
            # 获取更新后的记忆内容预览
            core_memory = plugin.memory_service.get_core_memory(avatar_name, user_id)
            preview = core_memory[:200] + "..." if len(core_memory) > 200 else core_memory
            
            await bot.send(event, f"✅ 成功刷新长期记忆总结\n\n📝 记忆预览：\n{preview}")
        else:
            await bot.send(event, "刷新记忆总结失败，请稍后重试")
    except Exception as e:
        logger.error(f"刷新长期记忆总结失败: {e}")
        import traceback
        traceback.print_exc()
        await bot.send(event, f"刷新记忆总结失败: {str(e)}")


@toggle_recognition_cmd.handle()
async def handle_toggle_recognition(bot: Bot, event: Event):
    """切换意图识别和表情包识别的开关（仅私聊可用）"""
    # 群聊完全禁用
    if isinstance(event, GroupMessageEvent):
        return
    
    # 切换状态
    plugin.recognition_enabled = not plugin.recognition_enabled
    plugin.emoji_recognition_enabled = not plugin.emoji_recognition_enabled
    
    # 保存状态到文件
    plugin._save_recognition_state()
    
    status = "开启" if plugin.recognition_enabled else "关闭"
    
    logger.info(f"[ChatPlugin] 用户切换识别功能状态: {status}")
    await bot.send(event, f"✅ 已{status}意图识别和表情包识别功能\n\n💾 状态已保存，重启后将保持此设置")


# 导出插件
__plugin_name__ = "chat"
__plugin_usage__ = "聊天对话功能，完整支持记忆和内容生成"
__plugin_version__ = "2.0.0"