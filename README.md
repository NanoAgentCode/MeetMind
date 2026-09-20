# 会智录

基于 React、FastAPI 与 LangGraph 的 AI 会议纪要辅助系统。当前第一阶段已实现：

`上传录音 → 语音转写 → 生成纪要 → 人工修改 → 导出 Word/Markdown`

## 技术栈

- 前端：React + TypeScript + Vite + Ant Design
- 后端：FastAPI + LangGraph + LangChain
- 模型协议：OpenAI、Claude、Ollama、vLLM
- 导出：python-docx
- 文件存储：RustFS（S3 兼容对象存储）

后端配置在 `backend/app/config.py` 中按 `app`、`asr`、`llm`、各模型 Provider 和 `rustfs` 分组；环境变量名称保持扁平格式，兼容 `.env` 与容器部署。

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
uv run python backend\main.py
```

`backend/main.py` 是后端启动入口；`backend/app/main.py` 只负责 FastAPI 应用和路由定义。需要热更新时可使用 `uv run uvicorn backend.app.main:app --reload`。

如果复制项目后出现 `VIRTUAL_ENV ... does not match`，请重启终端，或在 PowerShell 中执行：

```powershell
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
uv sync
```

IDE 的 Python 解释器应指向当前项目的 `.venv\Scripts\python.exe`，不要继续使用旧目录中的虚拟环境。

默认 `ASR_BACKEND=demo`，可无需密钥走通全部功能，但转写内容是用于产品演示的固定示例。

要转写真实录音，请修改 `backend/.env`：

```dotenv
ASR_BACKEND=openai
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.openai.com/v1
ASR_MODEL=whisper-1
```

`OPENAI_BASE_URL` 可替换为实现兼容接口的语音转写服务地址。

### 选择纪要模型协议

默认 `LLM_PROVIDER=demo`，LangGraph 运行无需模型服务的确定性提取流程。接入模型时选择下面一种配置：

```dotenv
# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.openai.com/v1

# Claude（Anthropic 原生协议）
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=你的密钥
ANTHROPIC_BASE_URL=https://api.anthropic.com

# Ollama
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434

# vLLM（OpenAI-compatible 协议）
LLM_PROVIDER=vllm
LLM_MODEL=Qwen/Qwen3-8B
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_API_KEY=EMPTY
```

模型名称仅为配置示例，请替换为服务中实际可用的模型。四种协议统一输出并校验 `title`、`summary`、`key_points`、`decisions` 和 `action_items` 字段。

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
npm run build
```

## 第一阶段约束

- 录音、会议元数据和导出文件均存储在 RustFS 的 `huizhi-meetings` 桶中。
- 当前为会后上传处理，不采集实时麦克风音频。
- 使用 `demo` 后端不会识别真实音频；正式演示前需配置真实 ASR 服务。
- `LLM_PROVIDER` 控制纪要模型；`ASR_BACKEND` 独立控制语音转写，两者不要混用。
