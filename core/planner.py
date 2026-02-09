"""
GeoMind Core - 智能方案规划系统
根据用户需求动态分析可用功能，生成执行方案
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class ToolType(Enum):
    """可用工具类型"""
    LITERATURE_SEARCH = "literature_search"  # 文献检索
    CODE_EXECUTION = "code_execution"        # 代码执行
    DATA_ANALYSIS = "data_analysis"          # 数据分析
    VISUALIZATION = "visualization"          # 可视化
    PAPER_WRITING = "paper_writing"          # 论文写作
    DIRECT_ANSWER = "direct_answer"          # 直接回答


@dataclass
class Tool:
    """工具定义"""
    type: ToolType
    name: str
    description: str
    icon: str
    keywords: List[str]  # 触发关键词


# 可用工具列表
AVAILABLE_TOOLS = [
    Tool(
        type=ToolType.LITERATURE_SEARCH,
        name="文献检索",
        description="搜索 70 万+ DOI 验证论文库",
        icon="📚",
        keywords=["文献", "论文", "检索", "搜索论文", "找论文", "参考文献", "引用",
                  "literature", "paper", "search", "reference", "citation"]
    ),
    Tool(
        type=ToolType.CODE_EXECUTION,
        name="代码执行",
        description="执行 Python 代码进行计算或生成图表",
        icon="💻",
        keywords=["代码", "计算", "编程", "python", "执行", "运行", "code", "compute"]
    ),
    Tool(
        type=ToolType.DATA_ANALYSIS,
        name="数据分析",
        description="统计分析、相关性分析、回归分析等",
        icon="📊",
        keywords=["分析", "统计", "相关性", "回归", "数据", "analysis", "statistics",
                  "correlation", "regression", "data"]
    ),
    Tool(
        type=ToolType.VISUALIZATION,
        name="可视化",
        description="生成学术级图表（折线图、散点图、热力图等）",
        icon="📈",
        keywords=["图表", "画图", "可视化", "折线图", "散点图", "热力图", "柱状图",
                  "plot", "chart", "visualization", "graph", "figure"]
    ),
    Tool(
        type=ToolType.PAPER_WRITING,
        name="论文写作",
        description="辅助撰写论文各章节（摘要、引言、方法等）",
        icon="✍️",
        keywords=["论文", "写作", "撰写", "摘要", "引言", "方法", "讨论", "结论",
                  "综述", "paper", "writing", "abstract", "introduction", "method"]
    ),
]


@dataclass
class PlanStep:
    """方案步骤"""
    order: int
    tool: Tool
    action: str  # 具体动作描述
    expected_output: str  # 预期输出


@dataclass
class Plan:
    """执行方案"""
    title: str
    summary: str
    steps: List[PlanStep]
    estimated_time: str  # 预估时间
    user_input_needed: bool  # 是否需要用户额外输入


def detect_tools_from_text(text: str) -> List[Tool]:
    """
    从用户输入中检测需要使用的工具

    Args:
        text: 用户输入文本

    Returns:
        检测到的工具列表
    """
    text_lower = text.lower()
    detected = []

    for tool in AVAILABLE_TOOLS:
        for keyword in tool.keywords:
            if keyword in text_lower:
                if tool not in detected:
                    detected.append(tool)
                break

    return detected


def get_planning_prompt(user_request: str, detected_tools: List[Tool]) -> str:
    """
    生成规划提示词

    Args:
        user_request: 用户原始请求
        detected_tools: 检测到的工具列表

    Returns:
        规划提示词
    """
    tools_desc = "\n".join([
        f"- {tool.icon} **{tool.name}**: {tool.description}"
        for tool in detected_tools
    ]) if detected_tools else "（未检测到特定工具需求，将直接回答）"

    all_tools_desc = "\n".join([
        f"- {tool.icon} **{tool.name}**: {tool.description}"
        for tool in AVAILABLE_TOOLS
    ])

    return f"""## 🎯 任务规划模式

用户请求："{user_request}"

### 检测到可能需要的功能：
{tools_desc}

### 所有可用功能：
{all_tools_desc}

### ⚠️ 重要规则：
1. **只生成执行方案，不要执行任何操作**
2. **绝对禁止编造或提供任何文献/论文信息**（包括标题、作者、DOI、年份）
3. **文献检索将在用户确认后由系统自动执行**
4. **方案中只描述"将要做什么"，不要给出具体内容或结果**

### 请按以下格式生成执行方案：

---
## 📋 执行方案

**目标**：[一句话描述目标]

**执行步骤**：

| 步骤 | 功能 | 具体操作 | 预期结果 |
|:----:|:----:|:---------|:---------|
| 1 | [功能名] | [具体操作描述] | [预期输出类型，不是具体内容] |
| 2 | [功能名] | [具体操作描述] | [预期输出类型，不是具体内容] |

**需要您确认**：
- [ ] 方案是否符合您的需求？
- [ ] 是否需要调整某些步骤？

请回复 **"确认执行"** 开始执行，或告诉我需要修改的地方。

---

请根据用户需求生成上述格式的方案。只描述步骤，不要提前给出任何结果或内容。
"""


def format_plan_card(plan: Plan) -> str:
    """
    格式化方案卡片

    Args:
        plan: 执行方案

    Returns:
        格式化的 Markdown 文本
    """
    steps_table = "| 步骤 | 功能 | 具体操作 | 预期结果 |\n|:----:|:----:|:---------|:---------|\n"
    for step in plan.steps:
        steps_table += f"| {step.order} | {step.tool.icon} {step.tool.name} | {step.action} | {step.expected_output} |\n"

    return f"""## 📋 执行方案

**{plan.title}**

{plan.summary}

### 执行步骤

{steps_table}

### 确认执行

请回复以下选项：
- **"确认执行"** 或 **"开始"** - 按方案执行
- **"修改步骤 X"** - 修改特定步骤
- **"取消"** - 取消本次方案

"""


def is_confirmation_message(text: str) -> bool:
    """
    检测用户消息是否是确认执行

    Args:
        text: 用户消息

    Returns:
        是否是确认消息
    """
    confirm_keywords = [
        "确认执行", "开始执行", "执行", "开始", "确认", "好的", "可以",
        "没问题", "就这样", "OK", "ok", "yes", "Yes", "YES"
    ]
    text_stripped = text.strip()
    return any(kw in text_stripped for kw in confirm_keywords)


def is_modification_message(text: str) -> Optional[str]:
    """
    检测用户消息是否是修改请求

    Args:
        text: 用户消息

    Returns:
        修改内容描述，如果不是修改请求则返回 None
    """
    modify_keywords = ["修改", "调整", "改一下", "换成", "不要", "去掉", "添加", "加上"]
    for kw in modify_keywords:
        if kw in text:
            return text
    return None


def is_cancel_message(text: str) -> bool:
    """
    检测用户消息是否是取消

    Args:
        text: 用户消息

    Returns:
        是否是取消消息
    """
    cancel_keywords = ["取消", "算了", "不用了", "cancel", "Cancel"]
    return any(kw in text for kw in cancel_keywords)


def should_use_planning_mode(text: str) -> bool:
    """
    判断是否应该使用规划模式

    对于复杂任务使用规划模式，简单问答直接回答

    Args:
        text: 用户输入

    Returns:
        是否使用规划模式
    """
    # 检测到的工具数量
    tools = detect_tools_from_text(text)

    # 如果只有文献检索且没有其他复杂需求，直接执行而不进入规划模式
    # 这样可以避免 LLM 在规划阶段瞎编文献
    if len(tools) == 1 and tools[0].type == ToolType.LITERATURE_SEARCH:
        # 只有同时需要其他操作时才进入规划模式
        other_complex_keywords = ["然后", "之后", "接着", "并且", "同时", "再",
                                   "分析", "可视化", "画图", "写", "撰写"]
        if not any(kw in text for kw in other_complex_keywords):
            return False  # 简单文献检索，不需要规划

    # 如果检测到多个工具，或者是复杂任务关键词，使用规划模式
    complex_keywords = [
        "帮我", "请帮", "我想", "我要", "能不能", "可以",
        "如何", "怎么", "怎样", "步骤", "流程",
        "分析", "研究", "调研", "综述", "报告"
    ]

    has_complex_keyword = any(kw in text for kw in complex_keywords)

    # 规则：
    # 1. 检测到 2+ 工具 → 规划模式
    # 2. 检测到 1 个工具 + 复杂关键词 + 不是简单文献检索 → 规划模式
    # 3. 文本较长（>80字）+ 2个以上工具 → 规划模式

    if len(tools) >= 2:
        return True
    if len(tools) == 1 and has_complex_keyword:
        # 额外检查：只有文献检索时，需要更强的复杂性指标
        if tools[0].type == ToolType.LITERATURE_SEARCH:
            return len(text) > 80  # 文献检索需要更长的文本才触发规划
        return True
    if len(text) > 80 and len(tools) >= 2:
        return True

    return False
