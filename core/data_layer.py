"""
GeoMind Core - Chainlit 数据层
实现对话历史持久化和恢复
"""

from typing import Optional, List, Dict, Any
from chainlit.data import BaseDataLayer
from chainlit.types import ThreadDict, Pagination, PageInfo, PaginatedResponse
from chainlit.user import User, PersistedUser
from chainlit.element import ElementDict
from chainlit.step import StepDict
import uuid
from datetime import datetime

from core.database import (
    get_user_by_id,
    create_conversation,
    get_user_conversations,
    get_conversation_messages,
    add_message,
    update_conversation_title,
    delete_conversation,
    _get_connection,
)


class GeoMindDataLayer(BaseDataLayer):
    """GeoMind 自定义数据层，使用 SQLite 存储对话历史"""

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        """根据 identifier 获取用户"""
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, created_at FROM users WHERE username = ?",
            (identifier,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return PersistedUser(
                id=str(row["id"]),
                identifier=row["username"],
                metadata={"email": row["email"]},
                createdAt=row["created_at"],
            )
        return None

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        """创建用户（已在 auth_callback 中处理）"""
        return await self.get_user(user.identifier)

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """获取对话详情"""
        conn = _get_connection()
        cursor = conn.cursor()

        # 获取对话信息
        cursor.execute(
            "SELECT id, user_id, title, created_at FROM conversations WHERE id = ?",
            (int(thread_id),)
        )
        conv_row = cursor.fetchone()
        if not conv_row:
            conn.close()
            return None

        # 获取用户信息
        cursor.execute(
            "SELECT username FROM users WHERE id = ?",
            (conv_row["user_id"],)
        )
        user_row = cursor.fetchone()
        conn.close()

        return ThreadDict(
            id=str(conv_row["id"]),
            name=conv_row["title"],
            createdAt=conv_row["created_at"],
            userId=str(conv_row["user_id"]),
            userIdentifier=user_row["username"] if user_row else None,
            metadata={},
            steps=[],
            tags=[],
        )

    async def create_thread(
        self,
        thread_id: Optional[str] = None,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[str]:
        """创建新对话"""
        if user_id:
            conv_id = create_conversation(int(user_id), name)
            return str(conv_id)
        return None

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        """更新对话"""
        if name:
            update_conversation_title(int(thread_id), name)

    async def delete_thread(self, thread_id: str):
        """删除对话"""
        delete_conversation(int(thread_id))

    async def list_threads(
        self,
        pagination: Pagination,
        filters: Dict,
    ) -> PaginatedResponse[ThreadDict]:
        """列出用户的对话历史"""
        user_id = filters.get("userId") or filters.get("user_id")
        if not user_id:
            return PaginatedResponse(
                data=[],
                pageInfo=PageInfo(hasNextPage=False, endCursor=None),
            )

        # 获取对话列表
        conversations = get_user_conversations(int(user_id), limit=50)

        threads = []
        for conv in conversations:
            threads.append(
                ThreadDict(
                    id=str(conv["id"]),
                    name=conv["title"],
                    createdAt=conv["created_at"],
                    userId=str(user_id),
                    userIdentifier=None,
                    metadata={},
                    steps=[],
                    tags=[],
                )
            )

        return PaginatedResponse(
            data=threads,
            pageInfo=PageInfo(hasNextPage=False, endCursor=None),
        )

    async def get_thread_author(self, thread_id: str) -> Optional[str]:
        """获取对话作者"""
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM conversations WHERE id = ?",
            (int(thread_id),)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return str(row["user_id"])
        return None

    async def create_step(self, step_dict: StepDict):
        """保存消息步骤"""
        thread_id = step_dict.get("threadId")
        step_type = step_dict.get("type")
        output = step_dict.get("output", "")

        if thread_id and step_type in ("user_message", "assistant_message"):
            role = "user" if step_type == "user_message" else "assistant"
            if output:
                add_message(int(thread_id), role, output)

    async def update_step(self, step_dict: StepDict):
        """更新步骤（暂不实现）"""
        pass

    async def delete_step(self, step_id: str):
        """删除步骤（暂不实现）"""
        pass

    async def get_element(self, thread_id: str, element_id: str) -> Optional[ElementDict]:
        """获取元素（暂不实现）"""
        return None

    async def create_element(self, element: ElementDict):
        """创建元素（暂不实现）"""
        pass

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        """删除元素（暂不实现）"""
        pass

    async def upsert_feedback(self, feedback: Any) -> str:
        """保存反馈（暂不实现）"""
        return str(uuid.uuid4())

    async def delete_feedback(self, feedback_id: str) -> bool:
        """删除反馈（暂不实现）"""
        return True

    async def build_debug_url(self) -> str:
        """调试 URL（暂不实现）"""
        return ""

    async def close(self):
        """关闭数据层连接"""
        pass

    async def get_favorite_steps(self, user_id: str) -> List[StepDict]:
        """获取用户收藏的步骤（暂不实现）"""
        return []
