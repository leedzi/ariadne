"""
提醒功能插件 - QQ版本
支持定时提醒和任务管理，使用NoneBot调度器
集成LLM服务生成自然对话
"""

from nonebot import require, on_command, get_bot
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent
from nonebot.log import logger
from typing import Optional, List, Dict
from datetime import datetime
import json
import os
import asyncio

# 加载调度器
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

# 导入AI服务和表情处理
try:
    from data.config import config
    from src.services.ai.llm_service import LLMService
    from modules.memory.memory_service import MemoryService
    from plugins.emoji import process_emotion_tags, create_emoji_messages
except ImportError as e:
    logger.warning(f"[ReminderPlugin] 导入模块失败: {e}")
    config = None
    LLMService = None
    MemoryService = None
    process_emotion_tags = None
    create_emoji_messages = None


# 创建命令处理器
add_reminder_cmd = on_command("提醒", aliases={"remind", "添加提醒"}, priority=5)
list_reminder_cmd = on_command("提醒列表", aliases={"reminders", "我的提醒"}, priority=5)
del_reminder_cmd = on_command("删除提醒", aliases={"取消提醒"}, priority=5)


class SimpleReminderService:
    """简化的提醒服务 - 适配QQ环境"""
    
    def __init__(self, data_file: str = "data/reminders.json"):
        self.data_file = data_file
        self.reminders: Dict[str, Dict] = {}
        self._load_reminders()
        logger.info("[SimpleReminderService] 提醒服务初始化完成")
    
    def _load_reminders(self):
        """从文件加载提醒"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    # 处理空文件
                    if not content:
                        self.reminders = {}
                        logger.info("[SimpleReminderService] 提醒文件为空，初始化为空字典")
                    else:
                        self.reminders = json.loads(content)
                        logger.info(f"[SimpleReminderService] 加载了 {len(self.reminders)} 条提醒")
            else:
                # 文件不存在，创建空文件
                self.reminders = {}
                self._save_reminders()
                logger.info("[SimpleReminderService] 创建新的提醒文件")
        except json.JSONDecodeError as e:
            logger.error(f"[SimpleReminderService] 提醒文件JSON格式错误: {e}")
            self.reminders = {}
            # 备份损坏的文件
            if os.path.exists(self.data_file):
                backup_file = f"{self.data_file}.backup"
                os.rename(self.data_file, backup_file)
                logger.info(f"[SimpleReminderService] 已备份损坏的文件到: {backup_file}")
            self._save_reminders()
        except Exception as e:
            logger.error(f"[SimpleReminderService] 加载提醒失败: {e}")
            self.reminders = {}
    
    def _save_reminders(self):
        """保存提醒到文件"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[SimpleReminderService] 保存提醒失败: {e}")
    
    def add_reminder(
        self,
        user_id: str,
        content: str,
        remind_time: datetime,
        is_group: bool = False,
        group_id: Optional[str] = None
    ) -> str:
        """
        添加提醒
        
        Returns:
            str: 提醒ID
        """
        task_id = f"reminder_{user_id}_{int(remind_time.timestamp())}"
        
        self.reminders[task_id] = {
            'task_id': task_id,
            'user_id': user_id,
            'content': content,
            'remind_time': remind_time.isoformat(),
            'remind_timestamp': int(remind_time.timestamp()),
            'is_group': is_group,
            'group_id': group_id,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        self._save_reminders()
        logger.info(f"[SimpleReminderService] 添加提醒: {task_id}")
        return task_id
    
    def get_user_reminders(self, user_id: str) -> List[Dict]:
        """获取用户的所有提醒"""
        user_reminders = []
        for task_id, reminder in self.reminders.items():
            if reminder['user_id'] == user_id and reminder['status'] == 'pending':
                user_reminders.append(reminder)
        
        # 按时间排序
        user_reminders.sort(key=lambda x: x['remind_timestamp'])
        return user_reminders
    
    def get_due_reminders(self) -> List[Dict]:
        """获取所有到期的提醒"""
        now = datetime.now()
        due_reminders = []
        
        for task_id, reminder in list(self.reminders.items()):
            if reminder['status'] == 'pending':
                remind_time = datetime.fromisoformat(reminder['remind_time'])
                if now >= remind_time:
                    due_reminders.append(reminder)
        
        return due_reminders
    
    def mark_as_sent(self, task_id: str):
        """标记提醒为已发送"""
        if task_id in self.reminders:
            self.reminders[task_id]['status'] = 'sent'
            self._save_reminders()
            logger.info(f"[SimpleReminderService] 标记提醒为已发送: {task_id}")
    
    def delete_reminder(self, task_id: str) -> bool:
        """删除提醒"""
        if task_id in self.reminders:
            del self.reminders[task_id]
            self._save_reminders()
            logger.info(f"[SimpleReminderService] 删除提醒: {task_id}")
            return True
        return False


class ReminderPlugin:
    """提醒插件类 - 集成LLM生成自然对话"""
    
    def __init__(self):
        self.reminder_service = SimpleReminderService()
        self._initialized = True
        self.bot: Optional[Bot] = None
        
        # AI服务
        self.llm_service = None
        self.memory_service = None
        self.current_avatar = None
        self.root_dir = os.getcwd()
        
        # 初始化AI服务
        self._init_ai_services()
        
        logger.info("[ReminderPlugin] 提醒插件初始化完成")
    
    def _init_ai_services(self):
        """初始化AI服务"""
        if not config or not LLMService or not MemoryService:
            logger.warning("[ReminderPlugin] AI服务未配置，将直接发送提醒内容")
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
            
            logger.info("[ReminderPlugin] AI服务初始化成功")
        except Exception as e:
            logger.error(f"[ReminderPlugin] AI服务初始化失败: {e}")
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
            logger.warning(f"[ReminderPlugin] 加载角色设定失败: {e}")
        return "你是一个友好的AI助手。"
    
    async def _generate_reminder_message(self, user_id: str, reminder_content: str) -> Optional[str]:
        """使用AI生成提醒消息"""
        if not self.llm_service or not self.memory_service:
            logger.warning("[ReminderPlugin] AI服务未初始化，无法生成提醒消息")
            return None
        
        try:
            avatar_name = self.current_avatar
            
            # 初始化该用户的记忆文件
            self.memory_service.initialize_memory_files(avatar_name, user_id)
            
            # 获取核心记忆
            core_memory = self.memory_service.get_core_memory(avatar_name, user_id)
            core_memory_prompt = f"# 核心记忆\n{core_memory}" if core_memory else ""
            
            # 获取最近对话上下文
            recent_context = []
            if user_id not in self.llm_service.chat_contexts:
                recent_context = self.memory_service.get_recent_context(avatar_name, user_id)
                if recent_context:
                    logger.info(f"[ReminderPlugin] 从记忆加载了 {len(recent_context)//2} 轮历史对话")
            
            # 加载角色设定
            system_prompt = self._load_avatar_prompt(avatar_name)
            
            # 构造系统指令
            instruction = f'现在提醒时间到了，用户之前设定的提示内容为"{reminder_content}"。请以你的人设中的身份主动找用户聊天，提醒相关事项。保持角色设定的一致性和上下文的连贯性。'
            
            # 调用LLM生成回复
            response = self.llm_service.get_response(
                message=instruction,
                user_id=user_id,
                system_prompt=system_prompt,
                previous_context=recent_context,
                core_memory=core_memory_prompt
            )
            
            # 保存到记忆系统
            if response:
                self.memory_service.add_conversation(
                    avatar_name=avatar_name,
                    user_message=instruction,
                    bot_reply=response,
                    user_id=user_id
                )
                logger.debug(f"[ReminderPlugin] 已保存对话到记忆系统")
            
            return response
            
        except Exception as e:
            logger.error(f"[ReminderPlugin] AI生成提醒消息失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _send_split_message(self, bot: Bot, user_id: int, group_id: Optional[int], is_group: bool, message: str):
        """按$分割并发送消息，支持表情处理"""
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
                        if is_group and group_id:
                            await bot.send_group_msg(group_id=group_id, message=clean_text)
                        else:
                            await bot.send_private_msg(user_id=user_id, message=clean_text)
                        await asyncio.sleep(0.5)
                    
                    if emoji_paths:
                        emoji_messages = await create_emoji_messages(emoji_paths)
                        for emoji_msg in emoji_messages:
                            if is_group and group_id:
                                await bot.send_group_msg(group_id=group_id, message=emoji_msg)
                            else:
                                await bot.send_private_msg(user_id=user_id, message=emoji_msg)
                            await asyncio.sleep(0.3)
                else:
                    # 如果表情处理不可用，直接发送
                    if is_group and group_id:
                        await bot.send_group_msg(group_id=group_id, message=msg_part)
                    else:
                        await bot.send_private_msg(user_id=user_id, message=msg_part)
                    await asyncio.sleep(0.5)
            
            logger.debug(f"[ReminderPlugin] 已分割发送 {len(message_parts)} 条消息")
            
        except Exception as e:
            logger.error(f"[ReminderPlugin] 分割发送消息失败: {e}")
            # 降级：直接发送整条消息
            try:
                if is_group and group_id:
                    await bot.send_group_msg(group_id=group_id, message=message)
                else:
                    await bot.send_private_msg(user_id=user_id, message=message)
            except Exception as e2:
                logger.error(f"[ReminderPlugin] 发送消息完全失败: {e2}")
    
    async def add_reminder(
        self,
        user_id: str,
        content: str,
        remind_time: datetime,
        is_group: bool = False,
        group_id: Optional[str] = None
    ) -> bool:
        """添加提醒"""
        try:
            task_id = self.reminder_service.add_reminder(
                user_id=user_id,
                content=content,
                remind_time=remind_time,
                is_group=is_group,
                group_id=group_id
            )
            logger.info(f"[ReminderPlugin] 已添加提醒: {remind_time} - {content}")
            return True
        except Exception as e:
            logger.error(f"[ReminderPlugin] 添加提醒失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def get_user_reminders(self, user_id: str) -> List[Dict]:
        """获取用户的提醒列表"""
        try:
            return self.reminder_service.get_user_reminders(user_id)
        except Exception as e:
            logger.error(f"[ReminderPlugin] 获取提醒列表失败: {e}")
            return []
    
    async def delete_reminder(self, task_id: str) -> bool:
        """删除提醒"""
        try:
            return self.reminder_service.delete_reminder(task_id)
        except Exception as e:
            logger.error(f"[ReminderPlugin] 删除提醒失败: {e}")
            return False
    
    async def check_and_send_reminders(self):
        """检查并发送到期的提醒（使用AI生成自然对话）"""
        try:
            # 获取到期的提醒
            due_reminders = self.reminder_service.get_due_reminders()
            
            if not due_reminders:
                return
            
            # 获取bot实例
            try:
                bot = get_bot()
            except Exception:
                logger.warning("[ReminderPlugin] 无法获取Bot实例")
                return
            
            # 发送提醒
            for reminder in due_reminders:
                try:
                    user_id = reminder['user_id']
                    content = reminder['content']
                    is_group = reminder.get('is_group', False)
                    group_id = reminder.get('group_id')
                    
                    # 如果AI服务可用，生成自然对话
                    if self.llm_service and self.current_avatar:
                        logger.info(f"[ReminderPlugin] 正在使用AI生成提醒消息...")
                        
                        ai_message = await self._generate_reminder_message(user_id, content)
                        
                        if ai_message:
                            # 按$分割消息并发送
                            await self._send_split_message(
                                bot=bot,
                                user_id=int(user_id),
                                group_id=int(group_id) if group_id else None,
                                is_group=is_group,
                                message=ai_message
                            )
                            logger.info(f"[ReminderPlugin] 成功发送AI生成的提醒: {reminder['task_id']}")
                        else:
                            logger.warning(f"[ReminderPlugin] AI生成失败，发送原始提醒内容")
                            # 降级：发送原始内容
                            fallback_message = f"⏰ 提醒时间到了！\n\n{content}"
                            await self._send_split_message(
                                bot=bot,
                                user_id=int(user_id),
                                group_id=int(group_id) if group_id else None,
                                is_group=is_group,
                                message=fallback_message
                            )
                    else:
                        # AI服务不可用，直接发送原始内容
                        logger.warning(f"[ReminderPlugin] AI服务不可用，发送原始提醒内容")
                        fallback_message = f"⏰ 提醒时间到了！\n\n{content}"
                        await self._send_split_message(
                            bot=bot,
                            user_id=int(user_id),
                            group_id=int(group_id) if group_id else None,
                            is_group=is_group,
                            message=fallback_message
                        )
                    
                    # 标记为已发送
                    self.reminder_service.mark_as_sent(reminder['task_id'])
                    
                except Exception as e:
                    logger.error(f"[ReminderPlugin] 发送提醒失败: {e}")
                    import traceback
                    traceback.print_exc()
                    
        except Exception as e:
            logger.error(f"[ReminderPlugin] 检查提醒失败: {e}")


# 创建全局插件实例
plugin = ReminderPlugin()


@add_reminder_cmd.handle()
async def handle_add_reminder(bot: Bot, event: Event):
    """处理添加提醒命令"""
    # 解析命令参数
    message = str(event.get_message()).strip()
    # 移除命令前缀
    for prefix in ["提醒", "remind", "添加提醒"]:
        if message.startswith(prefix):
            message = message[len(prefix):].strip()
            break
    
    if not message:
        await bot.send(event, """
使用方法：
/提醒 <时间> <内容>

示例：
/提醒 明天9点 开会
/提醒 2小时后 休息一下
/提醒 2024-01-01 10:00 新年快乐
        """.strip())
        return
    
    try:
        # 这里需要解析时间和内容
        # 简化示例：假设格式为 "时间 内容"
        parts = message.split(maxsplit=1)
        if len(parts) < 2:
            await bot.send(event, "格式错误！请使用：/提醒 <时间> <内容>")
            return
        
        time_str, content = parts
        
        # 解析时间（这里需要实现时间解析逻辑）
        # 简化示例：假设总是明天此时
        from datetime import timedelta
        remind_time = datetime.now() + timedelta(days=1)
        
        # 添加提醒
        user_id = str(event.get_user_id())
        group_id = None
        is_group = False
        
        if hasattr(event, 'group_id'):
            group_id = str(event.group_id)
            is_group = True
        
        success = await plugin.add_reminder(
            user_id=user_id,
            content=content,
            remind_time=remind_time,
            is_group=is_group,
            group_id=group_id
        )
        
        if success:
            await bot.send(event, f"✅ 提醒已设置！\n时间：{remind_time.strftime('%Y-%m-%d %H:%M')}\n内容：{content}")
        else:
            await bot.send(event, "❌ 设置提醒失败，请稍后再试")
    except Exception as e:
        logger.error(f"[ReminderPlugin] 处理添加提醒命令失败: {e}")
        await bot.send(event, f"❌ 设置提醒失败：{str(e)}")


@list_reminder_cmd.handle()
async def handle_list_reminders(bot: Bot, event: Event):
    """处理查看提醒列表命令"""
    try:
        user_id = str(event.get_user_id())
        reminders = await plugin.get_user_reminders(user_id)
        
        if not reminders:
            await bot.send(event, "📝 你还没有设置任何提醒")
            return
        
        # 格式化提醒列表
        message = "📝 你的提醒列表：\n\n"
        for i, reminder in enumerate(reminders, 1):
            remind_time = datetime.fromisoformat(reminder['remind_time'])
            content = reminder['content']
            task_id = reminder['task_id']
            
            message += f"{i}. ⏰ {remind_time.strftime('%m-%d %H:%M')} - {content}\n"
            message += f"   ID: {task_id}\n\n"
        
        await bot.send(event, message.strip())
    except Exception as e:
        logger.error(f"[ReminderPlugin] 处理查看提醒列表失败: {e}")
        await bot.send(event, "❌ 获取提醒列表失败")


@del_reminder_cmd.handle()
async def handle_delete_reminder(bot: Bot, event: Event):
    """处理删除提醒命令"""
    message = str(event.get_message()).strip()
    # 移除命令前缀
    for prefix in ["删除提醒", "取消提醒"]:
        if message.startswith(prefix):
            message = message[len(prefix):].strip()
            break
    
    if not message:
        await bot.send(event, "请指定要删除的提醒ID，例如：/删除提醒 reminder_123456_1234567890")
        return
    
    try:
        reminder_id = message.strip()
        success = await plugin.delete_reminder(reminder_id)
        
        if success:
            await bot.send(event, "✅ 提醒已删除")
        else:
            await bot.send(event, "❌ 删除提醒失败，请检查提醒ID是否正确")
    except Exception as e:
        logger.error(f"[ReminderPlugin] 处理删除提醒命令失败: {e}")
        await bot.send(event, "❌ 删除提醒失败")


# 定时任务：每分钟检查一次提醒
@scheduler.scheduled_job("interval", minutes=1, id="check_reminders")
async def scheduled_check_reminders():
    """定时检查提醒"""
    try:
        await plugin.check_and_send_reminders()
    except Exception as e:
        logger.error(f"[ReminderPlugin] 定时检查提醒失败: {e}")


# 导出插件
__plugin_name__ = "reminder"
__plugin_usage__ = "提醒功能"
__plugin_version__ = "2.0.0"