# 表情包AI命名工具 - 视觉识别提示词

## 🎯 用途

使用视觉AI模型（如GPT-4V、Claude、Gemini等）自动识别表情包内容并生成中文文件名，特别适合处理日文表情包。

## 📋 提示词模板

### 标准版提示词

```
请帮我分析这个表情包图片，并为它生成一个简洁的中文文件名。

要求：
1. 识别图片中的主要内容、情绪、动作
2. 如果有文字（日文、英文等），请翻译成中文
3. 文件名格式：[主要情绪或动作][关键词]
4. 文件名要简短（2-6个汉字）
5. 使用最常见的中文表达
7. 保留原文件扩展名（.png/.jpg/.gif/.webp等）

**支持的格式**：
- `.png` - 静态图片，支持透明背景（推荐）
- `.jpg/.jpeg` - 静态图片
- `.gif` - 动态图片
- `.webp` - 现代格式（静态/动态都支持）
- 其他：`.bmp`、`.svg` 等

6. 如果是系列表情，可以加编号

示例：
- 表情：开心地笑 → "开心大笑"
- 表情：生气跺脚 → "生气跺脚"
- 表情：委屈哭泣 → "委屈哭"
- 表情：吃东西 → "吃饭"
- 表情：下雨打伞 → "下雨打伞"

请直接给出建议的文件名，不需要额外解释。
```

### 批量处理版提示词

```
我有多张表情包需要命名，请帮我为每张图片生成中文文件名。

命名规则：
1. 识别主要情绪/动作/场景
2. 翻译所有文字内容（日文→中文）
3. 格式：[核心关键词][辅助描述]
4. 2-6个汉字，简洁易懂
5. 便于搜索和分类

分类参考：
- 情感类：开心、生气、难过、委屈、害羞、惊讶
- 动作类：吃饭、喝水、睡觉、看书、工作、玩游戏
- 天气类：下雨、晴天、阴天、下雪
- 日常类：早安、晚安、加油、谢谢、对不起

请为每张图片输出：
图片1: [文件名]
图片2: [文件名]
...
```

### 分类命名版提示词

```
请分析这个表情包并提供分类命名建议。

分析维度：
1. 主要情绪（happy/sad/angry/surprised等）
2. 具体场景或动作
3. 图片中的文字内容（翻译成中文）
4. 适合的使用场景

输出格式：
```json
{
  "category": "情感类/动作类/场景类",
  "emotion": "具体情绪",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "text_content": "图片中的文字（中文翻译）",
  "suggested_names": [
    "推荐名称1",
    "推荐名称2",
    "推荐名称3"
  ],
  "best_name": "最佳文件名"
}
```

请提供详细分析。
```

## 🔧 使用方法

### 方法1：手动使用（推荐）

1. 打开支持视觉识别的AI服务（GPT-4V、Claude等）
2. 上传表情包图片
3. 复制上述提示词
4. 获取AI建议的文件名
5. 批量重命名文件

### 方法2：API调用（自动化）

```python
# 示例代码（使用OpenAI GPT-4V）
import openai
import base64

def analyze_emoji(image_path):
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    
    response = openai.ChatCompletion.create(
        model="gpt-4-vision-preview",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请帮我分析这个表情包，并生成一个简洁的中文文件名。要求：2-6个汉字，格式为[情绪或动作][关键词]"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                }
            ]
        }],
        max_tokens=100
    )
    
    return response.choices[0].message.content

# 使用
suggested_name = analyze_emoji("path/to/emoji")
print(f"建议文件名: {suggested_name}")
```

### 方法3：使用项目内置的图片识别服务

```python
# 使用项目的 image_recognition_service
from src.services.ai.image_recognition_service import ImageRecognitionService

# 初始化服务
service = ImageRecognitionService(api_key, base_url, model)

# 分析表情包
prompt = """
请帮我分析这个表情包，并生成一个简洁的中文文件名。
要求：识别主要情绪和动作，2-6个汉字，格式：[关键词]
"""

result = await service.analyze_image(image_path, prompt)
print(f"建议文件名: {result}")
```

## 📝 命名规范建议

### 好的命名示例

✅ **简洁明确**：
- `开心`
- `生气`
- `下雨`
- `吃饭`

✅ **双关键词**：
- `开心大笑`
- `生气跺脚`
- `委屈哭泣`
- `下雨打伞`

✅ **系列编号**：
- `开心1`、`开心2`
- `吃饭1`、`吃饭2`

### 不好的命名示例

❌ **过于复杂**：
- `非常开心地大笑并且跳起来`（太长）
- `IMG_001`（无意义）
- `emoji_happy_laugh_jump`（英文不便检索）

❌ **关键词不准确**：
- `高兴` → 应该用`开心`（更常用）
- `进食` → 应该用`吃饭`（更口语化）
- `降水` → 应该用`下雨`（更自然）

## 🎨 分类体系参考

### 1. 情感类 (emotion/)
- 正面：开心、兴奋、满意、自豪、感动
- 负面：生气、难过、委屈、失望、沮丧
- 中性：害羞、惊讶、疑惑、思考、无语

### 2. 动作类 (action/)
- 日常：吃饭、喝水、睡觉、起床、洗澡
- 活动：看书、工作、学习、运动、玩游戏
- 社交：打招呼、鞠躬、挥手、拥抱、亲亲

### 3. 天气类 (weather/)
- 雨：下雨、打伞、雨天、暴雨
- 晴：晴天、太阳、阳光
- 其他：阴天、下雪、打雷、起风

### 4. 时间类 (time/)
- 早安、中午好、晚安、午夜
- 周末、假期、生日

### 5. 节日类 (festival/)
- 春节、情人节、圣诞节
- 生日、纪念日

### 6. 食物类 (food/)
- 主食：米饭、面条、面包
- 饮品：水、茶、咖啡、奶茶
- 零食：糖果、蛋糕、水果

## 🚀 快速批量重命名脚本

```python
#!/usr/bin/env python3
"""
表情包批量命名工具
使用视觉AI自动识别并重命名表情包文件
"""

import os
import base64
from pathlib import Path
from openai import OpenAI

# 配置
client = OpenAI(api_key="your-api-key")
EMOJI_DIR = "data/avatars/your_avatar/emoji"

def get_suggested_name(image_path):
    """使用GPT-4V分析图片并获取建议文件名"""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请分析这个表情包并生成简洁的中文文件名。格式：[关键词]，2-6个汉字。只输出文件名，不要其他内容。"
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/gif;base64,{image_data}"}
                }
            ]
        }],
        max_tokens=50
    )
    
    return response.choices[0].message.content.strip()

def batch_rename():
    """批量重命名表情包"""
    emoji_files = list(Path(EMOJI_DIR).rglob("*"))
    
    print(f"找到 {len(emoji_files)} 个表情包文件")
    
    for i, file_path in enumerate(emoji_files, 1):
        print(f"\n[{i}/{len(emoji_files)}] 处理: {file_path.name}")
        
        try:
            # 获取AI建议
            suggested_name = get_suggested_name(str(file_path))
            print(f"  建议名称: {suggested_name}")
            
            # 确认重命名
            confirm = input("  是否重命名？(y/n/s=跳过): ").lower()
            
            if confirm == 'y':
                new_path = file_path.parent / suggested_name
                file_path.rename(new_path)
                print(f"  ✅ 已重命名为: {suggested_name}")
            elif confirm == 's':
                print("  ⏭️  跳过")
            else:
                custom_name = input("  输入自定义名称（或回车跳过）: ").strip()
                if custom_name:
                    new_path = file_path.parent / custom_name
                    file_path.rename(new_path)
                    print(f"  ✅ 已重命名为: {custom_name}")
                    
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            continue

if __name__ == "__main__":
    batch_rename()
```

## 💡 使用技巧

1. **优先处理日文表情包**：先用AI识别翻译，避免手动翻译错误
2. **建立分类文件夹**：按情感、动作、场景分类存放
3. **保持命名一致性**：同类表情使用相似的命名模式
4. **添加编号区分**：相似表情用数字编号（开心1、开心2）
5. **定期整理**：重复或相似的表情合并删除

## 📚 相关资源

- GPT-4 Vision API: https://platform.openai.com/docs/guides/vision
- Claude Vision: https://www.anthropic.com/claude
- Gemini Vision: https://ai.google.dev/

---

**提示**：使用视觉AI命名表情包可以大大提高效率，特别是处理大量日文或其他语言的表情包时。建议先小批量测试，确认命名风格符合需求后再批量处理。