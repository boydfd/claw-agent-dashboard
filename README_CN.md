[English](README.md)

# claw-agent-dashboard

用于监控和管理 [OpenClaw](https://github.com/openclaw/openclaw) AI 智能体的 Web 仪表盘。

<!-- ![截图](docs/screenshot.png) -->

## 功能特性

- **智能体工作区文件浏览器** — 浏览智能体工作区文件，支持语法高亮和浏览器内编辑
- **会话查看器** — 查看智能体会话历史，支持分页消息展示，显示提供商/模型信息
- **蓝图管理** — 查看、比较和同步蓝图到工作区的变更，支持 diff 审查
- **全文搜索** — 文件内容搜索和 Elasticsearch 会话搜索，支持跳转和高亮
- **文件翻译** — 使用内置 LLM 翻译服务将任意文件翻译为中文
- **文件版本历史** — 重新设计的版本历史面板，内联 diff 比较，支持一键还原
- **变更检测器** — 后台磁盘同步，自动检测工作区文件变更
- **系统指标仪表盘** — 实时监控 CPU、内存、磁盘和网络使用情况
- **网关健康监控** — 跟踪 OpenClaw Gateway 状态和连接情况
- **全局技能浏览器** — 浏览全局安装的 OpenClaw 技能
- **双语界面** — 完整的中英文界面支持

## 快速开始

### 前置条件

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### 步骤

**方式 A — Docker Hub（推荐）**

```bash
# 1. 创建项目目录
mkdir claw-agent-dashboard && cd claw-agent-dashboard

# 2. 下载 docker-compose 和环境配置示例
curl -LO https://raw.githubusercontent.com/openclaw/claw-agent-dashboard/main/docker-compose.yml
curl -LO https://raw.githubusercontent.com/openclaw/claw-agent-dashboard/main/.env.example
cp .env.example .env
# 编辑 .env 文件，填入你的配置（参见下方"配置说明"）

# 3. 启动服务（从 Docker Hub 拉取镜像）
docker compose up -d
```

**方式 B — 从源码构建**

```bash
# 1. 克隆仓库
git clone https://github.com/openclaw/claw-agent-dashboard.git
cd claw-agent-dashboard

# 2. 复制并编辑环境配置文件
cp .env.example .env
# 编辑 .env 文件，填入你的配置（参见下方"配置说明"）

# 3. 构建并启动服务
docker compose up -d --build
```

访问仪表盘：[http://localhost:8080](http://localhost:8080)。

## 配置说明

| 变量 | 必填 | 描述 | 默认值 |
|------|------|------|--------|
| `OPENCLAW_HOME` | 是 | OpenClaw 主目录路径 | `~/.openclaw` |
| `DATA_HOST_DIR` | 是 | 可写数据目录路径（翻译文件、配置等） | `./data` |
| `GATEWAY_URL` | 否 | OpenClaw Gateway URL | `http://host.docker.internal:18789` |
| `GATEWAY_TOKEN` | 是 | Gateway 认证令牌 | — |
| `OPENCLAW_SKILLS_DIR` | 否 | 自定义全局技能目录 | — |
| `OPENCLAW_LOGS_DIR` | 否 | 自定义日志目录 | — |
| `OPENCLAW_AGENTS_DIR` | 否 | 自定义智能体目录 | — |

## 构建参数

如果你在代理环境下或需要使用镜像源，可以传递构建参数：

| 构建参数 | 描述 | 默认值 |
|----------|------|--------|
| `NPM_REGISTRY` | npm 镜像源 | `https://registry.npmjs.org` |
| `PIP_INDEX_URL` | pip 索引 URL | `https://pypi.org/simple` |

示例：

```bash
docker compose build \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

## 架构概述

前端是一个由 FastAPI 后端托管的 Vue 3 单页应用。后端提供 REST API，用于文件浏览、翻译、版本历史和系统指标查询，同时作为代理与 OpenClaw Gateway API 通信，获取智能体和会话数据。

## 参与贡献

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

Copyright 2026 Lin Ran.
