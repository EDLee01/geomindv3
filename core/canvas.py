"""
GeoMind Core - Canvas 侧边栏模块

支持在侧边栏显示代码、Markdown、图片，并提供多格式下载
"""

import re
import io
import base64
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CanvasItem:
    """Canvas 内容项"""
    type: str  # "code", "markdown", "image", "table"
    content: str  # 原始内容或 base64 图片数据
    language: str = ""  # 代码语言
    title: str = ""  # 显示标题
    filename: str = ""  # 文件名
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


class CanvasManager:
    """
    Canvas 管理器

    管理当前会话的 Canvas 内容，支持：
    - 从 LLM 输出中提取代码块和 Markdown
    - 生成多种格式的下载文件
    - 追踪所有生成的内容
    """

    def __init__(self):
        self.items: List[CanvasItem] = []
        self.images: List[CanvasItem] = []  # 单独存储图片
        self._counter = 0

    def clear(self):
        """清空所有内容"""
        self.items = []
        self.images = []
        self._counter = 0

    def _generate_id(self, prefix: str = "item") -> str:
        """生成唯一 ID"""
        self._counter += 1
        return f"{prefix}_{self._counter}"

    # ============================================================
    # 内容提取
    # ============================================================

    def extract_from_response(self, response: str) -> List[CanvasItem]:
        """
        从 LLM 响应中提取可展示的内容

        提取：
        - ```language 代码块
        - Markdown 表格
        - 特殊标记的内容（如 [CANVAS:xxx]）
        """
        items = []

        # 提取代码块
        code_pattern = r'```(\w+)?\n(.*?)```'
        for match in re.finditer(code_pattern, response, re.DOTALL):
            language = match.group(1) or "text"
            code = match.group(2).strip()

            if len(code) > 10:  # 忽略太短的代码
                item = CanvasItem(
                    type="code",
                    content=code,
                    language=language,
                    title=self._guess_code_title(code, language),
                    filename=self._generate_filename(language),
                )
                items.append(item)
                self.items.append(item)

        # 提取 Markdown 表格
        table_pattern = r'(\|.+\|[\r\n]+\|[-:\| ]+\|[\r\n]+(?:\|.+\|[\r\n]*)+)'
        for match in re.finditer(table_pattern, response):
            table = match.group(1).strip()
            item = CanvasItem(
                type="table",
                content=table,
                title="数据表格",
                filename=f"table_{self._generate_id()}.md",
            )
            items.append(item)
            self.items.append(item)

        return items

    def add_image(self, image_data: str, filename: str = "") -> CanvasItem:
        """
        添加图片到 Canvas

        Args:
            image_data: base64 编码的图片数据
            filename: 文件名
        """
        if not filename:
            filename = f"figure_{self._generate_id()}.png"

        item = CanvasItem(
            type="image",
            content=image_data,
            title=filename.replace("_", " ").replace(".png", ""),
            filename=filename,
        )
        self.images.append(item)
        self.items.append(item)
        return item

    def add_markdown(self, content: str, title: str = "") -> CanvasItem:
        """添加 Markdown 内容"""
        item = CanvasItem(
            type="markdown",
            content=content,
            title=title or "Markdown 文档",
            filename=f"document_{self._generate_id()}.md",
        )
        self.items.append(item)
        return item

    def _guess_code_title(self, code: str, language: str) -> str:
        """根据代码内容猜测标题"""
        # Python 函数/类定义
        if language == "python":
            if match := re.search(r'def\s+(\w+)\s*\(', code):
                return f"函数: {match.group(1)}"
            if match := re.search(r'class\s+(\w+)', code):
                return f"类: {match.group(1)}"
            if "plt." in code or "matplotlib" in code:
                return "数据可视化代码"
            if "pd." in code or "pandas" in code:
                return "数据处理代码"

        # 通用
        lang_names = {
            "python": "Python",
            "javascript": "JavaScript",
            "js": "JavaScript",
            "typescript": "TypeScript",
            "ts": "TypeScript",
            "sql": "SQL 查询",
            "bash": "Shell 脚本",
            "r": "R 语言",
            "julia": "Julia",
        }
        return f"{lang_names.get(language, language.upper())} 代码"

    def _generate_filename(self, language: str) -> str:
        """根据语言生成文件名"""
        ext_map = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "sql": "sql",
            "bash": "sh",
            "r": "r",
            "julia": "jl",
            "json": "json",
            "yaml": "yaml",
            "markdown": "md",
            "html": "html",
            "css": "css",
        }
        ext = ext_map.get(language, "txt")
        return f"code_{self._generate_id()}.{ext}"

    # ============================================================
    # 格式转换 & 下载
    # ============================================================

    def to_markdown(self, items: List[CanvasItem] = None) -> str:
        """将所有内容转换为 Markdown 文档"""
        items = items or self.items
        if not items:
            return ""

        lines = [
            "# GeoMind 生成内容",
            f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        ]

        for i, item in enumerate(items, 1):
            lines.append(f"\n## {i}. {item.title}\n")

            if item.type == "code":
                lines.append(f"```{item.language}")
                lines.append(item.content)
                lines.append("```\n")
            elif item.type == "table":
                lines.append(item.content)
                lines.append("")
            elif item.type == "markdown":
                lines.append(item.content)
                lines.append("")
            elif item.type == "image":
                lines.append(f"![{item.title}]({item.filename})")
                lines.append("")

        return "\n".join(lines)

    def get_code_content(self, index: int = -1) -> Optional[str]:
        """获取指定索引的代码内容（默认最后一个）"""
        code_items = [item for item in self.items if item.type == "code"]
        if code_items:
            return code_items[index].content
        return None

    def get_latest_image(self) -> Optional[CanvasItem]:
        """获取最新的图片"""
        if self.images:
            return self.images[-1]
        return None

    def generate_downloads(self, item: CanvasItem) -> List[Tuple[str, bytes, str]]:
        """
        为单个内容项生成多种格式的下载

        Returns:
            List of (filename, content_bytes, mime_type)
        """
        downloads = []

        if item.type == "code":
            # 原始代码文件
            downloads.append((
                item.filename,
                item.content.encode("utf-8"),
                "text/plain"
            ))

            # Markdown 包装版本
            md_content = f"# {item.title}\n\n```{item.language}\n{item.content}\n```\n"
            downloads.append((
                item.filename.rsplit(".", 1)[0] + ".md",
                md_content.encode("utf-8"),
                "text/markdown"
            ))

        elif item.type == "image":
            # PNG 图片
            downloads.append((
                item.filename,
                base64.b64decode(item.content),
                "image/png"
            ))

            # 尝试生成 PDF（如果有 reportlab）
            pdf_bytes = self._image_to_pdf(item)
            if pdf_bytes:
                downloads.append((
                    item.filename.replace(".png", ".pdf"),
                    pdf_bytes,
                    "application/pdf"
                ))

        elif item.type in ("markdown", "table"):
            downloads.append((
                item.filename,
                item.content.encode("utf-8"),
                "text/markdown"
            ))

        return downloads

    def _image_to_pdf(self, item: CanvasItem) -> Optional[bytes]:
        """将图片转换为 PDF"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas as pdf_canvas
            from reportlab.lib.utils import ImageReader

            img_data = base64.b64decode(item.content)
            img_reader = ImageReader(io.BytesIO(img_data))

            buffer = io.BytesIO()
            c = pdf_canvas.Canvas(buffer, pagesize=A4)

            # 获取图片尺寸并适配 A4
            img_width, img_height = img_reader.getSize()
            page_width, page_height = A4

            # 计算缩放比例（保持宽高比，最大 90% 页面）
            scale = min(
                (page_width * 0.9) / img_width,
                (page_height * 0.8) / img_height
            )

            new_width = img_width * scale
            new_height = img_height * scale

            # 居中绘制
            x = (page_width - new_width) / 2
            y = (page_height - new_height) / 2

            # 添加标题
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(page_width / 2, page_height - 40, item.title)

            # 绘制图片
            c.drawImage(img_reader, x, y - 30, new_width, new_height)

            # 添加页脚
            c.setFont("Helvetica", 8)
            c.drawCentredString(
                page_width / 2, 30,
                f"Generated by GeoMind | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            c.save()
            return buffer.getvalue()

        except ImportError:
            return None
        except Exception:
            return None

    def generate_combined_pdf(self) -> Optional[bytes]:
        """生成包含所有内容的 PDF"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas as pdf_canvas
            from reportlab.lib.utils import ImageReader
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Preformatted
            from reportlab.lib.units import inch

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            # 标题
            story.append(Paragraph("GeoMind 生成报告", styles['Title']))
            story.append(Spacer(1, 0.5 * inch))

            for item in self.items:
                story.append(Paragraph(item.title, styles['Heading2']))
                story.append(Spacer(1, 0.2 * inch))

                if item.type == "code":
                    # 代码块
                    code_style = styles['Code']
                    story.append(Preformatted(item.content[:2000], code_style))

                elif item.type == "image":
                    # 图片
                    img_data = base64.b64decode(item.content)
                    img = Image(io.BytesIO(img_data), width=5*inch, height=4*inch)
                    story.append(img)

                elif item.type in ("markdown", "table"):
                    # 文本内容
                    story.append(Paragraph(item.content[:1000], styles['Normal']))

                story.append(Spacer(1, 0.3 * inch))

            doc.build(story)
            return buffer.getvalue()

        except ImportError:
            return None
        except Exception:
            return None


def extract_canvas_content(response: str) -> Dict:
    """
    从 LLM 响应中提取所有可 Canvas 化的内容

    Returns:
        {
            "code_blocks": [{"language": str, "code": str, "title": str}],
            "tables": [str],
            "has_content": bool
        }
    """
    result = {
        "code_blocks": [],
        "tables": [],
        "has_content": False
    }

    # 提取代码块
    code_pattern = r'```(\w+)?\n(.*?)```'
    for match in re.finditer(code_pattern, response, re.DOTALL):
        language = match.group(1) or "text"
        code = match.group(2).strip()
        if len(code) > 10:
            result["code_blocks"].append({
                "language": language,
                "code": code,
                "title": _guess_title(code, language)
            })

    # 提取表格
    table_pattern = r'(\|.+\|[\r\n]+\|[-:\| ]+\|[\r\n]+(?:\|.+\|[\r\n]*)+)'
    for match in re.finditer(table_pattern, response):
        result["tables"].append(match.group(1).strip())

    result["has_content"] = bool(result["code_blocks"] or result["tables"])
    return result


def _guess_title(code: str, language: str) -> str:
    """猜测代码标题"""
    if language == "python":
        if "plt." in code or "matplotlib" in code:
            return "数据可视化"
        if "pd." in code or "DataFrame" in code:
            return "数据处理"
        if match := re.search(r'def\s+(\w+)', code):
            return f"函数: {match.group(1)}"
    return f"{language.upper()} 代码"
