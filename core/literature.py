"""
GeoMind Core - 文献检索模块
使用 qdrant-client 官方库（替代 httpx REST API）
"""

import os
from typing import List, Dict, Optional
from qdrant_client import QdrantClient

# ============================================================
# 配置
# ============================================================

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "geomind_papers")

# 缓存
_embedding_model = None
_qdrant_client: Optional[QdrantClient] = None


# ============================================================
# Qdrant Client 单例
# ============================================================

def _get_qdrant_client() -> Optional[QdrantClient]:
    """获取/复用 Qdrant 客户端"""
    global _qdrant_client

    if _qdrant_client is not None:
        return _qdrant_client

    qdrant_url = QDRANT_URL.rstrip("/")
    if not qdrant_url:
        return None

    _qdrant_client = QdrantClient(
        url=qdrant_url,
        api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
        timeout=30,
    )
    return _qdrant_client


# ============================================================
# Embedding
# ============================================================

def _get_embedding(text: str) -> Optional[List[float]]:
    """生成查询向量 (768 维, BGE-base-en-v1.5)"""
    global _embedding_model

    # 方案 1: fastembed（轻量，推荐）
    try:
        from fastembed import TextEmbedding

        if _embedding_model is None:
            _embedding_model = TextEmbedding("BAAI/bge-base-en-v1.5")
        embeddings = list(_embedding_model.embed([text]))
        return embeddings[0].tolist()
    except ImportError:
        pass

    # 方案 2: sentence-transformers
    try:
        from sentence_transformers import SentenceTransformer

        if _embedding_model is None:
            _embedding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")
        return _embedding_model.encode(text).tolist()
    except ImportError:
        pass

    return None


# ============================================================
# 文献检索
# ============================================================

async def search_papers(
    query: str,
    limit: int = 15,
    score_threshold: float = 0.5,
) -> Dict:
    """
    搜索 Qdrant 文献库（使用 qdrant-client）

    Returns:
        {
            "success": bool,
            "papers": [...],
            "total": int,
            "error": str | None,
            "debug": str | None
        }
    """
    debug_info = f"URL配置: {'✅' if QDRANT_URL else '❌'}, KEY配置: {'✅' if QDRANT_API_KEY else '❌'}, Collection: {COLLECTION_NAME}"

    # 获取客户端
    client = _get_qdrant_client()
    if client is None:
        return {
            "success": False,
            "papers": [],
            "total": 0,
            "error": "Qdrant 未配置。请设置 QDRANT_URL 和 QDRANT_API_KEY 环境变量。",
            "debug": debug_info,
        }

    # 生成向量
    query_vector = _get_embedding(query)
    if query_vector is None:
        return {
            "success": False,
            "papers": [],
            "total": 0,
            "error": "Embedding 模型未安装。请运行: pip install fastembed",
            "debug": debug_info,
        }

    debug_info += f", Query: '{query[:50]}...', Vector dim: {len(query_vector)}"

    # 调用 qdrant-client 搜索
    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            score_threshold=score_threshold,
        )

        hits = results.points
        debug_info += f", Raw results: {len(hits)}"

        if not hits:
            return {
                "success": True,
                "papers": [],
                "total": 0,
                "error": None,
                "debug": debug_info + " (无结果，可能是阈值太高或查询词不匹配)",
            }

        # 解析结果
        papers = []
        for hit in hits:
            p = hit.payload or {}
            score = hit.score or 0

            # 作者处理
            authors_raw = p.get("authors", [])
            if isinstance(authors_raw, str):
                authors_raw = [authors_raw]
            author_names = []
            for a in authors_raw[:5]:
                if isinstance(a, dict):
                    author_names.append(
                        a.get("name", a.get("display_name", "Unknown"))
                    )
                else:
                    author_names.append(str(a))

            # 作者显示
            if len(author_names) == 0:
                author_display = "Unknown"
            elif len(author_names) <= 2:
                author_display = " & ".join(author_names)
            else:
                author_display = f"{author_names[0]} et al."

            doi = (p.get("doi", "") or "").strip()

            papers.append(
                {
                    "title": p.get("title", "Untitled"),
                    "authors": author_names,
                    "author_display": author_display,
                    "year": p.get("year", 0),
                    "journal": p.get("journal_name", "") or "Unknown",
                    "doi": doi,
                    "citations": p.get("cited_by_count", 0),
                    "impact_factor": p.get("impact_factor", 0),
                    "cas_zone": p.get("cas_zone", ""),
                    "abstract": (p.get("abstract", "") or "")[:400],
                    "score": round(score, 3),
                }
            )

        debug_info += f", Filtered papers: {len(papers)}"
        return {
            "success": True,
            "papers": papers,
            "total": len(papers),
            "error": None,
            "debug": debug_info,
        }

    except Exception as e:
        return {
            "success": False,
            "papers": [],
            "total": 0,
            "error": str(e),
            "debug": debug_info,
        }


# ============================================================
# 格式化输出
# ============================================================

def format_papers_markdown(papers: List[Dict], max_display: int = 15) -> str:
    """将论文列表格式化为 Markdown"""
    if not papers:
        return "未找到相关文献。"

    lines = [f"### 📚 检索到 {len(papers)} 篇相关文献\n"]

    for i, p in enumerate(papers[:max_display], 1):
        line = f"**[{i}]** {p['author_display']} ({p['year']}). "
        line += f"*{p['title']}*. "
        line += f"{p['journal']}."

        extras = []
        if p.get("citations"):
            extras.append(f"引用: {p['citations']}")
        if p.get("impact_factor"):
            extras.append(f"IF: {p['impact_factor']}")
        if p.get("cas_zone"):
            extras.append(f"CAS {p['cas_zone']}区")
        if extras:
            line += f" ({', '.join(extras)})"

        if p.get("doi"):
            line += f"\n   🔗 [DOI]({p['doi']})"

        line += f"  |  相关度: {p.get('score', 0)}"
        lines.append(line)

    return "\n\n".join(lines)


def format_papers_bibtex(papers: List[Dict]) -> str:
    """将论文列表导出为 BibTeX"""
    entries = []
    for p in papers:
        first_author = (
            p["authors"][0].split()[-1] if p.get("authors") else "Unknown"
        )
        key = f"{first_author}{p.get('year', 0)}"
        authors_str = " and ".join(p.get("authors", ["Unknown"]))

        entry = f"""@article{{{key},
  title = {{{p.get('title', '')}}},
  author = {{{authors_str}}},
  year = {{{p.get('year', 0)}}},
  journal = {{{p.get('journal', '')}}},
  doi = {{{p.get('doi', '')}}}
}}"""
        entries.append(entry)

    return "\n\n".join(entries)
