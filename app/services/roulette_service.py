"""검증 가능한(provably-fair) 룰렛/추첨 로직.

commit-reveal 방식:
- 비밀 seed 는 게임 시작(in_progress) 시 생성된다.
- commitment = sha256(seed) 를 미리 공개해 결과 조작이 없음을 약속한다.
- 결과는 HMAC-SHA256(seed, nonce) 로 결정론적으로 도출 → 같은 (seed, nonce) 면 항상 같은 결과.
- 게임 종료 후 seed 를 공개하면 누구나 결과를 재계산해 검증할 수 있다.

이 모듈은 순수 함수만 가진다 (DB/상태 의존 없음).
"""

import hashlib
import hmac


def commitment(seed: str) -> str:
    """seed 의 공개용 커밋값 (단방향 해시)."""
    return hashlib.sha256(seed.encode()).hexdigest()


def _digest(seed: str, nonce: int) -> bytes:
    return hmac.new(seed.encode(), str(nonce).encode(), hashlib.sha256).digest()


def draw_float(seed: str, nonce: int) -> float:
    """[0, 1) 범위의 결정론적 실수."""
    digest = _digest(seed, nonce)
    return int.from_bytes(digest[:8], "big") / 2**64


def draw_index(seed: str, nonce: int, n: int) -> int:
    """0..n-1 중 하나를 결정론적으로 선택."""
    if n <= 0:
        raise ValueError("n 은 1 이상이어야 합니다.")
    return int(draw_float(seed, nonce) * n)
