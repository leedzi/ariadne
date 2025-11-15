"""
智能表情系统
支持全局检索、语义匹配和自动索引构建
"""

import os
import json
import re
import random
from typing import List, Dict, Optional, Tuple
from nonebot.log import logger


class EmojiIndexBuilder:
    """表情索引构建器 - 自动扫描并生成索引"""
    
    def __init__(self):
        # 同义词映射（可扩展）
        self.synonyms = {
            "下雨": ["雨天", "rain", "打伞", "雨伞"],
            "晴天": ["太阳", "阳光", "sunny", "天晴"],
            "看书": ["阅读", "读书", "学习", "看小说"],
            "吃饭": ["用餐", "干饭", "美食", "吃东西"],
            "睡觉": ["休息", "困了", "sleep", "睡了"],
            "开心": ["高兴", "快乐", "happy", "开心"],
            "难过": ["伤心", "sad", "哭"],
            "生气": ["愤怒", "angry", "气"],
        }
    
    def build_index(self, emoji_root: str) -> Dict:
        """
        扫描emojis目录，自动生成索引
        
        Args:
            emoji_root: 表情包根目录路径
        
        Returns:
            索引字典
        """
        from datetime import datetime
        
        index = {
            "version": "1.0",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "emojis": []
        }
        
        if not os.path.exists(emoji_root):
            logger.warning(f"[EmojiIndexBuilder] 表情包目录不存在: {emoji_root}")
            return index
        
        # 递归扫描所有文件
        for root, dirs, files in os.walk(emoji_root):
            for file in files:
                if file.lower().endswith(('.gif', '.jpg', '.png', '.jpeg', '.webp')):
                    try:
                        # 构造相对路径
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, emoji_root)
                        category = os.path.dirname(rel_path) or "未分类"
                        
                        # 提取关键词
                        keywords = self.extract_keywords_from_filename(file)
                        
                        # 检查是否是情感表情
                        emotion_tag = self.detect_emotion_tag(file, category)
                        
                        emoji_info = {
                            "filename": file,
                            "path": rel_path.replace('\\', '/'),  # 统一使用/
                            "keywords": keywords,
                            "category": category,
                            "auto_generated": True
                        }
                        
                        if emotion_tag:
                            emoji_info["emotion_tag"] = emotion_tag
                        
                        index["emojis"].append(emoji_info)
                        
                    except Exception as e:
                        logger.error(f"[EmojiIndexBuilder] 处理文件失败 {file}: {e}")
        
        logger.info(f"[EmojiIndexBuilder] 索引构建完成，共 {len(index['emojis'])} 个表情")
        return index
    
    def extract_keywords_from_filename(self, filename: str) -> List[str]:
        """从文件名提取关键词"""
        # 去除扩展名
        name = os.path.splitext(filename)[0]
        
        # 去除数字后缀（如"下雨1" → "下雨"）
        name_clean = re.sub(r'\d+$', '', name).strip()
        
        keywords = [name_clean] if name_clean else [name]
        
        # 添加同义词
        if name_clean in self.synonyms:
            keywords.extend(self.synonyms[name_clean])
        
        # 去重
        keywords = list(set(keywords))
        
        return keywords
    
    def detect_emotion_tag(self, filename: str, category: str) -> Optional[str]:
        """检测是否是情感表情"""
        emotion_keywords = {
            'happy': ['开心', '高兴', '快乐', 'happy', '笑'],
            'sad': ['难过', '伤心', 'sad', '哭'],
            'angry': ['生气', '愤怒', 'angry', '气'],
            'love': ['爱', '喜欢', 'love', '心'],
            'neutral': ['调皮', '中立', 'neutral']
        }
        
        name_lower = filename.lower()
        category_lower = category.lower()
        
        for emotion, keywords in emotion_keywords.items():
            for keyword in keywords:
                if keyword in name_lower or keyword in category_lower:
                    return emotion
        
        return None


class GlobalEmojiSelector:
    """全局表情选择器 - 智能检索和匹配"""
    
    def __init__(self, emoji_root: str):
        self.emoji_root = emoji_root
        self.index_file = os.path.join(emoji_root, "emoji_index.json")
        self.index = self.load_or_build_index()
    
    def load_or_build_index(self) -> Dict:
        """加载或构建索引"""
        # 尝试加载现有索引
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    index = json.load(f)
                logger.info(f"[GlobalEmojiSelector] 加载索引: {len(index.get('emojis', []))} 个表情")
                return index
            except Exception as e:
                logger.warning(f"[GlobalEmojiSelector] 加载索引失败: {e}，重新构建")
        
        # 构建新索引
        builder = EmojiIndexBuilder()
        index = builder.build_index(self.emoji_root)
        
        # 保存索引
        try:
            os.makedirs(os.path.dirname(self.index_file), exist_ok=True)
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            logger.info(f"[GlobalEmojiSelector] 索引已保存到: {self.index_file}")
        except Exception as e:
            logger.error(f"[GlobalEmojiSelector] 保存索引失败: {e}")
        
        return index
    
    def rebuild_index(self):
        """重建索引"""
        builder = EmojiIndexBuilder()
        self.index = builder.build_index(self.emoji_root)
        
        # 保存
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
            logger.info(f"[GlobalEmojiSelector] 索引已重建: {len(self.index['emojis'])} 个表情")
        except Exception as e:
            logger.error(f"[GlobalEmojiSelector] 保存索引失败: {e}")
    
    def search(self, query_keywords: List[str], context_hint: str = None) -> List[Dict]:
        """
        全局检索表情
        
        Args:
            query_keywords: 搜索关键词列表
            context_hint: 情境提示（可选）
        
        Returns:
            匹配结果列表，按相关度排序
        """
        if not query_keywords:
            return []
        
        results = []
        
        for emoji in self.index.get("emojis", []):
            score = self.calculate_relevance(
                emoji.get("keywords", []),
                query_keywords,
                emoji.get("category", ""),
                context_hint
            )
            
            if score > 0:
                results.append({
                    "emoji": emoji,
                    "score": score
                })
        
        # 按得分排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        logger.debug(f"[GlobalEmojiSelector] 检索'{query_keywords}'找到 {len(results)} 个匹配")
        return results
    
    def calculate_relevance(self, emoji_keywords: List[str], query_keywords: List[str],
                           category: str, context_hint: str = None) -> float:
        """
        计算相关度得分（增强版 - 支持模糊匹配）
        
        规则：
        - 完全匹配: +10分
        - 包含匹配: +6分 (如 "午睡" 包含 "睡")
        - 被包含匹配: +5分 (如 "睡" 被 "睡觉" 包含)
        - 单字匹配: +3分 (如 "午睡" 拆成 "午"+"睡" 匹配 "睡")
        - 分类匹配: +3分
        """
        score = 0.0
        
        # 1. 完全匹配（最高优先级）
        for qk in query_keywords:
            if qk in emoji_keywords:
                score += 10
        
        # 2. 包含匹配（query包含emoji，如"午睡"包含"睡"）
        for qk in query_keywords:
            for ek in emoji_keywords:
                if qk != ek and ek in qk and len(ek) >= 1:
                    score += 6
                    break
        
        # 3. 被包含匹配（emoji包含query，如"睡觉"包含"睡"）
        for qk in query_keywords:
            for ek in emoji_keywords:
                if qk != ek and qk in ek and len(qk) >= 1:
                    score += 5
                    break
        
        # 4. 单字模糊匹配（关键词拆分，如"午睡"→["午","睡"]）
        for qk in query_keywords:
            if len(qk) > 1:  # 只对多字词进行拆分
                # 拆分成单字
                chars = list(qk)
                for char in chars:
                    for ek in emoji_keywords:
                        if char in ek:
                            score += 3
                            break  # 每个字只加一次分
        
        # 5. 分类匹配
        if context_hint and context_hint in category:
            score += 3
        
        return score
    
    def select_best_emoji(self, query_keywords: List[str], context_hint: str = None) -> Optional[str]:
        """
        选择最佳匹配的表情
        
        Returns:
            表情文件的完整路径，如果没有匹配则返回None
        """
        results = self.search(query_keywords, context_hint)
        
        if not results:
            logger.debug(f"[GlobalEmojiSelector] 未找到匹配: {query_keywords}")
            return None
        
        # 获取最高分
        best_score = results[0]["score"]
        
        # 所有最高分的表情
        best_emojis = [r for r in results if r["score"] == best_score]
        
        # 随机选择一个
        selected = random.choice(best_emojis)
        emoji_path = os.path.join(self.emoji_root, selected["emoji"]["path"])
        
        logger.info(f"[GlobalEmojiSelector] 选择表情: {selected['emoji']['filename']} (得分: {best_score})")
        return emoji_path
    
    def get_emotion_emoji(self, emotion_tag: str) -> Optional[str]:
        """根据情感标签获取表情"""
        # 查找带有该emotion_tag的所有表情
        emotion_emojis = [
            e for e in self.index.get("emojis", [])
            if e.get("emotion_tag") == emotion_tag
        ]
        
        if not emotion_emojis:
            logger.debug(f"[GlobalEmojiSelector] 未找到情感表情: {emotion_tag}")
            return None
        
        # 随机选择
        selected = random.choice(emotion_emojis)
        emoji_path = os.path.join(self.emoji_root, selected["path"])
        
        logger.info(f"[GlobalEmojiSelector] 选择情感表情: {selected['filename']} [{emotion_tag}]")
        return emoji_path


# 导出
__all__ = ['EmojiIndexBuilder', 'GlobalEmojiSelector']