"""
GeoMind Core - Project Memory
跨对话持久化数据（当前为内存版，后续可接 SQLite/PostgreSQL）
"""

from typing import Dict, Any, Optional


class ProjectMemory:
    """项目记忆：存储跨对话的研究数据"""

    def __init__(self, project_id: str, name: str = "", topic: str = ""):
        self.project_id = project_id
        self.name = name
        self.topic = topic
        self.data = {
            "literature_list": [],
            "gap_candidates": [],
            "gap_selected": None,
            "methodology": {},
            "data_profile": {},
            "analysis_results": {},
            "figures": [],
            "tables": [],
            "sections": {
                "introduction": "",
                "methods": "",
                "results": "",
                "discussion": "",
                "conclusion": "",
            },
            "references_bibtex": "",
        }

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value

    def update(self, updates: Dict):
        for key, value in updates.items():
            self.data[key] = value

    def to_context(self) -> str:
        """将 Memory 转换为 LLM 上下文字符串"""
        parts = []

        if self.name:
            parts.append(f"[项目: {self.name}]")
        if self.topic:
            parts.append(f"[研究主题: {self.topic}]")

        lit = self.data.get("literature_list", [])
        if lit:
            parts.append(f"[已收集文献: {len(lit)} 篇]")

        gap = self.data.get("gap_selected")
        if gap:
            parts.append(f"[已选择研究方向: {gap}]")

        method = self.data.get("methodology", {}).get("name")
        if method:
            parts.append(f"[研究方案: {method}]")

        profile = self.data.get("data_profile", {})
        if profile:
            parts.append(
                f"[数据概况: {profile.get('rows', 0)} 行 × {profile.get('columns', 0)} 列]"
            )

        if self.data.get("analysis_results"):
            parts.append("[已完成数据分析]")

        figs = self.data.get("figures", [])
        if figs:
            parts.append(f"[已生成图表: {len(figs)} 个]")

        written = [
            k for k, v in self.data.get("sections", {}).items() if v
        ]
        if written:
            parts.append(f"[已撰写章节: {', '.join(written)}]")

        return "\n".join(parts) if parts else "[项目刚开始，尚无进展]"
