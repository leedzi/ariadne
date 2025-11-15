import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
import time
import re
from src.services.ai.llm_service import LLMService

# 获取日志记录器
logger = logging.getLogger('memory')

class MemoryService:
    """
    记忆服务模块 - 修改为模拟旧版长时记忆行为（追加总结），并保留新版滚动短期记忆。
    总结提示词从 'data/base/memory.md' 加载。
    【新】总结时会附带人设和历史记忆作为参考。
    【新】对话计数器已持久化，不受程序重启影响。
    """
    def __init__(self, root_dir: str, api_key: str, base_url: str, model: str, max_token: int, temperature: float, max_groups: int = 10):
        self.root_dir = root_dir
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_token = max_token
        self.temperature = temperature
        self.max_groups = max_groups
        self.llm_client = None
        
        #【关键改动】对话计数器现在从文件中加载，不再是简单的空字典
        self.conversation_count = self._load_conversation_count()

    #【关键改动】新增：获取计数统计文件的路径
    def _get_stats_path(self) -> str:
        """获取全局对话统计文件的路径。"""
        # 将统计文件放在记忆服务的根目录下，而不是每个用户下
        stats_dir = os.path.join(self.root_dir, "data", "memory_stats")
        os.makedirs(stats_dir, exist_ok=True)
        return os.path.join(stats_dir, "conversation_counts.json")

    #【关键改动】新增：加载对话计数
    def _load_conversation_count(self) -> Dict[str, int]:
        """从文件中加载对话计数器，如果文件不存在则返回空字典。"""
        stats_path = self._get_stats_path()
        try:
            if os.path.exists(stats_path):
                with open(stats_path, 'r', encoding='utf-8') as f:
                    counts = json.load(f)
                    logger.info(f"成功从 {stats_path} 加载了对话计数。")
                    return counts
            else:
                logger.info("对话计数文件不存在，将创建新的计数器。")
                return {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"加载对话计数文件失败: {e}，将使用空的计数器。")
            return {}
            
    #【关键改动】新增：保存对话计数
    def _save_conversation_count(self):
        """将当前的对话计数器保存到文件。"""
        stats_path = self._get_stats_path()
        try:
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_count, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"保存对话计数到 {stats_path} 失败: {e}")


    def _get_llm_client(self):
        # ... (此方法无变化) ...
        if not self.llm_client:
            self.llm_client = LLMService(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                max_token=self.max_token,
                temperature=self.temperature,
                max_groups=self.max_groups
            )
            logger.info(f"创建LLM客户端，API: {self.base_url}, Model: {self.model}, MaxGroups: {self.max_groups}")
        return self.llm_client

    def _get_avatar_memory_dir(self, avatar_name: str, user_id: str) -> str:
        # ... (此方法无变化) ...
        avatar_memory_dir = os.path.join(self.root_dir, "data", "avatars", avatar_name, "memory", user_id)
        os.makedirs(avatar_memory_dir, exist_ok=True)
        return avatar_memory_dir

    def _get_short_memory_path(self, avatar_name: str, user_id: str) -> str:
        # ... (此方法无变化) ...
        memory_dir = self._get_avatar_memory_dir(avatar_name, user_id)
        return os.path.join(memory_dir, "short_memory.json")

    def _get_core_memory_path(self, avatar_name: str, user_id: str) -> str:
        # ... (此方法无变化) ...
        memory_dir = self._get_avatar_memory_dir(avatar_name, user_id)
        return os.path.join(memory_dir, "long_memory_buffer.txt")

    def _get_timestamp(self) -> str:
        # ... (此方法无变化) ...
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def initialize_memory_files(self, avatar_name: str, user_id: str):
        # ... (此方法无变化) ...
        try:
            memory_dir = self._get_avatar_memory_dir(avatar_name, user_id)
            short_memory_path = self._get_short_memory_path(avatar_name, user_id)
            long_term_memory_path = self._get_core_memory_path(avatar_name, user_id)

            if not os.path.exists(short_memory_path):
                with open(short_memory_path, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                logger.info(f"创建短期记忆文件 (JSON): {short_memory_path}")

            if not os.path.exists(long_term_memory_path):
                with open(long_term_memory_path, "w", encoding="utf-8"):
                    pass # 创建空文件
                logger.info(f"创建长期记忆缓冲区文件 (TXT): {long_term_memory_path}")

        except Exception as e:
            logger.error(f"初始化记忆文件失败 ({avatar_name}/{user_id}): {str(e)}")

    def add_conversation(self, avatar_name: str, user_message: str, bot_reply: str, user_id: str, is_system_message: bool = False):
        conversation_key = f"{avatar_name}_{user_id}"
        if conversation_key not in self.conversation_count:
            self.conversation_count[conversation_key] = 0

        if is_system_message or (isinstance(bot_reply, str) and bot_reply.startswith("Error:")):
            logger.debug(f"跳过记录系统或错误消息: User: {user_message[:30]}...")
            return

        try:
            # ... (写入 short_memory.json 的逻辑保持不变) ...
            short_memory_path = self._get_short_memory_path(avatar_name, user_id)
            if not os.path.exists(short_memory_path) :
                 self.initialize_memory_files(avatar_name,user_id)
            short_memory = []
            if os.path.exists(short_memory_path):
                try:
                    with open(short_memory_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if content.strip(): short_memory = json.loads(content)
                except json.JSONDecodeError: short_memory = []
            
            new_conversation = {"timestamp": self._get_timestamp(), "user": user_message, "bot": bot_reply}
            short_memory.append(new_conversation)
            
            if len(short_memory) > 50: short_memory = short_memory[-50:]
            
            with open(short_memory_path, "w", encoding="utf-8") as f:
                json.dump(short_memory, f, ensure_ascii=False, indent=2)
            
            # --- 计数器更新逻辑 ---
            self.conversation_count[conversation_key] += 1
            #【关键改动】更新后，立即把计数写回文件
            self._save_conversation_count()
            
            current_count = self.conversation_count[conversation_key]
            
            summary_trigger_threshold = 30
            context_size_for_summary = 30
            
            logger.debug(f"当前对话累计计数(跨启动): {current_count}/{summary_trigger_threshold} ({avatar_name}/{user_id})")
            
            if current_count >= summary_trigger_threshold:
                logger.info(f"角色 {avatar_name} 达到 {summary_trigger_threshold} 轮对话阈值，开始智能总结...")
                context_for_summary = self.get_recent_context(avatar_name, user_id, context_size=context_size_for_summary)
                
                #【关键改动】总结成功后，重置计数器并再次保存
                self.update_core_memory(avatar_name, user_id, context_for_summary)
                self.conversation_count[conversation_key] = 0
                self._save_conversation_count()
                
        except Exception as e:
            logger.error(f"添加对话到短期记忆失败 ({avatar_name}/{user_id}): {str(e)}", exc_info=True)

    def _build_memory_prompt(self, filepath: str, relative_to_root: bool = True) -> str:
        # ... (此方法无变化) ...
        resolved_filepath = os.path.join(self.root_dir, filepath) if relative_to_root else filepath
        try:
            with open(resolved_filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"提示词文件未找到: {resolved_filepath} (源路径: {filepath})")
            return ""
        except Exception as e:
            logger.error(f"读取提示词模板 {resolved_filepath} 时出错: {e}")
            return ""

    # 在 MemoryService 类中 (memory_service.py)
    def update_core_memory(self, avatar_name: str, user_id: str, context_to_summarize: List[Dict]):
        """
        【最终路径修正版】执行短期对话总结，追加到长期记忆。
        已修正总结指令 (memory.md) 的文件路径为 src/base/memory.md。
        """
        logger.info(f"开始为角色 {avatar_name} 执行智能总结...")
        
        if not context_to_summarize:
            logger.warning(f"用于总结的短期对话为空，跳过总结: {avatar_name}/{user_id}")
            return
        dialog_to_summarize_str = "\n".join([f"用户: {entry['content']}" if entry['role'] == 'user' else f"bot: {entry['content']}" for entry in context_to_summarize])
        if not dialog_to_summarize_str.strip():
            logger.warning(f"转换后的待总结对话内容为空，跳过: {avatar_name}/{user_id}")
            return
        logger.debug(f"待总结的对话内容长度: {len(dialog_to_summarize_str)} 字节")

        # --- 【最终路径修正】 ---
        # 更新 memory.md 的路径，移除 prompts 子文件夹
        summarization_instruction = self._build_memory_prompt('src/base/memory.md')
        # --- 【修正完成】 ---

        if not summarization_instruction:
            logger.error(f"【总结失败】无法加载总结指令(src/base/memory.md)，取消本次总结。")
            return
        logger.debug(f"总结指令长度: {len(summarization_instruction)} 字节")

        avatar_prompt_path = os.path.join("data", "avatars", avatar_name, "avatar.md")
        avatar_personality = self._build_memory_prompt(avatar_prompt_path)
        if not avatar_personality:
            logger.warning(f"无法加载角色人设({avatar_prompt_path})，将不带人设进行总结。")
        logger.debug(f"角色人设长度: {len(avatar_personality)} 字节")

        existing_long_term_memory = self.get_core_memory(avatar_name, user_id)
        logger.debug(f"已有长期记忆长度: {len(existing_long_term_memory)} 字节")

        system_prompt_payload = json.dumps({
            "instruction": summarization_instruction,
            "personality": avatar_personality,
            "existing_memories": existing_long_term_memory
        }, ensure_ascii=False)
        logger.debug(f"发送给LLM的System Prompt (JSON负载) 总长度: {len(system_prompt_payload)} 字节")
        
        max_retries = 3
        summary_text_from_llm = None
        for attempt in range(max_retries):
            try:
                llm = self._get_llm_client()
                logger.info(f"正在进行第 {attempt + 1}/{max_retries} 次总结API调用...")
                summary_text_from_llm = llm.get_response(
                    message=dialog_to_summarize_str,
                    user_id=f"summarize_{avatar_name}_{user_id}",
                    system_prompt=system_prompt_payload
                )
                
                logger.debug(f"LLM为总结任务返回的原始结果 (尝试 {attempt + 1}): '{summary_text_from_llm}'")

                if summary_text_from_llm and summary_text_from_llm.strip() and not summary_text_from_llm.strip().lower().startswith("error"):
                    logger.info("成功从LLM获取到有效的总结内容。")
                    break
                else:
                    logger.warning(f"LLM返回空、无效或错误内容。准备重试...")
                    summary_text_from_llm = None
                    time.sleep(2)
            except Exception as e:
                logger.error(f"记忆总结LLM调用时发生异常 (尝试 {attempt + 1}/{max_retries}): {e}", exc_info=True)
        
        if summary_text_from_llm and summary_text_from_llm.strip():
            # --- 【关键修正点】 ---
            # 1. 清理LLM返回的文本，移除可能存在的列表标记 (如 "- " 或 "1. ")
            cleaned_lines = [re.sub(r'^\s*-\s*|\d+\.\s*', '', line).strip() for line in summary_text_from_llm.strip().splitlines() if line.strip()]
            
            # 2. 用分号和空格连接所有要点，形成单行文本
            final_summary_to_write = "; ".join(cleaned_lines)

            try:
                long_term_memory_path = self._get_core_memory_path(avatar_name, user_id)
                with open(long_term_memory_path, "a", encoding="utf-8") as f:
                    # 只在开头写入一次“总结时间”
                    f.write(f"总结时间: {self._get_timestamp()}\n")
                    # 直接写入LLM生成的、干净的要点列表
                    f.write(final_summary_to_write + "\n\n")
                logger.info(f"【总结成功】已将新总结({len(final_summary_to_write)}字节)以简洁格式追加到长期记忆。")
            except Exception as e_write:
                logger.error(f"【总结失败】写入长期记忆缓冲区时失败: {str(e_write)}")
        else:
            logger.error(f"【总结失败】经过 {max_retries} 次尝试后，仍无法获取有效的记忆总结。")

    def get_core_memory(self, avatar_name: str, user_id: str) -> str:
        # ... (此方法无变化) ...
        long_term_memory_path = self._get_core_memory_path(avatar_name, user_id)
        if not os.path.exists(long_term_memory_path):
            return ""
        try:
            with open(long_term_memory_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"获取全部长期记忆内容失败 for {avatar_name}/{user_id}: {str(e)}")
            return ""

    def get_recent_context(self, avatar_name: str, user_id: str, context_size: Optional[int] = None) -> List[Dict]:
        """
        获取最近的对话上下文 (从 short_memory.json)。
        已修正 AttributeError: 'MemoryService' object has no attribute 'config' 错误。
        """
        try:
            # ---【修正点】---
            # 如果 context_size 未提供，直接使用 self.max_groups 属性
            num_dialogues_to_fetch = context_size if context_size is not None else self.max_groups
            # ---【修正完成】---

            logger.debug(f"为 {avatar_name}/{user_id} 获取最近上下文，目标轮数: {num_dialogues_to_fetch}")
            
            short_memory_path = self._get_short_memory_path(avatar_name, user_id)
            
            if not os.path.exists(short_memory_path):
                return []
            
            short_memory_entries = []
            with open(short_memory_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip(): return []
                try:
                    short_memory_entries = json.loads(content)
                except json.JSONDecodeError:
                    logger.warning(f"短期记忆文件损坏 ({short_memory_path})，无法加载上下文。")
                    return []

            context = []
            for conv in short_memory_entries[-num_dialogues_to_fetch:]:
                context.append({"role": "user", "content": conv["user"]})
                context.append({"role": "assistant", "content": conv["bot"]})
            
            logger.debug(f"已加载 {len(context)//2} 轮对话作为上下文 for {avatar_name}/{user_id}")
            return context
        
        except Exception as e:
            logger.error(f"获取最近上下文时发生错误 ({avatar_name}/{user_id}): {str(e)}", exc_info=True)
            return []

