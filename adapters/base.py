"""
平台适配器基类
定义所有平台适配器必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class MessageType(str, Enum):
    """消息类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    EMOJI = "emoji"
    AT = "at"
    UNKNOWN = "unknown"


class Platform(str, Enum):
    """平台类型枚举"""
    WECHAT = "wechat"
    QQ = "qq"
    TELEGRAM = "telegram"


@dataclass
class Message:
    """统一消息格式"""
    id: str                              # 消息ID
    user_id: str                         # 发送者ID
    user_name: str                       # 发送者昵称
    group_id: Optional[str] = None       # 群组ID（私聊时为None）
    group_name: Optional[str] = None     # 群组名称
    content: str = ""                    # 消息内容
    msg_type: MessageType = MessageType.TEXT  # 消息类型
    timestamp: int = 0                   # 时间戳
    raw_message: Any = None              # 原始消息对象
    is_at_me: bool = False              # 是否@机器人
    reply_to: Optional[str] = None       # 回复的消息ID
    
    def is_group_message(self) -> bool:
        """判断是否为群消息"""
        return self.group_id is not None
    
    def is_private_message(self) -> bool:
        """判断是否为私聊消息"""
        return self.group_id is None


@dataclass
class User:
    """统一用户格式"""
    id: str                              # 用户ID
    name: str                            # 用户昵称
    avatar: Optional[str] = None         # 头像URL
    platform: Platform = Platform.QQ     # 所属平台
    extra: Dict[str, Any] = None        # 额外信息
    
    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


@dataclass
class SendResult:
    """发送结果"""
    success: bool                        # 是否成功
    message_id: Optional[str] = None     # 消息ID
    error: Optional[str] = None          # 错误信息
    timestamp: int = 0                   # 发送时间戳


class PlatformAdapter(ABC):
    """
    平台适配器基类
    所有平台适配器都需要继承此类并实现抽象方法
    """
    
    def __init__(self):
        self.platform: Platform = Platform.QQ
        self._message_callbacks: List[Callable] = []
        self._initialized: bool = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化连接
        
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        pass
    
    @abstractmethod
    async def send_text(
        self, 
        target: str, 
        content: str, 
        is_group: bool = False
    ) -> SendResult:
        """
        发送文本消息
        
        Args:
            target: 目标ID（用户ID或群ID）
            content: 消息内容
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        pass
    
    @abstractmethod
    async def send_image(
        self, 
        target: str, 
        image: Union[str, bytes],
        is_group: bool = False
    ) -> SendResult:
        """
        发送图片
        
        Args:
            target: 目标ID
            image: 图片路径或字节流
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        pass
    
    @abstractmethod
    async def send_voice(
        self, 
        target: str, 
        voice: Union[str, bytes],
        is_group: bool = False
    ) -> SendResult:
        """
        发送语音
        
        Args:
            target: 目标ID
            voice: 语音路径或字节流
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        pass
    
    async def send_file(
        self,
        target: str,
        file_path: str,
        is_group: bool = False
    ) -> SendResult:
        """
        发送文件（可选实现）
        
        Args:
            target: 目标ID
            file_path: 文件路径
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        return SendResult(
            success=False,
            error="此平台不支持发送文件"
        )
    
    @abstractmethod
    async def get_user_info(self, user_id: str) -> Optional[User]:
        """
        获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            User: 用户信息，失败返回None
        """
        pass
    
    @abstractmethod
    async def get_group_members(self, group_id: str) -> List[User]:
        """
        获取群成员列表
        
        Args:
            group_id: 群ID
            
        Returns:
            List[User]: 群成员列表
        """
        pass
    
    async def get_group_info(self, group_id: str) -> Optional[Dict[str, Any]]:
        """
        获取群信息（可选实现）
        
        Args:
            group_id: 群ID
            
        Returns:
            Dict: 群信息
        """
        return None
    
    def on_message(self, callback: Callable[[Message], None]) -> None:
        """
        注册消息回调函数
        
        Args:
            callback: 回调函数，接收Message对象
        """
        self._message_callbacks.append(callback)
    
    async def _dispatch_message(self, message: Message) -> None:
        """
        分发消息到所有回调函数
        
        Args:
            message: 消息对象
        """
        for callback in self._message_callbacks:
            try:
                if callable(callback):
                    await callback(message)
            except Exception as e:
                print(f"消息回调执行失败: {e}")
    
    async def is_healthy(self) -> bool:
        """
        检查适配器健康状态
        
        Returns:
            bool: 是否健康
        """
        return self._initialized
    
    def get_platform_name(self) -> str:
        """
        获取平台名称
        
        Returns:
            str: 平台名称
        """
        return self.platform.value
    
    async def recall_message(self, message_id: str) -> bool:
        """
        撤回消息（可选实现）
        
        Args:
            message_id: 消息ID
            
        Returns:
            bool: 是否成功
        """
        return False
    
    async def send_forward_message(
        self,
        target: str,
        messages: List[Message],
        is_group: bool = False
    ) -> SendResult:
        """
        发送合并转发消息（可选实现）
        
        Args:
            target: 目标ID
            messages: 消息列表
            is_group: 是否为群消息
            
        Returns:
            SendResult: 发送结果
        """
        return SendResult(
            success=False,
            error="此平台不支持合并转发"
        )