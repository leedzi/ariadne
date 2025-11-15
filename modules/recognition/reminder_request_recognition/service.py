"""
任务识别服务

负责识别消息中的提醒任务意图
"""

import json
import os
import logging
import sys
import ast
from datetime import datetime
from typing import Optional, List, Dict, Union
from openai import OpenAI

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from src.services.ai.llm_service import LLMService
from src.autoupdate.updater import Updater
from data.config import config

logger = logging.getLogger('main')

class ReminderRecognitionService:
    def __init__(self, llm_service: LLMService):
        """
        初始化任务识别服务
        
        Args:
            llm_service: LLM 服务实例，用于调用 LLM
        """
        self.llm_service = llm_service
        self.intent_recognition_settings = {
            "api_key": config.intent_recognition.api_key,
            "base_url": config.intent_recognition.base_url,
            "model": config.intent_recognition.model,
            "temperature": config.intent_recognition.temperature
        }
        self.updater = Updater()
        self.client = OpenAI(
            api_key=self.intent_recognition_settings["api_key"],
            base_url=self.intent_recognition_settings["base_url"],
            default_headers={
                "Content-Type": "application/json",
                "User-Agent": self.updater.get_version_identifier(),
                "X-KouriChat-Version": self.updater.get_current_version()
            }
        )
        self.config = self.llm_service.config

        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(current_dir, "prompt.md"), "r", encoding="utf-8") as f:
            self.sys_prompt = f.read().strip()

    def recognize(self, message: str) -> Union[str, List[Dict], None]:
        """
        识别并提取消息中的任务意图，支持多个任务意图的识别

        Args:
            message: 用户消息
        
        Returns:
            Union[str, List[Dict], None]: "NOT_TIME_RELATED"或包含提醒任务的列表
        """
        current_time = datetime.now()        
        messages = [ {"role": "system", "content": self.sys_prompt}]
        current_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(current_dir, "example_message.json"), 'r', encoding='utf-8') as f:
            data = json.load(f)
        for example in data.values():
            messages.append({
                "role": example["input"]["role"],
                "content": example["input"]["content"]
            })
            messages.append({
                "role": example["output"]["role"],
                "content": str(example["output"]["content"])
            })
        messages.append({
            "role": "user",
            "content": f"时间：{current_time.strftime('%Y-%m-%d %H:%M:%S')}\n消息：{message}"
        })

        # 使用config字典访问max_token，添加安全检查
        max_tokens = 2000  # 默认值
        if self.llm_service and hasattr(self.llm_service, 'config') and self.llm_service.config:
            max_tokens = self.llm_service.config.get("max_token", 2000)
        
        request_config = {
            "model": self.intent_recognition_settings["model"],
            "messages": messages,
            "temperature": self.intent_recognition_settings["temperature"],
            "max_tokens": max_tokens,
        }

        # 添加重试限制，防止无限循环
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = self.client.chat.completions.create(**request_config)
                response_content = response.choices[0].message.content
                
                # 针对 Gemini 模型的回复进行预处理
                if response_content.startswith("```json") and response_content.endswith("```"):
                    response_content = response_content[7:-3].strip()
                
                # 不包含定时提醒意图
                if response_content == "NOT_TIME_RELATED":
                    return response_content
                
                try:
                    response_content = ast.literal_eval(response_content)
                    if isinstance(response_content, list):
                        return response_content
                except (ValueError, SyntaxError) as e:
                    retry_count += 1
                    logger.warning(f"识别定时任务意图失败 (尝试 {retry_count}/{max_retries}): {e}")
                    if retry_count >= max_retries:
                        logger.error("识别定时任务意图失败，已达到最大重试次数")
                        return None
            except Exception as e:
                retry_count += 1
                logger.error(f"调用意图识别API失败 (尝试 {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    logger.error("意图识别API调用失败，已达到最大重试次数")
                    return None
        
        return None


'''
单独对模块进行调试时，可以使用该代码
'''
if __name__ == '__main__':
    llm_service = LLMService(
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
        model=config.llm.model,
        max_token=1024,
        temperature=0.8,
        max_groups=5
    )
    test = ReminderRecognitionService(llm_service)
    time_infos = test.recognize("我再做一会儿，三点半提醒我休息")
    if time_infos == "NOT_TIME_RELATED":
        print(time_infos)
    else:
        for task in time_infos:
            print(f"提醒时间: {task['target_time']}, 内容: {task['reminder_content']}")