"""
情境识别服务
识别对话中的场景和情境，支持智能表情选择
"""

import json
import os
import logging
import ast
from typing import Optional, Dict, Union
from openai import OpenAI

logger = logging.getLogger('main')


class ContextRecognitionService:
    """情境识别服务 - 双向分析用户消息和Bot回复"""
    
    def __init__(self, llm_service):
        """
        初始化情境识别服务
        
        Args:
            llm_service: LLM服务实例
        """
        self.llm_service = llm_service
        
        # 从llm_service获取配置
        try:
            from data.config import config
            self.recognition_settings = {
                "api_key": config.intent_recognition.api_key,
                "base_url": config.intent_recognition.base_url,
                "model": config.intent_recognition.model,
                "temperature": config.intent_recognition.temperature
            }
        except Exception as e:
            logger.warning(f"[ContextRecognition] 使用LLM主配置: {e}")
            # 降级使用主LLM配置
            self.recognition_settings = {
                "api_key": self.llm_service.api_key,
                "base_url": self.llm_service.base_url,
                "model": self.llm_service.model,
                "temperature": 0.3  # 情境识别使用较低温度
            }
        
        # 初始化OpenAI客户端
        try:
            from src.autoupdate.updater import Updater
            updater = Updater()
            self.client = OpenAI(
                api_key=self.recognition_settings["api_key"],
                base_url=self.recognition_settings["base_url"],
                default_headers={
                    "Content-Type": "application/json",
                    "User-Agent": updater.get_version_identifier(),
                    "X-KouriChat-Version": updater.get_current_version()
                }
            )
        except Exception:
            # 简化版客户端
            self.client = OpenAI(
                api_key=self.recognition_settings["api_key"],
                base_url=self.recognition_settings["base_url"]
            )
        
        # 加载提示词
        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(current_dir, "prompt.md"), "r", encoding="utf-8") as f:
            self.sys_prompt = f.read().strip()
        
        logger.info("[ContextRecognition] 情境识别服务初始化完成")
    
    async def recognize(self, user_message: str, bot_reply: str) -> Union[Dict, None]:
        """
        识别对话情境（双向分析）- 异步方法
        
        Args:
            user_message: 用户的消息
            bot_reply: Bot的回复
        
        Returns:
            Dict: 情境信息，包括：
                - has_context: 是否检测到情境
                - context_type: 情境类型 (weather/food/daily/special)
                - context_name: 具体情境 (rain/eating/reading等)
                - keywords: 关键词列表
                - should_send_emoji: 是否应该发送表情
                - has_emotion: 是否检测到情感
                - emotion: 情感类型
                - is_playful: 是否是打情骂俏
                - should_send_emotion: 是否应该发送情感表情
                - confidence: 置信度
                - reason: 判断原因
            None: 识别失败
        """
        try:
            # 构造输入
            input_data = {
                "user_message": user_message,
                "bot_reply": bot_reply
            }
            
            # 构造消息
            messages = [{"role": "system", "content": self.sys_prompt}]
            
            # 加载Few-shot示例
            current_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                with open(os.path.join(current_dir, "example_message.json"), 'r', encoding='utf-8') as f:
                    examples = json.load(f)
                
                for example in examples.values():
                    messages.append({
                        "role": example["input"]["role"],
                        "content": example["input"]["content"]
                    })
                    messages.append({
                        "role": example["output"]["role"],
                        "content": example["output"]["content"]
                    })
            except Exception as e:
                logger.warning(f"[ContextRecognition] 加载示例失败: {e}")
            
            # 添加当前对话
            messages.append({
                "role": "user",
                "content": json.dumps(input_data, ensure_ascii=False)
            })
            
            # 调用API，添加安全检查
            max_tokens = 2000  # 默认值
            if self.llm_service and hasattr(self.llm_service, 'config') and self.llm_service.config:
                max_tokens = self.llm_service.config.get("max_token", 2000)
            
            request_config = {
                "model": self.recognition_settings["model"],
                "messages": messages,
                "temperature": self.recognition_settings["temperature"],
                "max_tokens": max_tokens,
            }
            
            # 重试机制
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.client.chat.completions.create(**request_config)
                    response_content = response.choices[0].message.content
                    
                    # 预处理（处理Gemini格式）
                    if response_content.startswith("```json") and response_content.endswith("```"):
                        response_content = response_content[7:-3].strip()
                    elif response_content.startswith("```") and response_content.endswith("```"):
                        response_content = response_content[3:-3].strip()
                    
                    # 解析JSON
                    try:
                        result = json.loads(response_content)
                        logger.info(f"[ContextRecognition] 识别成功: {result.get('has_context', False)}")
                        return result
                    except json.JSONDecodeError:
                        # 尝试使用ast.literal_eval
                        try:
                            result = ast.literal_eval(response_content)
                            logger.info(f"[ContextRecognition] 识别成功: {result.get('has_context', False)}")
                            return result
                        except Exception as e:
                            logger.warning(f"[ContextRecognition] JSON解析失败 (尝试 {attempt+1}/{max_retries}): {e}")
                            if attempt >= max_retries - 1:
                                return None
                
                except Exception as e:
                    logger.error(f"[ContextRecognition] API调用失败 (尝试 {attempt+1}/{max_retries}): {e}")
                    if attempt >= max_retries - 1:
                        return None
            
            return None
            
        except Exception as e:
            logger.error(f"[ContextRecognition] 情境识别异常: {e}")
            import traceback
            traceback.print_exc()
            return None


# 单独测试
if __name__ == '__main__':
    from src.services.ai.llm_service import LLMService
    from data.config import config
    
    llm_service = LLMService(
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
        model=config.llm.model,
        max_token=1024,
        temperature=0.8,
        max_groups=5
    )
    
    service = ContextRecognitionService(llm_service)
    
    # 测试1：下雨场景
    result1 = service.recognize(
        user_message="你那边天气怎么样？",
        bot_reply="我这边下雨了，有点冷"
    )
    print("测试1（下雨）:", result1)
    
    # 测试2：打情骂俏
    result2 = service.recognize(
        user_message="你怎么这样！",
        bot_reply="哼，不理你了~"
    )
    print("测试2（打情骂俏）:", result2)
    
    # 测试3：看书
    result3 = service.recognize(
        user_message="你在干嘛？",
        bot_reply="我在看书呢"
    )
    print("测试3（看书）:", result3)