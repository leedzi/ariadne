"""
图片处理插件
支持图片识别和处理
"""

from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.log import logger
from typing import Optional
import httpx
import os
from pathlib import Path

# 导入现有的图片识别服务
try:
    from src.services.ai.image_recognition_service import ImageRecognitionService
except ImportError as e:
    logger.warning(f"导入图片识别服务失败: {e}")
    ImageRecognitionService = None


# 创建图片消息处理器
image_handler = on_message(priority=5, block=False)


class ImagePlugin:
    """图片处理插件类"""
    
    def __init__(self):
        self.recognition_service = None
        self._initialized = False
        self.temp_dir = Path("temp/images")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """初始化插件"""
        if self._initialized:
            return
        
        try:
            # 初始化图片识别服务
            if ImageRecognitionService:
                # 读取配置
                import json
                config_path = Path("data/config/config.json")
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    # 获取图片识别配置
                    img_config = config.get('categories', {}).get('media_settings', {}).get('settings', {}).get('image_recognition', {})
                    api_key = img_config.get('api_key', {}).get('value', '')
                    base_url = img_config.get('base_url', {}).get('value', '')
                    model = img_config.get('model', {}).get('value', 'gemini-2.5-pro')
                    temperature = img_config.get('temperature', {}).get('value', 0.7)
                    
                    if api_key and base_url:
                        self.recognition_service = ImageRecognitionService(
                            api_key=api_key,
                            base_url=base_url,
                            temperature=temperature,
                            model=model
                        )
                        logger.info(f"[ImagePlugin] 图片识别服务初始化成功 (模型: {model})")
                    else:
                        logger.warning("[ImagePlugin] 图片识别配置不完整，服务未初始化")
                else:
                    logger.warning("[ImagePlugin] 配置文件不存在")
            else:
                logger.warning("[ImagePlugin] 图片识别服务未找到")
            
            self._initialized = True
            logger.info("[ImagePlugin] 图片插件初始化完成")
        except Exception as e:
            logger.error(f"[ImagePlugin] 初始化失败: {e}", exc_info=True)
    
    def has_image(self, event: Event) -> bool:
        """
        检查消息是否包含图片
        
        Args:
            event: 消息事件
            
        Returns:
            bool: 是否包含图片
        """
        message: Message = event.get_message()
        for seg in message:
            if seg.type == "image":
                return True
        return False
    
    async def download_image(self, url: str) -> Optional[str]:
        """
        下载图片到本地
        
        Args:
            url: 图片URL
            
        Returns:
            str: 本地路径，失败返回None
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                
                # 生成文件名
                filename = f"img_{hash(url)}.jpg"
                filepath = self.temp_dir / filename
                
                # 保存图片
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"[ImagePlugin] 图片已下载: {filepath}")
                return str(filepath)
        except Exception as e:
            logger.error(f"[ImagePlugin] 下载图片失败: {e}")
            return None
    
    async def recognize_image(self, image_path: str, is_emoji: bool = False) -> Optional[str]:
        """
        识别图片内容
        
        Args:
            image_path: 图片路径
            is_emoji: 是否为表情包
            
        Returns:
            str: 识别结果，失败返回None
        """
        try:
            if not self.recognition_service:
                return "图片识别服务未配置"
            
            # 调用识别服务（同步方法，在异步函数中直接调用）
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.recognition_service.recognize_image,
                image_path,
                is_emoji
            )
            return result
        except Exception as e:
            logger.error(f"[ImagePlugin] 图片识别失败: {e}", exc_info=True)
            return f"识别失败: {str(e)}"
    
    async def process_images(self, event: Event) -> list:
        """
        处理消息中的所有图片
        
        Args:
            event: 消息事件
            
        Returns:
            list: 识别结果列表
        """
        results = []
        message: Message = event.get_message()
        
        for seg in message:
            if seg.type == "image":
                try:
                    # 获取图片URL
                    image_url = seg.data.get("url")
                    if not image_url:
                        logger.warning("[ImagePlugin] 图片URL为空")
                        continue
                    
                    logger.info(f"[ImagePlugin] 处理图片: {image_url}")
                    
                    # 下载图片
                    image_path = await self.download_image(image_url)
                    if not image_path:
                        results.append("图片下载失败")
                        continue
                    
                    # 识别图片
                    recognition_result = await self.recognize_image(image_path)
                    if recognition_result:
                        results.append(recognition_result)
                    
                    # 清理临时文件（可选）
                    # os.remove(image_path)
                except Exception as e:
                    logger.error(f"[ImagePlugin] 处理图片异常: {e}")
                    results.append(f"处理失败: {str(e)}")
        
        return results


# 创建全局插件实例
plugin = ImagePlugin()


@image_handler.handle()
async def handle_image_message(bot: Bot, event: Event):
    """处理包含图片的消息 - 识别图片时通知队列暂停，识别完成后放行"""
    from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
    
    # 初始化插件（仅第一次）
    if not plugin._initialized:
        await plugin.initialize()
    
    # 检查是否包含图片
    if not plugin.has_image(event):
        # 不包含图片，放行给其他插件
        return
    
    # 【群聊图片不处理】
    if isinstance(event, GroupMessageEvent):
        logger.debug("[ImagePlugin] 群聊图片不处理，放行")
        return
    
    # 如果图片识别服务未配置，直接放行
    if not plugin.recognition_service:
        logger.debug("[ImagePlugin] 图片识别服务未配置，放行")
        return
    
    try:
        # 获取队列key（与chat插件保持一致）
        user_id = str(event.get_user_id())
        group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else None
        queue_key = f"{group_id}_{user_id}" if group_id else user_id
        
        # 【关键1】通知chat插件：开始识别图片，暂停队列超时
        try:
            from plugins.chat import plugin as chat_plugin
            chat_plugin.set_image_recognizing(queue_key, True)
            logger.info(f"[ImagePlugin] 🖼️ 已通知队列 {queue_key} 暂停超时，等待图片识别")
        except Exception as e:
            logger.warning(f"[ImagePlugin] 无法通知队列系统: {e}")
        
        # 仅处理私聊图片
        logger.info("[ImagePlugin] 开始识别图片...")
        
        # 同步识别图片（阻塞等待识别完成）
        results = await plugin.process_images(event)
        
        # 【关键2】通知chat插件：识别完成，恢复队列处理
        try:
            chat_plugin.set_image_recognizing(queue_key, False)
            logger.info(f"[ImagePlugin] ✅ 已通知队列 {queue_key} 图片识别完成")
        except Exception as e:
            logger.warning(f"[ImagePlugin] 无法通知队列系统: {e}")
        
        # 过滤有效结果
        valid_results = [r for r in results if r and "未配置" not in r and "失败" not in r]
        
        if valid_results:
            recognition_text = "\n".join(valid_results)
            original_text = event.get_plaintext().strip()
            
            # 构建新的消息内容：图片识别结果
            if original_text and not original_text.startswith('http'):
                # 图片附带文本
                new_message_text = f"[图片内容: {recognition_text}] {original_text}"
            else:
                # 纯图片
                new_message_text = f"[图片内容: {recognition_text}]"
            
            logger.info(f"[ImagePlugin] ✅ 图片识别完成: {recognition_text[:50]}...")
            
            # 【关键3】修改消息内容为识别结果，然后放行给Chat插件的消息队列
            new_message = Message(new_message_text)
            event._message = new_message
            event.message = new_message
            
            logger.info(f"[ImagePlugin] 已将图片替换为识别结果，放行给消息队列")
            
            # 放行给Chat插件，让它加入消息队列
            return
        else:
            logger.debug("[ImagePlugin] 无有效识别结果，放行")
            return
            
    except Exception as e:
        logger.error(f"[ImagePlugin] 处理图片消息失败: {e}", exc_info=True)
        # 发生异常时，确保解除队列暂停状态
        try:
            from plugins.chat import plugin as chat_plugin
            chat_plugin.set_image_recognizing(queue_key, False)
        except:
            pass
        return


# 导出插件
__plugin_name__ = "image"
__plugin_usage__ = "图片识别功能"
__plugin_version__ = "1.0.0"