"""
GeoMind 4.0 - Chainlit 版
地球科学 AI 研究助手

Features:
- 多模型切换（Claude / Kimi / DeepSeek）
- 文献检索（70 万+ 验证论文）
- 代码自动执行 + 失败重试
- Skills 系统（.md 知识库）
- 流式输出
- 用户登录认证
- Canvas 侧边栏（代码/图片下载，支持 md/png/pdf）
"""

import chainlit as cl
from chainlit.types import ThreadDict
import os
import re
import base64
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional

from core.llm import (
    MODEL_PROVIDERS,
    get_available_providers,
    stream_llm,
    call_llm,
)
from core.literature import search_papers, format_papers_markdown, format_papers_bibtex
from core.code_runner import execute_python, extract_code_blocks, format_execution_result, build_fix_prompt
from core.skills import SkillsManager
from core.memory import ProjectMemory
from core.canvas import CanvasManager, extract_canvas_content

# ============================================================
# 全局配置
# ============================================================

BASE_DIR = Path(__file__).parent
SKILLS_DIR = BASE_DIR / "skills"
MAX_CODE_RETRIES = 3  # 代码执行最大重试次数
USERS_FILE = BASE_DIR / "users.json"  # 用户数据文件

# 初始化 Skills
skills_manager = SkillsManager(SKILLS_DIR)


# ============================================================
# 用户认证系统（可选，需设置 CHAINLIT_AUTH_SECRET 环境变量）
# ============================================================

# 检查是否启用认证
AUTH_ENABLED = bool(os.getenv("CHAINLIT_AUTH_SECRET", ""))

def _hash_password(password: str) -> str:
    """对密码进行哈希处理"""
    return hashlib.sha256(password.encode()).hexdigest()


def _load_users() -> Dict:
    """加载用户数据"""
    # 优先从环境变量读取用户配置（Zeabur 部署）
    env_users = os.getenv("GEOMIND_USERS", "")
    if env_users:
        try:
            return json.loads(env_users)
        except json.JSONDecodeError:
            pass

    # 从文件读取
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # 默认用户（如果配置了环境变量）
    default_user = os.getenv("GEOMIND_DEFAULT_USER", "")
    default_pass = os.getenv("GEOMIND_DEFAULT_PASSWORD", "")

    if default_user and default_pass:
        return {
            default_user: {
                "password": _hash_password(default_pass),
                "role": "admin",
                "name": default_user
            }
        }

    return {}


def _save_users(users: Dict):
    """保存用户数据到文件"""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def _verify_user(username: str, password: str) -> Optional[Dict]:
    """验证用户凭据"""
    users = _load_users()

    if username in users:
        user_data = users[username]
        hashed = _hash_password(password)
        if user_data.get("password") == hashed:
            return {
                "username": username,
                "role": user_data.get("role", "user"),
                "name": user_data.get("name", username)
            }
    return None


# 只有在设置了 CHAINLIT_AUTH_SECRET 时才启用认证
if AUTH_ENABLED:
    @cl.password_auth_callback
    async def auth_callback(username: str, password: str) -> Optional[cl.User]:
        """
        Chainlit 密码认证回调

        支持以下方式配置用户:
        1. 环境变量 GEOMIND_USERS (JSON 格式)
        2. 环境变量 GEOMIND_DEFAULT_USER + GEOMIND_DEFAULT_PASSWORD
        3. users.json 文件
        """
        user_data = _verify_user(username, password)

        if user_data:
            return cl.User(
                identifier=user_data["username"],
                metadata={
                    "role": user_data["role"],
                    "name": user_data["name"],
                    "provider": "credentials"
                }
            )
        return None


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    """恢复历史会话"""
    # 重新初始化 Memory
    memory = ProjectMemory("default", name="恢复的对话")
    cl.user_session.set("memory", memory)

    # 恢复用户选择的模型
    profile = cl.user_session.get("chat_profile")
    if profile:
        cl.user_session.set("provider", profile)


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

    # 获取当前登录用户
    user = cl.user_session.get("user")
    user_name = "访客"
    if user:
        user_name = user.metadata.get("name", user.identifier)

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

    # 初始化 Memory（使用用户标识）
    user_id = user.identifier if user else "default"
    memory = ProjectMemory(user_id, name="快速对话")
    cl.user_session.set("memory", memory)
    cl.user_session.set("provider", profile)

    # 欢迎消息
    config = MODEL_PROVIDERS.get(profile, {})
    model_name = config.get("default_model", "unknown")

    await cl.Message(
        content=f"👋 你好，**{user_name}**！我是 **GeoMind**，你的地球科学 AI 研究助手。\n\n"
        f"当前模型: **{profile}** (`{model_name}`)\n\n"
        f"我可以帮你：\n"
        f"- 🔍 检索 70 万+ 验证论文\n"
        f"- 📊 分析数据、执行代码\n"
        f"- 📈 生成学术级图表\n"
        f"- ✍️ 辅助论文写作\n\n"
        f"直接告诉我你的需求吧！"
    ).send()


# ============================================================
# Canvas 侧边栏功能
# ============================================================

async def send_canvas_downloads(
    canvas: CanvasManager,
    response_text: str,
    images: List[Dict] = None
):
    """
    发送 Canvas 内容和下载链接

    在侧边栏显示代码、图片，并提供多格式下载
    """
    elements = []

    # 从响应中提取内容
    canvas.extract_from_response(response_text)

    # 添加执行生成的图片
    if images:
        for img in images:
            canvas.add_image(img["data"], img["filename"])

    # 如果没有内容，直接返回
    if not canvas.items:
        return

    # 生成下载文件
    download_elements = []

    # 1. 所有代码合并为一个 Markdown
    code_items = [item for item in canvas.items if item.type == "code"]
    if code_items:
        md_content = canvas.to_markdown(code_items)
        download_elements.append(
            cl.File(
                name="code_all.md",
                content=md_content.encode("utf-8"),
                display="side",
            )
        )

        # 每个代码块单独下载
        for item in code_items:
            download_elements.append(
                cl.File(
                    name=item.filename,
                    content=item.content.encode("utf-8"),
                    display="side",
                )
            )

    # 2. 图片下载（PNG + PDF）
    for item in canvas.images:
        # PNG
        download_elements.append(
            cl.File(
                name=item.filename,
                content=base64.b64decode(item.content),
                display="side",
            )
        )

        # PDF（如果可用）
        downloads = canvas.generate_downloads(item)
        for filename, content, mime_type in downloads:
            if filename.endswith(".pdf"):
                download_elements.append(
                    cl.File(
                        name=filename,
                        content=content,
                        display="side",
                    )
                )

    # 3. 生成完整报告（如果有多个内容）
    if len(canvas.items) > 1:
        full_md = canvas.to_markdown()
        download_elements.append(
            cl.File(
                name="geomind_report.md",
                content=full_md.encode("utf-8"),
                display="side",
            )
        )

        # PDF 报告
        pdf_bytes = canvas.generate_combined_pdf()
        if pdf_bytes:
            download_elements.append(
                cl.File(
                    name="geomind_report.pdf",
                    content=pdf_bytes,
                    display="side",
                )
            )

    # 发送 Canvas 消息
    if download_elements:
        # 构建下载列表说明
        file_list = "\n".join([f"- {el.name}" for el in download_elements[:5]])
        if len(download_elements) > 5:
            file_list += f"\n- ...共 {len(download_elements)} 个文件"

        await cl.Message(
            content=f"📎 **Canvas 下载**\n\n{file_list}",
            elements=download_elements,
        ).send()


# ============================================================
# 文件上传处理
# ============================================================

async def handle_uploaded_files(files: List[cl.File]) -> str:
    """处理上传的文件，返回附加上下文"""
    if not files:
        return ""

    context_parts = []
    for f in files:
        name = f.name
        ext = Path(name).suffix.lower()

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

    # 初始化 Canvas（每次对话）
    canvas = CanvasManager()
    cl.user_session.set("canvas", canvas)

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

    # 流式输出
    response_msg = cl.Message(content="")
    await response_msg.send()

    full_response = ""
    async for token in stream_llm(
        messages=clean_history,
        system_prompt=system_prompt,
        provider=provider,
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
    collected_images = []  # 收集执行生成的图片

    if code_blocks:
        collected_images = await _auto_execute_code(
            code_blocks=code_blocks,
            provider=provider,
            system_prompt=system_prompt,
            history=clean_history,
        )

    # ── Step 5: Canvas 侧边栏下载 ──
    # 只有当有代码块或图片时才显示 Canvas
    if code_blocks or collected_images:
        await send_canvas_downloads(canvas, full_response, collected_images)


# ============================================================
# 代码自动执行 + 重试循环
# ============================================================

async def _auto_execute_code(
    code_blocks: List[str],
    provider: str,
    system_prompt: str,
    history: List[Dict],
) -> List[Dict]:
    """
    自动执行代码块，失败则让 AI 修复重试

    流程: 执行 → 检查 → OK 输出结果 / 失败 → AI 修代码 → 重试（最多 3 轮）

    Returns:
        收集到的图片列表 [{"data": base64, "filename": str}]
    """
    collected_images = []  # 收集所有生成的图片

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

                result = execute_python(current_code)

                if result["success"]:
                    # ✅ 执行成功
                    step.output = format_execution_result(result)

                    # 显示输出
                    if result["output"]:
                        await cl.Message(
                            content=f"**执行结果：**\n```\n{result['output']}\n```"
                        ).send()

                    # 显示图表并收集
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

                        # 收集图片用于 Canvas
                        collected_images.append(img)

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

    return collected_images


# ============================================================
# Settings 变更处理
# ============================================================

@cl.on_settings_update
async def on_settings_update(settings):
    """处理用户修改设置"""
    # 预留：未来可在这里处理 API Key 等运行时设置
    pass
