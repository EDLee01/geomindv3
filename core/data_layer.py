"""
GeoMind Core - Chainlit 数据层
实现对话历史持久化和恢复（使用 UUID 作为 thread_id）
"""

from typing import Optional, List, Dict, Any
from chainlit.data import BaseDataLayer
from chainlit.types import ThreadDict, Pagination, PageInfo, PaginatedResponse
from chainlit.user import User, PersistedUser
from chainlit.element import ElementDict
from chainlit.step import StepDict
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from core.database import (
    get_user_by_identifier,
    get_user_by_id,
    create_thread,
    get_thread,
    get_user_threads,
    update_thread,
    delete_thread,
    create_step,
    get_thread_steps,
    update_step,
    delete_step,
    _get_connection,
)


class GeoMindDataLayer(BaseDataLayer):
    """GeoMind 自定义数据层，使用 SQLite 存储对话历史"""

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        """根据 identifier 获取用户"""
        logger.info(f"[DATA_LAYER] get_user called: identifier={identifier}")
        print(f"[DATA_LAYER] get_user called: identifier={identifier}")

        user = get_user_by_identifier(identifier)
        if user:
            logger.info(f"[DATA_LAYER] User found: id={user['id']}, uuid={user['uuid']}, username={user['username']}")
            print(f"[DATA_LAYER] User found: id={user['id']}, uuid={user['uuid']}, username={user['username']}")
            return PersistedUser(
                id=user["uuid"],  # 使用 UUID 作为 Chainlit 的用户 ID
                identifier=user["username"],
                metadata={"email": user["email"], "db_id": user["id"]},
                createdAt=user["created_at"],
            )
        logger.warning(f"[DATA_LAYER] User not found: {identifier}")
        print(f"[DATA_LAYER] User not found: {identifier}")
        return None

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        """创建用户（已在 auth_callback 中处理）"""
        return await self.get_user(user.identifier)

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """获取对话详情"""
        thread = get_thread(thread_id)
        if not thread:
            return None

        # 获取线程的步骤
        steps = get_thread_steps(thread_id)
        step_dicts = []
        for step in steps:
            step_dicts.append(
                StepDict(
                    id=step["id"],
                    threadId=thread_id,
                    parentId=step["parent_id"],
                    name=step["name"] or "",
                    type=step["type"],
                    input=step["input"] or "",
                    output=step["output"] or "",
                    metadata=step["metadata"],
                    startTime=step["start_time"],
                    endTime=step["end_time"],
                    createdAt=step["created_at"],
                )
            )

        return ThreadDict(
            id=thread["id"],
            name=thread["name"],
            createdAt=thread["created_at"],
            userId=str(thread["user_id"]),
            userIdentifier=thread["user_identifier"],
            metadata=thread["metadata"],
            steps=step_dicts,
            tags=thread["tags"],
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
        logger.info(f"[DATA_LAYER] create_thread called: thread_id={thread_id}, name={name}, user_id={user_id}")
        print(f"[DATA_LAYER] create_thread called: thread_id={thread_id}, name={name}, user_id={user_id}")

        if not thread_id:
            thread_id = str(uuid.uuid4())

        # user_id 是 Chainlit 传入的（用户的 UUID），需要获取数据库中的整数 ID
        db_user_id = None
        user_identifier = None
        if user_id:
            # 尝试通过 UUID 查找用户
            conn = _get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM users WHERE uuid = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                db_user_id = row["id"]
                user_identifier = row["username"]
                logger.info(f"[DATA_LAYER] Found user: db_id={db_user_id}, username={user_identifier}")
                print(f"[DATA_LAYER] Found user: db_id={db_user_id}, username={user_identifier}")
            else:
                logger.warning(f"[DATA_LAYER] User not found by UUID: {user_id}")
                print(f"[DATA_LAYER] User not found by UUID: {user_id}")
            conn.close()

        if db_user_id:
            create_thread(
                user_id=db_user_id,
                user_identifier=user_identifier,
                name=name,
                thread_id=thread_id,
                metadata=metadata,
                tags=tags
            )
            logger.info(f"[DATA_LAYER] Thread created: {thread_id}")
            print(f"[DATA_LAYER] Thread created: {thread_id}")
        else:
            logger.warning(f"[DATA_LAYER] No db_user_id, thread NOT saved to database")
            print(f"[DATA_LAYER] No db_user_id, thread NOT saved to database")

        return thread_id

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        """更新对话"""
        update_thread(thread_id, name=name, metadata=metadata, tags=tags)

    async def delete_thread(self, thread_id: str):
        """删除对话"""
        delete_thread(thread_id)

    async def list_threads(
        self,
        pagination: Pagination,
        filters,
    ) -> PaginatedResponse[ThreadDict]:
        """列出用户的对话历史"""
        logger.info(f"[DATA_LAYER] list_threads called with filters: {filters}, type: {type(filters)}")
        print(f"[DATA_LAYER] list_threads called with filters: {filters}, type: {type(filters)}")

        # 获取 userId（Chainlit 传入的是用户 UUID）
        user_uuid = None
        if hasattr(filters, 'userId'):
            user_uuid = filters.userId
        elif isinstance(filters, dict):
            user_uuid = filters.get("userId")

        logger.info(f"[DATA_LAYER] Extracted user_uuid: {user_uuid}")
        print(f"[DATA_LAYER] Extracted user_uuid: {user_uuid}")

        # 通过 UUID 获取数据库用户 ID
        db_user_id = None
        if user_uuid:
            conn = _get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE uuid = ?", (user_uuid,))
            row = cursor.fetchone()
            conn.close()
            if row:
                db_user_id = row["id"]
                logger.info(f"Found db_user_id: {db_user_id}")

        if not db_user_id:
            logger.warning("No db_user_id found, returning empty list")
            return PaginatedResponse(
                data=[],
                pageInfo=PageInfo(
                    hasNextPage=False,
                    startCursor=None,
                    endCursor=None
                ),
            )

        # 获取线程列表
        threads = get_user_threads(db_user_id, limit=50)
        logger.info(f"Found {len(threads)} threads for user {db_user_id}")

        thread_dicts = []
        for thread in threads:
            thread_dicts.append(
                ThreadDict(
                    id=thread["id"],
                    name=thread["name"],
                    createdAt=thread["created_at"],
                    userId=user_uuid,
                    userIdentifier=thread["user_identifier"],
                    metadata=thread["metadata"],
                    steps=[],
                    tags=thread["tags"],
                )
            )

        return PaginatedResponse(
            data=thread_dicts,
            pageInfo=PageInfo(
                hasNextPage=False,
                startCursor=None,
                endCursor=None
            ),
        )

    async def get_thread_author(self, thread_id: str) -> Optional[str]:
        """获取对话作者"""
        thread = get_thread(thread_id)
        if thread:
            return thread["user_identifier"]
        return None

    async def create_step(self, step_dict: StepDict):
        """保存消息步骤"""
        thread_id = step_dict.get("threadId")
        step_id = step_dict.get("id")
        step_type = step_dict.get("type")
        name = step_dict.get("name")
        input_text = step_dict.get("input")
        output_text = step_dict.get("output")
        parent_id = step_dict.get("parentId")
        metadata = step_dict.get("metadata", {})
        start_time = step_dict.get("startTime")
        end_time = step_dict.get("endTime")

        if thread_id:
            create_step(
                thread_id=thread_id,
                step_type=step_type,
                name=name,
                step_id=step_id,
                parent_id=parent_id,
                input_text=input_text,
                output_text=output_text,
                metadata=metadata,
                start_time=start_time,
                end_time=end_time
            )

    async def update_step(self, step_dict: StepDict):
        """更新步骤"""
        step_id = step_dict.get("id")
        output_text = step_dict.get("output")
        end_time = step_dict.get("endTime")
        metadata = step_dict.get("metadata")

        if step_id:
            update_step(step_id, output_text=output_text, end_time=end_time, metadata=metadata)

    async def delete_step(self, step_id: str):
        """删除步骤"""
        delete_step(step_id)

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
