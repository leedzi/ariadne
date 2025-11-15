"""
QQ平台适配器
基于NoneBot2和OneBot协议实现
"""

import asyncio
from typing import Optional, List, Union
from datetime import datetime
import nonebot
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.exception import ActionFailed

from .base import (
    PlatformAdapter, Message, User, SendResult,
    MessageType, Platform
)


class QQAdapter(PlatformAdapter):
    """QQ平台适配器实现"""
    
    def __init__(self):
        super().__init__()
        self.platform = Platform.QQ
        self.bot: Optional[Bot] = None
        self._retry_count = 3
        self._retry_delay = 1.0
    
    async def initialize(self) -> bool:
        """
        初始化QQ连接
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 获取NoneBot实例
            self.bot = get_bot()
            self._initialized = True
            print(f"[QQAdapter] QQ适配器初始化成功，Bot ID: {self.bot.self_id}")
            return True
        except ValueError as e:
            print(f"[QQAdapter] 无法获取Bot实例，请确保NoneBot已启动: {e}")
            self._initialized = False
            return False
        except Exception as e:
            print(f"[QQAdapter] QQ适配器初始化失败: {e}")
            self._initialized = False
            return False
    
    async def close(self) -> None:
        """关闭连接"""
        self._initialized = False
        self.bot = None
        print("[QQAdapter] QQ适配器已关闭")
    
    async def _retry_action(self, action, *args, **kwargs):
        """
        带重试的动作执行
        
        Args:
            action: 要执行的动作函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            执行结果
        """
        for attempt in range(self._retry_count):
            try:
                return await action(*args, **kwargs)
            except ActionFailed as e:
                if attempt < self._retry_count - 1:
                    print(f"[QQAdapter] 动作失败，正在重试 ({attempt + 1}/{self._retry_count}): {e}")
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise
    
    async def send_text(
        self, 
        target: str, 
        content: str, 
        is_group: bool = False
    ) -> SendResult:
        """
        发送文本消息
        
        Args:
            target: 目标QQ号或群号
            content: 消息内容
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        if not self._initialized or not self.bot:
            return SendResult(
                success=False,
                error="适配器未初始化"
            )
        
        try:
            if is_group:
                result = await self._retry_action(
                    self.bot.send_group_msg,
                    group_id=int(target),
                    message=content
                )
            else:
                result = await self._retry_action(
                    self.bot.send_private_msg,
                    user_id=int(target),
                    message=content
                )
            
            return SendResult(
                success=True,
                message_id=str(result.get('message_id', '')),
                timestamp=int(datetime.now().timestamp())
            )
        except ActionFailed as e:
            error_msg = f"发送失败: {e}"
            print(f"[QQAdapter] {error_msg}")
            return SendResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"发送异常: {e}"
            print(f"[QQAdapter] {error_msg}")
            return SendResult(success=False, error=error_msg)
    
    async def send_image(
        self, 
        target: str, 
        image: Union[str, bytes],
        is_group: bool = False
    ) -> SendResult:
        """
        发送图片
        
        Args:
            target: 目标QQ号或群号
            image: 图片路径（绝对路径）或字节流
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        if not self._initialized or not self.bot:
            return SendResult(
                success=False,
                error="适配器未初始化"
            )
        
        try:
            # 构造图片消息段
            if isinstance(image, str):
                # 使用file协议或URL
                if image.startswith(('http://', 'https://')):
                    msg = MessageSegment.image(image)
                else:
                    # 本地文件路径，转换为file://协议
                    image_path = image.replace('\\', '/')
                    msg = MessageSegment.image(f"file:///{image_path}")
            else:
                # 字节流
                msg = MessageSegment.image(image)
            
            if is_group:
                result = await self._retry_action(
                    self.bot.send_group_msg,
                    group_id=int(target),
                    message=msg
                )
            else:
                result = await self._retry_action(
                    self.bot.send_private_msg,
                    user_id=int(target),
                    message=msg
                )
            
            return SendResult(
                success=True,
                message_id=str(result.get('message_id', '')),
                timestamp=int(datetime.now().timestamp())
            )
        except ActionFailed as e:
            error_msg = f"发送图片失败: {e}"
            print(f"[QQAdapter] {error_msg}")
            return SendResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"发送图片异常: {e}"
            print(f"[QQAdapter] {error_msg}")
            return SendResult(success=False, error=error_msg)
    
    async def send_voice(
        self, 
        target: str, 
        voice: Union[str, bytes],
        is_group: bool = False
    ) -> SendResult:
        """
        发送语音
        
        Args:
            target: 目标QQ号或群号
            voice: 语音路径或字节流
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        if not self._initialized or not self.bot:
            return SendResult(
                success=False,
                error="适配器未初始化"
            )
        
        try:
            # 构造语音消息段
            if isinstance(voice, str):
                voice_path = voice.replace('\\', '/')
                msg = MessageSegment.record(f"file:///{voice_path}")
            else:
                msg = MessageSegment.record(voice)
            
            if is_group:
                result = await self._retry_action(
                    self.bot.send_group_msg,
                    group_id=int(target),
                    message=msg
                )
            else:
                result = await self._retry_action(
                    self.bot.send_private_msg,
                    user_id=int(target),
                    message=msg
                )
            
            return SendResult(
                success=True,
                message_id=str(result.get('message_id', '')),
                timestamp=int(datetime.now().timestamp())
            )
        except ActionFailed as e:
            error_msg = f"发送语音失败: {e}"
            print(f"[QQAdapter] {error_msg}")
            return SendResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"发送语音异常: {e}"
            print(f"[QQAdapter] {error_msg}")
            return SendResult(success=False, error=error_msg)
    
    async def send_file(
        self,
        target: str,
        file_path: str,
        is_group: bool = False
    ) -> SendResult:
        """
        发送文件
        
        Args:
            target: 目标QQ号或群号
            file_path: 文件路径
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        if not self._initialized or not self.bot:
            return SendResult(
                success=False,
                error="适配器未初始化"
            )
        
        try:
            if is_group:
                result = await self._retry_action(
                    self.bot.upload_group_file,
                    group_id=int(target),
                    file=file_path,
                    name=file_path.split('/')[-1]
                )
            else:
                result = await self._retry_action(
                    self.bot.upload_private_file,
                    user_id=int(target),
                    file=file_path,
                    name=file_path.split('/')[-1]
                )
            
            return SendResult(
                success=True,
                timestamp=int(datetime.now().timestamp())
            )
        except ActionFailed as e:
            error_msg = f"发送文件失败: {e}"
            print(f"[QQAdapter] {error_msg}")
            return SendResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"发送文件异常: {e}"
            print(f"[QQAdapter] {error_msg}")
            return SendResult(success=False, error=error_msg)
    
    async def get_user_info(self, user_id: str) -> Optional[User]:
        """
        获取用户信息
        
        Args:
            user_id: QQ号
            
        Returns:
            User: 用户信息，失败返回None
        """
        if not self._initialized or not self.bot:
            return None
        
        try:
            info = await self.bot.get_stranger_info(user_id=int(user_id))
            return User(
                id=str(info['user_id']),
                name=info.get('nickname', '未知'),
                avatar=None,  # OneBot v11不直接提供头像URL
                platform=Platform.QQ,
                extra={
                    'sex': info.get('sex', 'unknown'),
                    'age': info.get('age', 0)
                }
            )
        except ActionFailed as e:
            print(f"[QQAdapter] 获取用户信息失败: {e}")
            return None
        except Exception as e:
            print(f"[QQAdapter] 获取用户信息异常: {e}")
            return None
    
    async def get_group_members(self, group_id: str) -> List[User]:
        """
        获取群成员列表
        
        Args:
            group_id: 群号
            
        Returns:
            List[User]: 群成员列表
        """
        if not self._initialized or not self.bot:
            return []
        
        try:
            members = await self.bot.get_group_member_list(group_id=int(group_id))
            return [
                User(
                    id=str(m['user_id']),
                    name=m.get('card') or m.get('nickname', '未知'),
                    avatar=None,
                    platform=Platform.QQ,
                    extra={
                        'role': m.get('role', 'member'),
                        'title': m.get('title', ''),
                        'join_time': m.get('join_time', 0)
                    }
                )
                for m in members
            ]
        except ActionFailed as e:
            print(f"[QQAdapter] 获取群成员失败: {e}")
            return []
        except Exception as e:
            print(f"[QQAdapter] 获取群成员异常: {e}")
            return []
    
    async def get_group_info(self, group_id: str) -> Optional[dict]:
        """
        获取群信息
        
        Args:
            group_id: 群号
            
        Returns:
            dict: 群信息
        """
        if not self._initialized or not self.bot:
            return None
        
        try:
            info = await self.bot.get_group_info(group_id=int(group_id))
            return {
                'group_id': str(info['group_id']),
                'group_name': info.get('group_name', ''),
                'member_count': info.get('member_count', 0),
                'max_member_count': info.get('max_member_count', 0)
            }
        except ActionFailed as e:
            print(f"[QQAdapter] 获取群信息失败: {e}")
            return None
        except Exception as e:
            print(f"[QQAdapter] 获取群信息异常: {e}")
            return None
    
    async def recall_message(self, message_id: str) -> bool:
        """
        撤回消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            bool: 是否成功
        """
        if not self._initialized or not self.bot:
            return False
        
        try:
            await self.bot.delete_msg(message_id=int(message_id))
            return True
        except ActionFailed as e:
            print(f"[QQAdapter] 撤回消息失败: {e}")
            return False
        except Exception as e:
            print(f"[QQAdapter] 撤回消息异常: {e}")
            return False
    
    def parse_message_from_event(self, event) -> Message:
        """
        从OneBot事件解析为统一Message格式
        
        Args:
            event: OneBot v11事件对象
            
        Returns:
            Message: 统一消息对象
        """
        # 获取基本信息
        user_id = str(event.user_id)
        message_id = str(event.message_id)
        timestamp = event.time
        
        # 判断是否为群消息
        group_id = None
        group_name = None
        if hasattr(event, 'group_id'):
            group_id = str(event.group_id)
        
        # 解析消息内容和类型
        content = ""
        msg_type = MessageType.TEXT
        is_at_me = False
        
        # 【关键修复】检查是否有被图片识别插件修改过的消息
        # 如果event._message只包含纯文本，说明已经被ImagePlugin处理过
        message_to_parse = event.message
        has_been_processed = False
        
        # 调试日志
        print(f"[QQAdapter] 开始解析消息，event.message长度: {len(event.message)}")
        if hasattr(event, '_message'):
            print(f"[QQAdapter] event._message存在，长度: {len(event._message)}")
            print(f"[QQAdapter] event._message内容: {event._message}")
        
        if hasattr(event, '_message') and len(event._message) == 1:
            first_seg = event._message[0]
            print(f"[QQAdapter] 第一个segment类型: {first_seg.type}")
            has_image_in_original = any(seg.type == "image" for seg in event.message)
            print(f"[QQAdapter] 原始消息包含image: {has_image_in_original}")
            
            if first_seg.type == "text" and not has_image_in_original:
                # 这是被ImagePlugin处理过的纯文本消息，直接使用
                has_been_processed = True
                message_to_parse = event._message
                print(f"[QQAdapter] ✅ 检测到消息已被ImagePlugin处理")
            else:
                print(f"[QQAdapter] ❌ 未满足处理条件")
        else:
            print(f"[QQAdapter] ❌ 不满足基本条件")
        
        # 如果消息已被处理（图片识别结果），直接提取文本
        if has_been_processed:
            content = event._message[0].data.get("text", "")
            msg_type = MessageType.TEXT
        else:
            # 正常解析消息
            for seg in message_to_parse:
                if seg.type == "text":
                    content += seg.data.get("text", "")
                    msg_type = MessageType.TEXT
                elif seg.type == "image":
                    content = seg.data.get("url", "")
                    msg_type = MessageType.IMAGE
                elif seg.type == "record":
                    content = seg.data.get("url", "")
                    msg_type = MessageType.VOICE
                elif seg.type == "video":
                    content = seg.data.get("url", "")
                    msg_type = MessageType.VIDEO
                elif seg.type == "at":
                    if seg.data.get("qq") == "all":
                        content += "@全体成员 "
                    elif str(seg.data.get("qq")) == str(self.bot.self_id):
                        is_at_me = True
                        content += f"@{seg.data.get('qq')} "
                    else:
                        content += f"@{seg.data.get('qq')} "
                elif seg.type == "face":
                    content += f"[表情{seg.data.get('id')}]"
                    msg_type = MessageType.EMOJI
        
        # 获取发送者昵称
        sender = getattr(event, 'sender', None)
        if sender:
            user_name = getattr(sender, 'nickname', user_id)
            if hasattr(event, 'group_id'):
                card = getattr(sender, 'card', None)
                if card:
                    user_name = card
        else:
            user_name = user_id
        
        return Message(
            id=message_id,
            user_id=user_id,
            user_name=user_name,
            group_id=group_id,
            group_name=group_name,
            content=content.strip(),
            msg_type=msg_type,
            timestamp=timestamp,
            raw_message=event,
            is_at_me=is_at_me
        )