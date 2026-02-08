"""
GeoMind Core - 用户数据库模块
支持用户注册、登录和对话历史保存
适配 Chainlit 数据层（使用 UUID 作为 thread_id）
"""

import sqlite3
import hashlib
import json
import os
import uuid
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

    # 用户表（保持整数 ID，添加 uuid 字段用于 Chainlit）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    # 线程表（使用 UUID 作为主键，适配 Chainlit）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            user_identifier TEXT,
            name TEXT,
            metadata TEXT DEFAULT '{}',
            tags TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 步骤表（使用 UUID 作为主键，存储消息和其他步骤）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS steps (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            parent_id TEXT,
            name TEXT,
            type TEXT NOT NULL,
            input TEXT,
            output TEXT,
            metadata TEXT DEFAULT '{}',
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (thread_id) REFERENCES threads(id)
        )
    """)

    # 保留旧的 conversations 和 messages 表以兼容性（可选迁移）
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

    # 添加 uuid 列到现有用户表（如果不存在）
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN uuid TEXT")
    except sqlite3.OperationalError:
        pass  # 列已存在

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN metadata TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass  # 列已存在

    # 为没有 UUID 的现有用户生成 UUID
    cursor.execute("SELECT id FROM users WHERE uuid IS NULL")
    users_without_uuid = cursor.fetchall()
    for user in users_without_uuid:
        cursor.execute(
            "UPDATE users SET uuid = ? WHERE id = ?",
            (str(uuid.uuid4()), user["id"])
        )

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
        {"success": bool, "error": str | None, "user_id": int | None, "user_uuid": str | None}
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        password_hash = _hash_password(password)
        user_uuid = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO users (uuid, username, email, password_hash) VALUES (?, ?, ?, ?)",
            (user_uuid, username, email, password_hash)
        )
        conn.commit()
        return {
            "success": True,
            "error": None,
            "user_id": cursor.lastrowid,
            "user_uuid": user_uuid
        }

    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return {"success": False, "error": "用户名已存在", "user_id": None, "user_uuid": None}
        elif "email" in str(e):
            return {"success": False, "error": "邮箱已被注册", "user_id": None, "user_uuid": None}
        return {"success": False, "error": str(e), "user_id": None, "user_uuid": None}

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
        "SELECT id, uuid, username, email FROM users WHERE username = ? AND password_hash = ?",
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
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "username": row["username"],
            "email": row["email"]
        }

    conn.close()
    return None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """根据 ID 获取用户信息"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, uuid, username, email FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "username": row["username"],
            "email": row["email"]
        }
    return None


def get_user_by_identifier(identifier: str) -> Optional[Dict]:
    """根据 username（identifier）获取用户信息"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, uuid, username, email, created_at FROM users WHERE username = ?",
        (identifier,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "uuid": row["uuid"],
            "username": row["username"],
            "email": row["email"],
            "created_at": row["created_at"]
        }
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
# 线程管理（Chainlit 兼容）
# ============================================================

def create_thread(
    user_id: int,
    user_identifier: str = None,
    name: str = None,
    thread_id: str = None,
    metadata: Dict = None,
    tags: List[str] = None
) -> str:
    """创建新线程，返回线程 UUID"""
    conn = _get_connection()
    cursor = conn.cursor()

    if not thread_id:
        thread_id = str(uuid.uuid4())
    if not name:
        name = f"对话 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    cursor.execute(
        """INSERT INTO threads (id, user_id, user_identifier, name, metadata, tags)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            thread_id,
            user_id,
            user_identifier,
            name,
            json.dumps(metadata or {}),
            json.dumps(tags or [])
        )
    )
    conn.commit()
    conn.close()

    return thread_id


def get_thread(thread_id: str) -> Optional[Dict]:
    """获取线程信息"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT id, user_id, user_identifier, name, metadata, tags, created_at, updated_at
           FROM threads WHERE id = ?""",
        (thread_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "user_identifier": row["user_identifier"],
            "name": row["name"],
            "metadata": json.loads(row["metadata"] or "{}"),
            "tags": json.loads(row["tags"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    return None


def get_user_threads(user_id: int, limit: int = 50) -> List[Dict]:
    """获取用户的线程列表"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT id, user_id, user_identifier, name, metadata, tags, created_at, updated_at
           FROM threads
           WHERE user_id = ?
           ORDER BY updated_at DESC
           LIMIT ?""",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "user_identifier": row["user_identifier"],
            "name": row["name"],
            "metadata": json.loads(row["metadata"] or "{}"),
            "tags": json.loads(row["tags"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]


def update_thread(thread_id: str, name: str = None, metadata: Dict = None, tags: List[str] = None):
    """更新线程"""
    conn = _get_connection()
    cursor = conn.cursor()

    updates = ["updated_at = ?"]
    params = [datetime.now().isoformat()]

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if metadata is not None:
        updates.append("metadata = ?")
        params.append(json.dumps(metadata))
    if tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(tags))

    params.append(thread_id)
    cursor.execute(
        f"UPDATE threads SET {', '.join(updates)} WHERE id = ?",
        params
    )
    conn.commit()
    conn.close()


def delete_thread(thread_id: str):
    """删除线程及其所有步骤"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM steps WHERE thread_id = ?", (thread_id,))
    cursor.execute("DELETE FROM threads WHERE id = ?", (thread_id,))

    conn.commit()
    conn.close()


# ============================================================
# 步骤管理（Chainlit 兼容）
# ============================================================

def create_step(
    thread_id: str,
    step_type: str,
    name: str = None,
    step_id: str = None,
    parent_id: str = None,
    input_text: str = None,
    output_text: str = None,
    metadata: Dict = None,
    start_time: str = None,
    end_time: str = None
) -> str:
    """创建步骤，返回步骤 UUID"""
    conn = _get_connection()
    cursor = conn.cursor()

    if not step_id:
        step_id = str(uuid.uuid4())

    cursor.execute(
        """INSERT INTO steps (id, thread_id, parent_id, name, type, input, output, metadata, start_time, end_time)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            step_id,
            thread_id,
            parent_id,
            name,
            step_type,
            input_text,
            output_text,
            json.dumps(metadata or {}),
            start_time,
            end_time
        )
    )

    # 更新线程的更新时间
    cursor.execute(
        "UPDATE threads SET updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(), thread_id)
    )

    conn.commit()
    conn.close()

    return step_id


def get_thread_steps(thread_id: str) -> List[Dict]:
    """获取线程的所有步骤"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT id, thread_id, parent_id, name, type, input, output, metadata, start_time, end_time, created_at
           FROM steps
           WHERE thread_id = ?
           ORDER BY created_at ASC""",
        (thread_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "thread_id": row["thread_id"],
            "parent_id": row["parent_id"],
            "name": row["name"],
            "type": row["type"],
            "input": row["input"],
            "output": row["output"],
            "metadata": json.loads(row["metadata"] or "{}"),
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]


def update_step(step_id: str, output_text: str = None, end_time: str = None, metadata: Dict = None):
    """更新步骤"""
    conn = _get_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if output_text is not None:
        updates.append("output = ?")
        params.append(output_text)
    if end_time is not None:
        updates.append("end_time = ?")
        params.append(end_time)
    if metadata is not None:
        updates.append("metadata = ?")
        params.append(json.dumps(metadata))

    if updates:
        params.append(step_id)
        cursor.execute(
            f"UPDATE steps SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()

    conn.close()


def delete_step(step_id: str):
    """删除步骤"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM steps WHERE id = ?", (step_id,))
    conn.commit()
    conn.close()


# ============================================================
# 旧版对话管理（向后兼容）
# ============================================================

def create_conversation(user_id: int, title: str = None) -> int:
    """创建新对话，返回对话 ID（旧版兼容）"""
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
    """获取用户的对话列表（旧版兼容）"""
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
    """更新对话标题（旧版兼容）"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, datetime.now(), conversation_id)
    )
    conn.commit()
    conn.close()


def delete_conversation(conversation_id: int):
    """删除对话及其所有消息（旧版兼容）"""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    conn.commit()
    conn.close()


def add_message(conversation_id: int, role: str, content: str) -> int:
    """添加消息到对话（旧版兼容）"""
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
    """获取对话的所有消息（旧版兼容）"""
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
