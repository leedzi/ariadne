# KouriChat QQ版本

基于NoneBot2和NapCat的QQ对话机器人，从微信版本迁移而来。

## 🌟 特性

- ✅ **AI对话**: 支持OpenAI GPT、Claude等多种AI模型
- ✅ **图片识别**: 自动识别和分析图片内容
- ✅ **定时提醒**: 支持设置各种提醒和定时任务
- ✅ **群聊支持**: 支持私聊和群聊场景
- ✅ **Web管理**: 保留原有的Web配置界面
- ✅ **低封号风险**: 基于官方NTQQ协议，相比微信更安全

## 📋 系统要求

- Python 3.9+
- Windows 10/11 或 Linux
- 至少 4GB 可用内存
- 一个QQ账号（建议使用小号）

## 🚀 快速开始

### 1. 安装NapCat

**Windows用户：**
```bash
# 下载NapCat
# 访问 https://github.com/NapNeko/NapCatQQ/releases
# 下载最新版本并解压
```

**Linux用户（Docker）：**
```bash
docker pull mlikiowa/napcat-docker:latest
docker run -d --name napcat -p 8080:8080 -p 8081:8081 mlikiowa/napcat-docker:latest
```

### 2. 配置NapCat

编辑 `napcat/config/config.json`：
```json
{
  "http": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 8080
  },
  "ws": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 8081
  },
  "token": "your_random_token_here"
}
```

### 3. 启动NapCat并登录QQ

运行NapCat，扫码登录你的QQ账号。

### 4. 安装Bot依赖

```bash
# 克隆项目（如果还没有）
cd kourichat

# 安装依赖
pip install -r requirements_qq.txt
```

### 5. 配置Bot

```bash
# 复制配置模板
cp .env.prod.example .env.prod

# 编辑配置文件
# Windows: notepad .env.prod
# Linux: nano .env.prod
```

关键配置项：
```env
# NapCat的Token（必须与NapCat配置一致）
ONEBOT_ACCESS_TOKEN=your_random_token_here

# 超级用户QQ号（你的QQ号）
SUPERUSERS=["123456789"]

# OpenAI API密钥
OPENAI_API_KEY=sk-...
```

### 6. 启动Bot

```bash
python run_qq.py
```

成功启动后，你会看到：
```
==================================================
🤖 QQ Bot 启动成功！
==================================================
```

### 7. 测试功能

给Bot的QQ发送消息：
```
你好
```

Bot应该会回复！

## 📁 项目结构

```
kourichat/
├── adapters/              # 平台适配器
│   ├── base.py           # 抽象基类
│   ├── qq_adapter.py     # QQ适配器 ✨新增
│   └── wechat_adapter.py # 微信适配器（保留）
├── plugins/               # NoneBot2插件 ✨新增
│   ├── chat.py           # 对话功能
│   ├── image.py          # 图片处理
│   └── reminder.py       # 提醒功能
├── src/                   # 原有代码（复用）
│   ├── services/         # AI服务
│   ├── handlers/         # 消息处理
│   └── webui/            # Web界面
├── data/                  # 数据目录
├── logs/                  # 日志目录
├── run_qq.py             # QQ版启动脚本 ✨新增
├── run.py                # 微信版启动脚本（保留）
├── requirements_qq.txt   # QQ版依赖 ✨新增
└── .env.prod             # 环境配置
```

## 🎮 使用说明

### 基础命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/help` | 显示帮助信息 | `/help` |
| `/status` | 查看Bot状态 | `/status` |
| `/提醒` | 添加提醒 | `/提醒 明天9点 开会` |
| `/提醒列表` | 查看提醒列表 | `/提醒列表` |
| `/删除提醒` | 删除提醒 | `/删除提醒 1` |

### 对话功能

**私聊：**
直接发送消息即可对话。

**群聊：**
@Bot + 消息内容，例如：
```
@Bot 你好
```

### 图片识别

发送图片给Bot，会自动识别并返回结果。

### 定时提醒

```bash
# 添加提醒
/提醒 明天9点 开会
/提醒 2小时后 休息一下

# 查看提醒
/提醒列表

# 删除提醒
/删除提醒 1
```
### 表情包管理工具

本项目提供了一套强大的表情包管理工具，位于 `tools/` 目录下。

**主要功能：**
- **自动重命名**：使用 GPT-4V 等视觉模型自动识别表情包内容并重命名为中文（如 `happy.jpg` -> `开心大笑.jpg`）。
- **批量处理**：支持一键批量处理整个文件夹。
- **多模型支持**：兼容 OpenAI, Gemini, Claude 等多种模型。

**使用方法：**
1. 进入 `tools/` 目录。
2. Windows 用户直接双击 `rename_emoji.bat`。
3. 首次运行需配置 API Key。

详细说明请参考 [表情包工具文档](tools/README.md)。

## ⚙️ 配置说明

### AI服务配置

在 `.env.prod` 中配置：

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Claude（可选）
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-sonnet-20240229
```

### 超级用户配置

超级用户拥有管理权限：

```env
SUPERUSERS=["123456789", "987654321"]
```

### 功能开关

```env
ENABLE_IMAGE_RECOGNITION=true  # 图片识别
ENABLE_REMINDER=true            # 提醒功能
ENABLE_WEB_SEARCH=false         # 网络搜索
```

## 🔧 高级配置

### 多账号支持

可以同时运行多个Bot实例，每个使用不同的端口和配置。

### 自定义插件

在 `plugins/` 目录创建新的插件文件：

```python
# plugins/my_plugin.py
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Event

my_cmd = on_command("mycommand")

@my_cmd.handle()
async def handle_my_command(bot: Bot, event: Event):
    await bot.send(event, "Hello from my plugin!")
```

### 数据库配置

默认使用SQLite，数据库文件位于 `data/bot.db`。

## 🐛 常见问题

### Q: Bot不回复消息

**排查步骤：**
1. 检查NapCat是否正常运行
2. 检查Token配置是否一致
3. 查看日志文件 `logs/qq_bot_*.log`
4. 确认QQ已成功登录

### Q: 图片识别失败

**解决方案：**
1. 检查AI API配置
2. 确认图片格式正确（jpg/png）
3. 检查网络连接

### Q: 提醒不触发

**检查：**
1. 确认apscheduler插件已加载
2. 查看日志中的定时任务状态
3. 检查系统时间是否正确

### Q: 被QQ风控

**预防措施：**
- 使用小号测试
- 避免频繁发送消息
- 不发送敏感内容
- 消息间隔 > 1秒

## 📊 性能对比

| 指标 | 微信版 | QQ版 |
|------|--------|------|
| 消息延迟 | 1-3秒 | <500ms |
| 稳定性 | 一般 | 优秀 |
| 封号风险 | 高 | 低 |
| 并发处理 | 有限 | 优秀 |

## 🔄 从微信版迁移

如果你之前使用的是微信版：

1. **保留原有数据**：
   - 数据库文件在 `data/` 目录
   - 配置文件在 `data/config/`

2. **配置映射**：
   ```python
   # 微信配置 -> QQ配置
   wechat_config['listen_list'] -> QQ群/好友列表
   wechat_config['auto_reply'] -> 保持不变
   ```

3. **AI服务**：
   完全兼容，无需修改。

## 📚 相关文档

- [完整迁移计划](migration_plan.md)
- [架构对比说明](architecture_comparison.md)
- [快速开始指南](QUICK_START_QQ.md)
- [风险评估报告](RISK_ASSESSMENT.md)

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📝 更新日志

### v2.0.0 (2024-10-26)
- ✨ 新增QQ平台支持
- ✨ 基于NoneBot2重构
- ✨ 实现平台抽象层
- ✨ 支持微信/QQ双平台
- 🔥 大幅降低封号风险
- ⚡ 性能优化，消息延迟降低

### v1.0.0
- 初始微信版本

## 📄 许可证

[MIT License](LICENSE)

## 🙏 致谢

- [NoneBot2](https://nonebot.dev/) - 优秀的Python机器人框架
- [NapCat](https://github.com/NapNeko/NapCatQQ) - 新一代QQ协议实现
- [wxauto](https://github.com/cluic/wxauto) - 微信自动化工具

## ⚠️ 免责声明

本项目仅供学习交流使用，请遵守相关平台的服务条款。使用本项目所产生的一切后果由使用者自行承担。

---

如有问题，请查看[常见问题解答](QUICK_START_QQ.md#常见问题)或提交Issue。