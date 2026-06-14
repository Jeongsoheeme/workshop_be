"""테스트 공통 픽스처.

핵심: **실제 운영 DB(workshop_26)를 건드리지 않도록** 테스트 전용 DB
(workshop_26_test)로 격리한다. app 모듈을 import 하기 전에 환경변수
DATABASE_URL 을 테스트 DB 로 덮어쓰므로, 앱 엔진 / AsyncSessionLocal /
get_db 의존성은 물론 테스트가 직접 쓰는 세션까지 모두 테스트 DB 를 바라본다.

테스트 DB 는 세션 시작 시 drop_all + create_all 로 깨끗하게 초기화된다.
TEST_DATABASE_NAME 환경변수로 DB 이름을 바꿀 수 있다(기본: <원본>_test).
"""

import asyncio
import os

from sqlalchemy import make_url

# ---------------------------------------------------------------------------
# 1. app import 전에 DATABASE_URL 을 테스트 DB 로 강제한다.
# ---------------------------------------------------------------------------
def _resolve_test_url() -> tuple["make_url", "make_url", str]:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        from dotenv import dotenv_values

        raw = dotenv_values(".env").get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL 을 .env 또는 환경변수에서 찾을 수 없습니다.")
    orig = make_url(raw)
    test_name = os.environ.get("TEST_DATABASE_NAME", f"{orig.database}_test")
    test_url = orig.set(database=test_name)
    return orig, test_url, test_name


_ORIG_URL, _TEST_URL, _TEST_NAME = _resolve_test_url()
os.environ["DATABASE_URL"] = _TEST_URL.render_as_string(hide_password=False)

# 이제 app 모듈을 import 하면 테스트 DB 기준 엔진이 만들어진다.
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin1234"
USER_USERNAME = "tester"
USER_PASSWORD = "tester1234"


# ---------------------------------------------------------------------------
# 2. 테스트 DB 생성 + 스키마 초기화 (수집 전에 1회)
# ---------------------------------------------------------------------------
async def _create_database_if_missing() -> None:
    import asyncpg

    conn = await asyncpg.connect(
        host=_ORIG_URL.host,
        port=_ORIG_URL.port,
        user=_ORIG_URL.username,
        password=_ORIG_URL.password,
        database=_ORIG_URL.database,  # 임의의 기존 DB 에서 CREATE DATABASE 실행
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", _TEST_NAME
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{_TEST_NAME}"')
    finally:
        await conn.close()


async def _reset_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()  # 부트스트랩 루프에 묶인 커넥션 정리


def _bootstrap() -> None:
    asyncio.run(_create_database_if_missing())
    asyncio.run(_reset_schema())


_bootstrap()


# ---------------------------------------------------------------------------
# 3. 픽스처
# ---------------------------------------------------------------------------
async def _ensure_user(username: str, password: str, role: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none() is None:
            db.add(
                User(
                    username=username,
                    password=hash_password(password),
                    nickname=username,
                    role=role,
                )
            )
            await db.commit()


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine():
    """테스트마다 엔진 커넥션 풀을 정리해 'Event loop is closed' 경고를 막는다.

    async 엔진은 테스트별 이벤트 루프에 묶이므로, 루프가 닫히기 전(픽스처 teardown)에
    같은 루프에서 dispose 해야 풀링된 커넥션이 깨끗하게 닫힌다.
    """
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def seeded_admin() -> dict[str, str]:
    """admin 유저가 없으면 생성한다 (재실행 안전)."""
    await _ensure_user(ADMIN_USERNAME, ADMIN_PASSWORD, "admin")
    return {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}


@pytest_asyncio.fixture
async def seeded_user() -> dict[str, str]:
    """일반(user) 권한 유저."""
    await _ensure_user(USER_USERNAME, USER_PASSWORD, "user")
    return {"username": USER_USERNAME, "password": USER_PASSWORD}


async def _login_token(client: AsyncClient, creds: dict[str, str]) -> str:
    res = await client.post("/api/auth/login", data=creds)
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, seeded_admin) -> dict[str, str]:
    token = await _login_token(client, seeded_admin)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_headers(client: AsyncClient, seeded_user) -> dict[str, str]:
    token = await _login_token(client, seeded_user)
    return {"Authorization": f"Bearer {token}"}
