"""
LLM AI 服务模块 (最终融合版)
集成了时间感知、世界书、智能总结和CoT支持。
"""

import logging
import re
import os
import random
import json
import time
import datetime #【修正】确保导入
import pathlib
import requests
from typing import Dict, List, Optional, Union #【修正】确保导入
from openai import OpenAI
from src.autoupdate.updater import Updater
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type
import emoji

logger = logging.getLogger('main')

class LLMService:
    def __init__(self, api_key: str, base_url: str, model: str,
                 max_token: int, temperature: float, max_groups: int, auto_model_switch: bool = False, stream: bool = False):
        updater = Updater()
        version = updater.get_current_version()
        version_identifier = updater.get_version_identifier()
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "Content-Type": "application/json",
                "User-Agent": version_identifier,
                "X-KouriChat-Version": version
            }
        )
        self.config = {
            "model": model, "max_token": max_token, "temperature": temperature,
            "max_groups": max_groups, "auto_model_switch": auto_model_switch, "stream": stream
        }
        self.chat_contexts: Dict[str, List[Dict]] = {}
        self.original_model = model
        self.safe_pattern = re.compile(r'[\x00-\x1F\u202E\u200B]')
        if 'localhost:11434' in base_url:
            self.ollama_models = self.get_ollama_models()
        else:
            self.ollama_models = []
        self.available_models = self._get_available_models()

    def _manage_context(self, user_id: str, message_obj: Dict):
        """【升级版】上下文管理器，处理带时间戳的字典"""
        if user_id not in self.chat_contexts:
            self.chat_contexts[user_id] = []
        
        # 确保所有进入上下文的消息都有时间戳
        if 'timestamp' not in message_obj:
            message_obj['timestamp'] = datetime.datetime.now().isoformat()
        
        self.chat_contexts[user_id].append(message_obj)

        max_len = self.config["max_groups"] * 2
        while len(self.chat_contexts[user_id]) > max_len:
            self.chat_contexts[user_id].pop(0)

    def _build_time_context(self, user_id: str) -> str:
        """构建时间上下文信息"""
        if user_id not in self.chat_contexts or len(self.chat_contexts[user_id]) < 2:
            return "这是你们今天的第一次对话。"
        try:
            last_msg = self.chat_contexts[user_id][-2]
            if 'timestamp' in last_msg:
                last_msg_time = datetime.datetime.fromisoformat(last_msg['timestamp'])
                time_diff = datetime.datetime.now() - last_msg_time
                seconds = int(time_diff.total_seconds())
                if seconds < 60: return f"距离上条消息仅过去了{seconds}秒"
                if seconds < 3600: return f"距离上条消息过去了{seconds // 60}分钟"
                return f"距离上条消息过去了{seconds // 3600}小时"
        except Exception as e:
            logger.error(f"构建时间上下文失败: {str(e)}")
        return "请注意时间的连续性。"

    def _sanitize_response(self, raw_text: str) -> str:
        if not isinstance(raw_text, str): return ""
        try:
            cleaned = re.sub(self.safe_pattern, '', raw_text)
            cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
            return self._process_emojis(cleaned)
        except Exception as e:
            logger.error(f"Response sanitization failed: {str(e)}")
            return "响应处理异常"

    def _process_emojis(self, text: str) -> str:
        try:
            return emoji.emojize(emoji.demojize(text))
        except Exception:
            return text

    def _filter_thinking_content(self, content: str) -> str:
        try:
            if not isinstance(content, str): return ""
            # 优先处理我们自己的 [think] 标签
            think_pattern_square = re.compile(r'\[think\].*?\[/think\]\s*', re.DOTALL | re.IGNORECASE)
            content = think_pattern_square.sub('', content).strip()
            
            # 处理XML风格的 <think> 和 <thinking>
            think_pattern_xml = re.compile(r'<(think|thinking)>.*?</\1>\s*', re.DOTALL | re.IGNORECASE)
            content = think_pattern_xml.sub('', content).strip()
            
            # 最后处理三换行符
            triple_newline_match = re.search(r'\n\n\n', content)
            if triple_newline_match:
                content = content[triple_newline_match.end():]
            
            return content.strip()
        except Exception as e:
            logger.error(f"过滤思考内容失败: {str(e)}")
            return content

    def _validate_response(self, response: dict) -> bool:
        try:
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices and isinstance(choices, list) and choices[0]:
                    message = choices[0].get("message", {})
                    if message and isinstance(message.get("content"), str):
                        return True
            return False
        except Exception as e:
            logger.error(f"验证响应时发生错误: {str(e)}")
            return False

    def get_response(self, message: str, user_id: str, system_prompt: str, previous_context: List[Dict] = None, core_memory: str = None, image_data: str = None) -> str:
        is_summarization_task = user_id.startswith("summarize_")
        if not message.strip() and not image_data: return "Error: Empty message received"
        
        final_system_prompt_content = ""
        messages_for_api = []

        if is_summarization_task:
            logger.info(f"检测到总结任务 (user_id: {user_id}), 构建独立的、无状态的总结请求。")
            try:
                summary_payload = json.loads(system_prompt)
                instruction = summary_payload.get("instruction", "")
                #personality = summary_payload.get("personality", "")
                existing_memories = summary_payload.get("existing_memories", "")
                
                prompt_parts = []
                if instruction: prompt_parts.append(f"\n# 任务指令\n{instruction}")
                if existing_memories: prompt_parts.append(f"\n# 已有记忆参考（请勿重复总结）\n---\n{existing_memories}\n---")
                
                final_system_prompt_content = "\n\n".join(filter(None, prompt_parts))
            except (json.JSONDecodeError, TypeError):
                final_system_prompt_content = system_prompt
            
            # 总结任务的消息列表是独立的，不使用 self.chat_contexts
            messages_for_api = [
                {"role": "system", "content": final_system_prompt_content},
                {"role": "user", "content": f"请严格按照system指令，处理以下对话内容：\n---\n{message}\n---"}
            ]
        else: # 普通对话任务
            if previous_context and user_id not in self.chat_contexts:
                self.chat_contexts[user_id] = previous_context
            
            # 先计算时间
            now = datetime.datetime.now()
            weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            current_time_str = now.strftime(f"%Y年%m月%d日 %H:%M:%S {weekdays[now.weekday()]}")
            
            # 将"当前时间"作为前缀拼进本次用户消息内容（主动消息也走这里）
            msg_with_time = f"【系统消息：现在时间是 {current_time_str}】\n{message}"
            
            if image_data:
                # 多模态消息结构
                user_message_content = [
                    {"type": "text", "text": msg_with_time},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
                user_message_obj = {"role": "user", "content": user_message_content, "timestamp": datetime.datetime.now().isoformat()}
            else:
                user_message_obj = {"role": "user", "content": msg_with_time}
                
            self._manage_context(user_id, user_message_obj)
            
            # 后续保持不变
            time_context = self._build_time_context(user_id)
            time_prompt = f"当前时间是 {current_time_str}..."
            
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
                base_prompt_path = os.path.join(project_root, "src", "base", "base.md")
                with open(base_prompt_path, "r", encoding="utf-8") as f: base_content = f.read()
            except Exception: base_content = ""
            
            worldview_content = ""
            custom_cot_content = ""
            try:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                config_path = os.path.join(project_root, "data", "config", "config.json")
                if os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                        
                        # 加载世界书
                        if 'worldbooks' in config_data and config_data.get('worldbooks'):
                            wb_contents = [wb['content'].strip() for wb in config_data['worldbooks'] if wb.get('enabled') and wb.get('content','').strip()]
                            if wb_contents:
                                worldview_content = '\n\n'.join(wb_contents)
                                logger.info(f"已加载 {len(wb_contents)} 个世界书")
                        
                        # 加载自定义思维链
                        llm_settings = config_data.get("categories", {}).get("llm_settings", {}).get("settings", {})
                        custom_cot_enabled = llm_settings.get("custom_cot_enabled", {}).get("value", False)
                        
                        if custom_cot_enabled:
                            cot_path = os.path.join(project_root, "data", "prompts", "custom_cot.md")
                            if os.path.exists(cot_path):
                                with open(cot_path, "r", encoding="utf-8") as f:
                                    custom_cot_content = f.read().strip()
                                    if custom_cot_content:
                                        logger.info("已加载自定义思维链提示词")

            except Exception as e:
                logger.error(f"从配置文件加载配置失败: {str(e)}")
            
            character_prompt_parts = [base_content]
            if worldview_content: character_prompt_parts.append(f"你所饰演的角色所处世界的世界观为：\n{worldview_content}")
            if core_memory: character_prompt_parts.append(f"你所饰演角色所具备的核心记忆为：\n{core_memory}")
            character_prompt_parts.append(f"你所扮演的角色介绍如下：\n{system_prompt}")
            if custom_cot_content: character_prompt_parts.append(f"{custom_cot_content}")
            
            character_prompt = "\n\n".join(filter(None, character_prompt_parts))
            final_prompt = f"{time_prompt}\n\n{character_prompt}"

        # 这个 messages_for_api 现在会根据上面的 if/else 结果，包含正确的 system prompt
            clean_context_for_api = [{"role": msg["role"], "content": msg["content"]} for msg in self.chat_contexts.get(user_id, [])]
            messages_for_api = [{"role": "system", "content": final_prompt}, *clean_context_for_api]
        
        max_retries = 3
        last_error = None
        current_model = self.config["model"]
        models_tried = []
        is_ollama = 'localhost:11434' in str(self.client.base_url)

        for attempt in range(max_retries):
            try:
                models_tried.append(current_model)
                if is_ollama:
                    # (Ollama 请求逻辑)
                    pass 
                else: # OpenAI
                    request_config = {
                        "model": current_model,
                        "messages": messages_for_api,
                        "temperature": self.config["temperature"],
                        "max_tokens": self.config["max_token"],
                        "frequency_penalty": 0.2,
                        "stream": self.config.get("stream", False)
                    }
                    
                    raw_content = ""
                    if self.config.get("stream", False):
                        stream_response = self.client.chat.completions.create(**request_config)
                        for chunk in stream_response:
                            if chunk.choices:
                                delta = chunk.choices[0].delta
                                if delta.content:
                                    raw_content += delta.content
                    else:
                        response = self.client.chat.completions.create(**request_config)
                        
                        # 兼容性处理：获取响应字典
                        response_dict = None
                        if isinstance(response, dict):
                            response_dict = response
                        elif hasattr(response, 'model_dump'):
                            response_dict = response.model_dump()
                        else:
                            # 尝试作为字符串解析
                            try:
                                response_dict = json.loads(str(response))
                            except:
                                logger.warning(f"API响应类型未知: {type(response)}")
                        
                        if not response_dict or not self._validate_response(response_dict):
                            raise ValueError(f"错误的API响应结构: {type(response)}")
                            
                        # 获取内容
                        if hasattr(response, 'choices'):
                            raw_content = response.choices[0].message.content or ""
                        elif isinstance(response, dict):
                            raw_content = response.get('choices', [])[0].get('message', {}).get('content', "") or ""
                        else:
                            raw_content = ""
                
                # 清理响应：移除思维链标签
                cleaned_content = self._sanitize_response(raw_content)
                filtered_content = self._filter_thinking_content(cleaned_content)
                
                if not is_summarization_task:
                    assistant_reply_obj = {"role": "assistant", "content": filtered_content, "timestamp": datetime.datetime.now().isoformat()}
                    self._manage_context(user_id, assistant_reply_obj)

                return filtered_content

            except Exception as e:
                last_error = f"Error: {str(e)}"
                logger.warning(f"模型 {current_model} API请求失败 (尝试 {attempt+1}/{max_retries}): {str(e)}")
                if self.config.get("auto_model_switch", False) and attempt < max_retries - 1:
                    next_model = self._get_next_model(current_model)
                    if next_model and next_model not in models_tried:
                        logger.info(f"自动切换到模型: {next_model}")
                        current_model = next_model
                        continue
        
        logger.error(f"所有模型尝试均失败: {last_error}")
        return last_error
    
    def clear_history(self, user_id: str) -> bool:
        """
        清空指定用户的对话历史
        """
        if user_id in self.chat_contexts:
            del self.chat_contexts[user_id]
            logger.info("已清除用户 %s 的对话历史", user_id)
            return True
        return False

    def analyze_usage(self, response: dict) -> Dict:
        """
        用量分析工具
        """
        usage = response.get("usage", {})
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "estimated_cost": (usage.get("total_tokens", 0) / 1000) * 0.02  # 示例计价
        }

    def chat(self, messages: list, **kwargs) -> str:
        """
        发送聊天请求并获取回复

        Args:
            messages: 消息列表，每个消息是包含 role 和 content 的字典
            **kwargs: 额外的参数配置，包括 model、temperature 等

        Returns:
            str: AI的回复内容
        """
        try:
            # 使用传入的model参数，如果没有则使用默认模型
            model = kwargs.get('model', self.config["model"])
            logger.info(f"使用模型: {model} 发送聊天请求")

            stream = kwargs.get('stream', self.config.get("stream", False))
            if stream:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=kwargs.get('temperature', self.config["temperature"]),
                    max_tokens=self.config["max_token"],
                    stream=True
                )
                raw_content = ""
                for chunk in response:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            raw_content += delta.content
            else:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=kwargs.get('temperature', self.config["temperature"]),
                    max_tokens=self.config["max_token"]
                )

                # 兼容性处理
                response_dict = None
                if isinstance(response, dict):
                    response_dict = response
                elif hasattr(response, 'model_dump'):
                    response_dict = response.model_dump()
                
                if not response_dict or not self._validate_response(response_dict):
                    error_msg = f"错误的API响应结构: {type(response)}"
                    logger.error(error_msg)
                    return f"Error: {error_msg}"

                if hasattr(response, 'choices'):
                    raw_content = response.choices[0].message.content
                else:
                    raw_content = response_dict.get('choices', [])[0].get('message', {}).get('content', "")
            # 清理和过滤响应内容
            clean_content = self._sanitize_response(raw_content)
            filtered_content = self._filter_thinking_content(clean_content)

            return filtered_content or ""

        except Exception as e:
            logger.error(f"Chat completion failed: {str(e)}")
            return f"Error: {str(e)}"

    def get_ollama_models(self) -> List[Dict]:
        """获取本地 Ollama 可用的模型列表"""
        try:
            response = requests.get('http://localhost:11434/api/tags')
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [
                    {
                        "id": model['name'],
                        "name": model['name'],
                        "status": "active",
                        "type": "chat",
                        "context_length": 16000  # 默认上下文长度
                    }
                    for model in models
                ]
            return []
        except Exception as e:
            logger.error(f"获取Ollama模型列表失败: {str(e)}")
            return []

    def _get_available_models(self) -> List[str]:
        """
        通过API动态获取当前提供商支持的聊天模型列表
        
        Returns:
            List[str]: 可用的聊天模型列表
        """
        try:
            base_url = str(self.client.base_url).lower()
            
            # 特殊处理Ollama
            if 'localhost:11434' in base_url:
                return [model['id'] for model in self.ollama_models]
            
            # 使用OpenAI标准的v1/models端点获取模型列表
            logger.info(f"正在从 {self.client.base_url} 获取可用模型列表...")
            
            try:
                # 使用OpenAI客户端获取模型列表
                models_response = self.client.models.list()
                
                # 过滤出聊天模型
                chat_models = []
                for model in models_response.data:
                    model_id = model.id
                    
                    # 过滤聊天模型的关键词
                    chat_keywords = [
                        'chat', 'gpt', 'claude', 'deepseek', 'kourichat', 'grok',
                        'llama', 'mistral', 'qwen', 'yi', 'baichuan'
                    ]
                    
                    # 排除非聊天模型的关键词
                    exclude_keywords = [
                        'embedding', 'whisper', 'tts', 'dall-e', 'vision',
                        'moderation', 'edit', 'completion', 'instruct',
                        'image', 'search', 'weblens', 'tool'
                    ]
                    
                    model_lower = model_id.lower()
                    
                    # 检查是否包含聊天关键词且不包含排除关键词
                    is_chat_model = (
                        any(keyword in model_lower for keyword in chat_keywords) and
                        not any(keyword in model_lower for keyword in exclude_keywords)
                    )
                    
                    if is_chat_model:
                        chat_models.append(model_id)
                
                if chat_models:
                    # 对模型进行优先级排序，DeepSeek系列优先
                    sorted_models = self._sort_models_by_priority(chat_models)
                    logger.info(f"成功获取到 {len(sorted_models)} 个聊天模型: {sorted_models}")
                    return sorted_models
                else:
                    logger.warning("未找到聊天模型，使用当前模型作为唯一选项")
                    return [self.original_model]
                    
            except Exception as api_error:
                logger.warning(f"通过API获取模型列表失败: {str(api_error)}")
                
                # API调用失败时的后备方案：根据base_url推测可能的模型
                return self._get_fallback_models(base_url)
                
        except Exception as e:
            logger.error(f"获取可用模型列表失败: {str(e)}")
            # 最终后备方案：只返回当前模型
            return [self.original_model]
    
    def _sort_models_by_priority(self, models: List[str]) -> List[str]:
        """
        按优先级对模型进行排序
        优先级顺序：Grok-4 > Grok-3 > Grok-2 > DeepSeek > KouriChat > Qwen > GPT > Claude > 其他
        
        Args:
            models: 原始模型列表
            
        Returns:
            List[str]: 按优先级排序后的模型列表
        """
        def get_model_priority(model_name: str) -> int:
            """获取模型的优先级数字，数字越小优先级越高"""
            model_lower = model_name.lower()
            
            # Grok系列 - 最高优先级
            if 'grok' in model_lower:
                if '4' in model_lower:
                    return 1  # Grok-4 最优先
                elif '3' in model_lower:
                    if 'fast' in model_lower:
                        return 2  # Grok-3-fast 次优先
                    else:
                        return 3  # Grok-3 第三优先
                elif '2' in model_lower:
                    return 4  # Grok-2 第四优先
                elif '1.5' in model_lower:
                    return 5  # Grok-1.5 第五优先
                else:
                    return 6  # 其他 Grok 模型
            
            # DeepSeek系列 - 第二优先级（稳定快速）
            elif 'deepseek' in model_lower:
                if 'r1' in model_lower or 'reasoner' in model_lower:
                    return 7  # DeepSeek R1/Reasoner
                elif 'v3' in model_lower:
                    return 8  # DeepSeek V3
                else:
                    return 9  # 其他 DeepSeek 模型
            
            # KouriChat系列 - 第三优先级
            elif 'kourichat' in model_lower:
                if 'r1' in model_lower:
                    return 10  # KouriChat R1
                elif 'v3' in model_lower:
                    return 11  # KouriChat V3
                else:
                    return 12  # 其他 KouriChat 模型
            
            # Qwen系列 - 第四优先级
            elif 'qwen' in model_lower:
                if 'plus' in model_lower:
                    return 13  # Qwen Plus
                elif 'turbo' in model_lower:
                    return 14  # Qwen Turbo
                else:
                    return 15  # 其他 Qwen 模型
            
            # GPT系列 - 第五优先级
            elif 'gpt' in model_lower:
                if '4o' in model_lower:
                    return 16  # GPT-4o 系列
                elif '4' in model_lower:
                    return 17  # 其他 GPT-4 系列
                elif '5' in model_lower:
                    return 18  # GPT-5 系列
                else:
                    return 19  # 其他 GPT 模型
            
            # Claude系列 - 第六优先级（速度较慢）
            elif 'claude' in model_lower:
                return 20
            
            # 其他模型 - 最低优先级
            else:
                return 21
        
        # 按优先级排序
        sorted_models = sorted(models, key=get_model_priority)
        
        logger.debug(f"模型优先级排序结果: {sorted_models}")
        return sorted_models

    def _get_fallback_models(self, base_url: str) -> List[str]:
        """
        当API调用失败时的后备模型列表
        
        Args:
            base_url: API基础URL
            
        Returns:
            List[str]: 后备模型列表
        """
        fallback_models = []
        
        if 'kourichat.com' in base_url:
            # KouriChat API - 优先Grok-4系列
            fallback_models = [
                "grok-4", "grok-3", "grok-3-fast", "grok-2", "grok-1.5", "grok",
                "deepseek-r1", "deepseek-v3", "deepseek-chat",
                "kourichat-r1", "kourichat-v3",
                "qwen-plus-latest", "qwen-turbo-latest"
            ]
        elif 'deepseek.com' in base_url:
            fallback_models = ["deepseek-reasoner", "deepseek-chat"]
        elif 'openai.com' in base_url:
            fallback_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
        elif 'api.moonshot.cn' in base_url:
            fallback_models = ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]
        elif 'api.siliconflow.cn' in base_url:
            fallback_models = ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct"]
        else:
            # 通用后备列表
            fallback_models = [self.original_model]
        
        # 对后备模型也进行优先级排序
        return self._sort_models_by_priority(fallback_models)

    def _get_next_model(self, current_model: str) -> Optional[str]:
        """
        获取下一个可用的模型
        
        Args:
            current_model: 当前使用的模型
            
        Returns:
            Optional[str]: 下一个可用的模型，如果没有则返回None
        """
        if not self.available_models:
            return None
        
        # 如果当前模型不在可用模型列表中（比如配置了错误的模型名）
        # 直接返回第一个可用的模型
        if current_model not in self.available_models:
            logger.info(f"当前模型 '{current_model}' 不在可用模型列表中，切换到第一个可用模型")
            return self.available_models[0]
            
        current_index = self.available_models.index(current_model)
        next_index = (current_index + 1) % len(self.available_models)
        
        # 如果只有一个模型，返回None表示没有其他模型可用
        if len(self.available_models) == 1:
            return None
        
        # 如果循环回到当前模型，说明已经尝试了所有模型
        if next_index == current_index:
            return None
            
        return self.available_models[next_index]

    def get_config(self) -> Dict:
        """
        获取当前LLM服务的配置参数
        方便外部服务（如记忆服务）获取最新配置

        Returns:
            Dict: 包含当前配置的字典
        """
        return self.config.copy()  # 返回配置的副本以防止外部修改
