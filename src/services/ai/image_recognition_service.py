"""
图像识别 AI 服务模块 (最终修正版)
加入了图片压缩功能，以解决 413 Payload Too Large 错误。
"""
import base64
import logging
import requests
from typing import Optional
import os
import json
import copy
from openai import OpenAI
from PIL import Image #【关键修正】从 Pillow (PIL) 库中导入 Image 类
import io

logger = logging.getLogger('main')

class ImageRecognitionService:
    def __init__(self, api_key: str, base_url: str, temperature: float, model: str, stream: bool = False):
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = min(max(0.0, temperature), 1.0)
        self.model = model
        self.stream = stream

        from src.autoupdate.updater import Updater
        updater = Updater()
        self.client = OpenAI(
            api_key=api_key, base_url=base_url,
            default_headers={
                'Content-Type': 'application/json',
                'User-Agent': updater.get_version_identifier(),
                'X-KouriChat-Version': updater.get_current_version()
            },
            timeout=120.0
        )

    def _compress_and_encode_image(self, image_path: str, max_size_kb: int = 4096) -> Optional[str]:
        """【新方法】压缩图片并进行Base64编码"""
        try:
            with Image.open(image_path) as img:
                # 确保图片是RGB模式
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # 使用内存中的字节流来保存压缩后的图片，避免写入临时文件
                buffer = io.BytesIO()
                
                # 初始压缩质量
                quality = 90
                
                # 循环降低质量，直到文件大小达标
                while quality > 10:
                    buffer.seek(0) # 重置缓冲区指针
                    buffer.truncate() # 清空缓冲区
                    img.save(buffer, format="JPEG", quality=quality, optimize=True)
                    size_kb = buffer.tell() / 1024
                    if size_kb <= max_size_kb:
                        logger.info(f"图片已成功压缩至 {size_kb:.2f} KB (质量: {quality}%)")
                        break
                    quality -= 10 # 每次降低10%的质量
                else:
                    logger.error(f"无法将图片 {image_path} 压缩到 {max_size_kb} KB 以下。")
                    return None

                # 对压缩后的图片数据进行Base64编码
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"压缩或编码图片时失败: {image_path}, 错误: {e}", exc_info=True)
            return None

    def recognize_image(self, image_path: str, is_emoji: bool = False) -> str:
        """使用多模态AI识别图片内容并返回文本"""
        try:
            if not os.path.exists(image_path):
                return "抱歉，图片文件不存在"

            #【关键改动】调用新的压缩和编码方法
            logger.info(f"正在压缩和编码图片: {image_path}")
            image_content = self._compress_and_encode_image(image_path)
            if not image_content:
                return "抱歉，处理图片时出错" # 如果压缩失败，则返回错误

            text_prompt = "请描述这个图片" if not is_emoji else "这是一张微信聊天的图片截图..."

            messages_for_api = [
                {"role": "user", "content": [
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_content}"}}
                ]}
            ]
            
            logger.info(f"准备通过 OpenAI 客户端发送图像识别请求 (模型: {self.model}, Stream: {self.stream})")
            
            try:
                if self.stream:
                    stream_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages_for_api,
                        temperature=self.temperature,
                        max_tokens=2000,
                        top_p=0.7,
                        stream=True
                    )
                    recognized_text = ""
                    for chunk in stream_response:
                        if chunk.choices:
                            delta = chunk.choices[0].delta
                            if delta.content:
                                recognized_text += delta.content
                else:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages_for_api,
                        temperature=self.temperature,
                        max_tokens=2000,
                        top_p=0.7,
                        stream=False
                    )
                    
                    if not hasattr(response, 'choices') or not response.choices or not response.choices[0].message:
                        error_detail = response.model_dump_json(indent=2) if hasattr(response, 'model_dump_json') else str(response)
                        
                        # 尝试解析SSE格式的字符串 (data: {...}data: {...})
                        if isinstance(response, str) and "data: {" in response:
                            try:
                                logger.info("检测到SSE格式字符串，尝试解析...")
                                parsed_content = ""
                                chunks = response.split('data: ')
                                for chunk in chunks:
                                    chunk = chunk.strip()
                                    if not chunk or chunk == '[DONE]': continue
                                    try:
                                        data = json.loads(chunk)
                                        if 'choices' in data and len(data['choices']) > 0:
                                            delta = data['choices'][0].get('delta', {})
                                            part = delta.get('content', '')
                                            if part:
                                                parsed_content += part
                                    except json.JSONDecodeError:
                                        continue
                                
                                if parsed_content:
                                    logger.info(f"SSE解析成功，提取内容长度: {len(parsed_content)}")
                                    recognized_text = parsed_content
                            except Exception as e:
                                logger.error(f"SSE解析失败: {e}")
                                raise ValueError(f"API响应格式异常: {error_detail}")
                        else:
                             raise ValueError(f"API响应格式异常: {error_detail}")

                    else:
                         recognized_text = response.choices[0].message.content or ""
                
                if not recognized_text.strip():
                    logger.warning(f"API调用成功，但返回了空内容 (模型: {self.model})。可能是API服务商的特定问题。")
                    return "抱歉，图片识别失败(AI未返回任何内容)"                

                # 处理表情包识别结果
                if is_emoji:
                    if "最后一张表情包是" in recognized_text:
                        recognized_text = recognized_text.split("最后一张表情包是", 1)[1].strip()
                    recognized_text = "用户发送了一张表情包，表情包的内容是：：" + recognized_text
                else:
                    recognized_text = "用户发送了一张照片，照片的内容是：" + recognized_text

                logger.info(f"Moonshot AI图片识别结果: {recognized_text}")
                return recognized_text


            except Exception as e:
                # OpenAI库会抛出更具体的异常，但我们用一个总的来捕获
                logger.error(f"API请求失败 (模型: {self.model}): {str(e)}", exc_info=True)
                # 检查错误信息是否包含 "timeout"
                if 'timeout' in str(e).lower():
                    return "抱歉，图片识别服务响应超时"
                return "抱歉，图片识别服务出现错误"

        except Exception as e:
            logger.error(f"图片识别过程失败: {str(e)}", exc_info=True)
            return "抱歉，图片识别过程出现内部错误"

    def chat_completion(self, messages: list, **kwargs) -> Optional[str]:
        """发送聊天请求到 Moonshot AI"""
        try:
            data = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get('temperature', self.temperature)
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data
            )
            response.raise_for_status()

            result = response.json()
            return result['choices'][0]['message']['content']

        except Exception as e:
            logger.error(f"图像识别服务请求失败: {str(e)}")
            return None