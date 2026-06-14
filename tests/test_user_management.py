"""유저 생성/관리 API 테스트."""

import uuid


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_user(client, admin_headers, **overrides):
    payload = {
        "username": _unique("u"),
        "password": "pw12345678",
        "nickname": "참가자",
        "role": "user",
    }
    payload.update(overrides)
    return await client.post("/api/users", json=payload, headers=admin_headers)


async def test_create_user(client, admin_headers):
    res = await _create_user(client, admin_headers, nickname="홍길동")
    assert res.status_code == 201
    body = res.json()
    assert body["nickname"] == "홍길동"
    assert body["role"] == "user"
    assert body["point"] == 0
    assert "password" not in body  # 비밀번호는 응답에 노출되지 않음


async def test_create_duplicate_username_conflict(client, admin_headers):
    username = _unique("dup")
    first = await _create_user(client, admin_headers, username=username)
    assert first.status_code == 201
    second = await _create_user(client, admin_headers, username=username)
    assert second.status_code == 409


async def test_create_invalid_role_422(client, admin_headers):
    res = await _create_user(client, admin_headers, role="superadmin")
    assert res.status_code == 422


async def test_list_and_filter(client, admin_headers):
    res = await _create_user(client, admin_headers, role="user")
    created_id = res.json()["id"]

    res = await client.get("/api/users", headers=admin_headers)
    assert res.status_code == 200
    assert any(u["id"] == created_id for u in res.json())

    res = await client.get("/api/users", params={"role": "user"}, headers=admin_headers)
    assert all(u["role"] == "user" for u in res.json())


async def test_get_user_404(client, admin_headers):
    res = await client.get("/api/users/99999999", headers=admin_headers)
    assert res.status_code == 404


async def test_update_fields(client, admin_headers):
    user_id = (await _create_user(client, admin_headers)).json()["id"]
    res = await client.patch(
        f"/api/users/{user_id}",
        json={"nickname": "수정됨", "point": 50, "role": "admin"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["nickname"] == "수정됨"
    assert body["point"] == 50
    assert body["role"] == "admin"
    assert body["updated_at"] is not None


async def test_update_password_then_login(client, admin_headers):
    username = _unique("pw")
    user_id = (
        await _create_user(client, admin_headers, username=username, password="oldpw123")
    ).json()["id"]

    # 비밀번호 변경
    res = await client.patch(
        f"/api/users/{user_id}", json={"password": "newpw456"}, headers=admin_headers
    )
    assert res.status_code == 200

    # 새 비밀번호로 로그인 성공, 옛 비밀번호는 실패
    ok = await client.post(
        "/api/auth/login", data={"username": username, "password": "newpw456"}
    )
    assert ok.status_code == 200
    bad = await client.post(
        "/api/auth/login", data={"username": username, "password": "oldpw123"}
    )
    assert bad.status_code == 401


async def test_assign_team_membership(client, admin_headers):
    # 시즌 + 팀 준비
    season = await client.post(
        "/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers
    )
    season_id = season.json()["id"]
    team = await client.post(
        f"/api/seasons/{season_id}/teams", json={"name": "팀A"}, headers=admin_headers
    )
    team_id = team.json()["id"]
    user_id = (await _create_user(client, admin_headers)).json()["id"]

    # 멤버십 배정
    res = await client.post(
        f"/api/seasons/{season_id}/teams/{team_id}/members",
        json={"user_id": user_id},
        headers=admin_headers,
    )
    assert res.status_code == 201
    assert res.json() == {"user_id": user_id, "team_id": team_id}

    # 시즌 멤버십 현황에 반영
    members = (
        await client.get(f"/api/seasons/{season_id}/members", headers=admin_headers)
    ).json()
    assert {"user_id": user_id, "team_id": team_id} in members

    # 팀 멤버 목록에도 반영
    team_members = (
        await client.get(f"/api/teams/{team_id}/members", headers=admin_headers)
    ).json()
    assert any(m["id"] == user_id for m in team_members)

    # 해제
    res = await client.delete(
        f"/api/seasons/{season_id}/members/{user_id}", headers=admin_headers
    )
    assert res.status_code == 204
    members = (
        await client.get(f"/api/seasons/{season_id}/members", headers=admin_headers)
    ).json()
    assert all(m["user_id"] != user_id for m in members)


async def test_create_requires_admin(client, user_headers):
    res = await client.post(
        "/api/users",
        json={"username": "x", "password": "pw", "nickname": "x", "role": "user"},
        headers=user_headers,
    )
    assert res.status_code == 403


async def test_list_requires_admin(client, user_headers):
    res = await client.get("/api/users", headers=user_headers)
    assert res.status_code == 403
