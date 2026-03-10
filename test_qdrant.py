#!/usr/bin/env python3
"""
Qdrant 连接测试脚本
测试文献检索功能是否正常工作
"""

import asyncio
import os

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 手动读取 .env 文件
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

# 检查环境变量
print("=" * 60)
print("1. 检查环境变量")
print("=" * 60)

qdrant_url = os.getenv("QDRANT_URL", "")
qdrant_key = os.getenv("QDRANT_API_KEY", "")
collection = os.getenv("QDRANT_COLLECTION", "geomind_papers")

print(f"QDRANT_URL: {qdrant_url[:50]}..." if qdrant_url else "QDRANT_URL: ❌ 未设置")
print(f"QDRANT_API_KEY: {'✅ 已设置 (' + qdrant_key[:10] + '...)' if qdrant_key else '❌ 未设置'}")
print(f"QDRANT_COLLECTION: {collection}")

if not qdrant_url or not qdrant_key:
    print("\n❌ 环境变量未完整配置，请检查 .env 文件")
    exit(1)

# 测试 HTTP 连接
print("\n" + "=" * 60)
print("2. 测试 Qdrant HTTP 连接")
print("=" * 60)

import httpx

try:
    # 测试基本连接
    headers = {"api-key": qdrant_key}
    with httpx.Client(timeout=10.0) as client:
        # 获取集合信息
        resp = client.get(
            f"{qdrant_url.rstrip('/')}/collections/{collection}",
            headers=headers
        )

        if resp.status_code == 200:
            info = resp.json().get("result", {})
            print(f"✅ 连接成功！")
            print(f"   集合名称: {collection}")
            print(f"   向量数量: {info.get('points_count', 'N/A')}")
            print(f"   向量维度: {info.get('config', {}).get('params', {}).get('vectors', {}).get('size', 'N/A')}")
            print(f"   状态: {info.get('status', 'N/A')}")
        else:
            print(f"❌ 连接失败: HTTP {resp.status_code}")
            print(f"   响应: {resp.text[:200]}")
            exit(1)

except Exception as e:
    print(f"❌ 连接异常: {e}")
    exit(1)

# 测试 Embedding 模型
print("\n" + "=" * 60)
print("3. 测试 Embedding 模型")
print("=" * 60)

try:
    from fastembed import TextEmbedding
    model = TextEmbedding("BAAI/bge-base-en-v1.5")
    test_text = "dissolved oxygen prediction deep learning"
    embeddings = list(model.embed([test_text]))
    vector = embeddings[0].tolist()
    print(f"✅ Embedding 模型加载成功")
    print(f"   测试文本: '{test_text}'")
    print(f"   向量维度: {len(vector)}")
    print(f"   向量前5维: {vector[:5]}")
except ImportError:
    print("❌ fastembed 未安装，请运行: pip install fastembed")
    exit(1)
except Exception as e:
    print(f"❌ Embedding 错误: {e}")
    exit(1)

# 测试文献检索
print("\n" + "=" * 60)
print("4. 测试文献检索")
print("=" * 60)

async def test_search():
    from core.literature import search_papers

    test_queries = [
        "dissolved oxygen prediction deep learning",
        "water quality machine learning",
        "climate change",
    ]

    for query in test_queries:
        print(f"\n查询: '{query}'")
        result = await search_papers(query, limit=5, score_threshold=0.5)

        print(f"   成功: {result['success']}")
        print(f"   结果数: {result['total']}")
        print(f"   调试: {result.get('debug', 'N/A')}")

        if result.get("error"):
            print(f"   错误: {result['error']}")

        if result["papers"]:
            print(f"   前3篇论文:")
            for i, p in enumerate(result["papers"][:3], 1):
                print(f"      [{i}] {p['title'][:60]}... (score: {p['score']})")

if __name__ == "__main__":
    asyncio.run(test_search())

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
