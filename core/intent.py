"""
GeoMind Core - 意图识别模块
将用户自然语言输入转化为结构化的意图，供系统自动执行
"""

import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class IntentType(Enum):
    """意图类型"""
    LITERATURE_SEARCH = "literature_search"  # 文献检索
    CODE_EXECUTION = "code_execution"        # 代码执行
    DATA_ANALYSIS = "data_analysis"          # 数据分析
    VISUALIZATION = "visualization"          # 可视化
    DIRECT_ANSWER = "direct_answer"          # 直接回答（闲聊、问答）
    PAPER_WRITING = "paper_writing"          # 论文写作辅助


@dataclass
class Intent:
    """结构化意图"""
    primary_intent: IntentType              # 主要意图
    search_query: Optional[str] = None      # 文献检索查询（英文优化）
    search_keywords: Optional[List[str]] = None  # 检索关键词
    needs_code: bool = False                # 是否需要代码执行
    needs_visualization: bool = False       # 是否需要可视化
    code_task: Optional[str] = None         # 代码任务描述
    confidence: float = 1.0                 # 置信度


# 意图识别的 System Prompt
INTENT_SYSTEM_PROMPT = """你是一个意图识别助手。分析用户输入，返回 JSON 格式的结构化意图。

## 可识别的意图类型：
- literature_search: 用户想要搜索/查找/检索论文、文献、参考资料
- code_execution: 用户想要执行代码、计算、编程
- data_analysis: 用户想要分析数据、统计
- visualization: 用户想要生成图表、可视化
- paper_writing: 用户想要写论文、撰写文档
- direct_answer: 简单问答、闲聊、解释概念（不需要调用任何工具）

## 重要规则：
1. 如果用户提到"论文"、"文献"、"检索"、"搜索论文"、"找论文"、"参考文献"，primary_intent 必须是 literature_search
2. search_query 应该是**英文**的学术检索词，从用户输入中提取核心概念并翻译
3. 如果用户同时需要多个功能，在相应字段标记 true
4. 只返回 JSON，不要有其他文字

## 返回格式（严格 JSON）：
```json
{
  "primary_intent": "literature_search",
  "search_query": "deep learning remote sensing image classification",
  "search_keywords": ["深度学习", "遥感", "影像分类"],
  "needs_code": false,
  "needs_visualization": false,
  "code_task": null,
  "confidence": 0.95
}
```"""


def get_intent_prompt(user_input: str) -> str:
    """生成意图识别的用户提示"""
    return f"""分析以下用户输入，返回结构化意图 JSON：

用户输入："{user_input}"

请返回 JSON（不要有其他内容）："""


def parse_intent_response(response: str) -> Optional[Intent]:
    """
    解析 LLM 返回的意图 JSON

    Args:
        response: LLM 返回的文本

    Returns:
        Intent 对象，解析失败返回 None
    """
    try:
        # 尝试提取 JSON（可能在 ```json 代码块中）
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析
            json_str = response.strip()
            # 移除可能的前后缀
            if json_str.startswith('{'):
                json_str = json_str[json_str.index('{'):]
            if '}' in json_str:
                json_str = json_str[:json_str.rindex('}')+1]

        data = json.loads(json_str)

        # 转换 intent 类型
        intent_type_str = data.get("primary_intent", "direct_answer")
        try:
            intent_type = IntentType(intent_type_str)
        except ValueError:
            intent_type = IntentType.DIRECT_ANSWER

        return Intent(
            primary_intent=intent_type,
            search_query=data.get("search_query"),
            search_keywords=data.get("search_keywords"),
            needs_code=data.get("needs_code", False),
            needs_visualization=data.get("needs_visualization", False),
            code_task=data.get("code_task"),
            confidence=data.get("confidence", 1.0)
        )

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[Intent] 解析失败: {e}")
        return None


def fallback_intent_detection(text: str) -> Intent:
    """
    基于关键词的后备意图检测（当 LLM 调用失败时使用）

    Args:
        text: 用户输入

    Returns:
        Intent 对象
    """
    text_lower = text.lower()

    # 文献检索关键词
    literature_keywords = [
        "文献", "论文", "检索", "搜索论文", "找论文", "参考文献", "引用",
        "literature", "paper", "search", "reference", "citation", "doi"
    ]

    # 代码执行关键词
    code_keywords = [
        "代码", "计算", "编程", "python", "执行", "运行", "code", "compute",
        "程序", "脚本"
    ]

    # 可视化关键词
    viz_keywords = [
        "图表", "画图", "可视化", "折线图", "散点图", "热力图", "柱状图",
        "plot", "chart", "visualization", "graph", "figure"
    ]

    # 数据分析关键词
    analysis_keywords = [
        "分析", "统计", "相关性", "回归", "analysis", "statistics",
        "correlation", "regression"
    ]

    # 检测主要意图
    needs_literature = any(kw in text_lower for kw in literature_keywords)
    needs_code = any(kw in text_lower for kw in code_keywords)
    needs_viz = any(kw in text_lower for kw in viz_keywords)
    needs_analysis = any(kw in text_lower for kw in analysis_keywords)

    # 确定主要意图
    if needs_literature:
        primary = IntentType.LITERATURE_SEARCH
    elif needs_analysis:
        primary = IntentType.DATA_ANALYSIS
    elif needs_viz:
        primary = IntentType.VISUALIZATION
    elif needs_code:
        primary = IntentType.CODE_EXECUTION
    else:
        primary = IntentType.DIRECT_ANSWER

    return Intent(
        primary_intent=primary,
        search_query=None,  # 后备方案不生成优化查询
        search_keywords=None,
        needs_code=needs_code or needs_analysis,
        needs_visualization=needs_viz,
        code_task=None,
        confidence=0.6  # 后备方案置信度较低
    )


def intent_to_dict(intent: Intent) -> Dict[str, Any]:
    """将 Intent 转换为字典"""
    result = asdict(intent)
    result["primary_intent"] = intent.primary_intent.value
    return result
