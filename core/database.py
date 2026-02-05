"""
GeoMind Core - 用户数据库模块
支持用户注册、登录和对话历史保存
"""

import sqlite3
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

# 数据库路径
DB_PATH = os.getenv("GEOMIND_DB_PATH", "data/geomind.db")


def _get_db_path() -> Path:
    """获取数据库路径并确保目录存在"""
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """初始化数据库表"""
    conn = _get_connection()
    cursor = conn.cursor()

    # 用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    # 对话表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 消息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# 密码哈希
# ============================================================

def _hash_password(password: str) -> str:
    """哈希密码"""
    return hashlib.sha256(password.encode()).hexdigest()


# ============================================================
# 用户管理
# ============================================================

def create_user(username: str, email: str, password: str) -> Dict:
    """
    创建新用户

    Returns:
        {"success": bool, "error": str | None, "user_id": int | None}
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        password_hash = _hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash)
        )
        conn.commit()
        return {"success": True, "error": None, "user_id": cursor.lastrowid}

    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return {"success": False, "error": "用户名已存在", "user_id": None}
        elif "email" in str(e):
            return {"success": False, "error": "邮箱已被注册", "user_id": None}
        return {"success": False, "error": str(e), "user_id": None}

    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    验证用户登录

    Returns:
        用户信息 dict 或 None（验证失败）
    """
    conn = _get_connection()
    cursor = conn.cursor()

    password_hash = _hash_password(password)
    cursor.execute(
        "SELECT id, username, email FROM users WHERE username = ? AND password_hash = ?",
        (username, password_hash)
    )
    row = cursor.fetchone()

    if row:
        # 更新最后登录时间
        cursor.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now(), row["id"])
        )
        conn.commit()
        conn.close()
        return {"id": row["id"], "username": row["username"], "email": row["email"]}

    conn.close()
    return None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """根据 ID 获取用户信息"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, username, email FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {"id": row["id"], "username": row["username"], "email": row["email"]}
    return None


def user_exists(username: str) -> bool:
    """检查用户名是否已存在"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    exists = cursor.fetchone() is not None
    conn.close()

    return exists


# ============================================================
# 对话管理
# ============================================================

def create_conversation(user_id: int, title: str = None) -> int:
    """创建新对话，返回对话 ID"""
    conn = _get_connection()
    cursor = conn.cursor()

    if not title:
        title = f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    cursor.execute(
        "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
        (user_id, title)
    )
    conn.commit()
    conversation_id = cursor.lastrowid
    conn.close()

    return conversation_id


def get_user_conversations(user_id: int, limit: int = 20) -> List[Dict]:
    """获取用户的对话列表"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def update_conversation_title(conversation_id: int, title: str):
    """更新对话标题"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, datetime.now(), conversation_id)
    )
    conn.commit()
    conn.close()


def delete_conversation(conversation_id: int):
    """删除对话及其所有消息"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    conn.commit()
    conn.close()


# ============================================================
# 消息管理
# ============================================================

def add_message(conversation_id: int, role: str, content: str) -> int:
    """添加消息到对话"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conversation_id, role, content)
    )

    # 更新对话的更新时间
    cursor.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (datetime.now(), conversation_id)
    )

    conn.commit()
    message_id = cursor.lastrowid
    conn.close()

    return message_id


def get_conversation_messages(conversation_id: int) -> List[Dict]:
    """获取对话的所有消息"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, role, content, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
        """,
        (conversation_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


# 初始化数据库（模块加载时执行）
init_database()
