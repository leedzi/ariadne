"""
网络搜索服务模块
提供网络搜索和网页内容提取功能，包含以下核心功能：
- URL 检测
- 网页内容提取
- 网络搜索
- API 请求管理
"""

import logging
import re
import requests
import json
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
from readability import Document
from src.services.ai.llm_service import LLMService
from data.config import NETWORK_SEARCH_ENABLED, WEBLENS_ENABLED
from src.autoupdate.updater import Updater

# 获取 logger
logger = logging.getLogger('main')

class NetworkSearchService:
    def __init__(self, llm_service: LLMService):
        """
        初始化网络搜索服务

        :param llm_service: LLM服务实例，用于调用API
        """
        self.llm_service = llm_service

        # 使用全局配置变量获取API密钥和基础URL
        from data.config import NETWORK_SEARCH_API_KEY, DEEPSEEK_API_KEY
        
        # 如果网络搜索API密钥为空，则使用LLM的API密钥
        self.api_key = NETWORK_SEARCH_API_KEY if NETWORK_SEARCH_API_KEY else DEEPSEEK_API_KEY
        # 固定使用KouriChat API地址
        self.base_url = "https://api.kourichat.com/v1"

        # 创建 Updater 实例获取版本信息
        updater = Updater()
        version = updater.get_current_version()
        version_identifier = updater.get_version_identifier()

        # 设置请求头
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': version_identifier,
            'X-KouriChat-Version': version
        }

        # URL 检测正则表达式
        self.url_pattern = re.compile(r'(https?://)?((?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})(:\d{2,5})?(/[^\s]*)?')

    def detect_urls(self, text: str) -> List[str]:
        """
        从文本中检测 URL

        :param text: 要检测的文本
        :return: 检测到的 URL 列表
        """
        if not text:
            return []

        urls = []
        matches = self.url_pattern.finditer(text)
        for match in matches:
            urls.append(match.group(0))
        return urls

    def get_weblens_model(self) -> str:
        """
        获取网页内容提取模型

        :return: 模型名称
        """
        return "kourichat-weblens"  # 始终返回KouriChat模型

    def get_search_model(self) -> str:
        """
        获取网络搜索模型

        :return: 模型名称
        """
        return "kourichat-search"  # 始终返回KouriChat模型

    def extract_web_content_direct(self, url: str) -> Optional[str]:
        """
        直接使用 requests 调用 API 提取网页内容

        :param url: 要提取内容的 URL
        :return: 提取的内容，如果失败则返回 None
        """
        try:
            # 始终使用KouriChat模型
            model = "kourichat-weblens"
            logger.info(f"使用模型 {model} 提取网页内容 (直接调用)")

            # 构建请求数据
            # 直接传递URL，不包含提示词
            user_content = url

            data = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": user_content
                    }
                ]
            }

            # 发送请求
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=120
            )

            # 检查响应状态
            if response.status_code != 200:
                logger.error(f"API 请求失败 - 状态码: {response.status_code}, 响应: {response.text}")
                return None

            # 处理响应
            result = response.json()
            if 'choices' not in result or not result['choices']:
                logger.error(f"API 响应格式异常: {result}")
                return None

            # 提取内容
            content = result['choices'][0]['message']['content']

            # 处理响应内容
            if content:
                # 确保换行符被正确处理
                content = content.replace('\r\n', '\n').replace('\r', '\n')

                # 添加摘要标记
                if not content.startswith('#'):
                    content = f"# 网页内容摘要\n\n{content}"

                # 确保最后有链接
                if url not in content:
                    content = f"{content}\n\n原始链接: {url}"

            print(content)

            return content

        except Exception as e:
            logger.error(f"直接提取网页内容失败: {str(e)}")
            return None

    def extract_web_content(self, url: str) -> Dict[str, str]:
        """
        提取网页内容，返回原始内容和总结版本
        优先尝试本地提取，失败则回退到API

        :param url: 要提取内容的 URL
        :return: 包含原始内容和总结的字典，如果失败则返回空字典
        """
        result = {
            'original': None,  # 原始网页内容
            'summary': None    # 总结版本，用于系统提示词
        }

        # 尝试本地提取
        try:
            logger.info(f"尝试本地提取网页内容: {url}")
            
            # 检查是否是视频链接（简单判断）
            is_video = any(domain in url for domain in ['bilibili.com', 'youtube.com', 'v.qq.com', 'iqiyi.com', 'youku.com'])
            
            if is_video:
                logger.info("检测到视频链接，尝试提取视频信息")
                local_content = self._extract_video_info(url)
            else:
                local_content = self._extract_content_local(url)
            
            if local_content:
                logger.info("本地提取成功")
                result['original'] = f"以下是链接 {url} 的内容，可作为你的回复参考，但无需直接提及内容来源：\n\n{local_content}"
                return result
            else:
                logger.info("本地提取失败或内容为空，尝试使用API")
        except Exception as e:
            logger.warning(f"本地提取异常: {e}，尝试使用API")

        # API 提取逻辑 (作为回退)
        try:
            # 始终使用KouriChat模型
            model = "kourichat-weblens"
            logger.info(f"使用模型 {model} 提取网页内容")

            # 获取网页内容
            # 直接传递URL，不包含提示词
            user_content = url

            content_messages = [
                {
                    "role": "user",
                    "content": user_content
                }
            ]

            # 重新初始化API请求
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # 直接使用requests调用API而不是使用llm_service
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": content_messages
                },
                timeout=120
            )
            
            # 检查响应
            if response.status_code != 200:
                logger.error(f"提取网页内容API请求失败: {response.status_code}")
                return result
                
            response_data = response.json()
            web_content = response_data['choices'][0]['message']['content']

            if not web_content:
                logger.error("网页内容提取结果为空")
                return result

            # 格式化原始内容
            formatted_content = web_content.replace('\r\n', '\n').replace('\r', '\n')
            if not formatted_content.startswith('#'):
                formatted_content = f"# 网页内容摘要\n\n{formatted_content}"
            if url not in formatted_content:
                formatted_content = f"{formatted_content}\n\n原始链接: {url}"

            # 保存原始网页内容
            result['original'] = f"以下是链接 {url} 的内容，可作为你的回复参考，但无需直接提及内容来源：\n\n{formatted_content}"

            logger.info("获取到网页内容，总结将在异步线程中生成")

            # 总结将在异步线程中生成，不占用当前对话的时间

            return result
        except Exception as e:
            logger.error(f"提取网页内容失败: {str(e)}")
            return result

    def _extract_content_local(self, url: str) -> Optional[str]:
        """
        本地提取网页内容
        
        :param url: 网页URL
        :return: 提取的文本内容
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 获取网页内容
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # 自动检测编码
            response.encoding = response.apparent_encoding
            
            # 使用readability提取主要内容
            doc = Document(response.text)
            title = doc.title()
            summary_html = doc.summary()
            
            # 使用BeautifulSoup清理HTML
            soup = BeautifulSoup(summary_html, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style", "iframe", "noscript"]):
                script.decompose()
                
            # 获取文本
            text = soup.get_text(separator='\n')
            
            # 清理空白字符
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # 限制长度
            if len(text) > 5000:
                text = text[:5000] + "..."
                
            return f"# {title}\n\n{text}"
            
        except Exception as e:
            logger.warning(f"本地提取失败: {e}")
            return None

    def _extract_video_info(self, url: str) -> Optional[str]:
        """
        尝试提取视频页面信息（标题、简介等）
        针对B站等视频网站的优化
        
        :param url: 视频URL
        :return: 提取的视频信息
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取标题
            title = soup.title.string if soup.title else "未知标题"
            
            # 提取描述 (meta description)
            description = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc:
                description = meta_desc.get('content', '')
                
            # 提取关键词 (meta keywords)
            keywords = ""
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords:
                keywords = meta_keywords.get('content', '')
                
            # 组合信息
            info = f"# 视频信息\n\n标题: {title}\n"
            if description:
                info += f"\n简介: {description}\n"
            if keywords:
                info += f"\n关键词: {keywords}\n"
                
            return info
            
        except Exception as e:
            logger.warning(f"视频信息提取失败: {e}")
            return None

    def search_internet(self, query: str, conversation_context: str = None) -> Dict[str, str]:
        """
        搜索互联网，返回原始搜索结果和总结版本

        :param query: 搜索查询
        :param conversation_context: 对话上下文，用于提供更多背景信息
        :return: 包含原始结果和总结的字典，如果失败则返回空字典
        """
        result = {
            'original': None,  # 原始搜索结果
            'summary': None    # 总结版本，用于系统提示词
        }

        try:
            # 始终使用KouriChat模型
            model = "kourichat-search"
            logger.info(f"使用模型 {model} 搜索互联网")

            # 获取搜索结果
            # 直接传递查询，不包含提示词
            user_content = query

            # 如果有对话上下文，添加到查询中
            if conversation_context:
                user_content = f"本次对话上下文: {conversation_context}\n\n搜索查询: {query}"

            search_messages = [
                {
                    "role": "user",
                    "content": user_content
                }
            ]

            # 重新初始化API请求
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # 直接使用requests调用API而不是使用llm_service
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": search_messages
                },
                timeout=120
            )
            
            # 检查响应
            if response.status_code != 200:
                logger.error(f"搜索互联网API请求失败: {response.status_code}")
                return result
                
            response_data = response.json()
            search_result = response_data['choices'][0]['message']['content']

            if not search_result:
                logger.error("搜索结果为空")
                return result

            # 保存原始搜索结果
            result['original'] = f"以下是关于\"{query}\"的搜索结果，可作为你的回复参考，但无需直接提及搜索结果来源：\n\n{search_result}"

            logger.info("获取到搜索结果，总结将在异步线程中生成")

            # 总结将在异步线程中生成，不占用当前对话的时间

            return result
        except Exception as e:
            logger.error(f"搜索互联网失败: {str(e)}")
            return result

    def process_message(self, message: str) -> Tuple[bool, Dict[str, str], str]:
        """
        处理消息，只检测URL提取网页内容

        :param message: 用户消息
        :return: (是否处理, 处理结果字典, 处理类型)
        """
        # 只检测 URL，搜索意图由 TimeRecognitionService 处理
        if WEBLENS_ENABLED:
            urls = self.detect_urls(message)
            if urls:
                url = urls[0]  # 只处理第一个 URL
                logger.info(f"检测到 URL: {url}，正在提取内容...")

                # 提取网页内容，获取原始内容和总结
                result = self.extract_web_content(url)

                # 如果提取失败，不添加任何内容，直接返回空结果
                if not result['original']:
                    logger.info(f"提取网页内容失败，不添加任何内容到请求中")

                if result['original']:
                    return True, result, "weblens"

        return False, {'original': None, 'summary': None}, ""
