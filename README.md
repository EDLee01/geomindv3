# 🌍 GeoMind 4.0

**地球科学 AI 研究助手** — Chainlit 开源版

70 万+ 验证论文 · 多模型切换 · 代码自动执行 · 论文写作全流程

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🔄 **多模型切换** | Claude / Kimi / DeepSeek，顶部下拉切换 |
| 🔍 **文献检索** | 70 万+ DOI 验证论文，Qdrant 向量检索 |
| 💻 **代码自动执行** | 检测 Python 代码块 → 执行 → 失败自动修复（最多 3 轮） |
| 📊 **图表生成** | matplotlib 300dpi 学术级图表，自动显示 |
| 📎 **文件上传** | Excel / CSV / JSON，自动解析预览 |
| 🧠 **Skills 系统** | 13 个专业技能文件，根据意图自动匹配 |
| 🌊 **流式输出** | 实时显示 AI 回复 |

---

## 📁 项目结构

```
geomind/
├── app.py                    # Chainlit 入口
├── chainlit.md               # 欢迎页面
├── requirements.txt
├── .env.example              # 环境变量模板
├── .chainlit/
│   └── config.toml           # UI 配置（深海蓝主题）
├── core/                     # 框架无关的核心逻辑
│   ├── llm.py                # 多模型统一调用（Anthropic / OpenAI 兼容）
│   ├── literature.py         # Qdrant 文献检索
│   ├── code_runner.py        # Python 执行 + 自动重试
│   ├── skills.py             # Skills 管理器
│   └── memory.py             # 项目记忆（跨对话）
├── skills/                   # 技能知识库
│   ├── do/                   # 执行类技能（11 个）
│   │   ├── literature_search.md
│   │   ├── literature_review.md
│   │   ├── gap_analysis.md
│   │   ├── visualization.md
│   │   └── ...
│   └── critic/               # 验证类技能
│       ├── verify_literature.md
│       └── verify_data.md
└── public/                   # 静态资源（Starter 图标）
    └── *.svg
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd geomind
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env`，至少配置一个模型的 API Key：

```bash
# 选一个配置即可
CLAUDE_API_KEY=sk-ant-xxxxx          # Anthropic 官方
CLAUDE_ZEABUR_API_KEY=xxxxx          # Zeabur AI Hub（国内可用）
KIMI_API_KEY=sk-xxxxx                # Moonshot Kimi
DEEPSEEK_API_KEY=sk-xxxxx            # DeepSeek
```

Qdrant（文献检索）已预配置，无需修改。

### 3. 启动

```bash
chainlit run app.py
```

浏览器自动打开 `http://localhost:8000`

---

## 🎮 使用方式

### 模型切换
顶部下拉菜单选择模型（只显示已配置 API Key 的模型）

### 文献检索
```
帮我检索关于河流溶解氧预测的文献
```
系统自动检索 Qdrant 向量库，返回带 DOI 链接的论文列表

### 代码执行
```
帮我画一个 2020-2024 年发表论文数量的柱状图
```
AI 生成 Python 代码 → **自动执行** → 成功则显示图表 → 失败则 AI 自动修复重试

### 上传数据
点击输入框左侧 📎 按钮，上传 Excel/CSV 文件，系统自动解析并展示数据概况

---

## 🔧 代码自动执行流程

```
AI 回复包含 ```python 代码块
        │
        ▼
   ┌──────────────┐
   │  自动执行代码  │ ← Step: 💻 执行代码
   └──────┬───────┘
          │
    ┌─────┴─────┐
    │           │
   ✅ 成功     ❌ 失败
    │           │
显示输出    ┌───┴───┐
+图表      │ AI 修复 │ ← Step: 🤖 AI 修复代码
           └───┬───┘
               │
          ┌────┴────┐
          │ 重新执行 │ ← Step: 🔄 修复重试 (1/3)
          └────┬────┘
               │
         成功 / 再失败（最多 3 轮）
```

---

## 📐 架构设计

### core/ 层完全框架无关

`core/` 下的所有模块不依赖 Chainlit，可以直接用于：
- 其他 Web 框架（FastAPI, Streamlit）
- CLI 工具
- 测试脚本

### 多模型统一接口

```python
from core.llm import stream_llm

async for token in stream_llm(
    messages=[{"role": "user", "content": "你好"}],
    system_prompt="你是 GeoMind",
    provider="Claude",       # 或 "Kimi" / "DeepSeek"
):
    print(token, end="")
```

自动检测 Anthropic 原生格式 vs OpenAI 兼容格式。

---

## 🎨 主题配色

| 元素 | 颜色 | 色值 |
|------|------|------|
| 主色 | 深海蓝 | `#1e3a5f` |
| 强调色 | 地学绿 | `#2d9d78` |
| 辅助色 | 天蓝 | `#4a90d9` |
| 背景色 | 浅灰 | `#f5f7fa` |

---

## ⚠️ 注意事项

1. **Qdrant 字段名**：`journal_name`（不是 `journal`）
2. **DOI 格式**：数据库中已是完整 URL，不要再加 `https://doi.org/` 前缀
3. **Embedding 模型**：必须用 `BAAI/bge-base-en-v1.5`（768 维）
4. **中文字体**：代码执行环境自动尝试 SimHei / WenQuanYi
5. **代码执行超时**：默认 30 秒

---

## 📦 部署

### Zeabur

```bash
# 安装 Zeabur CLI
npm i -g @zeabur/cli

# 部署
zeabur deploy
```

在 Zeabur 控制台设置环境变量即可。

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install -y fonts-wqy-zenhei
CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 📄 License

MIT
