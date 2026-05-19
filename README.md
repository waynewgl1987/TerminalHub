# TerminalHub

**中文** | [English](#english)

---

## 中文文档

### 项目简介

TerminalHub 是一个基于 Python 的高性能 **Web 终端管理平台**，运行于本地，通过浏览器统一管理所有正在运行的终端会话。

它解决了以下痛点：
- 多个终端窗口分散在桌面，状态难以总览
- 无法实时掌握每个终端进程的资源占用
- 大模型 AI 代码助手（Copilot、Claude、Aider 等）悄悄修改文件，修改前后无从对比
- 会话结束后想回溯"这个终端做了什么"却没有记录
- 需要把日志、代码差异和 AI 分析汇总后发给同事

TerminalHub 将所有这些能力整合到一个简洁的浏览器界面中，同时保持极低的资源开销。

---

### 主要功能

#### 🖥️ 终端管理
- 在浏览器中创建、查看、交互、终止任意数量的终端
- 基于 **PTY（伪终端）** 实现，输出与原生终端完全一致（ANSI 颜色、光标控制均正常工作）
- 使用 **xterm.js** 渲染，支持字体缩放、滚动、选中复制
- 新建终端时可指定：Shell 类型（zsh / bash / sh / fish / cmd / PowerShell）、工作目录、自定义标题、任务描述、监听目录
- 每个终端卡片顶部可 **展开 / 收起** 信息区，显示完整元数据
- 终端卡片底部展示 **连接状态指示灯**（绿色 = 已连接，红色 = 已断开）
- **拖拽文件 / 文件夹** 到终端区域，自动将完整文件系统路径输入到命令行（阻止浏览器默认的打开新标签行为；路径含空格时自动加引号；支持同时拖入多个文件）

#### 📊 实时系统监控
- 仪表盘顶部实时显示：系统 CPU 占用率、内存用量、活跃终端数、检测到 AI 的终端数
- 每个终端卡片头部（展开状态）显示该终端进程的：
  - **CPU 占用率**（%）
  - **内存占用**（MB / %）
  - **线程数**
  - **进程状态**（running / sleeping / dead）
  - **进程 PID**
- 所有数据每 **2 秒** 自动刷新（可通过 `config.ini` 调整）
- 监控数据通过 WebSocket 广播，不轮询 HTTP，零开销
- 每个终端卡片实时显示 **WebSocket RTT 延迟**（毫秒），颜色区分：🟢 ≤20ms / 🟡 ≤80ms / 🔴 >80ms

#### 🤖 AI 模型自动识别
- 当终端正在运行 AI 相关工具时，自动在卡片上显示 **AI 徽章**
- 识别依据：进程命令行关键词 + 环境变量 + 网络连接特征
- 支持识别的框架 / 工具：

  | 工具 | 提供商 |
  |------|--------|
  | GitHub Copilot | GitHub |
  | Claude (claude CLI / API) | Anthropic |
  | Ollama | Meta / 各开源模型 |
  | OpenAI API / ChatGPT | OpenAI |
  | DeepSeek | DeepSeek |
  | Aider | 开源 |
  | Cursor AI | Cursor |
  | Qwen / QwQ | 阿里巴巴 |

- 识别结果包含：提供商名称、框架名称、检测到的模型名（如 `gpt-4o`）、置信度评分

#### 📂 代码变更实时监控
- 创建终端时指定 **监听目录**，自动追踪该目录下的所有文件变更
- 支持 25+ 种代码文件后缀（`.py` `.js` `.ts` `.swift` `.go` `.rs` `.java` `.kt` 等）
- 每次文件修改时：
  1. 从 Git 获取变更前的内容（`git show HEAD:<path>`），若不在 Git 仓库则使用内存缓存
  2. 读取变更后的新内容
  3. 使用 `difflib` 生成 unified diff，并转换为带颜色标注的 HTML
  4. 通过后台线程将记录写入 `tmp/code_changes_{terminal_id}.json`
- 文件读写使用 `threading.Lock` 保证线程安全，不阻塞主事件循环
- 忽略 `.git`、`node_modules`、`__pycache__` 等目录

#### 📋 会话日志导出报告
- 点击终端卡片的 **"导出报告"** 按钮，生成完整的自包含 HTML 报告
- 报告包含：
  - 会话摘要（标题、Shell、工作目录、创建时间、会话时长、变更文件数、代码行增删统计）
  - **Git 上下文**（当前分支、最新提交 SHA / 消息 / 作者 / 时间）
  - 完整终端日志（ANSI 转义码已剥离，保留可读文本）
  - 所有代码变更（逐文件展示变更前后内容，双栏对比 + unified diff 高亮）
  - AI 分析摘要（可选，由配置的大模型生成）
  - 底部生成时间与 TerminalHub 版本信息
- 报告文件完全自包含（CSS / JS 全部内联），可直接分享、离线查看
- 生成的报告同时保存到 `tmp/reports/` 目录，通过 `/reports/<filename>` URL 可直接访问（响应头 `X-Report-URL` 携带此地址）
- 导出操作全程显示 **底部进度条 Toast**，带步骤列表、动画进度条、完成 / 失败状态，操作按钮在进行中自动禁用防止重复点击

#### 🔬 报告内嵌 AI 分析
导出的 HTML 报告本身内置完整的 AI 交互能力：

- **顶部 AI 配置栏**：可直接在报告内配置 Provider / Model / API Key，实时测试连接状态
- **逐差异 AI 分析**：每个代码变更旁有 "让 AI 分析" 按钮，点击后将变更前后代码发送给大模型，获取：
  - 变更目的与原理说明
  - 代码质量评估
  - 潜在风险提示
- **四个操作按钮**（每个差异独立）：
  - ✅ **接受变更** — 将该差异标记为已接受（绿色高亮），并可通过 `POST /api/report/apply-change` 将"变更后"内容写回磁盘
  - ⚠️ **标记风险** — 将该差异标记为需要复查（红色高亮），同样可将"变更前"内容还原写回磁盘
  - 🔄 **请求更优方案** — 打开对话框，可输入具体要求，AI 给出改进后的代码
- 报告内支持 **中英文切换** 和 **浅色 / 深色主题切换**

#### 📧 邮件发送
- 任意报告可通过内置邮件功能直接发送到指定邮箱
- 支持：Gmail（STARTTLS:587）、Outlook、阿里云邮件、自定义 SMTP 服务器（SSL:465 / STARTTLS:587）
- 报告 HTML 文件作为附件随邮件一同发送，收件人可离线查看
- SMTP 配置按需填写，不存储明文密码

#### 🧠 AI 提供商配置面板
- 页面右上角的 **"AI 设置"** 打开侧边配置面板
- 支持的提供商：

  | Provider | 认证方式 |
  |----------|----------|
  | GitHub Copilot | 自动读取本地 gh CLI / apps.json / 环境变量，无需手动填 Key |
  | OpenAI | API Key |
  | Anthropic Claude | API Key |
  | DeepSeek | API Key |
  | Qwen（通义千问） | API Key（DashScope） |
  | Ollama | 无需 Key，本地 `http://localhost:11434` |
  | Custom（自定义） | API Key + 自定义 Base URL |

- 提供商选择后，**模型列表自动加载**（Copilot 从 API 获取实时列表）
- **"测试连接"** 按钮一键验证当前配置是否有效
- 配置自动保存到浏览器 `localStorage`，刷新页面后无需重填

#### 🌐 多语言 & 主题
- 页面顶栏提供 **中文 / English** 切换，所有 UI 文字即时更新
- **浅色 / 深色** 主题切换，偏好自动保存
- 导出的 HTML 报告同样支持独立的语言和主题切换

---

### 项目结构

```
TerminalHub/
├── main.py                     ← 应用入口 (FastAPI + uvicorn)
├── config.ini                  ← 应用配置文件
├── requirements.txt            ← Python 依赖清单
├── start.sh                    ← 一键启动脚本
│
├── modules/                    ← 后端功能模块（低耦合，各司其职）
│   ├── __init__.py             ← 统一导出入口
│   ├── terminal_manager.py     ← PTY 终端生命周期管理
│   ├── system_monitor.py       ← 系统与进程资源监控
│   ├── ai_detector.py          ← AI 框架 / 模型自动识别
│   ├── code_watcher.py         ← 文件系统变更监控与 diff 生成
│   ├── report_generator.py     ← HTML 报告渲染引擎
│   ├── email_sender.py         ← SMTP 邮件发送
│   ├── ai_provider.py          ← 多提供商 LLM 调用层
│   └── context_store.py        ← 会话上下文持久化（跨重启保留）
│
├── static/                     ← 前端静态资源
│   ├── index.html              ← 主界面 HTML
│   ├── css/
│   │   └── styles.css          ← 全局样式（浅色 / 深色 CSS 变量）
│   └── js/
│       ├── app.js              ← 主逻辑（应用初始化、监控 WebSocket）
│       ├── terminal.js         ← xterm.js 终端 Widget 类
│       ├── ai_panel.js         ← AI 提供商配置面板
│       ├── report.js           ← 报告导出 / 邮件 / 代码差异弹窗
│       └── i18n.js             ← 中英文国际化翻译表
│
└── tmp/                        ← 运行时临时目录（自动创建）
    ├── reports/                ← 生成的 HTML 报告 + 变更 sidecar JSON
    │   ├── report_<id>_<ts>.html
    │   └── sidecar_<id>_<ts>.json
    └── contexts/               ← 会话上下文快照（跨重启保留）
        └── <terminal_id>.json
```

---

### 模块详细说明

#### `main.py` — 应用入口

使用 **FastAPI** + **uvicorn** 构建高性能异步 HTTP / WebSocket 服务。

**REST API 路由：**

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 返回主界面 HTML |
| `GET` | `/api/terminals` | 列出所有终端（含实时 stats） |
| `POST` | `/api/terminals` | 创建新终端 |
| `DELETE` | `/api/terminals/{id}` | 终止并销毁终端 |
| `PATCH` | `/api/terminals/{id}` | 更新终端标题 / 描述 |
| `GET` | `/api/terminals/{id}/log` | 获取完整日志缓冲区 |
| `POST` | `/api/terminals/{id}/resolve-path` | 将拖入的文件 / 文件夹名解析为绝对路径 |
| `GET` | `/api/code-changes/{id}` | 获取终端关联的代码变更列表 |
| `GET` | `/api/contexts` | 列出所有持久化的会话上下文 |
| `GET` | `/api/contexts/{id}` | 获取指定终端的持久化上下文 |
| `DELETE` | `/api/contexts/{id}` | 删除指定终端的持久化上下文 |
| `POST` | `/api/report/generate` | 生成并返回 HTML 报告（同时保存到 `tmp/reports/`） |
| `POST` | `/api/report/apply-change` | 将接受 / 回滚的文件内容写回磁盘 |
| `POST` | `/api/email/send` | 通过 SMTP 发送报告邮件 |
| `GET` | `/api/git/info` | 获取指定目录的 Git 元数据（分支、提交、作者等） |
| `GET` | `/api/git/file-diff` | 获取指定文件的 HEAD~1 vs 工作区 diff |
| `GET` | `/api/ai/providers` | 获取支持的 AI 提供商列表 |
| `GET` | `/api/ai/models` | 获取指定提供商的模型列表 |
| `POST` | `/api/ai/test` | 测试 AI 提供商连接 |
| `POST` | `/api/ai/chat` | 异步发起 AI 对话（返回 job_id） |
| `GET` | `/api/ai/job/{job_id}` | 轮询异步 AI 任务状态 |

**WebSocket 路由：**

| 路径 | 说明 |
|------|------|
| `/ws/terminal/{id}` | 终端双向 I/O 通道 |
| `/ws/monitor` | 系统状态广播（每 2 秒推送一次） |

---

#### `modules/terminal_manager.py` — PTY 终端管理

**核心类：** `TerminalSession`、`TerminalManager`

`TerminalSession` 封装单个终端的完整生命周期：
- **Unix/macOS**：使用 `pty.openpty()` 创建 PTY 对，`subprocess.Popen` 以 PTY 作为 stdin/stdout/stderr 启动 Shell，父进程持有 master fd
- **Windows**：优先尝试 `pywinpty`（`winpty.PtyProcess`），若不可用则退化为带管道的 `subprocess.Popen`
- **PTY 输出读取**：在独立的后台线程中循环调用 `select.select` + `os.read(master_fd, 8192)`，将原始字节解码后分发给所有注册的 WebSocket 回调
- **输入写入**：`os.write(master_fd, data.encode())` 直接写入 PTY，完整传递功能键、方向键等控制序列
- **终端大小调整**：通过 `fcntl.ioctl(master_fd, termios.TIOCSWINSZ, ...)` 动态同步终端尺寸
- **日志缓冲**：使用 `collections.deque(maxlen=5000)` 滚动缓冲，新 WebSocket 客户端连接时立即回放最近 200 行
- **多客户端广播**：同一终端可被多个浏览器标签同时观察，输出实时同步

`TerminalManager` 管理所有会话的字典，提供线程安全的 `create` / `kill` / `get` / `list_all` 操作。

---

#### `modules/system_monitor.py` — 系统监控

基于 **psutil** 实现，带 TTL 缓存（默认 2 秒）避免频繁系统调用。

- `get_process_stats(pid)` → 返回 `{cpu_pct, mem_mb, mem_pct, status, threads}`
  - 每个 PID 缓存一个 `psutil.Process` 对象，避免重复查找
  - 首次访问时调用 `cpu_percent(interval=None)` 初始化 CPU 基线，后续调用才有意义的数值
- `get_system_stats()` → 返回 `{cpu_pct, mem_total_gb, mem_used_gb, mem_pct}`
- 进程消失时（`NoSuchProcess`）优雅返回零值，并清理缓存条目
- 所有缓存读写均持有 `threading.Lock`，对多线程安全

---

#### `modules/ai_detector.py` — AI 模型识别

基于三维特征对进程（及其子进程）打分，输出置信度：

| 特征 | 权重 |
|------|------|
| 进程命令行包含框架关键词 | +0.60 |
| 进程环境变量包含 API Key | +0.25 |
| Ollama：连接到本地 11434 端口 | +0.20 |
| 其他 AI API：有出向 443 连接 | +0.05 |

- 遍历目标进程及所有子进程，取得分最高者
- 额外从命令行 / 环境变量中提取具体模型名（支持 `gpt-*`、`claude-*`、`deepseek-*`、`qwen-*`、`llama-*`、`gemini-*` 等正则匹配）
- 检测结果结构：`{detected, provider, model, framework, confidence}`

---

#### `modules/code_watcher.py` — 代码变更监控

**按需计算（非实时文件监听）**：不依赖 watchdog 或后台文件事件，改为在导出报告时通过 `git diff HEAD` 一次性计算变更，彻底避免了 FSEvents 线程错误和持续的资源占用。

**工作流程（调用 `get_changes()` 时）：**
1. 查找监听目录下的 Git 仓库（支持嵌套，最多扫描 2 层子目录）
2. 执行 `git diff HEAD --name-status` 获取已修改/新增/删除的文件列表
3. 执行 `git status --porcelain` 补充未追踪的新文件（`??` 行）
4. 对每个变更文件：`git show HEAD:<path>` 获取修改前内容，读取磁盘文件获取修改后内容
5. 调用 `difflib.unified_diff` 生成 diff 文本，并转换为带颜色标注的 HTML
6. 若目录不在任何 Git 仓库中，退化为文件系统扫描（1 小时内 mtime 变化的代码文件）

**快速徽章计数（`count_changes()`）：**
仅执行 `git diff HEAD --name-only`（无需读取文件内容），结果缓存 120 秒，UI 徽章刷新不触发完整 diff。

**变更记录结构：**
```json
{
  "terminal_id": "...",
  "file_path": "/abs/path/to/file.py",
  "change_type": "modified",
  "before": "# HEAD 版本内容",
  "after": "# 当前磁盘内容",
  "diff": "--- before/file.py\n+++ after/file.py\n...",
  "diff_html": "<div class='diff-add'>...</div>",
  "timestamp": 1778739870.95,
  "git_commit": "a1b2c3d4...",
  "language": "python"
}
```

- 单个文件最多捕获 200,000 字符，防止超大文件导致内存膨胀
- 跳过 `.git`、`node_modules`、`__pycache__`、`venv`、`dist`、`build` 等目录

---

#### `modules/report_generator.py` — HTML 报告生成

纯 Python 字符串渲染，生成完整自包含的 HTML 文件（无外部依赖）。

报告结构：
1. **顶部 AI 配置栏** — Provider 下拉、Model 下拉、API Key 输入、连接状态指示、"测试连接" 按钮
2. **会话摘要卡片** — 终端标题、Shell、工作目录、创建时间、会话时长、变更文件数、增删行统计
3. **Git 上下文块**（可选）— 分支名、最新提交 SHA（含 `prev_commit`）、提交消息、作者、时间
4. **AI 分析摘要区**（可选）— 由后端 LLM 预生成，嵌入报告正文
5. **终端日志区** — ANSI 转义码剥离后的完整日志文本，等宽字体显示
6. **代码变更列表** — 每个变更文件一张卡片，包含：
   - 文件路径 + 变更类型 + 语言标签
   - 变更前 / 后代码（双栏对比）
   - Unified diff 高亮视图
   - "让 AI 分析" / "接受" / "标记风险" / "请求更优方案" 按钮
   - AI 响应展示区（按需填充）
7. **底部** — 生成时间、TerminalHub 版本

报告内嵌 JS 实现：
- 调用配置的 AI 提供商 API（OpenAI compatible format）
- 异步 fetch，带 loading 动画
- 结果以 Markdown-style 格式化展示
- 接受 / 拒绝状态持久化到 `localStorage`
- 点击"接受变更" / "标记风险"时，通过 `POST /api/report/apply-change`（携带 `sidecar_id` + `change_index` + `action`）将对应文件内容写回磁盘；sidecar JSON 在报告生成时同步落盘

---

#### `modules/email_sender.py` — SMTP 邮件发送

- 支持 **STARTTLS（端口 587）** 和 **SSL（端口 465）** 两种模式
- 邮件包含纯文本备注 + HTML 正文 + HTML 文件附件（三者同时发送）
- 超时设置 20 秒，避免网络卡顿导致服务阻塞
- 不存储任何 SMTP 凭据，每次请求时按需传入

---

#### `modules/context_store.py` — 会话上下文持久化

在服务重启之间保留每个终端的轻量快照，保存于 `tmp/contexts/{terminal_id}.json`。

**快照包含：**
- 元数据：id、title、description、shell、cwd、created_at、watch_path
- ai_info：最近一次 AI 检测结果
- log_tail：最近 500 行日志（ANSI 已剥离）
- code_changes_count：关联的代码变更数量
- saved_at：快照时间戳

**工作机制：**
- 启动时调用 `attach(sessions)` 关联活跃会话字典
- 后台线程每 **30 秒**将所有"脏"（dirty）会话刷新到磁盘；服务正常退出时同步 flush 所有会话
- 写入使用原子重命名（`.tmp` → `.json`），防止断电 / crash 损坏文件
- 公开 API：`mark_dirty(tid)` / `flush(tid)` / `load(tid)` / `list_contexts()` / `delete(tid)`
- 通过 `/api/contexts` 路由对外暴露，可用于会话历史浏览

---

#### `modules/ai_provider.py` — LLM 调用层

完整移植自 **GitAutoManageBoard** 项目的 AI 模块，支持以下提供商：

| Provider | 接口协议 | 特殊处理 |
|----------|----------|----------|
| GitHub Copilot | OpenAI-Compatible | 自动从 gh CLI / keychain / apps.json / 环境变量获取 OAuth Token，25 分钟缓存 |
| OpenAI | OpenAI-Compatible | 标准 Bearer Token |
| Anthropic Claude | Anthropic Messages API | 单独的请求格式与 Header |
| DeepSeek | OpenAI-Compatible | 自定义 Base URL |
| Qwen | OpenAI-Compatible | DashScope 端点 |
| Ollama | OpenAI-Compatible | 本地 `http://localhost:11434/v1` |
| Custom | OpenAI-Compatible | 用户自定义 Base URL |

**公开 API：**
```python
call_llm(provider, api_key, base_url, model, messages) -> (ok: bool, text: str)
test_provider(provider, api_key, base_url, model)       -> (ok: bool, message: str)
get_copilot_models()                                    -> list[str]
start_chat_job(provider, api_key, base_url, model, messages) -> job_id: str
get_job_status(job_id)                                  -> dict
```

AI 调用通过线程池异步执行，不阻塞 asyncio 事件循环。

---

#### 前端模块

| 文件 | 职责 |
|------|------|
| `static/index.html` | 主界面骨架：顶栏、仪表盘摘要、终端网格、新建终端弹窗、AI 配置面板、代码差异弹窗、邮件弹窗 |
| `static/css/styles.css` | CSS 自定义属性驱动的浅色 / 深色双主题；终端卡片、折叠面板、状态指示灯、差异高亮等完整样式 |
| `static/js/i18n.js` | 60+ 个 UI 字符串的中英文对照表；`setLang()` 函数全局替换所有 `data-i18n` 节点 |
| `static/js/app.js` | 连接 `/ws/monitor`，接收系统快照更新仪表盘；管理终端 Widget 的创建与销毁；绑定主题 / 语言切换事件 |
| `static/js/terminal.js` | `TerminalWidget` 类：初始化 xterm.js 实例 + FitAddon + WebLinksAddon，连接 `/ws/terminal/{id}`，处理输入输出、尺寸自适应、折叠动画、AI 徽章、连接状态灯 |
| `static/js/ai_panel.js` | 侧边 AI 配置面板：动态加载提供商列表和模型列表，测试连接，读写 localStorage |
| `static/js/report.js` | 报告导出（POST → 新标签打开）、代码差异弹窗渲染、邮件发送表单处理 |

---

### 快速开始

#### 前提条件

- Python 3.10+
- macOS / Linux / Windows
- （可选）Git — 用于获取代码变更的 "修改前" 版本

#### 安装与启动

```bash
# 克隆或进入项目目录
cd /path/to/TerminalHub

# 方法一：一键启动（自动安装依赖）
bash start.sh

# 方法二：手动安装后启动
pip install -r requirements.txt
python main.py
```

启动后访问：**http://localhost:8765**

---

### 配置参考

编辑 `config.ini` 自定义运行参数：

```ini
[app]
name                 = TerminalHub        # 界面显示名称
version              = v1.0.0
port                 = 8765               # 监听端口
host                 = 0.0.0.0            # 监听地址（0.0.0.0 = 所有网卡）
default_shell_unix   = /bin/zsh           # Unix 默认 Shell
default_shell_windows = cmd.exe           # Windows 默认 Shell
default_lang         = zh                 # 默认语言 (zh / en)
default_theme        = light              # 默认主题 (light / dark)

[monitoring]
stats_interval       = 2                  # 监控刷新间隔（秒）
log_max_lines        = 5000               # 每个终端最大日志行数
code_changes_file    = tmp/code_changes_{terminal_id}.json

[email]
smtp_host            = smtp.gmail.com     # 默认 SMTP 服务器
smtp_port            = 587
smtp_user            =                    # 留空则运行时填写
smtp_pass            =
```

---

### WebSocket 协议

#### `/ws/terminal/{id}` — 终端 I/O 通道

**客户端 → 服务端：**
```json
{ "type": "input",  "data": "ls -la\r" }
{ "type": "resize", "rows": 40, "cols": 120 }
{ "type": "ping",   "t": 1715673600123.45 }
```

**服务端 → 客户端：**
```json
{ "type": "output",  "data": "\u001b[1;32muser@host\u001b[0m:~$ " }
{ "type": "status",  "connected": true }
{ "type": "stats",   "cpu": 1.2, "mem_mb": 42.5, "mem_pct": 0.5, "status": "sleeping", "threads": 3, "cwd": "/Users/wayne/projects/foo" }
{ "type": "ai_info", "detected": true, "provider": "GitHub", "framework": "GitHub Copilot", "model": "gpt-4o", "confidence": 0.85 }
{ "type": "pong",    "t": 1715673600123.45 }
```

> **实时 cwd 追踪**：`stats` 消息中的 `cwd` 字段由 `psutil.Process(pid).cwd()` 读取 Shell 进程的当前工作目录，每 2 秒更新一次。用户或 AI 执行 `cd` 后，终端卡片副标题会自动切换到新目录，无需重建终端。读取失败时（macOS 权限竞争）使用上一次成功读取的值，而不是退回到终端初始目录，以避免路径闪烁。

> **延迟探针机制**：浏览器每 3 秒发送一个 `ping`（携带 `performance.now()` 时间戳），服务端以最高优先级（Priority 0）将 `pong` 插入发送队列，绕过所有积压的终端输出数据。浏览器收到 `pong` 后计算 `now - t`，得到真实的 WebSocket 往返延迟（RTT）。

#### `/ws/monitor` — 系统状态广播

```json
{
  "type": "monitor",
  "system": { "cpu_pct": 18.3, "mem_total_gb": 16.0, "mem_used_gb": 9.4, "mem_pct": 58.7 },
  "terminals": [ { "id": "...", "title": "...", "alive": true, "stats": {...} } ],
  "code_changes": { "<terminal_id>": 3 }
}
```

---

### 技术栈

| 层次 | 技术 |
|------|------|
| Web 框架 | [FastAPI](https://fastapi.tiangolo.com/) |
| ASGI 服务器 | [uvicorn](https://www.uvicorn.org/)（含 WebSocket 支持） |
| 事件循环加速 | [uvloop](https://github.com/MagicStack/uvloop)（Unix 专用，速度是纯 Python asyncio 的 2-4×） |
| 终端仿真（后端） | `pty` (Unix) / `pywinpty` (Windows) |
| 进程监控 | [psutil](https://github.com/giampaolo/psutil) |
| 文件系统监控 | `git diff HEAD`（按需 subprocess 调用，无后台 watcher 线程） |
| 终端渲染（前端） | [xterm.js 5.3](https://xtermjs.org/) |
| 异步 I/O | Python asyncio + threading（PTY 读取） |
| AI 调用 | 自实现 urllib 调用（无第三方 SDK 依赖） |

---

### 🔬 实时终端技术原理深度解析

> **这个终端是"真"终端，不是数据流模拟。** 本节详细解释其工作原理，以及与视频流的本质区别。

---

#### 一、PTY（伪终端）：连接浏览器与 Shell 的内核级桥梁

##### 什么是 PTY？

PTY（Pseudo-Terminal，伪终端）是操作系统内核提供的一对文件描述符：

```
master_fd ←→ slave_fd
   ↑                ↑
Python 进程      Shell 进程
(TerminalHub)   (zsh / bash)
```

- **slave_fd**：Shell 认为这是一个真实的物理终端设备（如 `/dev/tty`），它通过这个 fd 读取用户输入、写入输出
- **master_fd**：TerminalHub 持有的控制端，所有写入 slave 的数据都从 master 读出，反之亦然
- 内核的 PTY 驱动负责双向数据中继，并处理 termios（终端行规、回显、信号发送等）

Shell 进程**无法感知**自己连接的是 PTY 还是真实终端。这意味着：
- readline 行编辑（上下键翻历史、Tab 补全）完全正常
- `vim`、`htop`、`man`、`python` REPL、`copilot` TUI 等交互程序全部正常
- ANSI 颜色码、光标移动、清屏等控制序列原样传递

##### 创建过程（macOS / Linux）

```python
import pty, subprocess

master_fd, slave_fd = pty.openpty()   # 内核分配 PTY 对

proc = subprocess.Popen(
    ["/bin/zsh"],
    stdin=slave_fd,
    stdout=slave_fd,
    stderr=slave_fd,
    start_new_session=True,           # 成为新进程组的 leader，接管 SIGHUP 等信号
    close_fds=True,
)
os.close(slave_fd)                    # 父进程只持有 master_fd
```

---

#### 二、完整 I/O 数据流路径

```
【用户在浏览器按键】
        ↓
  xterm.js (前端)
  捕获 keydown 事件，将字符/控制序列编码为字符串
        ↓
  WebSocket.send(JSON.stringify({type:"input", data:"ls\r"}))
        ↓  （本地回环网络，延迟 <1ms）
  FastAPI WebSocket Handler (main.py)
  receive_text() → 解析 JSON → session.write_input(data)
        ↓
  os.write(master_fd, data.encode())
  直接写入 PTY 内核缓冲区，非阻塞，无线程池开销
        ↓
  【PTY 内核驱动】
  将数据传递给 slave_fd 端（Shell 的 stdin）
        ↓
  Shell (zsh) 读取输入，处理命令
        ↓
  Shell 输出结果（带 ANSI 转义码）写入 slave_fd
        ↓
  【PTY 内核驱动】
  数据从 slave_fd 路由到 master_fd
        ↓
  PTY 读取线程（独立后台线程）
  select.select(master_fd, timeout=5ms)
  os.read(master_fd, 65536)  ← 64KB 缓冲，减少系统调用次数
        ↓
  loop.call_soon_threadsafe(queue.put_nowait, payload)
  线程安全地将数据投递到 asyncio 事件循环，O(1) 操作
        ↓
  asyncio.PriorityQueue（优先级队列）
  pong 消息 priority=0 排在所有输出之前
  终端输出 priority=1
        ↓
  output_consumer 协程（贪心批处理）
  一次性取出队列中所有待发送的 output 块，合并为单个 WS 帧
        ↓
  websocket.send_json({"type":"output","data":"..."})
        ↓  （本地回环，延迟 <1ms）
  浏览器接收 WebSocket 消息
        ↓
  xterm.js.write(data)
  VT100 状态机解析 ANSI 转义码，更新终端内部缓冲区并重绘 Canvas
        ↓
【用户看到输出】
```

**输入到输出的总延迟（localhost）：< 5ms**

---

#### 三、这是"真终端"还是"视频流"？

| 对比维度 | 视频实时流（如视频会议） | TerminalHub 终端流 |
|----------|--------------------------|---------------------|
| **传输内容** | 像素帧（JPEG/H.264 编码） | ANSI 转义码字节序列 |
| **典型帧大小** | 数十 KB ~ 数 MB / 帧 | 几字节 ~ 几 KB / 帧 |
| **延迟来源** | 编码 + 网络传输 + 解码 | 仅网络传输（微秒级） |
| **终端感知** | 用户看的是视频画面 | Shell 认为自己连的是真实终端 |
| **交互性** | 单向流（用户不能"操控"视频） | 真正双向 I/O（输入影响输出） |
| **控制序列** | 无 | 完整 VT100/xterm 支持 |
| **状态** | 服务端无状态，每帧独立 | 有状态：终端行规、Shell 历史、当前目录 |

**结论：TerminalHub 是真终端**。ANSI 字节流不是"看起来像终端的视频"，而是 VT100 协议本身——xterm.js 实现了完整的 VT100 状态机，其行为与 macOS 的 Terminal.app 完全等价。

---

#### 四、实时性如何保证？五层优化机制

##### 1. 长连接 WebSocket，零轮询
- HTTP 轮询每次请求有 TCP 握手开销，且有固定间隔（如 500ms）
- WebSocket 建立一次后保持持久连接，数据到达即发送，无等待周期

##### 2. PTY 读取线程 + 5ms select 超时
```python
READ_BUF = 65536          # 64KB，大缓冲减少系统调用次数（burst 场景收益显著）
SELECT_TIMEOUT = 0.005    # 5ms，数据到达后最多等待 5ms 即被读取
```

##### 3. uvloop — 替换 Python 原生事件循环
```python
import uvloop
uvloop.install()  # 必须在 import uvicorn 之前调用
```
uvloop 用 Cython 实现，底层调用 libuv（Node.js 的事件循环库），比纯 Python asyncio 快 **2-4 倍**，对高频率小消息场景（终端输出）效果尤为明显。

##### 4. asyncio.PriorityQueue — 精确控制消息优先级
```
旧方案（asyncio.Queue）：
  [output₁][output₂]...[outputₙ][PONG]   ← pong 等待所有输出发完
  测量延迟 = 真实 RTT + 队列积压时间 = 317ms ❌

新方案（asyncio.PriorityQueue）：
  priority=0: [PONG]                       ← 立即出队
  priority=1: [output₁][output₂]...[outputₙ]
  测量延迟 = 真实 RTT ≈ 1-5ms ✅
```

##### 5. 贪心输出批处理 — 减少 WebSocket 帧开销
```python
async def output_consumer():
    _, _, payload = await pq.get()       # 等待第一块数据
    if payload["type"] == "output":
        data = payload["data"]
        while True:
            try:
                _, _, nxt = pq.get_nowait()  # 立即取出后续积压的块
                data += nxt["data"]          # 合并
            except asyncio.QueueEmpty:
                break
        await ws.send_json({"type": "output", "data": data})  # 一次发送
```
TUI 应用（如 Copilot CLI）刷新界面时会产生大量小输出块，批处理将它们合并为单个 WS 帧，大幅降低帧数量和 JavaScript 处理开销。

---

#### 五、多客户端并发观察

同一个终端可以被多个浏览器标签同时连接观察：

```python
# terminal_manager.py
class TerminalSession:
    _callbacks: list[Callable]    # 每个 WebSocket 连接注册一个回调
    _lock: threading.Lock

    def broadcast(self, payload):
        with self._lock:
            for cb in self._callbacks:
                cb(payload)       # 同时推送给所有连接的客户端
```

PTY 读取线程读到数据后，调用所有已注册的回调，每个回调对应一个 WebSocket 连接的 `enqueue` 函数，数据被分别放入各自的优先级队列。

---

#### 六、终端大小同步

浏览器窗口大小变化时，`ResizeObserver` 触发 `FitAddon.fit()` 重新计算行列数，并发送：
```json
{ "type": "resize", "rows": 45, "cols": 183 }
```
服务端通过 `ioctl` 系统调用同步给 PTY：
```python
import fcntl, termios, struct
fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
            struct.pack('HHHH', rows, cols, 0, 0))
```
PTY 驱动随后发送 `SIGWINCH` 信号给 Shell，Shell 重新查询终端大小并调整输出格式（如 `vim` 重新绘制、`ls` 调整列宽）。

---

## English

<a name="english"></a>

### Overview

**TerminalHub** is a high-performance, locally-hosted **Web Terminal Management Platform** built with Python. It gives you a single browser tab to manage all running terminal sessions — live I/O, resource metrics, AI detection, code-change diffs, and exportable reports.

**It solves:**
- Terminal sprawl — dozens of windows scattered across your desktop
- Inability to see resource usage across terminals at a glance
- AI coding agents (Copilot, Claude, Aider, etc.) silently editing files with no before/after record
- No audit trail for "what did this terminal session actually do?"
- No easy way to share session logs, diffs, and AI analysis with teammates

---

### Key Features

#### 🖥️ Terminal Management
- Create, interact with, and kill any number of terminals from the browser
- **Full PTY emulation** — ANSI colors, cursor control, readline, interactive programs all work correctly
- **xterm.js** rendering with font scaling, scroll, and copy-on-select
- Per-terminal config on creation: shell type, working directory, title, task description, watch path
- **Collapsible info panel** at the top of each terminal card
- **Live connection status indicator** (green = connected, red = disconnected)
- **Drag-and-drop files / folders** onto the terminal — the full filesystem path is inserted as typed text (prevents browser default "open in new tab" behavior; paths with spaces are auto-quoted; multiple files supported; resolved to absolute path via `POST /api/terminals/{id}/resolve-path`, which follows the shell's live `cwd`)

#### 📊 Real-time System Monitoring
- Dashboard header: system-wide CPU %, memory usage, active terminal count, detected-AI count
- Per-terminal (in expanded header): CPU %, memory (MB / %), thread count, process status, PID
- All data auto-refreshes every **2 seconds** via WebSocket push — no HTTP polling
- **Live WebSocket RTT latency** indicator per terminal, colour-coded: 🟢 ≤20ms / 🟡 ≤80ms / 🔴 >80ms

#### 🤖 AI Model Auto-detection
Detects when a terminal is running an AI agent and shows a badge with provider + model info.

Detection uses cmdline keywords + environment variables + network connection fingerprinting:

| Tool | Provider |
|------|----------|
| GitHub Copilot | GitHub |
| Claude CLI / API | Anthropic |
| Ollama | Meta / Open Source |
| OpenAI API | OpenAI |
| DeepSeek | DeepSeek |
| Aider | Open Source |
| Cursor AI | Cursor |
| Qwen / QwQ | Alibaba |

#### 📂 Code Change Monitoring
- Specify a **watch path** per terminal to track all file changes in that directory
- 25+ file extensions monitored (`.py` `.js` `.ts` `.swift` `.go` `.rs` `.java` `.kt` and more)
- On each modification:
  1. Fetches "before" content from Git (`git show HEAD:<path>`) or memory cache
  2. Reads "after" content from disk
  3. Generates unified diff with `difflib`, converts to colored HTML
  4. Appends record to `tmp/code_changes_<id>.json` via a background thread with `threading.Lock`
- Ignores `.git`, `node_modules`, `__pycache__`

#### 📋 Session Log Export
- Click **"Export Report"** on any terminal card to generate a full self-contained HTML report
- Report includes: session summary, **Git context** (branch / commit / author / message), full log (ANSI stripped), all code changes (side-by-side diffs), optional AI summary
- Fully self-contained — CSS and JS are inlined; sharable and viewable offline
- **Report persisted to disk** at `tmp/reports/report_<id>_<ts>.html`, served at `/reports/<filename>`; response headers carry `X-Report-URL` and `X-Report-Path`
- **Progress toast** at the bottom-center during export — animated step list + progress bar + auto-dismiss; buttons grey out to prevent double-clicks

#### 🔬 In-Report AI Analysis
The exported HTML report has its own AI interaction layer:
- **AI config bar** at the top: set Provider / Model / API Key, test connection in-place
- **"Ask AI to Analyze"** button per code diff — sends before/after to your LLM and shows:
  - Purpose and reasoning of the change
  - Code quality assessment
  - Potential risks
- Three action buttons per diff: **Accept** ✅ / **Flag Risk** ⚠️ / **Request Better Solution** 🔄
  - **Accept** and **Flag Risk** also write the corresponding file content back to disk via `POST /api/report/apply-change` (uses a per-report sidecar JSON saved alongside the report)
- Language and theme toggles work independently inside the report

#### 📧 Email Reports
- Send any report to any email address directly from the UI
- Supports Gmail (STARTTLS:587), Outlook, custom SMTP (SSL:465 / STARTTLS:587)
- HTML report attached as a file for offline viewing

#### 🧠 AI Provider Panel
Right-side slide-out panel for configuring the active AI provider:

| Provider | Auth Method |
|----------|-------------|
| GitHub Copilot | Auto-resolved from gh CLI / keychain / apps.json / env vars |
| OpenAI | API Key |
| Anthropic Claude | API Key |
| DeepSeek | API Key |
| Qwen | API Key (DashScope) |
| Ollama | No key — local `http://localhost:11434` |
| Custom | API Key + custom Base URL |

Model list loads automatically; "Test Connection" validates credentials immediately.

#### 🌐 i18n & Themes
- **Chinese / English** toggle — all UI text switches instantly
- **Light / Dark** theme toggle — preference persisted in `localStorage`
- Exported reports support independent language and theme switching

---

### Project Structure

```
TerminalHub/
├── main.py                     ← Application entry point (FastAPI + uvicorn)
├── config.ini                  ← Runtime configuration
├── requirements.txt            ← Python dependency list
├── start.sh                    ← One-command startup script
│
├── modules/                    ← Backend modules (low-coupling, single-responsibility)
│   ├── __init__.py             ← Unified export
│   ├── terminal_manager.py     ← PTY terminal lifecycle management
│   ├── system_monitor.py       ← Process and system resource monitoring
│   ├── ai_detector.py          ← AI framework / model auto-detection
│   ├── code_watcher.py         ← File system monitoring + diff generation
│   ├── report_generator.py     ← Self-contained HTML report renderer
│   ├── email_sender.py         ← SMTP email delivery
│   ├── ai_provider.py          ← Multi-provider LLM call layer
│   └── context_store.py        ← Session context persistence (survives restarts)
│
├── static/                     ← Frontend assets
│   ├── index.html              ← Main UI
│   ├── css/styles.css          ← Light/dark theme via CSS custom properties
│   └── js/
│       ├── app.js              ← App bootstrap + monitor WebSocket
│       ├── terminal.js         ← xterm.js TerminalWidget class
│       ├── ai_panel.js         ← AI provider config slide-out panel
│       ├── report.js           ← Report export / email / diff modal
│       └── i18n.js             ← Translation table (zh / en)
│
└── tmp/                        ← Runtime temp dir (auto-created on startup)
    ├── reports/                ← Generated HTML reports + change sidecar JSON
    │   ├── report_<id>_<ts>.html
    │   └── sidecar_<id>_<ts>.json
    └── contexts/               ← Session context snapshots (survive restarts)
        └── <terminal_id>.json
```

---

### Module Reference

#### `main.py` — Application Entry

FastAPI application with asyncio lifespan management. Serves all REST and WebSocket endpoints, mounts `/static` and `/reports`, manages the monitor broadcast loop, and coordinates all service modules.

Key design points:
- Blocking operations (PTY I/O, AI calls, psutil) are dispatched to a thread pool via `asyncio.run_in_executor`
- The monitor broadcast loop runs as a background asyncio task, not a thread
- All module instances are singletons shared across requests
- On shutdown, all live sessions are flushed to `ContextStore` before termination

**REST API routes:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Main UI HTML |
| `GET` | `/api/terminals` | List all terminals (with live stats) |
| `POST` | `/api/terminals` | Create a new terminal |
| `DELETE` | `/api/terminals/{id}` | Kill and remove a terminal |
| `PATCH` | `/api/terminals/{id}` | Update terminal title / description |
| `GET` | `/api/terminals/{id}/log` | Full log buffer |
| `POST` | `/api/terminals/{id}/resolve-path` | Resolve a dropped filename to its absolute path |
| `GET` | `/api/code-changes/{id}` | Code changes for a terminal |
| `GET` | `/api/contexts` | List all persisted session contexts |
| `GET` | `/api/contexts/{id}` | Get persisted context for a terminal |
| `DELETE` | `/api/contexts/{id}` | Delete a persisted context |
| `POST` | `/api/report/generate` | Generate HTML report (also saved to `tmp/reports/`) |
| `POST` | `/api/report/apply-change` | Write accepted / reverted file content back to disk |
| `POST` | `/api/email/send` | Send report via SMTP |
| `GET` | `/api/git/info` | Git metadata for a directory (branch, commit, author…) |
| `GET` | `/api/git/file-diff` | HEAD~1 vs working-tree diff for a specific file |
| `GET` | `/api/ai/providers` | List supported AI providers |
| `GET` | `/api/ai/models` | Models for a given provider |
| `POST` | `/api/ai/test` | Test provider credentials |
| `POST` | `/api/ai/chat` | Start async AI chat job (returns `job_id`) |
| `GET` | `/api/ai/job/{job_id}` | Poll async job status |

#### `modules/terminal_manager.py` — PTY Terminal Management

`TerminalSession` wraps a single shell process with full PTY support.

**Unix/macOS:** `pty.openpty()` → `subprocess.Popen` with slave fd as stdio → background reader thread with `select.select` + `os.read(master_fd, 8192)`.

**Windows:** tries `winpty.PtyProcess.spawn()`, falls back to `subprocess.Popen` with pipes.

**Key behaviors:**
- Reader thread decodes raw bytes as UTF-8 (errors='replace') and fans out to all registered WebSocket callbacks
- Callbacks are registered/deregistered safely under a `threading.Lock`
- `collections.deque(maxlen=5000)` rolling log buffer; 200-line tail sent to new WebSocket clients on connect
- Terminal resize: `fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))`

#### `modules/system_monitor.py` — System Monitoring

psutil-based with a 2-second TTL cache per PID and for system-wide stats.

- Caches `psutil.Process` objects to avoid repeated OS process table lookups
- `cpu_percent(interval=None)` is non-blocking (returns delta since last call)
- Handles `NoSuchProcess` / `AccessDenied` gracefully, evicts dead PIDs from cache

#### `modules/ai_detector.py` — AI Detection

Inspects a process and all its children using three signal sources:

| Signal | Weight |
|--------|--------|
| Cmdline keyword match | +0.60 |
| API key env var present | +0.25 |
| Ollama: connection to port 11434 | +0.20 |
| HTTPS connection (port 443) | +0.05 |

Takes the highest-confidence candidate. Extracts model name via regex from cmdline/env vars.

#### `modules/code_watcher.py` — Code Change Monitoring

**On-demand via `git diff HEAD`** — no background file-system watcher threads. Changes are computed only when explicitly requested (typically at report-export time), eliminating FSEvents errors and idle resource usage.

**Workflow (when `get_changes()` is called):**
1. Locate git repos under the watch path (walks up to 2 sub-directory levels)
2. Run `git diff HEAD --name-status` for tracked changes (modified / added / deleted)
3. Run `git status --porcelain` to include untracked new files (`??` lines)
4. For each changed file: `git show HEAD:<path>` → before content; disk read → after content
5. Generate unified diff via `difflib`, then convert to highlighted HTML
6. Falls back to filesystem scan (files with mtime < 1 hour) when no git repo exists

**Fast badge count (`count_changes()`):** runs only `git diff HEAD --name-only` (no file reads), cached for 120 s.

**Thread safety:** all shared state (`_watch_paths`, `_cache`, `_count_cache`) is protected by `threading.Lock`.

#### `modules/report_generator.py` — HTML Report Generator

Pure-Python string templating, zero external dependencies. All CSS and JavaScript is inlined into the output file.

The report structure:
1. **AI config bar** — Provider, Model, API Key, connection status, "Test" button
2. **Session summary card** — title, shell, cwd, created time, duration, changed-file count, line add/remove stats
3. **Git context block** (when available) — branch, latest commit SHA (`commit` + `prev_commit`), message, author, relative date
4. **AI analysis summary** (optional) — pre-generated by the backend LLM and embedded in the report body
5. **Terminal log** — full log with ANSI stripped, monospace font
6. **Code change cards** — one per changed file: before/after side-by-side, unified diff, action buttons, AI response area
7. **Footer** — generation timestamp, TerminalHub version

The report's embedded JS:
- Reads AI config from `localStorage`
- Makes `fetch()` calls to the configured provider's chat endpoint
- Renders AI responses into dedicated `<div>` containers per diff
- Persists accept/reject decisions in `localStorage` keyed by `{terminal_id}:{change_index}`
- **Accept / Flag Risk** calls `POST /api/report/apply-change` with the `sidecar_id` (a per-report JSON file saved at report-generation time) to write file content back to disk

#### `modules/email_sender.py` — SMTP Email Sender

Sends a multipart email with:
- Plain text fallback body
- HTML inline body
- HTML file attachment (`terminalhub_report.html`)

Auto-selects SMTP_SSL (port 465) vs STARTTLS (port 587) based on the configured port.

#### `modules/context_store.py` — Session Context Persistence

Saves a lightweight snapshot of each terminal session to `tmp/contexts/{terminal_id}.json`, allowing session history to survive service restarts.

**Snapshot contents:** id, title, description, shell, cwd, created_at, watch_path, last AI detection result, last 500 log lines (ANSI-stripped), code change count, saved_at timestamp.

**Mechanics:**
- Background thread flushes dirty sessions every **30 s**; all live sessions are flushed synchronously on shutdown
- Writes use an atomic rename (`.tmp` → `.json`) to prevent corruption on crash
- Public API: `mark_dirty(tid)` / `flush(tid, session)` / `load(tid)` / `list_contexts()` / `delete(tid)`
- Exposed via `/api/contexts` routes for session history browsing

#### `modules/ai_provider.py` — LLM Call Layer

Ported directly from the **GitAutoManageBoard** project. Provides a unified interface over all supported providers using only Python's standard library (`urllib`).

```python
# Synchronous call
ok, text = call_llm(provider, api_key, base_url, model, messages)

# Async (non-blocking) call via thread pool
job_id = start_chat_job(provider, api_key, base_url, model, messages)
status = get_job_status(job_id)  # {"done": bool, "ok": bool, "text": str, "error": str}
```

Copilot token resolution order: `COPILOT_GITHUB_TOKEN` env → `GH_TOKEN` env → macOS Keychain (service: `copilot-cli`) → `gh auth token` CLI → `~/.config/github-copilot/apps.json`.

---

### Quick Start

#### Prerequisites

- Python 3.10+
- macOS / Linux / Windows
- Git (optional, for before-content in code diffs)

#### Installation

```bash
cd /path/to/TerminalHub

# Option A: one-liner (installs deps automatically)
bash start.sh

# Option B: manual
pip install -r requirements.txt
python main.py
```

Open **http://localhost:8765** in your browser.

---

### Configuration

Edit `config.ini`:

```ini
[app]
name                  = TerminalHub
version               = v1.0.0
port                  = 8765
host                  = 0.0.0.0
default_shell_unix    = /bin/zsh
default_shell_windows = cmd.exe
default_lang          = zh          # zh | en
default_theme         = light       # light | dark

[monitoring]
stats_interval        = 2           # seconds between stat refreshes
log_max_lines         = 5000        # rolling log buffer size per terminal
code_changes_file     = tmp/code_changes_{terminal_id}.json

[email]
smtp_host             = smtp.gmail.com
smtp_port             = 587
smtp_user             =             # leave blank to fill at send time
smtp_pass             =
```

---

### WebSocket Protocol

#### `/ws/terminal/{id}`

**Client → Server:**
```json
{ "type": "input",  "data": "ls -la\r" }
{ "type": "resize", "rows": 40, "cols": 120 }
{ "type": "ping",   "t": 1715673600123.45 }
```

**Server → Client:**
```json
{ "type": "output",  "data": "..." }
{ "type": "status",  "connected": true }
{ "type": "stats",   "cpu": 1.2, "mem_mb": 42.5, "mem_pct": 0.5, "status": "sleeping", "threads": 3 }
{ "type": "ai_info", "detected": true, "provider": "GitHub", "framework": "GitHub Copilot", "model": "gpt-4o", "confidence": 0.85 }
{ "type": "pong",    "t": 1715673600123.45 }
```

> **Latency probe:** Browser sends `ping` with `performance.now()` timestamp every 3 s. Server enqueues `pong` at priority 0, bypassing all queued terminal output. Browser measures `now - payload.t` on receipt to get true WebSocket RTT.

#### `/ws/monitor`

Broadcast every 2 seconds:
```json
{
  "type": "monitor",
  "system": { "cpu_pct": 18.3, "mem_total_gb": 16.0, "mem_used_gb": 9.4, "mem_pct": 58.7 },
  "terminals": [{ "id": "...", "title": "...", "alive": true, "stats": {} }],
  "code_changes": { "<terminal_id>": 3 }
}
```

---

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| ASGI Server | [uvicorn](https://www.uvicorn.org/) (with WebSocket) |
| Event Loop | [uvloop](https://github.com/MagicStack/uvloop) (Unix; 2-4× faster than stdlib asyncio) |
| PTY Emulation | `pty` (Unix) / `pywinpty` (Windows) |
| Process Monitoring | [psutil](https://github.com/giampaolo/psutil) |
| Code Change Detection | `git diff HEAD` on-demand subprocess (no background watcher thread) |
| Terminal Rendering | [xterm.js 5.3](https://xtermjs.org/) |
| Async I/O | Python asyncio + threading |
| AI Calls | Stdlib `urllib` only (no SDK dependencies) |

---

### 🔬 How Real-Time Terminals Work — Technical Deep Dive

> **TerminalHub uses a real terminal, not a video stream or screen capture.** Here's exactly what that means and how it achieves low latency.

---

#### 1. PTY — The Kernel Bridge Between Browser and Shell

A **PTY (Pseudo-Terminal)** is a kernel-provided pair of file descriptors:

```
master_fd  ←→  slave_fd
    ↑                ↑
 Python           Shell process
(TerminalHub)    (zsh / bash)
```

- **slave_fd**: the shell connects here and behaves exactly as if it were talking to a real physical terminal (`/dev/tty`)
- **master_fd**: TerminalHub holds this end — data written to slave appears on master and vice versa
- The kernel's PTY driver handles bidirectional relay plus `termios` line discipline (echo, signal generation, line buffering)

The shell **cannot distinguish a PTY from a real terminal**. That means:
- `readline` history, Tab completion, arrow key navigation — all work
- `vim`, `htop`, `man`, interactive Python REPL, `copilot` TUI — all work natively
- ANSI color codes, cursor movement, clear-screen — all pass through unchanged

#### 2. Full I/O Data Flow

```
[User keypress in browser]
        ↓
  xterm.js captures keydown → encodes to VT100 sequence
        ↓
  WebSocket.send({type:"input", data:"ls\r"})
        ↓  (loopback, <1ms)
  FastAPI receive_text() → os.write(master_fd, data)
        ↓  (kernel PTY driver)
  Shell stdin receives input, executes command
        ↓
  Shell writes ANSI output to slave_fd
        ↓  (kernel PTY driver)
  Data routed to master_fd
        ↓
  PTY reader thread: select(5ms) + os.read(master_fd, 64KB)
        ↓
  loop.call_soon_threadsafe(queue.put_nowait, payload)  — O(1)
        ↓
  asyncio.PriorityQueue
  (pong priority=0, output priority=1)
        ↓
  output_consumer coroutine (greedy batch drain)
        ↓
  websocket.send_json({type:"output", data:"..."})
        ↓  (loopback, <1ms)
  xterm.js.write(data) → VT100 state machine → Canvas repaint
        ↓
[User sees output]

Total round-trip on localhost: < 5ms
```

#### 3. Real Terminal vs. Video Stream — Key Differences

| Dimension | Video Stream (e.g., screen share) | TerminalHub |
|-----------|-----------------------------------|-------------|
| **What's transmitted** | Pixel frames (JPEG/H.264) | ANSI escape byte sequences |
| **Typical frame size** | Tens of KB to MB per frame | A few bytes to a few KB |
| **Latency sources** | Encode + transmit + decode | Network only (microseconds) |
| **Shell awareness** | Shell doesn't know it's being watched | Shell thinks it's on a real terminal |
| **Interactivity** | One-way (you watch a video) | True bidirectional I/O |
| **Control sequences** | N/A | Full VT100/xterm support |
| **State** | Stateless frames | Stateful: line discipline, shell history, cwd |

**Bottom line:** TerminalHub is a real terminal. xterm.js implements a complete VT100 state machine identical to macOS Terminal.app. The shell cannot tell the difference.

#### 4. How Real-Time is Guaranteed — Five Optimization Layers

**Layer 1 — Persistent WebSocket, zero polling**
HTTP polling has TCP overhead and a fixed interval (e.g. 500ms). WebSocket keeps one persistent connection; data is sent the moment it arrives.

**Layer 2 — 5ms PTY read loop**
```python
READ_BUF     = 65536   # 64KB buffer — reduces syscalls for burst output
SELECT_TIMEOUT = 0.005 # 5ms — data is picked up within 5ms of arriving
```

**Layer 3 — uvloop replaces Python's asyncio**
```python
import uvloop
uvloop.install()   # must be called before importing uvicorn
```
uvloop is implemented in Cython, wrapping libuv (the same engine as Node.js). It is **2-4× faster** than stdlib asyncio for high-frequency small-message workloads — exactly what a terminal produces.

**Layer 4 — PriorityQueue fixes latency measurement**
```
Old (asyncio.Queue — FIFO):
  [output₁][output₂]...[outputₙ][PONG]
  measured latency = true RTT + queue drain time = 317ms ❌

New (asyncio.PriorityQueue):
  priority=0: [PONG]                   ← dequeued immediately
  priority=1: [output₁]...[outputₙ]
  measured latency = true RTT ≈ 1-5ms ✅
```

**Layer 5 — Greedy output batching**
```python
# Instead of one WebSocket frame per PTY read:
data = first_chunk["data"]
while True:
    nxt = pq.get_nowait()          # drain immediately-available chunks
    data += nxt["data"]            # merge into one frame
await ws.send_json({"type":"output","data": data})
```
TUI apps (like Copilot CLI) repaint their UI constantly, generating dozens of small PTY reads per second. Batching merges them into single WebSocket frames, cutting frame count and JavaScript parse overhead significantly.

#### 5. Terminal Resize Synchronization

When the browser window resizes, `ResizeObserver` fires → `FitAddon.fit()` recalculates rows/cols → sends:
```json
{ "type": "resize", "rows": 45, "cols": 183 }
```
Server calls:
```python
fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
            struct.pack('HHHH', rows, cols, 0, 0))
```
The PTY driver sends `SIGWINCH` to the shell. The shell re-queries its terminal size and adjusts output (vim redraws, `ls` adjusts column widths, etc.).

---

### License

MIT
