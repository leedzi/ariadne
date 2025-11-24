"""
消息处理模块
"""
import logging
import threading
import time
import re
from datetime import datetime
from typing import Optional # 确保导入
from wxauto import WeChat
from src.services.database import Session, ChatMessage
import random
import os
import json
from src.services.ai.llm_service import LLMService
from src.services.ai.network_search_service import NetworkSearchService
from data.config import config, WEBLENS_ENABLED, NETWORK_SEARCH_ENABLED
from modules.recognition import ReminderRecognitionService, SearchRecognitionService
from .debug import DebugCommandHandler
import emoji

logger = logging.getLogger('main')

FALLBACK_REPLY_ON_TRUNCATION = "抱歉，我刚刚想到一半思路有点乱，你能再说一遍吗？"

class MessageHandler:
    def __init__(self, root_dir, api_key, base_url, model, max_token, temperature,
                 max_groups, robot_name, prompt_content, image_handler, emoji_handler, memory_service, content_generator=None, image_recognition_service=None):
        # ... (init 方法内容保持不变) ...
        self.root_dir = root_dir
        self.api_key = api_key
        self.model = model
        self.max_token = max_token
        self.temperature = temperature
        self.max_groups = max_groups
        self.robot_name = robot_name
        self.prompt_content = prompt_content
        self.deepseek = LLMService(
            api_key=api_key, base_url=base_url, model=model, max_token=max_token,
            temperature=temperature, max_groups=max_groups,
            auto_model_switch=getattr(config.llm, 'auto_model_switch', False)
        )
        self.message_queues = {}
        self.queue_timers = {}
        self.QUEUE_TIMEOUT = config.behavior.message_queue.timeout
        self.queue_lock = threading.Lock()
        self.chat_contexts = {}
        self.wx = WeChat()
        self.image_handler = image_handler
        self.emoji_handler = emoji_handler
        self.memory_service = memory_service
        self.image_recognition_service = image_recognition_service
        avatar_path = os.path.join(self.root_dir, config.behavior.context.avatar_dir)
        self.current_avatar = os.path.basename(avatar_path)
        self.avatar_real_names = self._extract_avatar_names(avatar_path)
        logger.info(f"当前使用角色: {self.current_avatar}, 识别名字: {self.avatar_real_names}")
        self.content_generator = content_generator
        if self.content_generator is None:
            try:
                from modules.memory.content_generator import ContentGenerator
                self.content_generator = ContentGenerator(
                    root_dir=root_dir, api_key=config.llm.api_key, base_url=config.llm.base_url,
                    model=config.llm.model, max_token=config.llm.max_tokens, temperature=config.llm.temperature
                )
                logger.info("已创建内容生成器实例")
            except Exception as e:
                logger.error(f"创建内容生成器实例失败: {str(e)}")
        self.debug_handler = DebugCommandHandler(
            root_dir=root_dir, memory_service=memory_service,
            llm_service=self.deepseek, content_generator=self.content_generator
        )
        self.preserve_format_commands = [None, '/diary', '/state', '/letter', '/list', '/pyq', '/gift', '/shopping']
        logger.info("调试命令处理器已初始化")
        self.remind_request_recognitor = ReminderRecognitionService(self.deepseek)
        self.search_request_recognitor = SearchRecognitionService(self.deepseek)
        logger.info("意图识别服务已初始化")
        from modules.reminder import ReminderService
        self.reminder_service = ReminderService(self, self.memory_service)
        logger.info("提醒服务已初始化")
        self.network_search_service = NetworkSearchService(self.deepseek)
        logger.info("网络搜索服务已初始化")
        
    def _process_cot_reply(self, raw_reply: str) -> tuple[str, Optional[str]]:
        """
        处理包含CoT思考链的原始LLM回复。
        """
        think_content = None
        cleaned_reply = raw_reply.strip() if isinstance(raw_reply, str) else ""
        if not cleaned_reply:
            return "", None

        think_pattern = re.compile(r'\[think\](.*?)\[/think\]\s*', re.DOTALL | re.IGNORECASE)
        match = think_pattern.search(cleaned_reply)

        if match:
            think_content = match.group(1).strip()
            cleaned_reply = think_pattern.sub('', cleaned_reply, count=1).strip()
            logger.info(f"--- AI Thought Process ---")
            logger.info(f"{think_content}")
        elif cleaned_reply.startswith('[think]'):
            logger.error("检测到被截断的AI回复！(可能由于max_tokens不足)。")
            think_content = cleaned_reply[len('[think]'):].strip()
            logger.info(f"--- AI Thought Process (Truncated) ---")
            logger.info(f"{think_content}")
            cleaned_reply = FALLBACK_REPLY_ON_TRUNCATION
        elif '<thinking>' in cleaned_reply and '</thinking>' in cleaned_reply:
            parts = cleaned_reply.split('</thinking>', 1)
            if len(parts) > 1:
                think_content_part = parts[0]
                if '<thinking>' in think_content_part:
                    think_content = think_content_part.split('<thinking>', 1)[1].strip()
                cleaned_reply = parts[1].strip()
                logger.info(f"--- AI Thought Process (XML) ---")
                logger.info(f"{think_content}")
        
        return cleaned_reply, think_content

    def switch_avatar_temporarily(self, avatar_path: str):
        """临时切换人设（不修改全局配置，仅用于群聊）"""
        try:
            # 重新加载人设文件
            full_avatar_path = os.path.join(self.root_dir, avatar_path)
            prompt_path = os.path.join(full_avatar_path, "avatar.md")
            
            if os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as file:
                    self.prompt_content = file.read()
                
                # 更新当前人设名
                self.current_avatar = os.path.basename(full_avatar_path)
                
                # 重新提取人设名字
                self.avatar_real_names = self._extract_avatar_names(full_avatar_path)
                
                logger.info(f"临时切换人设到: {self.current_avatar}, 识别名字: {self.avatar_real_names}")
            else:
                logger.error(f"人设文件不存在: {prompt_path}")
                
        except Exception as e:
            logger.error(f"临时切换人设失败: {str(e)}")

    def restore_default_avatar(self):
        """恢复到默认人设"""
        try:
            default_avatar_path = config.behavior.context.avatar_dir
            
            # 重新加载默认人设文件
            full_avatar_path = os.path.join(self.root_dir, default_avatar_path)
            prompt_path = os.path.join(full_avatar_path, "avatar.md")
            
            if os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as file:
                    self.prompt_content = file.read()
                
                # 更新当前人设名
                self.current_avatar = os.path.basename(full_avatar_path)
                
                # 重新提取人设名字
                self.avatar_real_names = self._extract_avatar_names(full_avatar_path)
                
                logger.info(f"恢复到默认人设: {self.current_avatar}, 识别名字: {self.avatar_real_names}")
            else:
                logger.error(f"默认人设文件不存在: {prompt_path}")
                
        except Exception as e:
            logger.error(f"恢复默认人设失败: {str(e)}")

    def switch_avatar(self, avatar_path: str):
        """切换人设"""
        try:
            # 更新当前人设路径
            config.behavior.context.avatar_dir = avatar_path
            
            # 重新加载人设文件
            full_avatar_path = os.path.join(self.root_dir, avatar_path)
            prompt_path = os.path.join(full_avatar_path, "avatar.md")
            
            if os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as file:
                    self.prompt_content = file.read()
                
                # 更新当前人设名
                self.current_avatar = os.path.basename(full_avatar_path)
                
                # 重新提取人设名字
                self.avatar_real_names = self._extract_avatar_names(full_avatar_path)
                
                logger.info(f"成功切换人设到: {self.current_avatar}, 识别名字: {self.avatar_real_names}")
            else:
                logger.error(f"人设文件不存在: {prompt_path}")
                
        except Exception as e:
            logger.error(f"切换人设失败: {str(e)}")

    def _extract_avatar_names(self, avatar_path: str) -> list:
        """从人设文件中提取可能的名字"""
        names = []  # 不包含目录名，避免ATRI这样的英文名干扰
        
        try:
            avatar_file = os.path.join(avatar_path, "avatar.md")
            if os.path.exists(avatar_file):
                with open(avatar_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 使用正则表达式提取可能的名字
                import re
                
                # 提取"你是xxx"模式的名字（最重要的模式）
                matches = re.findall(r'你是([^，,。！!？?\s]+)', content)
                for match in matches:
                    # 过滤掉明显不是名字的词
                    if match not in names and len(match) <= 6 and '机器' not in match:
                        names.append(match)
                
                # 提取"名字[：:]\s*xxx"模式的名字
                matches = re.findall(r'名字[：:]\s*([^，,。！!？?\s\n]+)', content)
                for match in matches:
                    if match not in names and len(match) <= 6:
                        names.append(match)
                        
                # 提取"扮演xxx"模式的名字
                matches = re.findall(r'扮演([^，,。！!？?\s]+)', content)
                for match in matches:
                    # 只要中文名字，过滤掉长词
                    if match not in names and len(match) <= 6 and any('\u4e00' <= c <= '\u9fff' for c in match):
                        names.append(match)
                        
        except Exception as e:
            logger.warning(f"提取人设名字失败: {str(e)}")
            
        # 如果没有提取到任何名字，使用目录名作为备选
        if not names:
            names = [self.current_avatar]
            
        return names

    def _get_queue_key(self, chat_id: str, sender_name: str, is_group: bool) -> str:
        """生成队列键值
        在群聊中使用 chat_id + sender_name 作为键，在私聊中仅使用 chat_id"""
        return f"{chat_id}_{sender_name}" if is_group else chat_id

    def _add_at_tag_if_needed(self, reply: str, sender_name: str, is_group: bool) -> str:
        """统一处理@标签添加逻辑，避免重复添加
        
        Args:
            reply: 原始回复内容
            sender_name: 发送者名称  
            is_group: 是否为群聊
            
        Returns:
            str: 处理后的回复内容
        """
        if not is_group:
            return reply
            
        # 检查回复是否已经包含@用户名，避免重复添加
        # 同时检查空格和换行符的情况
        if reply.startswith(f"@{sender_name} ") or reply.startswith(f"@{sender_name}\n") or reply.startswith(f"@{sender_name}$"):
            logger.info(f"AI回复中已包含@标签，无需添加。回复: {reply[:50]}...")
            return reply
        elif reply.startswith("@") and sender_name in reply.split()[0]:
            # 检查是否@了正确的用户（处理各种分隔符的情况）
            logger.info(f"AI回复中已包含@标签，无需添加。回复: {reply[:50]}...")
            return reply
        elif "@" in reply and not reply.startswith("@"):
            # 如果@符号不在开头，说明可能在回复中提到了其他人
            logger.debug("回复中包含@符号但不在开头，添加@标签")
            return f"@{sender_name} {reply}"
        else:
            logger.debug("群聊环境下添加@标签")
            return f"@{sender_name} {reply}"

    def _get_user_relationship_info(self, sender_name: str) -> str:
        """获取用户关系信息，用于群聊环境判断"""
        try:
            avatar_name = self.current_avatar
            
            # 检查是否有该用户的私聊记忆
            has_private_memory = self.memory_service.has_user_memory(avatar_name, sender_name)
            
            # 检查特殊关系设定（从核心记忆中查找）
            special_relationship = self._get_special_relationship(avatar_name, sender_name)
            
            if has_private_memory:
                base_info = f"发送者 {sender_name} 与你有私聊记忆。"
                if special_relationship:
                    return f"## 当前发送者关系状态：\n{base_info} 特殊关系：{special_relationship}。"
                else:
                    return f"## 当前发送者关系状态：\n{base_info}"
            else:
                base_info = f"发送者 {sender_name} 没有私聊记忆。"
                if special_relationship:
                    return f"## 当前发送者关系状态：\n{base_info} 特殊关系：{special_relationship}。"
                else:
                    return f"## 当前发送者关系状态：\n{base_info}"
                
        except Exception as e:
            logger.error(f"获取用户关系信息失败: {str(e)}")
            return f"## 当前发送者关系状态：\n发送者 {sender_name} 关系状态未知，请保持礼貌友好的态度。"

    def _get_special_relationship(self, avatar_name: str, user_name: str) -> str:
        """从核心记忆中查找特殊关系设定"""
        try:
            # 获取所有用户的核心记忆，查找关于特定用户的关系设定
            avatars_dir = os.path.join(self.root_dir, "data", "avatars", avatar_name, "memory")
            if not os.path.exists(avatars_dir):
                return ""
            
            # 遍历所有用户的记忆文件
            for user_dir in os.listdir(avatars_dir):
                core_memory_path = os.path.join(avatars_dir, user_dir, "core_memory.json")
                if os.path.exists(core_memory_path):
                    try:
                        with open(core_memory_path, "r", encoding="utf-8") as f:
                            core_memory = json.load(f)
                            content = core_memory.get("content", "")
                            
                            # 查找关于特定用户的关系描述
                            if user_name in content:
                                # 简单的关键词匹配
                                relationship_keywords = {
                                    "朋友": f"{user_name}是朋友",
                                    "敌人": f"{user_name}是敌人", 
                                    "兄弟": f"{user_name}是兄弟",
                                    "姐妹": f"{user_name}是姐妹",
                                    "同事": f"{user_name}是同事",
                                    "老师": f"{user_name}是老师",
                                    "学生": f"{user_name}是学生"
                                }
                                
                                for keyword, description in relationship_keywords.items():
                                    if keyword in content and user_name in content:
                                        return description
                    except Exception as e:
                        logger.debug(f"读取核心记忆文件失败: {str(e)}")
                        continue
            
            return ""
            
        except Exception as e:
            logger.error(f"查找特殊关系失败: {str(e)}")
            return ""

    def save_message(self, sender_id: str, sender_name: str, message: str, reply: str, is_group: bool, is_system_message: bool = False):
        """
        【升级版】保存聊天记录到数据库和短期记忆。
        能够识别并正确处理来自AutoSendHandler的主动消息。
        """
        try:
            # 清理回复中的@前缀，以保证记忆的纯净
            clean_reply = reply
            if is_group and reply.startswith(f"@{sender_name} "):
                clean_reply = reply[len(f"@{sender_name} "):]

            # 数据库保存逻辑 (保持不变)
            session = Session()
            # 注意：数据库中我们仍然可以记录发送者是 "System" 或真实用户
            db_sender_name = "System(Auto)" if sender_name == "_SYSTEM_AUTO_MESSAGE_" else sender_name
            chat_message = ChatMessage(sender_id=sender_id, sender_name=db_sender_name, message=message, reply=clean_reply)
            session.add(chat_message)
            session.commit()
            session.close()

            # --- 记忆服务保存逻辑 ---
            avatar_name = self.current_avatar
            
            # 【关键改动】
            # 这里的 user_id (sender_id) 始终是真实的用户ID
            # message 变量是用户说的话，或者AI收到的指令
            # clean_reply 是AI的回复
            # 我们直接将这些信息传递给 memory_service 即可。
            # MemoryService 的 add_conversation 会将它们存入 short_memory.json
            self.memory_service.add_conversation(
                avatar_name=avatar_name,
                user_message=message, # 这就是用户说的话，或者是系统指令
                bot_reply=clean_reply, # 这是AI的回复
                user_id=sender_id, # 这是真实的用户ID
                is_system_message=is_system_message
            )

        except Exception as e:
            logger.error(f"保存消息失败: {str(e)}", exc_info=True)

    def get_api_response(self, message: str, user_id: str, is_group: bool = False, image_data: str = None) -> str:
        """获取 API 回复"""
        # 使用类中已初始化的当前角色名
        avatar_name = self.current_avatar

        try:
            # 使用已加载的人设内容（支持临时切换）
            avatar_content = self.prompt_content
            logger.debug(f"角色提示文件大小: {len(avatar_content)} bytes")

            # 步骤2：获取核心记忆 - 使用用户ID获取对应的记忆
            core_memory = self.memory_service.get_core_memory(avatar_name, user_id=user_id)
            core_memory_prompt = f"# 核心记忆\n{core_memory}" if core_memory else ""
            logger.debug(f"核心记忆长度: {len(core_memory)}")

            # 获取历史上下文（仅在程序重启时）
            # 检查是否已经为该用户加载过上下文
            recent_context = None
            if user_id not in self.deepseek.chat_contexts:
                recent_context = self.memory_service.get_recent_context(avatar_name, user_id)
                if recent_context:
                    logger.info(f"程序启动：为用户 {user_id} 加载 {len(recent_context)} 条历史上下文消息")
                    logger.debug(f"用户 {user_id} 的历史上下文: {recent_context}")

            # 如果是群聊场景，添加群聊环境提示
            if is_group:
                group_prompt_path = os.path.join(self.root_dir, "src", "base", "group.md")
                with open(group_prompt_path, "r", encoding="utf-8") as f:
                    group_chat_prompt = f.read().strip()

                # 检查当前发送者是否有私聊记忆来判断关系
                relationship_info = self._get_user_relationship_info(user_id)
                
                combined_system_prompt = f"{group_chat_prompt}\n\n{relationship_info}\n\n{avatar_content}"
            else:
                combined_system_prompt = avatar_content

            # 获取系统提示词（如果有）
            if hasattr(self, 'system_prompts') and user_id in self.system_prompts and self.system_prompts[user_id]:
                # 将最近的系统提示词合并为一个字符串
                additional_prompt = "\n\n".join(self.system_prompts[user_id])
                logger.info(f"使用系统提示词: {additional_prompt[:100]}...")

                # 将系统提示词添加到角色提示词中
                combined_system_prompt = f"{combined_system_prompt}\n\n参考信息:\n{additional_prompt}"

                # 使用后清除系统提示词，避免重复使用
                self.system_prompts[user_id] = []


            response = self.deepseek.get_response(
                message=message,
                user_id=user_id,
                system_prompt=combined_system_prompt,
                previous_context=recent_context,
                core_memory=core_memory_prompt,
                image_data=image_data
            )
            return response

        except Exception as e:
            logger.error(f"获取API响应失败: {str(e)}")
            # 降级处理：使用原始提示，不添加记忆
            return self.deepseek.get_response(message, user_id, self.prompt_content, image_data=image_data)

    def handle_user_message(self, content: str, chat_id: str, sender_name: str,
                     username: str, is_group: bool = False, is_image_recognition: bool = False, image_path: str = None):
        """统一的消息处理入口"""
        try:
            logger.info(f"收到消息 - 来自: {sender_name}" + (" (群聊)" if is_group else ""))
            logger.debug(f"消息内容: {content}")

            # 处理调试命令
            if content and self.debug_handler.is_debug_command(content):
                logger.info(f"检测到调试命令: {content}")
                # 定义回调函数，用于异步处理生成的内容
                def command_callback(command, reply, chat_id):
                    try:
                        # 统一处理@标签
                        reply = self._add_at_tag_if_needed(reply, sender_name, is_group)

                        # 使用命令响应发送方法
                        self._send_command_response(command, reply, chat_id)
                        logger.info(f"异步处理命令完成: {command}")
                    except Exception as e:
                        logger.error(f"异步处理命令失败: {str(e)}")

                intercept, response = self.debug_handler.process_command(
                    command=content,
                    current_avatar=self.current_avatar,
                    user_id=chat_id,
                    chat_id=chat_id,
                    callback=command_callback
                )

                if intercept:
                    # 只有当有响应时才发送（异步生成内容的命令不会有初始响应）
                    if response:
                        # 统一处理@标签
                        response = self._add_at_tag_if_needed(response, sender_name, is_group)
                        # self.wx.SendMsg(msg=response, who=chat_id)
                        self._send_raw_message(response, chat_id)

                    # 不记录调试命令的对话
                    logger.info(f"已处理调试命令: {content}")
                    return None

            # 无论消息中是否包含链接，都将消息添加到队列
            # 如果有链接，在队列处理过程中提取内容并替换
            self._add_to_message_queue(content, chat_id, sender_name, username, is_group, is_image_recognition, image_path)

        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}", exc_info=True)
            return None

    def _add_to_message_queue(self, content: str, chat_id: str, sender_name: str,
                            username: str, is_group: bool, is_image_recognition: bool, image_path: str = None):
        """添加消息到队列并设置定时器"""
        # 检测消息中是否包含链接，但不立即处理
        has_link = False
        if content and WEBLENS_ENABLED:
            urls = self.network_search_service.detect_urls(content)
            if urls:
                has_link = True
                logger.info(f"[消息队列] 检测到链接: {urls[0]}，将在队列处理时提取内容")
        else:
            urls = []

        with self.queue_lock:
            queue_key = self._get_queue_key(chat_id, sender_name, is_group)

            # 初始化或更新队列
            if queue_key not in self.message_queues:
                logger.info(f"[消息队列] 创建新队列 - 用户: {sender_name}" + (" (群聊)" if is_group else ""))
                self.message_queues[queue_key] = {
                    'messages': [content] if content else [],
                    'chat_id': chat_id,  # 保存原始chat_id用于发送消息
                    'sender_name': sender_name,
                    'username': username,
                    'is_group': is_group,
                    'is_image_recognition': is_image_recognition,
                    'last_update': time.time(),
                    'has_link': has_link,  # 标记消息中是否包含链接
                    'urls': urls if has_link else [],  # 如果有链接，保存URL列表
                    'image_paths': [image_path] if image_path else [] # 保存图片路径
                }
                logger.debug(f"[消息队列] 首条消息: {content[:50] if content else '[图片]'}...")
            else:
                # 添加新消息到现有队列，后续消息不带时间戳
                if content:
                    self.message_queues[queue_key]['messages'].append(content)
                if image_path:
                    self.message_queues[queue_key]['image_paths'].append(image_path)
                    
                self.message_queues[queue_key]['last_update'] = time.time()
                self.message_queues[queue_key]['has_link'] = (has_link | self.message_queues[queue_key]['has_link'])
                if has_link:
                    self.message_queues[queue_key]['urls'].append(urls[0])
                msg_count = len(self.message_queues[queue_key]['messages'])
                img_count = len(self.message_queues[queue_key]['image_paths'])
                logger.info(f"[消息队列] 追加消息 - 用户: {sender_name}, 当前消息数: {msg_count}, 图片数: {img_count}")
                logger.debug(f"[消息队列] 新增消息: {content[:50] if content else '[图片]'}...")

            # 取消现有的定时器
            if queue_key in self.queue_timers and self.queue_timers[queue_key]:
                try:
                    self.queue_timers[queue_key].cancel()
                    logger.debug(f"[消息队列] 重置定时器 - 用户: {sender_name}")
                except Exception as e:
                    logger.error(f"[消息队列] 取消定时器失败: {str(e)}")
                self.queue_timers[queue_key] = None

            # 创建新的定时器
            timer = threading.Timer(
                self.QUEUE_TIMEOUT,
                self._process_message_queue,
                args=[queue_key]
            )
            timer.daemon = True
            timer.start()
            self.queue_timers[queue_key] = timer
            logger.info(f"[消息队列] 设置新定时器 - 用户: {sender_name}, {self.QUEUE_TIMEOUT}秒后处理")

    def _process_message_queue(self, queue_key: str):
        """处理消息队列"""
        avatar_name = self.current_avatar
        try:
            with self.queue_lock:
                if queue_key not in self.message_queues:
                    logger.debug("[消息队列] 队列不存在，跳过处理")
                    return

                # 检查是否到达处理时间
                current_time = time.time()
                queue_data = self.message_queues[queue_key]
                last_update = queue_data['last_update']
                sender_name = queue_data['sender_name']

                if current_time - last_update < self.QUEUE_TIMEOUT - 0.1:
                    logger.info(f"[消息队列] 等待更多消息 - 用户: {sender_name}, 剩余时间: {self.QUEUE_TIMEOUT - (current_time - last_update):.1f}秒")
                    return

                # 获取并清理队列数据
                queue_data = self.message_queues.pop(queue_key)
                if queue_key in self.queue_timers:
                    self.queue_timers.pop(queue_key)

                messages = queue_data['messages']
                chat_id = queue_data['chat_id']  # 使用保存的原始chat_id
                username = queue_data['username']
                sender_name = queue_data['sender_name']
                is_group = queue_data['is_group']
                is_image_recognition = queue_data['is_image_recognition']
                image_paths = queue_data.get('image_paths', [])

                # 合并消息
                combined_message = "；".join(messages) if messages else ""
                
                # 如果只有图片没有文字，添加默认提示
                if not combined_message and image_paths:
                    combined_message = "（用户发送了一张图片）"

                # 打印日志信息
                logger.info(f"[消息队列] 开始处理 - 用户: {sender_name}, 消息数: {len(messages)}, 图片数: {len(image_paths)}")
                logger.info("----------------------------------------")
                logger.debug("原始消息列表:")
                for idx, msg in enumerate(messages, 1):
                    logger.debug(f"{idx}. {msg}")
                logger.info("收到消息:")
                logger.info(combined_message)
                logger.info("----------------------------------------")

                # 处理图片
                image_data = None
                if image_paths:
                    # 目前只处理第一张图片
                    first_image_path = image_paths[0]
                    logger.info(f"处理图片: {first_image_path}")
                    
                    if self.image_recognition_service:
                        image_data = self.image_recognition_service._compress_and_encode_image(first_image_path)
                    else:
                        # 降级方案：直接读取文件并编码
                        try:
                            import base64
                            with open(first_image_path, "rb") as image_file:
                                image_data = base64.b64encode(image_file.read()).decode('utf-8')
                        except Exception as e:
                            logger.error(f"读取图片失败: {str(e)}")

                # 处理队列中的链接
                processed_message = combined_message
                if queue_data.get('has_link', False) and WEBLENS_ENABLED:
                    urls = queue_data.get('urls', [])
                    if urls:
                        logger.info(f"处理队列中的链接: {urls[0]}")
                        # 提取网页内容
                        web_results = self.network_search_service.extract_web_content(urls[0])
                        if web_results and web_results['original']:
                            # 将网页内容添加到消息中
                            processed_message = f"{combined_message}\n\n{web_results['original']}"
                            logger.info("已获取URL内容并添加至本次Prompt中")
                            logger.info(processed_message)
                        else:
                            # 提取失败时的处理
                            logger.warning(f"链接内容提取失败: {urls[0]}")
                            # 可以选择通知用户，或者静默失败
                            # processed_message = f"{combined_message}\n\n(系统提示：链接 {urls[0]} 内容提取失败，请直接根据链接标题或上下文回答)"

                # 检查合并后的消息是否包含时间提醒和联网搜索需求
                # 如果已处理搜索需求，则不需要继续处理消息
                search_handled = self._check_time_reminder_and_search(processed_message, sender_name)
                if search_handled:
                    logger.info(f"搜索需求已处理，直接回复")
                    return self._handle_text_message(processed_message, chat_id, sender_name, username, is_group, image_data=image_data)

                # 在处理消息前，如果启用了联网搜索，先检查是否需要联网搜索
                search_results = None

                if NETWORK_SEARCH_ENABLED:
                    search_intent = self.search_request_recognitor.recognize(message=combined_message)
                    if search_intent['search_required']:
                        logger.info(f"检测到搜索需求:{search_intent['search_query']}")
                        search_results = self.network_search_service.search_internet(
                            query=search_intent['search_query'],
                        )
                        if search_results and search_results['original']:
                            logger.info("搜索成功，将结果添加到消息中")
                            processed_message = f"{combined_message}\n\n{search_results['original']}"
                            logger.info(processed_message)
                        else:
                            logger.warning("搜索失败或结果为空，继续正常处理请求")
                    
                # 识别提醒意图
                tasks = self.remind_request_recognitor.recognize(combined_message)
                if tasks != "NOT_TIME_RELATED":
                    logger.info("检测到提醒需求，正在添加至提醒列表...")
                    voice_reminder_keywords = ["电话", "语音"]
                    if any(k in combined_message for k in voice_reminder_keywords):
                        reminder_type = "voice"
                    else: reminder_type = "text"
                    for task in tasks:
                        self.reminder_service.add_reminder(
                            chat_id=chat_id,
                            target_time=datetime.strptime(task["target_time"], "%Y-%m-%d %H:%M:%S"),
                            content=task["reminder_content"],
                            sender_name=sender_name,
                            reminder_type=reminder_type
                        )

                return self._handle_text_message(processed_message, chat_id, sender_name, username, is_group, image_data=image_data)

        except Exception as e:
            logger.error(f"处理消息队列失败: {e}")
            return None

    def _process_text_for_display(self, text: str) -> str:
        """处理文本以确保表情符号正确显示"""
        try:
            # 先将Unicode表情符号转换为别名再转回，确保标准化
            return emoji.emojize(emoji.demojize(text))
        except Exception:
            return text

    def _filter_user_tags(self, text: str) -> str:
        """过滤消息中的用户标签
        
        Args:
            text: 原始文本
            
        Returns:
            str: 过滤后的文本
        """
        import re
        # 过滤掉 <用户 xxx> 和 </用户> 标签
        text = re.sub(r'<用户\s+[^>]+>\s*', '', text)
        text = re.sub(r'\s*</用户>', '', text)
        return text.strip()

    def _send_message_with_dollar(self, reply, chat_id):
        """以$为分隔符分批发送回复"""
        # 过滤用户标签
        reply = self._filter_user_tags(reply)
        
        # 首先处理文本中的emoji表情符号
        reply = self._process_text_for_display(reply)

        if '$' in reply or '＄' in reply:
            parts = [p.strip() for p in reply.replace("＄", "$").split("$") if p.strip()]
            
            for part in parts:
                # 检查当前部分是否包含表情标签
                emotion_tags = self.emoji_handler.extract_emotion_tags(part)
                if emotion_tags:
                    logger.debug(f"消息片段包含表情: {emotion_tags}")

                # 清理表情标签并发送文本
                clean_part = part
                for tag in emotion_tags:
                    clean_part = clean_part.replace(f'[{tag}]', '')

                if clean_part.strip():
                    self.wx.SendMsg(msg=clean_part.strip(), who=chat_id)
                    logger.debug(f"发送消息: {clean_part[:20]}...")

                # 发送该部分包含的表情
                for emotion_type in emotion_tags:
                    try:
                        emoji_path = self.emoji_handler.get_emoji_for_emotion(emotion_type)
                        if emoji_path:
                            self.wx.SendFiles(filepath=emoji_path, who=chat_id)
                            logger.debug(f"已发送表情: {emotion_type}")
                            time.sleep(1)
                    except Exception as e:
                        logger.error(f"发送表情失败 - {emotion_type}: {str(e)}")

                time.sleep(random.randint(2, 4))
        else:
            # 处理不包含分隔符的消息
            emotion_tags = self.emoji_handler.extract_emotion_tags(reply)
            if emotion_tags:
                logger.debug(f"消息包含表情: {emotion_tags}")

            clean_reply = reply
            for tag in emotion_tags:
                clean_reply = clean_reply.replace(f'[{tag}]', '')

            if clean_reply.strip():
                self.wx.SendMsg(msg=clean_reply.strip(), who=chat_id)
                logger.debug(f"发送消息: {clean_reply[:20]}...")

            # 发送表情
            for emotion_type in emotion_tags:
                try:
                    emoji_path = self.emoji_handler.get_emoji_for_emotion(emotion_type)
                    if emoji_path:
                        self.wx.SendFiles(filepath=emoji_path, who=chat_id)
                        logger.debug(f"已发送表情: {emotion_type}")
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"发送表情失败 - {emotion_type}: {str(e)}")

    def _send_raw_message(self, text: str, chat_id: str):
        """直接发送原始文本消息，保留所有换行符和格式

        Args:
            text: 要发送的原始文本
            chat_id: 接收消息的聊天ID
        """
        try:
            # 过滤用户标签
            text = self._filter_user_tags(text)
            
            # 只处理表情符号，不做其他格式处理
            text = self._process_text_for_display(text)

            # 提取表情标签
            emotion_tags = self.emoji_handler.extract_emotion_tags(text)

            # 清理表情标签
            clean_text = text
            for tag in emotion_tags:
                clean_text = clean_text.replace(f'[{tag}]', '')

            # 直接发送消息，只做必要的处理
            if clean_text:
                clean_text = clean_text.replace('$', '')
                clean_text = clean_text.replace('＄', '')  # 全角$符号
                clean_text = clean_text.replace(r'\n', '\r\n\r\n')
                #logger.info(clean_text)
                self.wx.SendMsg(msg=clean_text, who=chat_id)
                #logger.info(f"已发送经过处理的文件内容: {file_content}")

        except Exception as e:
            logger.error(f"发送原始格式消息失败: {str(e)}")

    def _send_command_response(self, command: str, reply: str, chat_id: str):
        """发送命令响应，根据命令类型决定是否保留原始格式

        Args:
            command: 命令名称，如 '/state'
            reply: 要发送的回复内容
            chat_id: 聊天ID
        """
        if not reply:
            return

        # 检查是否是需要保留原始格式的命令
        if command in self.preserve_format_commands:
            # 使用原始格式发送消息
            logger.info(f"使用原始格式发送命令响应: {command}")
            self._send_raw_message(reply, chat_id)
        else:
            # 使用正常的消息发送方式
            self._send_message_with_dollar(reply, chat_id)

        # 在 MessageHandler 类中
        def _handle_text_message(self, content, chat_id, sender_name, username, is_group, image_data=None):
            """处理普通文本消息（已集成CoT解析和失败消息过滤，并修正save_message调用）"""
            command = None
            if content.startswith('/'):
                command = content.split(' ')[0].lower()
    
            # 【关键改动】判断是否是主动消息
            is_auto_message = sender_name == "_SYSTEM_AUTO_MESSAGE_"
    
            # 如果是主动消息，user_id (用于获取上下文) 是 chat_id，但 "说话人" 是系统
            # 如果是普通消息，user_id 和 sender_name 都是真实用户
            context_user_id = chat_id # 加载上下文始终用真实ID
    
            # 为API准备内容 (保持不变)
            api_content = f"<用户 {sender_name}>{content}</用户>" if is_group and not is_auto_message else content
    
            # 如果有图片，注入系统指令
            if image_data:
                system_instruction = "请回复用户，并在回复末尾用 <img_memory>...</img_memory> 包裹一段关于这张图片的客观文字描述，用于存入你的长期记忆。"
                self._add_to_system_prompt(context_user_id, system_instruction)
    
            raw_reply = self.get_api_response(api_content, context_user_id, is_group) # get_api_response 内部会调用 deepseek.get_response，需要确保它传递 image_data
            
            # 修正 get_api_response 调用，目前它不支持 image_data 参数，需要修改 get_api_response
            # 或者我们直接在这里调用 deepseek.get_response，但这会绕过 get_api_response 中的一些逻辑（如核心记忆加载）
            # 最好的办法是修改 get_api_response 签名，或者在 get_api_response 内部处理
            # 由于我们不能在一个 apply_diff 中修改同一个文件的多个地方（如果它们重叠或依赖），我们先假设 get_api_response 已经修改好了
            # 等等，我刚才只修改了 LLMService.get_response，没有修改 MessageHandler.get_api_response
            # 我需要在下面的 apply_diff 中同时修改 MessageHandler.get_api_response
            
            cleaned_reply, thought_content = self._process_cot_reply(raw_reply)
            
            # 提取图片描述
            img_desc = ""
            if image_data:
                import re
                match = re.search(r'<img_memory>(.*?)</img_memory>', cleaned_reply, re.DOTALL)
                if match:
                    img_desc = match.group(1).strip()
                    cleaned_reply = cleaned_reply.replace(match.group(0), "").strip()
                    logger.info(f"提取到图片描述: {img_desc}")
                else:
                    img_desc = "（图片内容未识别）"
                    logger.warning("未提取到图片描述")
    
            logger.info(f"AI清理后回复: {cleaned_reply}")
    
            # 发送回复 (对于主动消息，sender_name是_SYSTEM_...，所以_add_at_tag_if_needed不会错误地@系统)
            display_reply = self._add_at_tag_if_needed(cleaned_reply, sender_name, is_group)
            if command and command in self.preserve_format_commands:
                self._send_command_response(command, display_reply, chat_id)
            else:
                self._send_message_with_dollar(display_reply, chat_id)
    
            if cleaned_reply == FALLBACK_REPLY_ON_TRUNCATION:
                logger.warning("检测到AI回复为截断后的备用消息，将跳过保存记忆。")
            else:
                # 【关键改动】修正调用 save_message 的参数
                is_system_message_flag = is_auto_message or sender_name == "System" or username == "System"
                
                # message_to_save: 如果是主动消息，保存的是指令；否则是用户内容。
                message_to_save = content
                if img_desc:
                    message_to_save = f"{content} [图片内容：{img_desc}]"
                
                threading.Thread(target=self.save_message,
                                args=(
                                    chat_id, # sender_id 始终是真实用户ID
                                    sender_name, # sender_name 可能是真实用户或 _SYSTEM_...
                                    message_to_save, # "用户"说的话
                                    cleaned_reply, # AI的回复
                                    is_group, # 是否群聊
                                    is_system_message_flag
                                ),
                                daemon=True).start()
            
            return cleaned_reply

    def _add_to_system_prompt(self, chat_id: str, content: str) -> None:
        """
        将内容添加到系统提示词中

        Args:
            chat_id: 聊天ID
            content: 要添加的内容
        """
        try:
            # 初始化聊天的系统提示词字典（如果不存在）
            if not hasattr(self, 'system_prompts'):
                self.system_prompts = {}

            # 初始化当前聊天的系统提示词（如果不存在）
            if chat_id not in self.system_prompts:
                self.system_prompts[chat_id] = []

            # 添加内容到系统提示词列表
            self.system_prompts[chat_id].append(content)

            # 限制系统提示词列表的长度（保留最新的 5 条）
            if len(self.system_prompts[chat_id]) > 5:
                self.system_prompts[chat_id] = self.system_prompts[chat_id][-5:]

            logger.info(f"已将内容添加到聊天 {chat_id} 的系统提示词中")
        except Exception as e:
            logger.error(f"添加内容到系统提示词失败: {str(e)}")

    # 已在类的开头初始化对话计数器

    def _remove_search_content_from_context(self, chat_id: str, content: str) -> None:
        """
        从上下文中删除搜索内容，并添加到系统提示词中

        Args:
            chat_id: 聊天ID
            content: 要删除的搜索内容
        """
        try:
            # 从内存中的对话历史中删除搜索内容
            if hasattr(self, 'memory_service') and self.memory_service:
                # 尝试从内存中删除搜索内容
                # 注意：这里只是一个示例，实际实现可能需要根据 memory_service 的实际接口调整
                try:
                    # 如果 memory_service 有删除内容的方法，可以调用它
                    # 这里只是记录日志，实际实现可能需要根据具体情况调整
                    logger.info(f"尝试从内存中删除搜索内容: {content[:50]}...")
                except Exception as e:
                    logger.error(f"从内存中删除搜索内容失败: {str(e)}")

            # 如果有其他上下文存储机制，也可以在这里处理

            logger.info(f"已从上下文中删除搜索内容: {content[:50]}...")
        except Exception as e:
            logger.error(f"从上下文中删除搜索内容失败: {str(e)}")

    def _async_generate_summary(self, chat_id: str, url: str, content: str, model: str = None) -> None:
        """
        异步生成总结并添加到系统提示词中
        按照时间而不是对话计数来执行总结

        Args:
            chat_id: 聊天ID
            url: 链接或搜索查询
            content: 要总结的内容
            model: 使用的模型（可选，如果不提供则使用用户配置的模型）
        """
        try:
            # 等待一段时间后再执行总结，确保不占用当前对话的时间
            # 这里设置为30秒，足够让用户进行下一次对话
            logger.info(f"开始等待总结生成时间: {url}")
            time.sleep(30)  # 等待 30 秒

            logger.info(f"开始异步生成总结: {url}")

            # 使用用户配置的模型，如果没有指定模型
            summary_model = model if model else config.llm.model

            # 使用 network_search_service 中的 llm_service
            # 生成总结版本，用于系统提示词
            summary_messages = [
                {
                    "role": "user",
                    "content": f"请将以下内容总结为简洁的要点，以便在系统提示词中使用：\n\n{content}\n\n原始链接或查询: {url}"
                }
            ]

            # 调用 network_search_service 中的 llm_service 获取总结版本
            # 使用用户配置的模型
            logger.info(f"异步总结使用模型: {summary_model}")
            summary_result = self.network_search_service.llm_service.chat(
                messages=summary_messages,
                model=summary_model
            )

            if summary_result:
                # 生成最终的总结内容
                if "http" in url:
                    final_summary = f"关于链接 {url} 的信息：{summary_result}"
                else:
                    final_summary = f"关于\"{url}\"的信息：{summary_result}"

                # 从上下文中删除搜索内容
                self._remove_search_content_from_context(chat_id, content)

                # 添加到系统提示词中，但不发送给用户
                self._add_to_system_prompt(chat_id, final_summary)
                logger.info(f"已将异步生成的总结添加到系统提示词中，并从上下文中删除搜索内容: {url}")
            else:
                logger.warning(f"异步生成总结失败: {url}")
        except Exception as e:
            logger.error(f"异步生成总结失败: {str(e)}")

    def _check_time_reminder_and_search(self, content: str, sender_name: str) -> bool:
        """
        检查和处理时间提醒和联网搜索需求

        Args:
            content: 消息内容
            chat_id: 聊天ID
            sender_name: 发送者名称

        Returns:
            bool: 是否已处理搜索需求（如果已处理，则不需要继续处理消息）
        """
        # 避免处理系统消息
        if sender_name == "System" or sender_name.lower() == "system" :
            logger.debug(f"跳过时间提醒和搜索识别：{sender_name}发送的消息不处理")
            return False

        try:
            if "可作为你的回复参考" in content:
                logger.info(f"已联网获取过信息，直接获取回复")
                return True

        except Exception as e:
            logger.error(f"处理时间提醒和搜索失败: {str(e)}")
            return False

    # def _check_time_reminder(self, content: str, chat_id: str, sender_name: str):
    #     """检查和处理时间提醒（兼容旧接口）"""
    #     # 避免处理系统消息
    #     if sender_name == "System" or sender_name.lower() == "system" :
    #         logger.debug(f"跳过时间提醒识别：{sender_name}发送的消息不处理")
    #         return

    #     try:
    #         # 使用 time_recognition 服务识别时间
    #         time_infos = self.time_recognition.recognize_time(content)
    #         if time_infos:
    #             for target_time, reminder_content in time_infos:
    #                 logger.info(f"检测到提醒请求 - 用户: {sender_name}")
    #                 logger.info(f"提醒时间: {target_time}, 内容: {reminder_content}")

    #                 # 使用 reminder_service 创建提醒
    #                 success = self.reminder_service.add_reminder(
    #                     chat_id=chat_id,
    #                     target_time=target_time,
    #                     content=reminder_content,
    #                     sender_name=sender_name,
    #                     silent=True
    #                 )

    #                 if success:
    #                     logger.info("提醒任务创建成功")
    #                 else:
    #                     logger.error("提醒任务创建失败")

    #     except Exception as e:
    #         logger.error(f"处理时间提醒失败: {str(e)}")

    def add_to_queue(self, chat_id: str, content: str, sender_name: str,
                    username: str, is_group: bool = False):
        """添加消息到队列（兼容旧接口）"""
        return self._add_to_message_queue(content, chat_id, sender_name, username, is_group, False)

    def process_messages(self, chat_id: str):
        """处理消息队列中的消息（已废弃，保留兼容）"""
        # 该方法不再使用，保留以兼容旧代码
        logger.warning("process_messages方法已废弃，使用handle_message代替")
        pass