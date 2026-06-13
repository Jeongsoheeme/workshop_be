"""초기 admin 유저 생성 스크립트.

admin 유저는 API 로 만들 수 없으므로(권한 체크에 admin 이 필요) CLI 로 생성한다.
이미 같은 username 이 있으면 건너뛴다 (재실행 안전).

사용:
    python -m scripts.create_admin --username admin --password 1234 --nickname 운영자
    python -m scripts.create_admin            # 인자 없으면 대화형 입력
"""

import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def create_admin(username: str, password: str, nickname: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none() is not None:
            print(f"[skip] username '{username}' 은 이미 존재합니다.")
            return

        user = User(
            username=username,
            password=hash_password(password),
            nickname=nickname,
            role="admin",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"[created] admin 유저 생성 완료: id={user.id}, username='{username}', nickname='{nickname}'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="초기 admin 유저 생성")
    parser.add_argument("--username", help="로그인 ID")
    parser.add_argument("--password", help="비밀번호 (미지정 시 안전하게 입력받음)")
    parser.add_argument("--nickname", help="화면 표시 이름")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    username = args.username or input("username: ").strip()
    nickname = args.nickname or input("nickname: ").strip()
    password = args.password or getpass.getpass("password: ")

    if not username or not password or not nickname:
        raise SystemExit("username, password, nickname 은 모두 필수입니다.")

    asyncio.run(create_admin(username, password, nickname))


if __name__ == "__main__":
    main()
