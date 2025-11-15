#!/usr/bin/env python3
"""
表情包自动批量重命名工具
使用GPT-4V视觉模型自动识别并重命名表情包文件

使用方法：
    python tools/auto_rename_emoji.py

配置：
    在运行前设置以下环境变量或修改代码中的配置：
    - OPENAI_API_KEY: OpenAI API密钥
    - OPENAI_BASE_URL: API基础URL（可选，默认使用官方地址）
    - EMOJI_DIR: 表情包目录路径
"""

import os
import base64
import time
from pathlib import Path
from typing import List, Tuple, Optional
import json

try:
    from openai import OpenAI
except ImportError:
    print("❌ 请先安装openai库: pip install openai")
    exit(1)


# ==================== 配置区域 ====================

# API配置（从环境变量读取，或直接修改这里）
API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")  # 可以改成其他兼容接口
MODEL = os.getenv("OPENAI_MODEL", "gpt-4-vision-preview")  # 支持自定义模型

# 常见模型配置示例：
# OpenAI: gpt-4-vision-preview, gpt-4o, gpt-4-turbo
# Gemini (通过OpenAI兼容接口): gemini-pro-vision, gemini-1.5-flash
# Claude: claude-3-opus-20240229, claude-3-sonnet-20240229

# 表情包目录（从环境变量读取，或直接修改这里）
EMOJI_DIR = os.getenv("EMOJI_DIR", "data/avatars/ATRI/emoji")

# 支持的图片格式
SUPPORTED_FORMATS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']

# 命名提示词
NAMING_PROMPT = """请帮我分析这个表情包图片，并生成一个简洁的中文文件名。

要求：
1. 识别图片中的主要内容、情绪、动作
2. 如果有文字（日文、英文等），请翻译成中文
3. 文件名格式：[主要情绪或动作][关键词]
4. 文件名要简短（2-6个汉字）
5. 使用最常见的中文表达
6. 如果是系列表情，可以加编号

示例：
- 表情：开心地笑 → "开心大笑"
- 表情：生气跺脚 → "生气跺脚"
- 表情：委屈哭泣 → "委屈哭"
- 表情：吃东西 → "吃饭"
- 表情：下雨打伞 → "下雨打伞"

请直接给出建议的文件名（不含扩展名），不需要额外解释。只输出文件名本身。"""

# 批处理配置
BATCH_SIZE = 5  # 每批处理的图片数量
DELAY_BETWEEN_BATCHES = 2  # 批次间延迟（秒）
DELAY_BETWEEN_REQUESTS = 0.5  # 请求间延迟（秒）

# 日志文件
LOG_FILE = "tools/rename_log.json"

# ==================== 核心功能 ====================

class EmojiRenamer:
    def __init__(self, api_key: str, base_url: str, model: str):
        """初始化重命名器"""
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.rename_log = []
        
    def get_image_base64(self, image_path: str) -> str:
        """读取图片并转换为base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    
    def analyze_emoji(self, image_path: str) -> Optional[str]:
        """使用GPT-4V分析表情包并获取建议文件名"""
        try:
            # 读取图片
            image_base64 = self.get_image_base64(image_path)
            file_ext = Path(image_path).suffix.lower()
            
            # 确定MIME类型
            mime_types = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.bmp': 'image/bmp'
            }
            mime_type = mime_types.get(file_ext, 'image/jpeg')
            
            # 调用API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": NAMING_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }],
                max_tokens=100,
                temperature=0.3
            )
            
            # 提取文件名
            suggested_name = response.choices[0].message.content.strip()
            
            # 清理文件名（移除可能的引号、特殊字符等）
            suggested_name = suggested_name.replace('"', '').replace("'", '')
            suggested_name = suggested_name.replace('\n', '').replace('\r', '')
            suggested_name = ''.join(c for c in suggested_name if c not in r'\/:*?"<>|')
            
            return suggested_name
            
        except Exception as e:
            print(f"      ❌ API调用失败: {e}")
            return None
    
    def rename_file(self, old_path: Path, new_name: str, dry_run: bool = False) -> bool:
        """重命名文件"""
        try:
            # 保留原扩展名
            new_path = old_path.parent / f"{new_name}{old_path.suffix}"
            
            # 处理文件名冲突
            counter = 1
            while new_path.exists() and new_path != old_path:
                new_path = old_path.parent / f"{new_name}{counter}{old_path.suffix}"
                counter += 1
            
            if dry_run:
                print(f"      [预览] {old_path.name} → {new_path.name}")
                return True
            
            # 实际重命名
            old_path.rename(new_path)
            
            # 记录日志
            self.rename_log.append({
                "old_name": old_path.name,
                "new_name": new_path.name,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            
            return True
            
        except Exception as e:
            print(f"      ❌ 重命名失败: {e}")
            return False
    
    def save_log(self):
        """保存重命名日志"""
        try:
            log_path = Path(LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有日志
            existing_log = []
            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8') as f:
                    existing_log = json.load(f)
            
            # 合并并保存
            existing_log.extend(self.rename_log)
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(existing_log, f, ensure_ascii=False, indent=2)
            
            print(f"\n📝 重命名日志已保存到: {LOG_FILE}")
            
        except Exception as e:
            print(f"\n⚠️  保存日志失败: {e}")


def scan_emoji_files(directory: str) -> List[Path]:
    """扫描目录中的所有表情包文件"""
    emoji_dir = Path(directory)
    if not emoji_dir.exists():
        print(f"❌ 目录不存在: {directory}")
        return []
    
    files = []
    for ext in SUPPORTED_FORMATS:
        files.extend(emoji_dir.rglob(f"*{ext}"))
    
    # 过滤掉已经是中文命名的文件
    files = [f for f in files if not is_chinese_named(f.name)]
    
    return sorted(files)


def is_chinese_named(filename: str) -> bool:
    """判断文件名是否已经是中文命名"""
    name_without_ext = Path(filename).stem
    # 简单判断：如果文件名包含中文字符，认为已经命名
    return any('\u4e00' <= char <= '\u9fff' for char in name_without_ext)


def print_banner():
    """打印横幅"""
    print("=" * 60)
    print("🎨 表情包自动批量重命名工具")
    print("=" * 60)
    print(f"📁 目标目录: {EMOJI_DIR}")
    print(f"🤖 使用模型: {MODEL}")
    print(f"📦 批处理大小: {BATCH_SIZE}")
    print("=" * 60)
    print()


def main():
    """主函数"""
    print_banner()
    
    # 检查配置
    if API_KEY == "your-api-key-here":
        print("❌ 请先设置 OPENAI_API_KEY 环境变量或修改脚本中的 API_KEY")
        print("   设置方法:")
        print("   Windows: set OPENAI_API_KEY=sk-...")
        print("   Linux/Mac: export OPENAI_API_KEY=sk-...")
        return
    
    # 扫描文件
    print("🔍 正在扫描表情包文件...")
    emoji_files = scan_emoji_files(EMOJI_DIR)
    
    if not emoji_files:
        print("✅ 没有找到需要重命名的文件（或所有文件已经是中文命名）")
        return
    
    print(f"📊 找到 {len(emoji_files)} 个需要重命名的文件\n")
    
    # 确认是否继续
    print("⚠️  即将开始自动重命名，这将调用AI API并产生费用。")
    confirm = input("是否继续？(y/n): ").lower()
    if confirm != 'y':
        print("❌ 已取消操作")
        return
    
    # 是否预览模式
    dry_run_confirm = input("是否仅预览（不实际重命名）？(y/n): ").lower()
    dry_run = (dry_run_confirm == 'y')
    
    if dry_run:
        print("\n🔍 预览模式 - 不会实际重命名文件\n")
    else:
        print("\n🚀 开始批量重命名...\n")
    
    # 初始化重命名器
    renamer = EmojiRenamer(API_KEY, BASE_URL, MODEL)
    
    # 统计信息
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    # 批量处理
    total_files = len(emoji_files)
    for i, file_path in enumerate(emoji_files, 1):
        print(f"[{i}/{total_files}] 处理: {file_path.name}")
        
        try:
            # 调用API分析
            print(f"      🤖 正在分析...")
            suggested_name = renamer.analyze_emoji(str(file_path))
            
            if not suggested_name:
                print(f"      ⏭️  跳过（分析失败）")
                skip_count += 1
                continue
            
            print(f"      💡 建议: {suggested_name}")
            
            # 重命名
            if renamer.rename_file(file_path, suggested_name, dry_run):
                if not dry_run:
                    print(f"      ✅ 已重命名")
                success_count += 1
            else:
                fail_count += 1
            
            # 延迟
            if i % BATCH_SIZE == 0 and i < total_files:
                print(f"\n⏸️  批次完成，等待 {DELAY_BETWEEN_BATCHES} 秒...\n")
                time.sleep(DELAY_BETWEEN_BATCHES)
            else:
                time.sleep(DELAY_BETWEEN_REQUESTS)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断，正在保存日志...")
            break
        except Exception as e:
            print(f"      ❌ 处理失败: {e}")
            fail_count += 1
            continue
    
    # 保存日志
    if not dry_run and renamer.rename_log:
        renamer.save_log()
    
    # 打印统计
    print("\n" + "=" * 60)
    print("📊 处理完成！")
    print("=" * 60)
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")
    print(f"⏭️  跳过: {skip_count}")
    print(f"📁 总计: {total_files}")
    print("=" * 60)
    
    if not dry_run and success_count > 0:
        print(f"\n💡 提示: 重命名日志已保存到 {LOG_FILE}")
        print("   如需撤销，可以参考日志文件手动恢复")


if __name__ == "__main__":
    main()