# Freeclouud 自动登录与签到脚本

🤖 一个功能强大的自动化脚本，用于自动登录 Freeclouud 账户、完成每日签到、自动续费云服务器。

## 功能特性

✨ **核心功能：**

- 🔐 **自动登录** - 自动填充用户名、密码并识别验证码
- 📋 **每日签到** - 自动完成数学验证，获取积分奖励
- 💻 **云服务器续费** - 当积分充足时自动续费云服务器
- 🛡️ **反爬虫对抗** - 内置 Cloudflare 5秒盾和 Turnstile 验证绕过
- 📸 **截图记录** - 自动保存每步操作的截图用于调试
- 🔄 **多账号支持** - 支持批量处理多个账号
- 🌐 **代理支持** - 支持通过环境变量配置 HTTP 代理

## 快速开始

### 1. Fork 本仓库

点击右上角的 **Fork** 按钮，将仓库复制到你的账户

### 2. 配置 GitHub Actions Secrets

在 Fork 后的仓库中：
1. 进入 **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. 添加以下 Secret：

| Secret 名称 | 说明 | 示例 |
|-------------|------|------|
| `ACOUNT` | Freeclouud 账户信息 | `user@example.com:password` |
| `PROXY` | hy2节点代理 | `hy2://proxy:8080` |

**账户格式：**
- 单个账户：`email@example.com:password`
- 多个账户：
  - 方式一：`ACOUNT=email1@example.com:password1`，`ACOUNT_2=email2@example.com:password2`
  - 方式二：`ACCOUNTS=email1@example.com:password1,email2@example.com:password2`
  - 兼容旧格式：`ACOUNT=email1@example.com:password1,email2@example.com:password2`

### 3. 启用 GitHub Actions

1. 进入仓库的 **Actions** 标签页
2. 启用 Workflows（如果提示）
3. 脚本将按照计划自动运行

## 工作流程

脚本执行的完整流程：

```
1. 访问登录页面
   ├─ 检测并绕过 Cloudflare 5秒盾
   └─ 检测并通过 Turnstile 验证

2. 自动登录
   ├─ 获取验证码图片
   ├─ OCR 识别验证码
   ├─ 填充用户名、密码、验证码
   └─ 点击登录

3. 每日签到
   ├─ 导航至签到页面
   ├─ 点击签到按钮
   ├─ 自动解答数学问题
   ├─ 提交答案
   └─ 提取并记录积分余额

4. 积分判断
   ├─ 若积分 >= 0.01 元
   │  ├─ 导航至云服务器列表
   │  ├─ 勾选待续费服务器
   │  ├─ 生成续费订单
   │  ├─ 完成支付
   │  └─ 返回签到中心查看最新积分
   └─ 若积分 < 0.01 元，安全退出

5. 脚本完成
   └─ 输出所有账户的处理结果
```

## 配置说明

脚本在 `auto_login.py` 中的 `CONFIG` 字典包含所有网页元素选择器配置。无需修改即可使用，但若网站更新样式，请根据以下说明调整：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `target_url` | 登录页面URL | `https://nat.freecloud.ltd/login` |
| `username_selector` | 用户名输入框选择器 | `#emailInp` |
| `password_selector` | 密码输入框选择器 | `#emailPwdInp` |
| `captcha_img_selector` | 验证码图片选择器 | `#allow_login_email_captcha` |
| `captcha_input_selector` | 验证码输入框选择器 | `#captcha_allow_login_email_captcha` |
| `login_btn_selector` | 登录按钮选择器 | `button[type="submit"]` |
| `sign_in_url` | 签到页面URL | `https://nat.freecloud.ltd/addons...` |
| `server_list_url` | 云服务器列表URL | `https://nat.freecloud.ltd/service?groupid=305` |

## 截图输出

脚本会在 GitHub Actions 中自动保存每个步骤的截图。运行日志可在 **Actions** 标签页查看。

## 常见问题

### Q: 脚本多久运行一次？

**A:** 根据 Workflow 配置，通常每天在指定时间自动运行。可在 `.github/workflows/` 中的配置文件修改计划。

### Q: 验证码识别失败怎么办？

**A:** `ddddocr` 的识别率约 90%。脚本会保存截图便于调试，可检查 GitHub Actions 日志。

### Q: 如何修改脚本配置？

**A:** 编辑 `auto_login.py` 中的 `CONFIG` 字典。使用浏览器开发者工具（F12）检查网页元素，获取正确的 CSS 选择器。

### Q: 如何更新账户信息？

**A:** 进入仓库的 **Settings** → **Secrets and variables** → **Actions**，编辑对应的 Secret 即可。

### Q: 脚本如何处理密码安全？

**A:** 
- 密码存储在 GitHub Secrets 中，加密保护
- 不会在日志中显示敏感信息
- 仅在运行时从环境变量读取

## 日志输出示例

```
🚀 自动化任务启动...
📋 共检测到 2 个账号。

==========================================
➡️ 开始处理账号: user1@example.com
==========================================
🌐 正在访问目标网站: https://nat.freecloud.ltd/login
🛡️ 检测到 CF 5秒盾，准备破除...
✅ CF 5秒盾已通过！
📄 登录成功，当前页面: FreeCloud - Dashboard

>>> 🎁 准备执行每日签到任务...
✅ 计算结果为整数: 42，正在提交...
🔔 签到系统提示: 【今天已经签到过了】
💰 当前账户原始信息: 可用积分: 5.26

🏁 所有队列任务已全部执行完成！
```

## 技术栈

- **Python 3.7+**
- **SeleniumBase** - 浏览器自动化框架
- **ddddocr** - 验证码识别
- **GitHub Actions** - 自动化执行环境

## 声明

⚠️ **仅供学习和研究使用**

此脚本仅用于个人账户的自动化操作。使用本脚本需遵守 [Freeclouud](https://nat.freecloud.ltd/clientarea) 服务条款。

用户对脚本的使用承担全部责任。开发者不对任何损失负责。

## 许可证

MIT License

## 作者

[@kystor](https://github.com/kystor)

---

