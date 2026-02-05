"""
GeoMind 4.0 - Chainlit 版
地球科学 AI 研究助手

Features:
- 多模型切换（Claude / Kimi / DeepSeek）
- 文献检索（70 万+ 验证论文）
- 代码自动执行 + 失败重试
- Skills 系统（.md 知识库）
- 流式输出
"""

import chainlit as cl
import os
import re
import base64
from pathlib import Path
from typing import List, Dict, Optional

from core.llm import (
    MODEL_PROVIDERS,
    get_available_providers,
    stream_llm,
    call_llm,
    get_provider_config,
)
from core.literature import search_papers, format_papers_markdown, format_papers_bibtex
from core.code_runner import execute_python, extract_code_blocks, format_execution_result, build_fix_prompt
from core.skills import SkillsManager
from core.memory import ProjectMemory

# ============================================================
# 全局配置
# ============================================================

BASE_DIR = Path(__file__).parent
SKILLS_DIR = BASE_DIR / "skills"
MAX_CODE_RETRIES = 3  # 代码执行最大重试次数

# 初始化 Skills
skills_manager = SkillsManager(SKILLS_DIR)


# ============================================================
# 系统提示词构建
# ============================================================

def build_system_prompt(
    skill_name: str = None,
    memory: ProjectMemory = None,
    extra_context: str = "",
) -> str:
    """构建系统提示词"""

    base = """你是 GeoMind，一个专业的地球科学 AI 研究助手。

## 核心能力
1. 🔍 **文献检索** — 搜索 70 万+ DOI 验证论文库
2. 📊 **数据分析** — 统计分析、时序分析、空间分析
3. 📈 **可视化** — 生成学术级图表（matplotlib）
4. ✍️ **论文写作** — 辅助撰写学术论文各章节

## 代码规范
当需要执行计算或生成图表时：
1. 将代码放在 ```python 代码块中
2. 图表使用 plt.savefig('output.png', dpi=300, bbox_inches='tight') 保存
3. 使用 print() 输出数值结果
4. 代码必须可以独立运行（包含所有 import）

## 重要规则
1. **文献必须真实** — 只引用检索到的文献，不要编造
2. **用中文回复**（除非用户要求英文）
3. **关键决策** — 询问用户意见
"""

    if memory:
        base += f"\n\n## 当前项目进展\n{memory.to_context()}\n"

    if skill_name:
        skill_prompt = skills_manager.get_skill_prompt(skill_name)
        if skill_prompt:
            base += skill_prompt

    if extra_context:
        base += f"\n\n{extra_context}"

    return base


# ============================================================
# Chat Profiles - 模型切换
# ============================================================

@cl.set_chat_profiles
async def chat_profiles():
    """定义可切换的模型"""
    profiles = []

    for name, config in MODEL_PROVIDERS.items():
        # 检查是否有 API Key
        has_key = bool(os.getenv(config["env_key"], ""))
        if not has_key:
            continue  # 只显示已配置的模型

        profiles.append(
            cl.ChatProfile(
                name=name,
                markdown_description=f"{config['icon']} {config['description']}",
                default=(name == "Claude" or name == "Claude (Zeabur)"),
            )
        )

    # 如果没有任何模型配置，显示提示
    if not profiles:
        profiles.append(
            cl.ChatProfile(
                name="未配置",
                markdown_description="⚠️ 请在 .env 文件中配置至少一个 API Key",
                default=True,
            )
        )

    return profiles


# ============================================================
# Starters - 首页卡片
# ============================================================

@cl.set_starters
async def starters():
    """首页快速启动卡片"""
    return [
        cl.Starter(
            label="📚 文献检索",
            message="帮我检索关于河流溶解氧预测的相关文献",
            icon="/public/search.svg",
        ),
        cl.Starter(
            label="📊 数据分析",
            message="我有一份水质监测数据（Excel），请帮我做探索性分析",
            icon="/public/chart.svg",
        ),
        cl.Starter(
            label="📈 生成图表",
            message="帮我画一个溶解氧月度变化的折线图",
            icon="/public/plot.svg",
        ),
        cl.Starter(
            label="✍️ 论文写作",
            message="我正在写一篇关于深度学习水质预测的综述，请帮我规划大纲",
            icon="/public/write.svg",
        ),
    ]


# ============================================================
# Chat 启动
# ============================================================

@cl.on_chat_start
async def on_chat_start():
    """对话启动时初始化"""

    # 获取当前选择的模型
    profile = cl.user_session.get("chat_profile")
    if not profile or profile == "未配置":
        await cl.Message(
            content="⚠️ **未检测到 API Key 配置**\n\n"
            "请在项目根目录的 `.env` 文件中配置至少一个 API Key：\n\n"
            "```\n"
            "CLAUDE_API_KEY=sk-ant-xxx\n"
            "# 或\n"
            "KIMI_API_KEY=sk-xxx\n"
            "# 或\n"
            "DEEPSEEK_API_KEY=sk-xxx\n"
            "```\n\n"
            "然后重启应用: `chainlit run app.py`"
        ).send()
        return

    # 初始化 Memory
    memory = ProjectMemory("default", name="快速对话")
    cl.user_session.set("memory", memory)
    cl.user_session.set("provider", profile)

    # 获取所有已配置的提供商
    available_providers = get_available_providers()

    # 获取当前提供商的配置
    config = MODEL_PROVIDERS.get(profile, {})
    default_model = config.get("default_model", "")

    # 构建所有可用模型的列表（格式: "提供商: 模型名"）
    all_models = []
    for provider_name in available_providers:
        provider_config = MODEL_PROVIDERS.get(provider_name, {})
        for model in provider_config.get("models", []):
            all_models.append(f"{provider_name}: {model}")

    # 当前选择的模型
    current_selection = f"{profile}: {default_model}"

    # 初始化设置
    cl.user_session.set("current_model", default_model)
    cl.user_session.set("temperature", 0.7)
    cl.user_session.set("max_tokens", 4096)

    # 创建设置面板
    settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="model",
                label="🤖 模型选择（服务: 模型）",
                values=all_models,
                initial_value=current_selection,
            ),
            cl.input_widget.Slider(
                id="temperature",
                label="🌡️ 温度 (Temperature)",
                initial=0.7,
                min=0,
                max=1,
                step=0.1,
            ),
            cl.input_widget.Slider(
                id="max_tokens",
                label="📝 最大输出长度 (Max Tokens)",
                initial=4096,
                min=256,
                max=8192,
                step=256,
            ),
        ]
    ).send()

    # 欢迎消息
    await cl.Message(
        content=f"👋 你好！我是 **GeoMind**，你的地球科学 AI 研究助手。\n\n"
        f"当前模型: **{profile}** (`{default_model}`)\n\n"
        f"我可以帮你：\n"
        f"- 🔍 检索 70 万+ 验证论文\n"
        f"- 📊 分析数据、执行代码\n"
        f"- 📈 生成学术级图表\n"
        f"- ✍️ 辅助论文写作\n\n"
        f"💡 **提示**: 点击输入框旁的 ⚙️ 齿轮图标可以切换模型和调整设置\n\n"
        f"直接告诉我你的需求吧！"
    ).send()


# ============================================================
# 文件上传处理
# ============================================================

async def handle_uploaded_files(files: List[cl.File]) -> str:
    """处理上传的文件，返回附加上下文"""
    if not files:
        return ""

    context_parts = []
    uploaded_files_list = []  # 保存文件信息用于代码执行

    for f in files:
        name = f.name
        ext = Path(name).suffix.lower()

        # 保存文件信息（路径和名称）
        uploaded_files_list.append({"name": name, "path": f.path})

        if ext in (".xlsx", ".xls", ".csv"):
            try:
                import pandas as pd

                if ext == ".csv":
                    df = pd.read_csv(f.path)
                else:
                    df = pd.read_excel(f.path)

                preview = df.head(5).to_string()
                desc = (
                    f"\n[已上传文件: {name}]\n"
                    f"- 大小: {df.shape[0]} 行 × {df.shape[1]} 列\n"
                    f"- 列名: {', '.join(df.columns.tolist())}\n"
                    f"- 数据类型:\n{df.dtypes.to_string()}\n"
                    f"- 前 5 行预览:\n{preview}\n"
                    f"- **代码中请使用文件名: '{name}'**\n"
                )
                context_parts.append(desc)

                # 保存到 Memory
                memory = cl.user_session.get("memory")
                if memory:
                    memory.set(
                        "data_profile",
                        {
                            "filename": name,
                            "rows": df.shape[0],
                            "columns": df.shape[1],
                            "column_names": df.columns.tolist(),
                        },
                    )

            except Exception as e:
                context_parts.append(f"\n[文件 {name} 解析失败: {e}]\n")

        elif ext == ".json":
            try:
                import json

                with open(f.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                preview = json.dumps(data, ensure_ascii=False, indent=2)[:2000]
                context_parts.append(f"\n[已上传 JSON: {name}]\n{preview}\n")
            except Exception as e:
                context_parts.append(f"\n[文件 {name} 解析失败: {e}]\n")

        else:
            context_parts.append(f"\n[已上传文件: {name} (类型: {ext})]\n")

    # 保存上传文件列表到 session，供代码执行时使用
    existing_files = cl.user_session.get("uploaded_files") or []
    existing_files.extend(uploaded_files_list)
    cl.user_session.set("uploaded_files", existing_files)

    return "\n".join(context_parts)


# ============================================================
# 核心消息处理
# ============================================================

@cl.on_message
async def on_message(message: cl.Message):
    """处理用户消息"""

    provider = cl.user_session.get("provider")
    if not provider or provider == "未配置":
        await cl.Message(content="⚠️ 请先配置 API Key（见 .env 文件）").send()
        return

    memory = cl.user_session.get("memory")
    user_text = message.content

    # 处理上传文件
    file_context = ""
    if message.elements:
        files = [e for e in message.elements if isinstance(e, cl.File)]
        if files:
            file_context = await handle_uploaded_files(files)

    # ── Step 1: 意图识别 & Skill 匹配 ──
    matched_skill = skills_manager.match_skill(user_text)
    if matched_skill:
        # 显示匹配到的 Skill
        async with cl.Step(name="🎯 技能匹配", type="tool") as step:
            step.output = f"匹配到: **{matched_skill}**"

    # ── Step 2: 文献检索（如果触发） ──
    literature_context = ""
    literature_keywords = ["文献", "论文", "检索", "搜索", "找", "@文献", "literature", "paper", "search"]
    needs_search = any(kw in user_text.lower() for kw in literature_keywords)

    if needs_search:
        async with cl.Step(name="🔍 文献检索", type="tool") as step:
            step.input = f"检索关键词: {user_text[:100]}"

            result = await search_papers(user_text, limit=15)

            if result["success"] and result["papers"]:
                papers = result["papers"]
                step.output = f"找到 {len(papers)} 篇相关文献"

                # 格式化为上下文
                papers_md = format_papers_markdown(papers)
                literature_context = f"\n\n[文献检索结果]\n{papers_md}\n[END]\n"

                # 保存到 Memory
                if memory:
                    existing = memory.get("literature_list", [])
                    existing.extend(papers)
                    memory.set("literature_list", existing)

                # 生成 BibTeX 下载
                bibtex = format_papers_bibtex(papers)
                bibtex_element = cl.File(
                    name="references.bib",
                    content=bibtex.encode("utf-8"),
                    display="side",
                )
                # 将在最终消息中附加
            else:
                error_msg = result.get("error", "未找到相关文献")
                step.output = f"⚠️ {error_msg}"

    # ── Step 3: 调用 LLM（流式输出） ──
    # 组装消息历史
    history = cl.chat_context.to_openai()

    # 确保消息格式正确 - 只保留 role 和 content
    clean_history = []
    for msg in history:
        if msg.get("role") in ("user", "assistant"):
            clean_history.append({"role": msg["role"], "content": msg.get("content", "")})

    # 如果有文件上下文，附加到最后一条用户消息
    extra_ctx = ""
    if file_context:
        extra_ctx += file_context
    if literature_context:
        extra_ctx += literature_context

    system_prompt = build_system_prompt(
        skill_name=matched_skill,
        memory=memory,
        extra_context=extra_ctx,
    )

    # 获取用户设置
    current_model = cl.user_session.get("current_model")
    temperature = cl.user_session.get("temperature", 0.7)
    max_tokens = cl.user_session.get("max_tokens", 4096)

    # 流式输出
    response_msg = cl.Message(content="")
    await response_msg.send()

    full_response = ""
    async for token in stream_llm(
        messages=clean_history,
        system_prompt=system_prompt,
        provider=provider,
        model=current_model,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        full_response += token
        await response_msg.stream_token(token)

    await response_msg.update()

    # 附加 BibTeX 文件（如果有文献搜索结果）
    if needs_search and "bibtex_element" in dir():
        # 在 side panel 显示文献列表
        pass  # BibTeX 已通过 Step 展示

    # ── Step 4: 自动代码执行 + 重试 ──
    code_blocks = extract_code_blocks(full_response)

    if code_blocks:
        await _auto_execute_code(
            code_blocks=code_blocks,
            provider=provider,
            system_prompt=system_prompt,
            history=clean_history,
        )


# ============================================================
# 代码自动执行 + 重试循环
# ============================================================

async def _auto_execute_code(
    code_blocks: List[str],
    provider: str,
    system_prompt: str,
    history: List[Dict],
):
    """
    自动执行代码块，失败则让 AI 修复重试

    流程: 执行 → 检查 → OK 输出结果 / 失败 → AI 修代码 → 重试（最多 3 轮）
    """

    # 获取上传的文件列表
    uploaded_files = cl.user_session.get("uploaded_files") or []

    # 获取用户设置
    current_model = cl.user_session.get("current_model")
    temperature = cl.user_session.get("temperature", 0.7)
    max_tokens = cl.user_session.get("max_tokens", 4096)

    for i, code in enumerate(code_blocks):
        retry_count = 0
        current_code = code

        while retry_count <= MAX_CODE_RETRIES:
            # 执行代码
            step_name = (
                f"💻 执行代码" if retry_count == 0
                else f"🔄 修复重试 ({retry_count}/{MAX_CODE_RETRIES})"
            )

            async with cl.Step(name=step_name, type="run") as step:
                step.input = f"```python\n{current_code[:500]}{'...' if len(current_code) > 500 else ''}\n```"

                result = execute_python(current_code, uploaded_files=uploaded_files)

                if result["success"]:
                    # ✅ 执行成功
                    step.output = format_execution_result(result)

                    # 显示自动安装的包
                    if result.get("installed"):
                        await cl.Message(
                            content=f"📦 **自动安装了以下依赖：** {', '.join(result['installed'])}"
                        ).send()

                    # 显示输出
                    if result["output"]:
                        await cl.Message(
                            content=f"**执行结果：**\n```\n{result['output']}\n```"
                        ).send()

                    # 显示图表
                    for img in result["images"]:
                        img_bytes = base64.b64decode(img["data"])
                        image_element = cl.Image(
                            name=img["filename"],
                            content=img_bytes,
                            display="inline",
                            size="large",
                        )
                        await cl.Message(
                            content=f"📊 **{img['filename']}**",
                            elements=[image_element],
                        ).send()

                    break  # 成功，退出重试循环

                else:
                    # ❌ 执行失败
                    step.output = format_execution_result(result)

                    if retry_count >= MAX_CODE_RETRIES:
                        await cl.Message(
                            content=f"⚠️ 代码执行失败（已重试 {MAX_CODE_RETRIES} 次）。"
                            f"请手动检查代码或告诉我具体问题。\n\n"
                            f"**错误信息：**\n```\n{result['error'][:500]}\n```"
                        ).send()
                        break

                    # 让 AI 修复代码
                    retry_count += 1
                    fix_prompt = build_fix_prompt(current_code, result["error"])

                    async with cl.Step(name="🤖 AI 修复代码", type="llm") as fix_step:
                        fix_step.input = f"错误: {result['error'][:200]}"

                        fix_messages = history + [
                            {"role": "assistant", "content": f"```python\n{current_code}\n```"},
                            {"role": "user", "content": fix_prompt},
                        ]

                        fix_response = await call_llm(
                            messages=fix_messages,
                            system_prompt=system_prompt,
                            provider=provider,
                            model=current_model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )

                        # 提取修复后的代码
                        fixed_blocks = extract_code_blocks(fix_response)
                        if fixed_blocks:
                            current_code = fixed_blocks[0]
                            fix_step.output = f"已生成修复代码（{len(current_code)} 字符）"
                        else:
                            fix_step.output = "AI 未返回有效代码，停止重试"
                            await cl.Message(
                                content=f"⚠️ AI 未能生成修复代码。原始错误：\n```\n{result['error'][:500]}\n```"
                            ).send()
                            break


# ============================================================
# Settings 变更处理
# ============================================================

@cl.on_settings_update
async def on_settings_update(settings):
    """处理用户修改设置"""
    # 更新模型选择（格式: "提供商: 模型"）
    if "model" in settings:
        model_str = settings["model"]
        if ": " in model_str:
            provider, model = model_str.split(": ", 1)
            cl.user_session.set("provider", provider)
            cl.user_session.set("current_model", model)
        else:
            cl.user_session.set("current_model", model_str)

    # 更新温度
    if "temperature" in settings:
        cl.user_session.set("temperature", settings["temperature"])

    # 更新最大 token 数
    if "max_tokens" in settings:
        cl.user_session.set("max_tokens", int(settings["max_tokens"]))

    # 显示设置更新提示
    provider = cl.user_session.get("provider", "未知")
    model = cl.user_session.get("current_model", "未知")
    temp = settings.get("temperature", cl.user_session.get("temperature", 0.7))
    tokens = settings.get("max_tokens", cl.user_session.get("max_tokens", 4096))

    # 获取提供商图标
    config = MODEL_PROVIDERS.get(provider, {})
    icon = config.get("icon", "🤖")

    await cl.Message(
        content=f"⚙️ **设置已更新**\n"
        f"- 服务: {icon} **{provider}**\n"
        f"- 模型: `{model}`\n"
        f"- 温度: `{temp}`\n"
        f"- 最大输出: `{int(tokens)}` tokens"
    ).send()
