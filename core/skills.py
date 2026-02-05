"""
GeoMind Core - Skills 技能管理器
加载 SKILL.md 文件，根据用户意图匹配对应技能
"""

import re
from pathlib import Path
from typing import List, Dict, Optional


class SkillsManager:
    """技能管理器：加载和匹配 Skills"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills: Dict[str, Dict] = {}
        self.load_skills()

    def load_skills(self):
        """加载所有 .md 文件"""
        if not self.skills_dir.exists():
            return

        for skill_file in self.skills_dir.rglob("*.md"):
            skill_name = skill_file.stem
            try:
                content = skill_file.read_text(encoding="utf-8")
                self.skills[skill_name] = {
                    "name": skill_name,
                    "path": str(skill_file),
                    "content": content,
                    "triggers": self._extract_triggers(content),
                }
            except Exception as e:
                print(f"加载 Skill 失败: {skill_file} - {e}")

    def _extract_triggers(self, content: str) -> List[str]:
        """从 SKILL.md 中提取触发词"""
        triggers = []
        match = re.search(r"## 触发条件\s*\n([\s\S]*?)(?=\n##|\Z)", content)
        if match:
            section = match.group(1)
            keywords = re.findall(r'["「](.*?)["」]', section)
            triggers.extend(keywords)
            items = re.findall(r'[-•]\s*.*?["「](.*?)["」]', section)
            triggers.extend(items)
        return triggers

    def get_skill(self, name: str) -> Optional[Dict]:
        """获取指定 Skill"""
        return self.skills.get(name)

    def get_skill_prompt(self, skill_name: str) -> str:
        """获取 Skill 的完整内容作为系统提示"""
        skill = self.skills.get(skill_name)
        if skill:
            return f"\n\n[SKILL INSTRUCTIONS]\n{skill['content']}\n[END SKILL]\n"
        return ""

    def match_skill(self, user_input: str) -> Optional[str]:
        """根据用户输入匹配最合适的 Skill"""
        user_lower = user_input.lower()

        keyword_skill_map = {
            # 文献相关
            ("文献", "论文", "搜索", "检索", "找", "@文献", "literature", "paper"): "literature_search",
            ("综述", "调研", "总结文献", "review"): "literature_review",
            ("gap", "空白", "研究方向", "选题"): "gap_analysis",
            # 方案
            ("方案", "方法", "技术路线", "怎么做", "methodology"): "methodology_design",
            # 数据
            ("预处理", "清洗", "处理数据", "preprocess"): "data_preprocess",
            ("统计", "相关性", "回归", "趋势", "statistic"): "statistical_analysis",
            # 图表
            ("画图", "图表", "可视化", "生成图", "visualization", "plot"): "visualization",
            # 写作
            ("results", "结果", "写结果"): "results_writing",
            ("discussion", "讨论", "写讨论"): "discussion_writing",
            ("参考文献", "引用", "bibtex", "reference"): "reference_format",
            ("翻译", "润色", "英文", "translate"): "translation",
            # 验证
            ("验证", "检查", "核实", "verify"): "verify_literature",
        }

        for keywords, skill_name in keyword_skill_map.items():
            if any(kw in user_lower for kw in keywords):
                return skill_name

        return None

    def list_skills(self) -> List[str]:
        """列出所有已加载的 Skill 名称"""
        return list(self.skills.keys())
