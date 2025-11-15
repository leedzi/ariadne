"""
语音处理模块
负责处理语音相关功能，包括:
- 语音请求识别
- TTS语音生成
- 语音文件管理
- 清理临时文件
"""

import os
import logging
import re
import emoji
import sys
from datetime import datetime
from typing import Optional
from fish_audio_sdk import Session, TTSRequest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from data.config import config

# 修改logger获取方式，确保与main模块一致
logger = logging.getLogger('main')

class TTSService:
    def __init__(self):
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        self.voice_dir = os.path.join(self.root_dir, "data", "voices")
        self.tts_api_key = config.media.text_to_speech.tts_api_key
        
        # 确保语音目录存在
        os.makedirs(self.voice_dir, exist_ok=True)

    def _clear_tts_text(self, text: str) -> str:
        """用于清洗回复,使得其适合进行TTS"""
        # 完全移除emoji表情符号
        try:
            # 将emoji转换为空字符串
            text = emoji.replace_emoji(text, replace='')
        except Exception:
            pass

        text = text.replace('$',',').replace('\r\n', '\n').replace('\r', '\n').replace('\n',',')
        text = re.sub(r'\[.*?\]','', text)
        return text.strip()

    def _generate_audio_file(self, text: str) -> Optional[str]:
        """调用TTS API生成语音"""
        try:
            # 检查 API 密钥是否配置
            if not self.tts_api_key or self.tts_api_key.strip() == "":
                logger.error("TTS API 密钥未配置")
                return None
            
            # 确保语音目录存在
            if not os.path.exists(self.voice_dir):
                os.makedirs(self.voice_dir)
                
            # 生成唯一的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            voice_path = os.path.join(self.voice_dir, f"voice_{timestamp}.mp3")
            
            logger.info(f"开始生成语音文件: {voice_path}")
            logger.debug(f"TTS 文本内容: {text[:100]}...")  # 只显示前100个字符
            
            # 调用TTS API
            with open(voice_path, "wb") as f:
                for chunk in Session(self.tts_api_key).tts(TTSRequest(
                    reference_id=config.media.text_to_speech.tts_model_id,
                    text=text
                )):
                    f.write(chunk)
            
            logger.info(f"语音文件生成成功: {voice_path}")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"语音生成失败: {error_msg}")
            
            # 针对不同错误类型提供具体建议
            if "402" in error_msg or "Payment Required" in error_msg:
                logger.error("Fish Audio API 账户余额不足，请充值后重试")
                logger.info("建议: 1. 登录 Fish Audio 官网检查账户余额")
                logger.info("建议: 2. 或者暂时禁用语音提醒功能")
            elif "401" in error_msg or "Unauthorized" in error_msg:
                logger.error("Fish Audio API 密钥无效，请检查配置")
            elif "403" in error_msg or "Forbidden" in error_msg:
                logger.error("Fish Audio API 访问被拒绝，请检查权限")
            elif "429" in error_msg or "Too Many Requests" in error_msg:
                logger.error("Fish Audio API 请求过于频繁，请稍后重试")
            else:
                logger.error(f"未知错误: {error_msg}")
            
            return None
        
        return voice_path

    def _del_audio_file(self, audio_file_path: str):
        """清理语音目录中的旧文件"""
        try:
            if os.path.isfile(audio_file_path):
                os.remove(audio_file_path)
                logger.info(f"清理语音文件: {audio_file_path}")
        except Exception as e:
            logger.error(f"清理语音文件失败 {audio_file_path}: {str(e)}")

tts = TTSService()