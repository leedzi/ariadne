# 表情包工具集

本目录包含表情包管理相关的工具。

## 📁 文件说明

### 1. `auto_rename_emoji.py` - 自动批量重命名工具 ⭐

**功能**：使用GPT-4V视觉模型自动识别表情包内容并批量重命名为中文。

**特点**：
- ✅ 完全自动化，无需手动输入
- ✅ 支持所有图片格式（.png/.jpg/.gif/.webp等）
- ✅ 智能翻译日文/英文表情包
- ✅ 自动跳过已经是中文命名的文件
- ✅ 批处理模式，避免API限流
- ✅ 预览模式，可先查看效果
- ✅ 完整日志记录

**使用方法**：

#### 🎯 方法1：一键启动（推荐Windows用户）

**双击运行** `tools/rename_emoji.bat` 即可！

首次运行会自动创建配置文件 `tools/config.bat`，编辑它设置你的API密钥：

```batch
@echo off
REM ========== API配置 ==========
set OPENAI_API_KEY=your-api-key-here
set OPENAI_BASE_URL=https://api.openai.com/v1
set OPENAI_MODEL=gpt-4-vision-preview

REM ========== 表情包目录 ==========
set EMOJI_DIR=data/avatars/ATRI/emoji
```

**使用Gemini的配置示例**：
```batch
set OPENAI_API_KEY=your-gemini-api-key
set OPENAI_BASE_URL=https://your-gemini-proxy.com/v1
set OPENAI_MODEL=gemini-pro-vision
```

然后再次双击 `rename_emoji.bat` 即可自动运行！

#### 🔧 方法2：手动运行（所有系统）

**Windows**:
```bash
set OPENAI_API_KEY=sk-your-api-key-here
set OPENAI_BASE_URL=https://api.openai.com/v1
set OPENAI_MODEL=gpt-4-vision-preview
python tools/auto_rename_emoji.py
```

**Linux/Mac**:
```bash
export OPENAI_API_KEY=sk-your-api-key-here
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_MODEL=gpt-4-vision-preview
python tools/auto_rename_emoji.py
```

#### 步骤：按提示操作

```
是否继续？(y/n): y
是否仅预览（不实际重命名）？(y/n): n  # 第一次建议选y预览
```

**示例输出**：
```
[1/50] 处理: IMG_001.png
      🤖 正在分析...
      💡 建议: 开心大笑
      ✅ 已重命名

[2/50] 处理: emoji_sad.jpg
      🤖 正在分析...
      💡 建议: 委屈哭泣
      ✅ 已重命名
```

**配置说明**：

```python
# 在脚本顶部可以修改这些参数：

BATCH_SIZE = 5               # 每批处理5个文件
DELAY_BETWEEN_BATCHES = 2    # 批次间等待2秒
DELAY_BETWEEN_REQUESTS = 0.5 # 请求间等待0.5秒
```

**日志文件**：
- 位置：`tools/rename_log.json`
- 记录所有重命名操作，方便撤销

### 2. `emoji_naming_prompt.md` - 命名提示词文档

**功能**：提供各种场景下的表情包命名提示词。

**包含内容**：
- 标准版提示词（单张处理）
- 批量版提示词（多张处理）
- 分类版提示词（详细分析）
- 手动使用指南
- API调用示例代码
- 命名规范和最佳实践

**使用场景**：
- 手动使用ChatGPT/Claude等AI命名
- 集成到自己的脚本中
- 学习命名规范

## 🚀 快速开始

### 方案1：一键启动（Windows用户推荐）⭐

```
1. 双击 tools/rename_emoji.bat
2. 首次运行会创建配置文件
3. 编辑 tools/config.bat 设置API密钥
4. 再次双击 tools/rename_emoji.bat
5. 按提示操作即可
```

### 方案2：命令行启动（全平台）

```bash
# 1. 设置API密钥和模型
export OPENAI_API_KEY=sk-xxxxx
export OPENAI_MODEL=gpt-4-vision-preview

# 2. 运行自动化脚本
python tools/auto_rename_emoji.py

# 3. 按提示操作即可
```

### 方案2：手动使用AI

适合少量表情包或想要自己控制的情况。

1. 打开 `emoji_naming_prompt.md`
2. 复制提示词
3. 上传图片到ChatGPT/Claude
4. 获取建议的文件名
5. 手动重命名

## 📊 效果对比

**处理前**：
```
data/avatars/ATRI/emoji/
├── IMG_001.png
├── IMG_002.png
├── emoji_happy.jpg
├── sad_face.gif
└── 雨の日.png (日文)
```

**处理后**：
```
data/avatars/ATRI/emoji/
├── 开心大笑.png
├── 生气跺脚.png
├── 委屈哭泣.jpg
├── 难过.gif
└── 下雨天.png
```

## ⚠️ 注意事项

1. **API费用**：使用GPT-4V会产生API费用，建议先小批量测试
2. **备份**：重命名前建议备份原文件
3. **预览模式**：第一次运行建议使用预览模式
4. **日志文件**：保存了所有操作记录，可用于撤销
5. **中文文件**：脚本会自动跳过已经是中文命名的文件

## 🔧 高级配置

### 使用Gemini（Google）

**配置方法1（BAT文件）**：
编辑 `tools/config.bat`:
```batch
set OPENAI_API_KEY=your-gemini-api-key
set OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
set OPENAI_MODEL=gemini-1.5-flash
```

**配置方法2（环境变量）**：
```bash
# Windows
set OPENAI_API_KEY=your-gemini-api-key
set OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
set OPENAI_MODEL=gemini-1.5-flash

# Linux/Mac
export OPENAI_API_KEY=your-gemini-api-key
export OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
export OPENAI_MODEL=gemini-1.5-flash
```

### 使用Claude（Anthropic）

```batch
set OPENAI_API_KEY=your-claude-api-key
set OPENAI_BASE_URL=https://api.anthropic.com/v1
set OPENAI_MODEL=claude-3-opus-20240229
```

### 使用其他兼容服务

任何支持OpenAI格式的API都可以使用：
```batch
set OPENAI_BASE_URL=https://your-api-endpoint.com/v1
set OPENAI_MODEL=your-model-name
```

### 调整批处理参数

根据API限流情况调整：

```python
BATCH_SIZE = 10              # 增大批处理数量
DELAY_BETWEEN_BATCHES = 5    # 增加延迟
DELAY_BETWEEN_REQUESTS = 1   # 增加请求间隔
```

### 自定义提示词

修改脚本中的 `NAMING_PROMPT` 变量来自定义命名风格。

## 💡 最佳实践

1. **分类存放**：按情感/动作/场景分文件夹存放
2. **系列编号**：相似表情用数字区分（开心1、开心2）
3. **简洁明了**：2-6个汉字最佳
4. **避免特殊字符**：不要使用`/\:*?"<>|`等字符
5. **定期整理**：删除重复或不常用的表情

## 📚 相关文档

- 智能表情系统使用指南：`../SMART_EMOJI_GUIDE.md`
- 技术实现文档：`../SMART_EMOJI_IMPLEMENTATION.md`
- 表情包命名提示词：`emoji_naming_prompt.md`

## 🆘 常见问题

**Q: 如何使用.py文件？**
A: Python脚本需要先安装Python 3.7+，然后用命令行运行。Windows用户推荐直接双击.bat文件。

**Q: BAT文件怎么用？**
A: Windows系统直接双击 `rename_emoji.bat` 文件即可，首次运行会引导你配置。

**Q: 如何使用Gemini？**
A: 编辑 `tools/config.bat`，设置Gemini的API密钥和endpoint，然后双击 `rename_emoji.bat`。

**Q: API调用失败怎么办？**
A: 检查API密钥和BASE_URL是否正确，确认网络连接正常。不同服务商的endpoint格式可能不同。

**Q: 命名结果不满意？**
A: 可以修改 `NAMING_PROMPT` 调整提示词，或手动修改部分文件。

**Q: 如何撤销重命名？**
A: 查看 `tools/rename_log.json` 日志文件，里面记录了所有原文件名。

**Q: 支持哪些图片格式？**
A: 支持 .png, .jpg, .jpeg, .gif, .webp, .bmp 等常见格式。

**Q: 会不会重复命名？**
A: 脚本会自动处理命名冲突，在文件名后加数字（如"开心1"、"开心2"）。

---

如有问题或建议，欢迎提Issue！