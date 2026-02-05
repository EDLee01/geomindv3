#!/usr/bin/env python3
"""
GeoMind 用户管理工具

用法:
    python scripts/create_user.py                    # 交互模式
    python scripts/create_user.py add <用户名>       # 添加用户
    python scripts/create_user.py list               # 列出所有用户
    python scripts/create_user.py delete <用户名>    # 删除用户
    python scripts/create_user.py hash <密码>        # 生成密码哈希
"""

import sys
import json
import hashlib
import getpass
from pathlib import Path

USERS_FILE = Path(__file__).parent.parent / "users.json"


def hash_password(password: str) -> str:
    """SHA256 哈希密码"""
    return hashlib.sha256(password.encode()).hexdigest()


def load_users() -> dict:
    """加载用户数据"""
    if USERS_FILE.exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users: dict):
    """保存用户数据"""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)
    print(f"已保存到 {USERS_FILE}")


def add_user(username: str = None, password: str = None, role: str = "user", name: str = None):
    """添加新用户"""
    users = load_users()

    if not username:
        username = input("用户名: ").strip()

    if username in users:
        overwrite = input(f"用户 '{username}' 已存在，是否覆盖? (y/N): ")
        if overwrite.lower() != 'y':
            print("已取消")
            return

    if not password:
        password = getpass.getpass("密码: ")
        confirm = getpass.getpass("确认密码: ")
        if password != confirm:
            print("密码不匹配")
            return

    if not name:
        name = input(f"显示名称 (默认: {username}): ").strip() or username

    if not role:
        role = input("角色 (admin/user, 默认: user): ").strip() or "user"

    users[username] = {
        "password": hash_password(password),
        "role": role,
        "name": name
    }

    save_users(users)
    print(f"用户 '{username}' 已创建 (角色: {role})")


def list_users():
    """列出所有用户"""
    users = load_users()
    if not users:
        print("暂无用户")
        return

    print("\n用户列表:")
    print("-" * 50)
    for username, data in users.items():
        print(f"  {username:<15} | {data.get('name', '-'):<15} | {data.get('role', 'user')}")
    print("-" * 50)
    print(f"共 {len(users)} 个用户\n")


def delete_user(username: str):
    """删除用户"""
    users = load_users()
    if username not in users:
        print(f"用户 '{username}' 不存在")
        return

    confirm = input(f"确定删除用户 '{username}'? (y/N): ")
    if confirm.lower() == 'y':
        del users[username]
        save_users(users)
        print(f"用户 '{username}' 已删除")
    else:
        print("已取消")


def show_hash(password: str):
    """显示密码哈希"""
    print(f"密码: {password}")
    print(f"SHA256: {hash_password(password)}")


def main():
    if len(sys.argv) < 2:
        # 交互模式
        print("\nGeoMind 用户管理工具")
        print("=" * 40)
        print("1. 添加用户")
        print("2. 列出用户")
        print("3. 删除用户")
        print("4. 生成密码哈希")
        print("0. 退出")
        print("=" * 40)

        choice = input("\n请选择操作 (0-4): ").strip()

        if choice == "1":
            add_user()
        elif choice == "2":
            list_users()
        elif choice == "3":
            username = input("要删除的用户名: ").strip()
            delete_user(username)
        elif choice == "4":
            password = getpass.getpass("输入密码: ")
            show_hash(password)
        elif choice == "0":
            print("退出")
        else:
            print("无效选择")
        return

    # 命令行模式
    cmd = sys.argv[1].lower()

    if cmd == "add":
        username = sys.argv[2] if len(sys.argv) > 2 else None
        add_user(username)
    elif cmd == "list":
        list_users()
    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("用法: python create_user.py delete <用户名>")
            return
        delete_user(sys.argv[2])
    elif cmd == "hash":
        if len(sys.argv) < 3:
            password = getpass.getpass("输入密码: ")
        else:
            password = sys.argv[2]
        show_hash(password)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
