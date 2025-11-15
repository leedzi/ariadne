"""
表情包处理插件 - QQ版
负责处理表情包相关功能，包括:
- 表情标签识别
- 表情包选择
- 文件管理
"""

from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment
from nonebot.log import logger
from typing import Optional
import os
import random
import re

try:
    from data.config import config
except ImportError:
    config = None


class EmojiHandler:
    """表情包处理器"""
    
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        # 修改表情包目录路径为avatar目录下的emojis
        if config:
            self.emoji_dir = os.path.join(root_dir, config.behavior.context.avatar_dir, "emojis")
        else:
            self.emoji_dir = os.path.join(root_dir, "data", "avatars", "default", "emojis")
        
        # 支持的表情类型（72种）
        self.emotion_types = [
            'happy', 'sad', 'angry', 'neutral', 'love', 'funny', 'cute', 'bored', 'shy',
            'embarrassed', 'sleepy', 'lonely', 'hungry', 'comfort', 'surprise', 'confused',
            'playful', 'excited', 'tease', 'hot', 'speechless', 'scared', 'emo_1',
            'emo_2', 'emo_3', 'emo_4', 'emo_5', 'afraid', 'amused', 'anxious',
            'confident', 'cold', 'suspicious', 'loving', 'curious', 'envious',
            'jealous', 'miserable', 'stupid', 'sick', 'ashamed', 'withdrawn',
            'indifferent', 'sorry', 'determined', 'crazy', 'bashful', 'depressed',
            'enraged', 'frightened', 'interested', 'hopeful', 'regretful', 'stubborn',
            'thirsty', 'guilty', 'nervous', 'disgusted', 'proud', 'ecstatic',
            'frustrated', 'hurt', 'tired', 'smug', 'thoughtful', 'pained', 'optimistic',
            'relieved', 'puzzled', 'shocked', 'joyful', 'skeptical', 'bad', 'worried'
        ]
    
    def extract_emotion_tags(self, text: str) -> list:
        """从文本中提取表情标签"""
        tags = []
        # 匹配 [emotion] 格式的标签
        pattern = r'\[([^\]]+)\]'
        matches = re.findall(pattern, text)
        
        for match in matches:
            tag = match.lower()
            if tag in self.emotion_types:
                tags.append(tag)
                logger.info(f"[EmojiHandler] 检测到表情标签: {tag}")
        
        return tags
    
    def get_emoji_for_emotion(self, emotion_type: str) -> Optional[str]:
        """根据情感类型获取对应表情包路径"""
        try:
            target_dir = os.path.join(self.emoji_dir, emotion_type)
            logger.debug(f"[EmojiHandler] 查找表情包目录: {target_dir}")
            
            if not os.path.exists(target_dir):
                logger.warning(f"[EmojiHandler] 情感目录不存在: {target_dir}")
                return None
            
            # 查找支持的图片格式
            emoji_files = [
                f for f in os.listdir(target_dir)
                if f.lower().endswith(('.gif', '.jpg', '.png', '.jpeg'))
            ]
            
            if not emoji_files:
                logger.warning(f"[EmojiHandler] 目录中未找到表情包: {target_dir}")
                return None
            
            # 随机选择一个表情包
            selected = random.choice(emoji_files)
            emoji_path = os.path.join(target_dir, selected)
            logger.info(f"[EmojiHandler] 已选择 {emotion_type} 表情包: {emoji_path}")
            return emoji_path
        
        except Exception as e:
            logger.error(f"[EmojiHandler] 获取表情包失败: {str(e)}")
            return None
    
    def remove_emotion_tags(self, text: str) -> str:
        """从文本中移除表情标签"""
        # 移除所有 [emotion] 格式的标签
        for emotion in self.emotion_types:
            text = text.replace(f'[{emotion}]', '')
            text = text.replace(f'[{emotion.upper()}]', '')
        return text.strip()


# 创建全局处理器实例
emoji_handler = None


def get_emoji_handler():
    """获取表情包处理器实例"""
    global emoji_handler
    if emoji_handler is None:
        root_dir = os.getcwd()
        emoji_handler = EmojiHandler(root_dir)
    return emoji_handler


async def process_emotion_tags(text: str) -> tuple[str, list]:
    """
    处理消息中的表情标签
    
    Args:
        text: 原始消息文本
    
    Returns:
        tuple: (处理后的文本, 表情图片路径列表)
    """
    handler = get_emoji_handler()
    
    # 提取表情标签
    emotion_tags = handler.extract_emotion_tags(text)
    
    # 移除标签后的文本
    clean_text = handler.remove_emotion_tags(text)
    
    # 获取表情图片路径
    emoji_paths = []
    for emotion in emotion_tags:
        emoji_path = handler.get_emoji_for_emotion(emotion)
        if emoji_path:
            emoji_paths.append(emoji_path)
    
    return clean_text, emoji_paths


async def create_emoji_messages(emoji_paths: list) -> list:
    """
    创建表情包消息段
    
    Args:
        emoji_paths: 表情图片路径列表
    
    Returns:
        list: MessageSegment列表
    """
    messages = []
    for path in emoji_paths:
        try:
            # 使用 file:/// 协议发送本地图片
            messages.append(MessageSegment.image(f"file:///{path}"))
            logger.info(f"[EmojiHandler] 准备发送表情包: {path}")
        except Exception as e:
            logger.error(f"[EmojiHandler] 创建表情消息失败: {e}")
    
    return messages


# 导出功能
__all__ = [
    'EmojiHandler',
    'get_emoji_handler',
    'process_emotion_tags',
    'create_emoji_messages'
]

__plugin_name__ = "emoji"
__plugin_usage__ = "表情包处理功能，自动识别并发送表情"
__plugin_version__ = "1.0.0"