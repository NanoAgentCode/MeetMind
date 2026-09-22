# 会智录

基于 React、FastAPI 与 LangGraph 的 AI 会议纪要辅助系统。当前第一阶段已实现：

`上传录音 → 语音转写 → 生成纪要 → 人工修改 → 会议内容问答 → 导出 Word/Markdown`

现支持账号登录与 RBAC。首次启动前在 `backend/.env` 设置 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`；系统在用户表为空时创建首个系统管理员，已有账号会自动迁移到内置角色。登录会话使用 HttpOnly Cookie，有效期 7 天。

侧边栏“权限管理”可管理用户、角色权限和部门树：创建与停用账号、重置密码、分配角色和部门；创建自定义角色并勾选权限；新增、移动、排序和删除部门。内置系统管理员拥有全部权限，普通成员仅能处理自己的会议。会议数据可按本人、本部门及下级、全部三档授权；后端对模型配置、会议、问答和管理 API 逐项校验，权限变更无需重新登录。最后一名管理员、仍有关联成员/下级的部门及仍被使用的角色受到删除保护。当前没有自助注册或 SSO。

超过 `BACKGROUND_AUDIO_MB`（默认 20 MB）的录音上传后自动进入后台转写队列；转写完成或失败时，所属用户会收到站内铃铛通知。服务重启后会恢复排队或处理中任务。打开页面并允许浏览器通知权限后，还可收到 Windows 桌面提醒；未打开页面时仍可在下次登录后查看站内通知。外部 ASR 服务的单文件大小限制仍然适用，超限会以失败通知反馈。

## 技术栈

- 前端：React + TypeScript + Vite + Ant Design
- 后端：FastAPI + LangGraph + LangChain
- 模型协议：OpenAI、Claude、Ollama、vLLM
- 导出：python-docx
- 结构化数据：SQLite
- 文件存储：RustFS（S3 兼容对象存储，仅保存录音和导出文件）

后端配置在 `backend/app/config.py` 中按 `app`、`asr`、`llm`、各模型 Provider、`database` 和 `rustfs` 分组；环境变量名称保持扁平格式，兼容 `.env` 与容器部署。
RustFS 存储桶不存在时，后端会在首次读写对象前自动创建；权限错误等非“不存在”异常不会被忽略。
会议标题、处理状态、转写内容和结构化纪要存储在 SQLite，默认文件为 `backend/data/meetmind.db`。会议记录页面支持查看、搜索、状态筛选、继续处理和删除；桌面端侧边栏可通过顶部按钮收起或展开。

“模型服务”页面支持管理 OpenAI、Anthropic、Ollama 和 OpenAI-compatible 供应商，可从供应商实时获取模型列表并选择模型，分别配置默认的 LLM 纪要模型、单会议 RAG 问答模型和语音转文字模型。数据库中的启用默认模型优先于 `.env`；未配置时继续使用原有环境变量配置。宽屏下供应商与模型配置并排显示，窄屏下改为单列。

侧边栏“会议问答”提供独立的多轮对话工作区：不选择会议时使用默认 LLM 进行普通问答；在输入框键入 `@` 可搜索并关联一场会议，关联后使用默认会议 RAG 模型，并仅根据该会议的转写和纪要回答。
左侧对话历史按当前账号保存在 SQLite 中。首次成功回答后生成记录；点击历史记录可查看并继续对话，“新对话”会开始独立会话。各页面的主内容区域仅在内容超出可用高度时滚动，会议问答的历史列表和消息区域也按可用高度滚动。
会话请求估算达到模型上下文窗口的 80% 时，会把较早消息合并为摘要，并保留最近消息参与下一轮问答；历史列表仍保存完整原始消息。Ollama 和返回窗口元数据的 OpenAI-compatible 服务会自动读取窗口大小，其他模型使用 `CHAT_CONTEXT_WINDOW_TOKENS`（默认 256K，即 262144 token）作为回退值；请按实际模型调整。该阈值基于跨模型 token 估算，并非供应商精确计费 token 数。
会议记录列表的“去对话”按钮可直接打开会议问答并关联当前会议；“打开”使用标准按钮进入会议处理详情。

## 快速启动

### 1. 启动 RustFS

```powershell
docker compose up -d rustfs
```

- S3 API：`http://localhost:9000`
- 管理控制台：`http://localhost:9001`

示例配置仅供本地开发。部署前必须在环境变量及 `backend/.env` 中替换访问密钥。

### 2. 后端

项目使用 uv 管理 Python 环境和依赖。在项目根目录执行：

```powershell
uv sync
Copy-Item backend\.env.example backend\.env
# 编辑 backend/.env，至少配置 ADMIN_USERNAME 和 ADMIN_PASSWORD
uv run python backend\main.py
```

`backend/main.py` 是后端启动入口；`backend/app/main.py` 装配 FastAPI 应用、全局鉴权与会议流程。账号权限、模型和对话路由分别在 `backend/app/access_routes.py`、`backend/app/model_routes.py`、`backend/app/chat_routes.py`；对话提示词与历史摘要在 `backend/app/chat_service.py`。需要热更新时可使用 `uv run uvicorn backend.app.main:app --reload`。

代码按职责组织：后端访问控制请求模型和权限规则在 `backend/app/access.py`，供应商模型目录请求在 `backend/app/provider_catalog.py`；前端 `src` 根目录仅保留入口和环境声明。应用外壳在 `frontend/src/app/`，认证、通知、对话、会议、模型及权限页面在 `frontend/src/features/`，通用类型和样式在 `frontend/src/shared/`，请求客户端及统一导出入口在 `frontend/src/api/`。修改时请保持现有 API 路径与响应结构兼容。

本地验证可在项目根目录运行 `uv run python -m pytest backend -q`，在 `frontend` 目录运行 `npm run lint`、`npm test` 和 `npm run build`。

如果复制项目后出现 `VIRTUAL_ENV ... does not match`，请重启终端，或在 PowerShell 中执行：

```powershell
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
uv sync
```

IDE 的 Python 解释器应指向当前项目的 `.venv\Scripts\python.exe`，不要继续使用旧目录中的虚拟环境。

ASR、LLM 和 RAG 的供应商、模型及 API Key 均在前端「模型服务」中配置，并为对应类型设置默认模型。未配置默认 ASR 模型时，转写返回固定演示内容；未配置默认 LLM 模型时，纪要使用本地确定性提取。旧的 `ASR_*`、`LLM_*`、`OPENAI_*`、`ANTHROPIC_*`、`OLLAMA_*`、`VLLM_*` 环境变量不再读取。纪要输出统一校验 `title`、`summary`、`key_points`、`decisions` 和 `action_items` 字段。

### 3. 前端

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。开发服务器会将 `/api` 代理到 `http://localhost:8000`。

## 测试与构建

```powershell
uv run python -m pytest backend -q

cd frontend
npm test
npm run build
```

## 第一阶段约束

- 会议元数据、转写和纪要存储在 SQLite；录音与导出文件存储在 RustFS 的 `huizhi-meetings` 桶中。
- 当前为会后上传处理，不采集实时麦克风音频。
- 未配置默认 ASR 模型时不会识别真实音频；正式使用前需在「模型服务」中配置 ASR 模型。
