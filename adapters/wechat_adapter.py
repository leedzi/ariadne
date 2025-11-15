"""
微信平台适配器
基于wxauto实现，保留原有微信功能兼容
"""

from typing import Optional, List, Union
from datetime import datetime
import os

from .base import (
    PlatformAdapter, Message, User, SendResult,
    MessageType, Platform
)


class WeChatAdapter(PlatformAdapter):
    """微信平台适配器实现"""
    
    def __init__(self):
        super().__init__()
        self.platform = Platform.WECHAT
        self.wx = None
        self._listen_list = []
    
    async def initialize(self) -> bool:
        """
        初始化微信连接
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            from wxauto import WeChat
            self.wx = WeChat()
            self._initialized = True
            print("[WeChatAdapter] 微信适配器初始化成功")
            return True
        except ImportError:
            print("[WeChatAdapter] wxauto未安装，请运行: pip install wxauto")
            self._initialized = False
            return False
        except Exception as e:
            print(f"[WeChatAdapter] 微信适配器初始化失败: {e}")
            self._initialized = False
            return False
    
    async def close(self) -> None:
        """关闭连接"""
        self._initialized = False
        self.wx = None
        print("[WeChatAdapter] 微信适配器已关闭")
    
    async def send_text(
        self, 
        target: str, 
        content: str, 
        is_group: bool = False
    ) -> SendResult:
        """
        发送文本消息
        
        Args:
            target: 目标微信昵称或群名
            content: 消息内容
            is_group: 是否为群消息（wxauto中不需要区分）
            
        Returns:
            SendResult: 发送结果
        """
        if not self._initialized or not self.wx:
            return SendResult(
                success=False,
                error="适配器未初始化"
            )
        
        try:
            self.wx.SendMsg(content, target)
            return SendResult(
                success=True,
                message_id=None,  # wxauto不提供消息ID
                timestamp=int(datetime.now().timestamp())
            )
        except Exception as e:
            error_msg = f"发送失败: {e}"
            print(f"[WeChatAdapter] {error_msg}")
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
            target: 目标微信昵称或群名
            image: 图片路径或字节流
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        if not self._initialized or not self.wx:
            return SendResult(
                success=False,
                error="适配器未初始化"
            )
        
        try:
            # wxauto需要文件路径
            if isinstance(image, bytes):
                # 保存字节流为临时文件
                temp_path = self._save_temp_file(image, 'temp_image.jpg')
                self.wx.SendFiles(temp_path, target)
            else:
                self.wx.SendFiles(image, target)
            
            return SendResult(
                success=True,
                message_id=None,
                timestamp=int(datetime.now().timestamp())
            )
        except Exception as e:
            error_msg = f"发送图片失败: {e}"
            print(f"[WeChatAdapter] {error_msg}")
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
            target: 目标微信昵称或群名
            voice: 语音路径或字节流
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        if not self._initialized or not self.wx:
            return SendResult(
                success=False,
                error="适配器未初始化"
            )
        
        try:
            # wxauto通过SendFiles发送语音
            if isinstance(voice, bytes):
                temp_path = self._save_temp_file(voice, 'temp_voice.mp3')
                self.wx.SendFiles(temp_path, target)
            else:
                self.wx.SendFiles(voice, target)
            
            return SendResult(
                success=True,
                message_id=None,
                timestamp=int(datetime.now().timestamp())
            )
        except Exception as e:
            error_msg = f"发送语音失败: {e}"
            print(f"[WeChatAdapter] {error_msg}")
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
            target: 目标微信昵称或群名
            file_path: 文件路径
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        if not self._initialized or not self.wx:
            return SendResult(
                success=False,
                error="适配器未初始化"
            )
        
        try:
            self.wx.SendFiles(file_path, target)
            return SendResult(
                success=True,
                message_id=None,
                timestamp=int(datetime.now().timestamp())
            )
        except Exception as e:
            error_msg = f"发送文件失败: {e}"
            print(f"[WeChatAdapter] {error_msg}")
            return SendResult(success=False, error=error_msg)
    
    async def get_user_info(self, user_id: str) -> Optional[User]:
        """
        获取用户信息
        
        注意：wxauto功能有限，只能返回基本信息
        
        Args:
            user_id: 微信昵称
            
        Returns:
            User: 用户信息
        """
        # wxauto无法获取详细用户信息，返回基本信息
        return User(
            id=user_id,
            name=user_id,
            avatar=None,
            platform=Platform.WECHAT
        )
    
    async def get_group_members(self, group_id: str) -> List[User]:
        """
        获取群成员列表
        
        注意：wxauto不支持此功能
        
        Args:
            group_id: 群名
            
        Returns:
            List[User]: 空列表
        """
        print("[WeChatAdapter] wxauto不支持获取群成员列表")
        return []
    
    def _save_temp_file(self, data: bytes, filename: str) -> str:
        """
        保存临时文件
        
        Args:
            data: 文件字节流
            filename: 文件名
            
        Returns:
            str: 临时文件路径
        """
        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_path = os.path.join(temp_dir, filename)
        with open(temp_path, 'wb') as f:
            f.write(data)
        
        return temp_path
    
    def set_listen_list(self, listen_list: List[str]):
        """
        设置监听列表
        
        Args:
            listen_list: 要监听的联系人/群列表
        """
        self._listen_list = listen_list
    
    def get_messages(self) -> List[Message]:
        """
        获取新消息
        
        Returns:
            List[Message]: 消息列表
        """
        if not self._initialized or not self.wx:
            return []
        
        messages = []
        try:
            # 遍历监听列表
            for who in self._listen_list:
                msgs = self.wx.GetAllMessage(who)
                if msgs:
                    for msg in msgs:
                        # 解析消息
                        message = self._parse_wx_message(msg, who)
                        if message:
                            messages.append(message)
        except Exception as e:
            print(f"[WeChatAdapter] 获取消息失败: {e}")
        
        return messages
    
    def _parse_wx_message(self, msg, who: str) -> Optional[Message]:
        """
        解析wxauto消息
        
        Args:
            msg: wxauto消息对象
            who: 联系人/群名
            
        Returns:
            Message: 解析后的消息
        """
        try:
            # wxauto消息格式较简单
            content = getattr(msg, 'content', '')
            msg_type = MessageType.TEXT
            
            # 判断消息类型
            if hasattr(msg, 'type'):
                if msg.type == 'image':
                    msg_type = MessageType.IMAGE
                elif msg.type == 'voice':
                    msg_type = MessageType.VOICE
                elif msg.type == 'video':
                    msg_type = MessageType.VIDEO
                elif msg.type == 'file':
                    msg_type = MessageType.FILE
            
            return Message(
                id=str(id(msg)),  # wxauto无消息ID，使用对象ID
                user_id=who,
                user_name=who,
                group_id=None,  # wxauto难以区分群聊
                group_name=None,
                content=content,
                msg_type=msg_type,
                timestamp=int(datetime.now().timestamp()),
                raw_message=msg
            )
        except Exception as e:
            print(f"[WeChatAdapter] 解析消息失败: {e}")
            return None