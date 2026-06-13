"""검증 가능한 룰렛/추첨 로직 테스트."""

import hashlib
import uuid

from app.services import roulette_service


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ----- 순수 함수 (결정론) -----

def test_commitment_is_sha256():
    seed = "deadbeef"
    assert roulette_service.commitment(seed) == hashlib.sha256(seed.encode()).hexdigest()


def test_draw_is_deterministic():
    seed = "abc123"
    # 같은 (seed, nonce) → 항상 같은 결과
    assert roulette_service.draw_index(seed, 1, 10) == roulette_service.draw_index(seed, 1, 10)
    assert roulette_service.draw_float(seed, 7) == roulette_service.draw_float(seed, 7)


def test_draw_index_in_range():
    seed = "xyz"
    for nonce in range(100):
        idx = roulette_service.draw_index(seed, nonce, 5)
        assert 0 <= idx < 5


def test_draw_float_in_unit_interval():
    seed = "s"
    for nonce in range(100):
        v = roulette_service.draw_float(seed, nonce)
        assert 0.0 <= v < 1.0


# ----- API (commit-reveal 흐름) -----

async def _started_session(client, admin_headers) -> int:
    """세션을 만들고 in_progress 까지 전이시켜 seed 를 생성한다."""
    season_id = (
        await client.post("/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers)
    ).json()["id"]
    game_id = (
        await client.post(
            "/api/games",
            json={"title": _unique("게임"), "participant_type": "individual", "input_type": "button"},
            headers=admin_headers,
        )
    ).json()["id"]
    timetable_id = (
        await client.post(
            f"/api/seasons/{season_id}/timetable",
            json={"game_id": game_id, "order_index": 1},
            headers=admin_headers,
        )
    ).json()["id"]
    session_id = (
        await client.post(f"/api/timetable/{timetable_id}/session", headers=admin_headers)
    ).json()["id"]
    await client.post(
        f"/api/sessions/{session_id}/transition", json={"to": "ready"}, headers=admin_headers
    )
    await client.post(
        f"/api/sessions/{session_id}/transition", json={"to": "in_progress"}, headers=admin_headers
    )
    return session_id


async def test_commitment_and_spin_deterministic(client, admin_headers):
    session_id = await _started_session(client, admin_headers)

    commit = (
        await client.get(
            f"/api/sessions/{session_id}/roulette/commitment", headers=admin_headers
        )
    ).json()["commitment"]
    assert len(commit) == 64  # sha256 hex

    options = ["A팀", "B팀", "C팀"]
    body = {"options": options, "nonce": 42}

    res1 = await client.post(
        f"/api/sessions/{session_id}/roulette/spin", json=body, headers=admin_headers
    )
    assert res1.status_code == 200
    r1 = res1.json()
    assert r1["selected"] == options[r1["selected_index"]]
    assert r1["commitment"] == commit

    # 같은 nonce 로 다시 돌리면 결과 동일 (결정론)
    res2 = await client.post(
        f"/api/sessions/{session_id}/roulette/spin", json=body, headers=admin_headers
    )
    assert res2.json()["selected_index"] == r1["selected_index"]


async def test_spin_before_seed_409(client, admin_headers):
    # in_progress 전(idle) 세션 → 시드 없음
    season_id = (
        await client.post("/api/seasons", json={"name": _unique("시즌")}, headers=admin_headers)
    ).json()["id"]
    game_id = (
        await client.post(
            "/api/games",
            json={"title": _unique("게임"), "participant_type": "team_vs", "input_type": "chat"},
            headers=admin_headers,
        )
    ).json()["id"]
    timetable_id = (
        await client.post(
            f"/api/seasons/{season_id}/timetable",
            json={"game_id": game_id, "order_index": 1},
            headers=admin_headers,
        )
    ).json()["id"]
    session_id = (
        await client.post(f"/api/timetable/{timetable_id}/session", headers=admin_headers)
    ).json()["id"]

    res = await client.post(
        f"/api/sessions/{session_id}/roulette/spin",
        json={"options": ["x"], "nonce": 0},
        headers=admin_headers,
    )
    assert res.status_code == 409


async def test_empty_options_422(client, admin_headers):
    session_id = await _started_session(client, admin_headers)
    res = await client.post(
        f"/api/sessions/{session_id}/roulette/spin",
        json={"options": [], "nonce": 1},
        headers=admin_headers,
    )
    assert res.status_code == 422


async def test_seed_reveal_only_after_done(client, admin_headers):
    session_id = await _started_session(client, admin_headers)

    # in_progress 상태에선 시드 공개 불가
    res = await client.get(
        f"/api/sessions/{session_id}/roulette/seed", headers=admin_headers
    )
    assert res.status_code == 409

    # 종료까지 전이
    for state in ("scoring", "done"):
        await client.post(
            f"/api/sessions/{session_id}/transition", json={"to": state}, headers=admin_headers
        )

    commit = (
        await client.get(
            f"/api/sessions/{session_id}/roulette/commitment", headers=admin_headers
        )
    ).json()["commitment"]

    res = await client.get(
        f"/api/sessions/{session_id}/roulette/seed", headers=admin_headers
    )
    assert res.status_code == 200
    seed = res.json()["seed"]
    # 공개된 seed 가 사전 commitment 와 일치 → 공정성 검증
    assert hashlib.sha256(seed.encode()).hexdigest() == commit


async def test_spin_requires_admin(client, admin_headers, user_headers):
    session_id = await _started_session(client, admin_headers)
    res = await client.post(
        f"/api/sessions/{session_id}/roulette/spin",
        json={"options": ["x", "y"], "nonce": 1},
        headers=user_headers,
    )
    assert res.status_code == 403


async def test_spin_broadcasts(client, admin_headers, monkeypatch):
    from app.websocket import manager as mgr_mod

    calls: list[dict] = []

    async def fake_broadcast(message: dict) -> None:
        calls.append(message)

    monkeypatch.setattr(mgr_mod.manager, "broadcast", fake_broadcast)

    session_id = await _started_session(client, admin_headers)
    await client.post(
        f"/api/sessions/{session_id}/roulette/spin",
        json={"options": ["A", "B"], "nonce": 5},
        headers=admin_headers,
    )
    assert any(c["type"] == "roulette_result" for c in calls)
