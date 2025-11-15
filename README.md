# 🎭 Ariadne - AI对话机器人
Kommt der neue Gott gegangen, hingegeben sind wir stumm！

<div align="center">

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![NoneBot2](https://img.shields.io/badge/NoneBot2-2.x-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

*基于 NoneBot2 框架的智能QQ对话机器人*

[快速开始](#-快速开始) • [功能特性](#-功能特性) • [配置指南](#-配置指南) • [文档](#-文档) • [许可证](#-许可证)

</div>

---

## 📖 简介

Ariadne（阿里阿德涅）是一个功能丰富的QQ对话机器人，基于 **NoneBot2** 框架和 **NapCat** 协议开发。它集成了先进的AI能力，包括自然语言处理、图片识别、智能表情、记忆系统等，能够提供更加自然和个性化的对话体验。

> **本项目基于 [KouriChat](https://github.com/KouriChat/KouriChat) 微信版本改造而来，迁移至QQ平台并进行了大量功能优化。**

### ⚠️ 重要说明

- **🔒 群聊功能已完全禁用** - 本版本仅支持私聊对话，所有群聊消息将被忽略

### ✨ 为什么选择 Ariadne？

- 🧠 **智能对话** - 集成主流LLM API，支持上下文记忆和个性化人设
- 🖼️ **图片识别** - 自动识别并理解图片内容，与文字消息无缝融合
- 😊 **智能表情** - AI驱动的情境表情系统，让对话更生动
- ⏰ **智能提醒** - 自然语言提醒功能，LLM生成人性化通知
- 💾 **记忆系统** - 短期+长期记忆机制，记住重要对话内容
- 🎨 **多人设支持** - 轻松切换不同角色人设，自定义Bot性格
- 🔧 **易于配置** - WebUI配置界面，无需手动编辑配置文件

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.9+
- QQ账号
- LLM API密钥（OpenAI / Claude / Gemini / 其他兼容服务）
- NapCat（QQ协议适配器）

### 2. 安装步骤

#### 克隆项目
```bash
git clone https://github.com/yourusername/ariadne.git
cd ariadne
```

#### 安装依赖
```bash
pip install -r requirements_qq.txt
```

#### 配置Bot
```bash
# 复制配置示例
cp data/config/config.example.json data/config/config.json

# 编辑配置文件，填写必要信息
# - API密钥
# - QQ号（listen_list）
# - 选择人设（avatar_dir）
```

#### 设置环境变量（推荐）
**Windows:**
```cmd
set LLM_API_KEY=your-api-key-here
set LLM_BASE_URL=https://api.openai.com/v1
set VISION_API_KEY=your-vision-api-key
```

**Linux/Mac:**
```bash
export LLM_API_KEY=your-api-key-here
export LLM_BASE_URL=https://api.openai.com/v1
export VISION_API_KEY=your-vision-api-key
```

#### 启动Bot
```bash
python run_qq.py
```

详细的配置步骤请查看 **[快速开始指南](QUICK_START_QQ.md)**。

---

## 🎯 功能特性

### 核心功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 💬 **智能对话** | 基于LLM的自然对话，支持多轮上下文 | ✅ |
| 🖼️ **图片识别** | Vision API识别图片内容并融入对话 | ✅ |
| 📝 **消息队列** | 10秒内多条消息自动合并处理 | ✅ |
| 😊 **智能表情** | AI判断情境自动发送合适表情（30%概率） | ✅ |
| ⏰ **智能提醒** | 自然语言设置提醒，LLM生成通知内容 | ✅ |
| 🧠 **记忆系统** | 短期记忆+长期总结，记住重要信息 | ✅ |
| 📨 **主动消息** | 定时随机发送主动消息（可配置时间间隔） | ✅ |
| 🎭 **多人设** | 内置3个示例人设，支持自定义 | ✅ |
| 🌐 **WebUI配置** | 图形化配置界面，方便管理 | ✅ |
| 🔐 **隐私保护** | 仅响应私聊，群聊功能完全禁用 | ✅ |

### 命令列表

| 命令 | 功能 | 示例 |
|------|------|------|
| `/help` | 显示帮助信息 | `/help` |
| `/status` | 查看Bot状态 | `/status` |
| `/reset` | 重置对话上下文 | `/reset` |
| `/clear` | 清空短期记忆 | `/clear` |
| `/context` | 查看当前上下文 | `/context` |
| `/refresh_memory` | 刷新长期记忆 | `/refresh_memory` |
| `/diary` | 生成日记 | `/diary` |
| `/letter` | 生成信件 | `/letter 主题` |
| `/pyq` | 生成朋友圈文案 | `/pyq` |
| `/reminder` | 设置提醒 | `/reminder 明天9点开会` |

---

## ⚙️ 配置指南

### 配置文件结构

```json
{
  "user_settings": {
    "listen_list": ["1234567890"]  // 监听的QQ号列表
  },
  "llm_settings": {
    "base_url": "${LLM_BASE_URL}",
    "api_key": "${LLM_API_KEY}",
    "model": "gpt-4"
  },
  "behavior_settings": {
    "context": {
      "avatar_dir": "data/avatars/ATRI"  // 人设目录
    },
    "auto_message": {
      "enabled": false,  // 主动消息开关
      "countdown": {
        "min_hours": 0.5,
        "max_hours": 3
      }
    }
  }
}
```

### 自定义人设

1. 在 `data/avatars/` 下创建新目录
2. 添加 `avatar.md` 文件定义人设
3. （可选）添加 `emoji/` 目录存放专属表情
4. 在配置中修改 `avatar_dir` 指向新人设

---

## 📚 文档

- **[快速开始指南](QUICK_START_QQ.md)** - 详细的安装和配置步骤
- **[故障排查](TROUBLESHOOTING.md)** - 常见问题和解决方案
- **[消息队列和主动消息](MESSAGE_QUEUE_AND_AUTOSEND_GUIDE.md)** - 高级功能配置
- **[智能表情系统](SMART_EMOJI_GUIDE.md)** - 表情包功能使用指南
- **[工具文档](tools/README.md)** - 表情包批量命名等工具

---

## 🛠️ 技术栈

- **框架**: NoneBot2 2.x
- **协议**: OneBot V11 (NapCat)
- **语言**: Python 3.9+
- **AI服务**: OpenAI / Claude / Gemini / 兼容API
- **异步**: asyncio + APScheduler
- **Web**: Flask (配置界面)

---

## 🔒 隐私与安全

- ✅ **仅响应私聊消息** - 群聊功能已完全禁用，保护用户隐私
- ✅ **环境变量管理** - API密钥支持环境变量，避免硬编码
- ✅ **本地存储** - 聊天记忆存储在本地，不上传第三方服务
- ✅ **密码保护** - 支持管理员密码保护配置界面

> **注意**: 群聊消息将被完全忽略，包括命令和普通对话。如需启用群聊功能，请修改 `plugins/chat.py` 中的相关代码。

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

### 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 🙏 致谢

本项目基于以下优秀的开源项目：

- **[KouriChat](https://github.com/KouriChat/KouriChat)** - 原始微信版本，本项目的核心基础
- [NoneBot2](https://github.com/nonebot/nonebot2) - 跨平台Python异步聊天机器人框架
- [NapCat](https://github.com/NapNeko/NapCatQQ) - QQ协议适配器

特别感谢:
- **KouriChat 项目组** - 提供了完整的微信Bot实现作为基础
- 所有贡献者和使用者的支持！

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star！**

Made with ❤️ by Ariadne Contributors

</div>
