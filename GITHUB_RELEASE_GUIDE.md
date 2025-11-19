# GitHub Release 发布指南

## ✅ 已完成步骤

### 1. Git 配置与推送
```bash
✓ git config --global user.name "leedzi"
✓ git config --global user.email "hatsuneqwer@outlook.com"
✓ git config core.autocrlf true
✓ git commit -m "feat: Initial QQ migration (based on KouriChat)"
✓ git branch -M main
✓ git remote add origin https://github.com/leedzi/ariadne.git
✓ git push -u origin main
✓ git tag -a v1.0.0 -m "Ariadne v1.0.0: Initial QQ platform release based on KouriChat"
✓ git push origin v1.0.0
```

**推送结果**：
- ✅ 180 个文件已提交
- ✅ 37,138 行代码已上传
- ✅ 版本标签 v1.0.0 已创建

---

## 📋 下一步：在 GitHub 网页创建 Release

### 步骤 1：访问 Release 页面
1. 打开浏览器访问：https://github.com/leedzi/ariadne/releases
2. 点击右上角 **"Draft a new release"** 按钮

### 步骤 2：填写 Release 信息

#### **Choose a tag**
- 选择：`v1.0.0` （已存在的标签）

#### **Release title**
```
Ariadne v1.0.0 - 初始发布版
```

#### **Describe this release**
复制粘贴以下内容：

```markdown
## 🎉 Ariadne v1.0.0 - 基于 KouriChat 的 QQ 平台迁移版

### 📖 项目简介
Ariadne 是一个基于 **NoneBot2** 和 **NapCat** 的 QQ 聊天机器人框架，由 [KouriChat](https://github.com/Cassius0924/KouriChat) 项目改造而来。本项目将原微信平台功能完整迁移到 QQ 平台，保留所有核心特性。

### ⚠️ 重要说明
- **群聊功能已完全禁用**：仅支持私聊场景
- **需要 NapCat 协议端**：请先部署 NapCat 服务
- **敏感信息已清理**：发布版不含任何 API 密钥和私有配置

### ✨ 核心功能

| 功能模块 | 描述 | 状态 |
|---------|------|------|
| 🤖 AI 对话 | 多 LLM 支持（OpenAI/Claude/Gemini/DeepSeek） | ✅ |
| 🖼️ 图片识别 | GPT-4V/Claude Vision 图像理解 | ✅ |
| 📝 记忆系统 | 短期/长期记忆 + 向量数据库 | ✅ |
| ⏰ 提醒功能 | 自然语言提醒创建 + LLM 生成回复 | ✅ |
| 😊 智能表情 | 双模式情境识别（精准/模糊） | ✅ |
| 💬 消息队列 | 10秒内消息自动合并 | ✅ |
| 🔍 网络搜索 | Tavily/SerpAPI 实时搜索 | ✅ |
| 📤 主动消息 | 定时主动发送（支持表情） | ✅ |

### 📦 内置人设
- **ATRI (アトリ)**：元气满满的仿生人
- **MONO (モノ)**：温柔体贴的陪伴者
- **Nijiko (虹子)**：活泼开朗的少女

### 🚀 快速开始

#### 1. 环境要求
- Python 3.10+
- NapCat 协议端（OneBot V11）
- ChromaDB 向量数据库

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

#### 3. 配置机器人
```bash
# 复制配置示例
cp data/config/config.example.json data/config/config.json

# 编辑配置文件（填写 QQ 号、API 密钥等）
notepad data/config/config.json
```

#### 4. 启动服务
```bash
# 启动 NapCat（先启动）
# 参考：https://napneko.github.io/

# 启动 Ariadne
python run_qq.py
```

### 📚 文档链接
- [快速开始指南](QUICK_START_QQ.md)
- [消息队列与主动消息](MESSAGE_QUEUE_AND_AUTOSEND_GUIDE.md)
- [智能表情系统](SMART_EMOJI_GUIDE.md)
- [故障排查](TROUBLESHOOTING.md)

### 🙏 致谢
- **KouriChat 项目组**：本项目基于 KouriChat 改造，感谢原作者的开源贡献
- **NoneBot2 社区**：提供强大的机器人开发框架
- **NapCat 项目**：提供稳定的 QQ 协议适配

### 📝 更新日志
- ✅ 完成微信到QQ平台的完整迁移
- ✅ 修复 50+ 个关键 Bug
- ✅ 实现智能情境表情系统
- ✅ 实现消息队列合并机制
- ✅ 完全禁用群聊功能
- ✅ 清理所有敏感信息

### 📄 许可证
MIT License - 详见 [LICENSE](LICENSE) 文件

### 🐛 问题反馈
发现 Bug 或有功能建议？请提交 [Issue](https://github.com/leedzi/ariadne/issues)

---

**⚠️ 免责声明**：本项目仅供学习交流使用，请遵守相关平台服务条款。
```

### 步骤 3：发布选项
- ✅ 勾选 **"Set as the latest release"**（设为最新版本）
- ✅ 勾选 **"Create a discussion for this release"**（可选，创建讨论）

### 步骤 4：点击发布
- 点击绿色按钮 **"Publish release"**

---

## 🎯 发布后检查清单

### GitHub 仓库检查
- [ ] README.md 正确显示（包含 KouriChat 致谢）
- [ ] 群聊禁用说明清晰可见
- [ ] LICENSE 文件存在
- [ ] .gitignore 正确排除敏感文件

### 文档完整性
- [ ] QUICK_START_QQ.md 可访问
- [ ] MESSAGE_QUEUE_AND_AUTOSEND_GUIDE.md 存在
- [ ] SMART_EMOJI_GUIDE.md 存在
- [ ] TROUBLESHOOTING.md 存在

### 配置文件检查
- [ ] config.example.json 不含真实密钥
- [ ] 所有 QQ 号已替换为占位符
- [ ] yuki 人设已完全移除

---

## 🔄 后续版本发布流程

### 创建新版本
```bash
# 1. 确保所有改动已提交
git add .
git commit -m "feat: 新功能描述"

# 2. 创建新标签（如 v1.1.0）
git tag -a v1.1.0 -m "版本描述"

# 3. 推送代码和标签
git push origin main
git push origin v1.1.0

# 4. 在 GitHub 网页创建 Release（同上步骤）
```

### 语义化版本规则
- **v1.0.0 → v1.0.1**：Bug 修复（PATCH）
- **v1.0.0 → v1.1.0**：新功能（MINOR）
- **v1.0.0 → v2.0.0**：破坏性变更（MAJOR）

---

## 🎊 恭喜！

你的 Ariadne 项目已成功发布到 GitHub！

**仓库地址**：https://github.com/leedzi/ariadne  
**Release 页面**：https://github.com/leedzi/ariadne/releases/tag/v1.0.0

现在其他开发者可以：
- ⭐ Star 你的项目
- 🍴 Fork 并改造
- 🐛 提交 Issue 反馈
- 🔀 提交 Pull Request 贡献代码