# 故障排查指南

## 🔧 NapCat 启动问题

### 问题：QQ文件校验错误

#### 错误信息
```
已触发QQ文件校验退出函数, 一般情况下有可能是LLQQNT框架/插件导致的问题
```

#### 原因分析
这个错误通常由以下原因引起：
1. QQ版本不兼容
2. NapCat版本问题
3. LLQQNT框架冲突
4. 插件冲突
5. QQ文件被修改或损坏

---

## ✅ 解决方案

### 方案1：使用推荐的QQ版本（推荐）

1. **卸载当前QQ**
   - 完全卸载现有QQ客户端
   - 清理残留文件

2. **下载指定版本**
   - 推荐版本：**QQ 9.9.2-9.9.5** （最稳定）
   - 下载地址：从QQ官网或NapCat文档获取

3. **重新配置NapCat**
   ```bash
   # 重新下载NapCat最新版本
   # 确保NapCat支持你的QQ版本
   ```

### 方案2：使用NapCat Shell模式

如果桌面版QQ有问题，可以尝试Shell模式：

1. **下载QQ Shell版本**
   - NapCat支持的无GUI版本

2. **配置Shell模式**
   ```bash
   # 编辑NapCat配置
   # 启用Shell模式
   ```

### 方案3：清理LLQQNT插件

1. **找到QQ插件目录**
   ```
   C:\Users\用户名\AppData\Local\Packages\QQ...\LocalState\plugins
   ```

2. **删除所有插件**
   - 备份插件目录
   - 删除所有第三方插件
   - 只保留NapCat必需的插件

3. **重新启动**

### 方案4：使用Lagrange（替代方案）

如果NapCat持续有问题，可以考虑使用Lagrange：

1. **下载Lagrange**
   - 项目地址：https://github.com/KonataDev/Lagrange.Core
   - 这是另一个优秀的OneBot实现

2. **配置Lagrange**
   ```json
   {
     "Implementations": [
       {
         "Type": "Http",
         "Host": "127.0.0.1",
         "Port": 3000
       },
       {
         "Type": "WebSocket",
         "Host": "127.0.0.1",
         "Port": 3001
       }
     ]
   }
   ```

3. **启动Bot**
   - Lagrange使用QQ扫码登录
   - 更稳定，维护更新快

### 方案5：使用go-cqhttp（备选）

如果以上都不行，可以尝试go-cqhttp：

1. **下载go-cqhttp**
   - 项目地址：https://github.com/Mrs4s/go-cqhttp
   - ⚠️ 注意：go-cqhttp可能有风控风险

2. **配置config.yml**
   ```yaml
   account:
     uin: 你的QQ号
     password: ''  # 扫码登录
   
   servers:
     - http:
         host: 127.0.0.1
         port: 3000
     - ws:
         host: 127.0.0.1
         port: 3001
   ```

---

## 🔍 诊断步骤

### 1. 检查QQ版本
```bash
# 查看QQ版本号
# 在QQ设置-关于中查看
```

**兼容性列表**：
- ✅ QQ 9.9.2-9.9.5 - 最稳定
- ⚠️ QQ 9.9.6+ - 可能有问题
- ❌ QQ 9.9.8+ - 已知不兼容

### 2. 检查NapCat版本
```bash
# 查看NapCat版本
# 确保使用最新稳定版
```

### 3. 查看日志文件
```bash
# NapCat日志位置
C:\Users\用户名\Documents\NapCat\logs\

# 查找关键错误信息
```

### 4. 测试网络连接
```bash
# 测试OneBot端口
curl http://127.0.0.1:3000
curl ws://127.0.0.1:3001
```

---

## 🛠️ 配置检查清单

### NapCat配置
- [ ] QQ版本兼容（9.9.2-9.9.5）
- [ ] NapCat版本最新
- [ ] 配置文件正确
- [ ] 端口未被占用（3000, 3001）
- [ ] 防火墙允许通信

### Bot配置
- [ ] `.env.prod` 配置正确
- [ ] OneBot地址正确（http://127.0.0.1:3000）
- [ ] WebSocket地址正确（ws://127.0.0.1:3001）
- [ ] API Token匹配（如果设置）

---

## 📋 推荐配置方案

### 方案A：NapCat + QQ 9.9.3（最推荐）

```bash
# 1. 下载QQ 9.9.3
# 官方下载或从NapCat文档链接下载

# 2. 安装QQ 9.9.3
# 不要更新到最新版

# 3. 下载NapCat最新版
# https://github.com/NapNeko/NapCatQQ

# 4. 配置NapCat
# 编辑 config/onebot11.json
```

**NapCat配置示例**：
```json
{
  "http": {
    "enable": true,
    "host": "127.0.0.1",
    "port": 3000,
    "secret": "",
    "enableHeart": true,
    "enablePost": false
  },
  "ws": {
    "enable": true,
    "host": "127.0.0.1",
    "port": 3001
  },
  "reverseWs": {
    "enable": false
  },
  "debug": false,
  "heartInterval": 30000,
  "messagePostFormat": "array",
  "enableLocalFile2Url": true,
  "musicSignUrl": "",
  "reportSelfMessage": false
}
```

### 方案B：Lagrange（推荐备选）

```bash
# 1. 下载Lagrange
# https://github.com/KonataDev/Lagrange.Core/releases

# 2. 创建配置文件 appsettings.json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information"
    }
  },
  "SignServerUrl": "",
  "Account": {
    "Uin": 0,
    "Password": "",
    "Protocol": "Linux",
    "AutoReconnect": true,
    "GetOptimumServer": true
  },
  "Implementations": [
    {
      "Type": "Http",
      "Host": "127.0.0.1",
      "Port": 3000,
      "AccessToken": ""
    },
    {
      "Type": "WebSocket",
      "Host": "127.0.0.1",
      "Port": 3001,
      "AccessToken": ""
    }
  ]
}

# 3. 启动Lagrange
./Lagrange.OneBot

# 4. 扫码登录
```

---

## 🆘 获取帮助

### 官方支持渠道

1. **NapCat**
   - GitHub: https://github.com/NapNeko/NapCatQQ
   - Issues: 提交详细的错误日志和截图

2. **Lagrange**
   - GitHub: https://github.com/KonataDev/Lagrange.Core
   - QQ群：请查看项目文档

3. **NoneBot2**
   - 文档: https://nonebot.dev
   - 社区: NoneBot2 QQ群

### 报告问题时请提供

- QQ版本号
- NapCat/Lagrange版本号
- 完整的错误日志
- 配置文件（隐藏敏感信息）
- 操作系统版本
- 问题复现步骤

---

## 💡 最佳实践

1. **版本控制**
   - 使用经过验证的稳定版本
   - 不要频繁更新QQ
   - 关闭QQ自动更新

2. **备份配置**
   - 定期备份配置文件
   - 记录工作的版本组合

3. **监控日志**
   - 定期查看日志文件
   - 设置日志轮转

4. **测试环境**
   - 在测试环境先验证
   - 确认稳定后再部署生产

---

## 🔄 快速恢复流程

如果遇到问题无法解决：

1. **保存配置和数据**
   ```bash
   # 备份配置
   copy data\config\config.json backup\
   copy .env.prod backup\
   
   # 备份记忆数据
   xcopy /E /I data\memory backup\memory
   ```

2. **完全重装**
   - 卸载QQ
   - 删除NapCat
   - 清理残留文件
   - 重新安装推荐版本

3. **恢复配置**
   ```bash
   # 恢复配置
   copy backup\config.json data\config\
   copy backup\.env.prod .
   
   # 恢复记忆
   xcopy /E /I backup\memory data\memory
   ```

4. **测试启动**
   ```bash
   # 先测试NapCat
   # 确认能正常登录QQ
   
   # 再测试Bot
   python run_qq.py
   ```

---

## 📞 紧急联系

如果以上方法都无法解决，请：

1. 在项目GitHub开Issue
2. 提供完整的错误日志
3. 说明已尝试的解决方案
4. 等待社区响应

**记住**：大多数问题都是版本兼容性导致的，使用推荐的版本组合通常能解决90%的问题！