"""
GeoMind Core - 文献检索模块
Qdrant REST API 直接调用（无需 torch/sentence-transformers）
"""

import httpx
import os
from typing import List, Dict, Optional


# ============================================================
# 配置
# ============================================================

QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "https://fd40a02c-5ba1-4d9c-b81a-78e5efef10a5.us-west-1-0.aws.cloud.qdrant.io:6333",
)
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "geomind_papers")

# Embedding 模型缓存
_embedding_model = None


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
    搜索 Qdrant 文献库

    Returns:
        {
            "success": bool,
            "papers": [...],
            "total": int,
            "error": str | None
        }
    """
    qdrant_url = QDRANT_URL.rstrip("/")
    qdrant_key = QDRANT_API_KEY

    if not qdrant_url or not qdrant_key:
        return {"success": False, "papers": [], "total": 0, "error": "Qdrant 未配置"}

    # 生成向量
    query_vector = _get_embedding(query)
    if query_vector is None:
        return {
            "success": False,
            "papers": [],
            "total": 0,
            "error": "Embedding 模型未安装。请运行: pip install fastembed",
        }

    # 调用 Qdrant REST API
    try:
        headers = {"Content-Type": "application/json", "api-key": qdrant_key}
        payload = {
            "vector": query_vector,
            "limit": limit,
            "score_threshold": score_threshold,
            "with_payload": True,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{qdrant_url}/collections/{COLLECTION_NAME}/points/search",
                headers=headers,
                json=payload,
            )

        if resp.status_code != 200:
            return {
                "success": False,
                "papers": [],
                "total": 0,
                "error": f"Qdrant 错误 ({resp.status_code}): {resp.text[:200]}",
            }

        results = resp.json().get("result", [])

        if not results:
            return {"success": True, "papers": [], "total": 0, "error": None}

        # 解析结果
        papers = []
        for hit in results:
            p = hit.get("payload", {})
            score = hit.get("score", 0)

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

            # DOI 已是完整 URL
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

        return {"success": True, "papers": papers, "total": len(papers), "error": None}

    except Exception as e:
        return {"success": False, "papers": [], "total": 0, "error": str(e)}


# ============================================================
# 格式化输出
# ============================================================

def format_papers_markdown(papers: List[Dict], max_display: int = 15) -> str:
    """将论文列表格式化为 Markdown"""
    if not papers:
        return "未找到相关文献。"

    lines = [f"### 📚 检索到 {len(papers)} 篇相关文献\n"]

    for i, p in enumerate(papers[:max_display], 1):
        # 基本信息
        line = f"**[{i}]** {p['author_display']} ({p['year']}). "
        line += f"*{p['title']}*. "
        line += f"{p['journal']}."

        # 附加信息
        extras = []
        if p.get("citations"):
            extras.append(f"引用: {p['citations']}")
        if p.get("impact_factor"):
            extras.append(f"IF: {p['impact_factor']}")
        if p.get("cas_zone"):
            extras.append(f"CAS {p['cas_zone']}区")
        if extras:
            line += f" ({', '.join(extras)})"

        # DOI 链接
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
