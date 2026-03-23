[English](README.md)

# Claw Agent Dashboard

用于管理 [OpenClaw](https://github.com/openclaw/openclaw) AI 智能体的 Web 仪表盘。监控系统健康状态、浏览智能体工作区、管理会话、编辑蓝图、与智能体交互 — 一个界面搞定一切。

<!-- ![截图](docs/screenshot.png) -->

## 这是什么？

[OpenClaw](https://github.com/openclaw/openclaw) 是一个跨多种消息通道（Signal、Telegram、Nextcloud Talk 等）运行 AI 智能体的平台。每个智能体都有一个**工作区** — 一组定义其行为的配置文件（人设、工具、记忆、技能）。

**Claw Agent Dashboard** 提供一个集中式 Web 界面，让你能够：

- **查看智能体在做什么** — 实时会话历史、消息流、模型使用情况
- **编辑智能体行为** — 修改蓝图、同步变更到工作区、应用前审查 diff
- **监控系统状态** — CPU、内存、磁盘、网关健康，全部实时展示
- **全局搜索** — 跨文件和会话记录全文搜索
- **与智能体对话** — 直接从会话详情页发送消息

专为需要可视化管理而无需 SSH 登录服务器的 OpenClaw 运维人员设计。

## 核心功能

### 🤖 智能体管理
- **工作区文件浏览器** — 浏览所有智能体工作区文件（`SOUL.md`、`AGENTS.md`、`TOOLS.md`、技能、记忆等），支持语法高亮和浏览器内编辑
- **蓝图编辑器** — 查看、比较、同步蓝图到工作区的变更，内联 diff 审查。蓝图是模板，工作区是实际配置 — 仪表盘精确展示两者差异
- **全局技能浏览器** — 浏览全局安装的 OpenClaw 技能及其配置

### 💬 会话监控与交互
- **会话查看器** — 每个智能体会话的分页消息历史，显示提供商、模型、时间戳、工具调用和思考过程
- **会话编写器** — 直接从会话详情页发送消息，支持两种模式：
  - **原生模式** — 直接发送纯文本给智能体
  - **信封模式** — 用 OpenClaw 兼容的上下文头（通道、发送者、时间戳）包装消息，模拟通道输入
- **对话视图** — 在详细视图（完整输出，含工具调用）和对话视图（仅显示用户消息和智能体回复的简洁对话）之间切换
- **模型切换** — 为任意运行中的会话切换活跃模型

### 🔍 搜索
- **文件搜索** — 跨所有智能体工作区文件全文搜索，支持跳转和关键词高亮
- **会话搜索** — 跨智能体会话记录搜索（需配置 Elasticsearch），命中高亮

### 📊 系统监控
- **仪表盘** — 实时系统指标：CPU、内存、磁盘、网络使用情况
- **网关健康监控** — 监控 OpenClaw Gateway 状态、连接性和运行时间
- **变更检测器** — 后台文件监视器，检测工作区变更并通知

### 📝 其他功能
- **文件翻译** — 使用可配置的 LLM 服务（OpenAI 兼容 API）将任意工作区文件翻译为中文
- **文件版本历史** — 跟踪文件变更，内联 diff 比较，一键还原到历史版本
- **移动端响应式** — 完整的手机和平板适配 — 随时随地管理你的智能体
- **双语界面** — 完整的中英文界面支持

## 快速开始

### 前置条件

- [Docker](https://docs.docker.com/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/install/)
- 一个正在运行的 [OpenClaw](https://github.com/openclaw/openclaw) 实例

### 方式 A — Docker Hub（推荐）

```bash
# 1. 创建项目目录
mkdir claw-agent-dashboard && cd claw-agent-dashboard

# 2. 下载配置文件
curl -LO https://raw.githubusercontent.com/boydfd/claw-agent-dashboard/main/docker-compose.yml
curl -LO https://raw.githubusercontent.com/boydfd/claw-agent-dashboard/main/.env.example
cp .env.example .env

# 3. 编辑 .env — 至少设置 OPENCLAW_HOME 和 GATEWAY_TOKEN
#    （详见下方"配置说明"）

# 4. 启动
docker compose up -d
```

### 方式 B — 从源码构建

```bash
git clone https://github.com/boydfd/claw-agent-dashboard.git
cd claw-agent-dashboard
cp .env.example .env
# 编辑 .env
docker compose up -d --build
```

访问 [http://localhost:8080](http://localhost:8080) 即可。

## 配置说明

### 环境变量

| 变量 | 必填 | 描述 | 默认值 |
|------|------|------|--------|
| `OPENCLAW_HOME` | 是 | OpenClaw 主目录路径（`~/.openclaw`） | `~/.openclaw` |
| `DATA_HOST_DIR` | 是 | 可写数据目录（翻译文件、版本库、配置） | `./data` |
| `GATEWAY_URL` | 否 | OpenClaw Gateway URL | `http://host.docker.internal:18789` |
| `GATEWAY_TOKEN` | 是 | Gateway 认证令牌（获取方式见下方） | — |
| `ALLOWED_ORIGINS` | 否 | CORS 允许的源（逗号分隔） | `*` |
| `OPENCLAW_SKILLS_DIR` | 否 | 全局技能目录路径 | — |
| `OPENCLAW_LOGS_DIR` | 否 | OpenClaw 日志目录路径 | — |
| `OPENCLAW_AGENTS_DIR` | 否 | 自定义智能体目录（覆盖 `OPENCLAW_HOME/agents`） | — |

### 获取 `GATEWAY_TOKEN`

仪表盘通过此令牌与 OpenClaw Gateway 认证，用于读取会话、切换模型和发送消息。在 OpenClaw 配置中查找：

```bash
cat ~/.openclaw/openclaw.json | python3 -c "import sys,json; print(json.load(sys.stdin)['gateway']['auth']['token'])"
```

或在 `~/.openclaw/openclaw.json` 中查找 `gateway.auth.token`：

```jsonc
{
  "gateway": {
    "auth": {
      "mode": "token",
      "token": "your-token-here"   // ← 复制这个值
    }
  }
}
```

> **注意：** 如果 `gateway.auth.mode` 未设为 `"token"`，Gateway 可能不需要认证，此时可将 `GATEWAY_TOKEN` 留空。

### 构建参数（代理 / 镜像源环境）

| 构建参数 | 描述 | 默认值 |
|----------|------|--------|
| `NPM_REGISTRY` | npm 镜像源 | `https://registry.npmjs.org` |
| `PIP_INDEX_URL` | pip 索引 URL | `https://pypi.org/simple` |

```bash
docker compose build \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

## 架构概述

```
┌─────────────────────────────────────────────┐
│              Docker 容器                     │
│                                             │
│  ┌─────────────┐   ┌────────────────────┐  │
│  │  Vue 3 SPA  │──▶│  FastAPI (:8080)   │  │
│  │  (静态文件)  │   │                    │  │
│  └─────────────┘   │  REST APIs:        │  │
│                     │  • /api/agents     │  │
│                     │  • /api/status     │  │
│                     │  • /api/translate  │  │
│                     │  • /api/versions   │  │
│                     │  • /api/search     │  │
│                     │  • /api/blueprints │  │
│                     │  • /api/settings   │  │
│                     └───┬────────┬───────┘  │
│                         │        │          │
│                  ┌──────▼──┐ ┌───▼────┐     │
│                  │ /agents │ │ /data  │     │
│                  │ (读/写)  │ │ (读/写) │     │
│                  └─────────┘ └────────┘     │
└─────────────────────────────────────────────┘
         │                          │
    ~/.openclaw               ./data
  (智能体工作区、             (versions.db、
   蓝图、配置)               翻译文件)
```

- **前端**：Vue 3 + Element Plus + Pinia，Vite 构建，作为静态文件提供
- **后端**：FastAPI (Python) 提供 REST API，代理 OpenClaw Gateway 获取会话和智能体数据
- **存储**：绑定挂载宿主机目录 — `/agents` 对应 OpenClaw 主目录，`/data` 存储仪表盘专属数据（SQLite 版本库、翻译文件、配置）
- **进程管理**：supervisord 运行 FastAPI 服务和后台 worker（变更检测、文件版本追踪）

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3、Element Plus、Pinia、Vite、markdown-it、highlight.js、Monaco Editor |
| 后端 | Python 3.12、FastAPI、httpx、aiosqlite |
| 基础设施 | Docker、supervisord |
| 测试 | pytest（后端）、Playwright（E2E） |

## 参与贡献

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

Copyright 2026 Lin Ran.
