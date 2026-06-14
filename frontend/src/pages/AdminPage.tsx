import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, type Team, type UserProfile } from '../api'
import { useAuth } from '../auth'
import { useSeason } from '../season'

interface Props {
  onClose: () => void
}

const STATUS_LABEL: Record<string, string> = {
  preparing: '준비중',
  active: '진행중',
  done: '종료',
}

export default function AdminPage({ onClose }: Props) {
  const { token } = useAuth()
  const t = token as string
  const { seasons, seasonId, setSeasonId, refresh: refreshSeasons } = useSeason()

  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (fn: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  // ---------- 시즌 ----------
  const [seasonName, setSeasonName] = useState('')

  const createSeason = () =>
    run(async () => {
      if (!seasonName.trim()) throw new ApiError(400, '시즌 이름을 입력하세요.')
      const s = await api.createSeason(t, seasonName.trim())
      setSeasonName('')
      await refreshSeasons()
      setSeasonId(s.id)
    })

  const activateSeason = (id: number) =>
    run(async () => {
      await api.updateSeason(t, id, { status: 'active' })
      await refreshSeasons()
    })

  // ---------- 팀 ----------
  const [teams, setTeams] = useState<Team[]>([])
  const [teamName, setTeamName] = useState('')

  const loadTeams = useCallback(() => {
    if (seasonId == null) {
      setTeams([])
      return
    }
    api.teams(t, seasonId).then(setTeams).catch(() => setTeams([]))
  }, [t, seasonId])
  useEffect(loadTeams, [loadTeams])

  const createTeam = () =>
    run(async () => {
      if (seasonId == null) throw new ApiError(400, '먼저 시즌을 선택/생성하세요.')
      if (!teamName.trim()) throw new ApiError(400, '팀 이름을 입력하세요.')
      await api.createTeam(t, seasonId, teamName.trim())
      setTeamName('')
      loadTeams()
    })

  // ---------- 유저 배치 ----------
  const [users, setUsers] = useState<UserProfile[]>([])
  const loadUsers = useCallback(() => {
    api.users(t).then(setUsers).catch(() => setUsers([]))
  }, [t])
  useEffect(loadUsers, [loadUsers])

  const assignTeam = (userId: number, value: string) =>
    run(async () => {
      const team_id = value === '' ? null : Number(value)
      await api.updateUser(t, userId, { team_id })
      loadUsers()
    })

  // 새 참가자 추가
  const [nu, setNu] = useState({ username: '', nickname: '', password: '' })
  const createUser = () =>
    run(async () => {
      if (!nu.username.trim() || !nu.nickname.trim() || !nu.password.trim())
        throw new ApiError(400, '아이디·닉네임·비밀번호를 모두 입력하세요.')
      await api.createUser(t, {
        username: nu.username.trim(),
        nickname: nu.nickname.trim(),
        password: nu.password.trim(),
        role: 'user',
        team_id: null, // 생성 후 아래 목록에서 팀 배정
      })
      setNu({ username: '', nickname: '', password: '' })
      loadUsers()
    })

  const teamName2 = (id: number | null) =>
    id == null ? '미배정' : teams.find((x) => x.id === id)?.name ?? `타 시즌 #${id}`

  return (
    <div className="page admin">
      <button className="back" onClick={onClose}>
        ← 닫기
      </button>
      <h2 className="detail-title">🛠 운영 관리</h2>
      {error && <p className="error">{error}</p>}

      {/* 시즌 */}
      <h3 className="sec-title">① 시즌</h3>
      <div className="op-row">
        <input
          placeholder="새 시즌 이름"
          value={seasonName}
          onChange={(e) => setSeasonName(e.target.value)}
        />
        <button className="op-btn" disabled={busy} onClick={createSeason}>
          생성
        </button>
      </div>
      <div className="admin-list">
        {seasons.map((s) => (
          <div key={s.id} className={`admin-row${s.id === seasonId ? ' sel' : ''}`}>
            <button className="row-main" onClick={() => setSeasonId(s.id)}>
              <b>{s.name}</b>
              <span className={`chip ${s.status === 'active' ? 'state' : ''}`}>
                {STATUS_LABEL[s.status] ?? s.status}
              </span>
            </button>
            {s.status !== 'active' && (
              <button className="mini-btn" disabled={busy} onClick={() => activateSeason(s.id)}>
                활성화
              </button>
            )}
          </div>
        ))}
      </div>

      {/* 팀 */}
      <h3 className="sec-title">② 팀 {seasonId != null && '(선택 시즌)'}</h3>
      {seasonId == null ? (
        <p className="muted">시즌을 먼저 선택하세요.</p>
      ) : (
        <>
          <div className="op-row">
            <input
              placeholder="새 팀 이름 (예: 🔴 레드팀)"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
            />
            <button className="op-btn" disabled={busy} onClick={createTeam}>
              생성
            </button>
          </div>
          <div className="admin-list">
            {teams.length === 0 ? (
              <p className="muted">아직 팀이 없습니다.</p>
            ) : (
              teams.map((tm) => (
                <div key={tm.id} className="admin-row">
                  <span className="row-main">
                    <b>{tm.name}</b>
                    <span className="chip">
                      {users.filter((u) => u.team_id === tm.id).length}명
                    </span>
                  </span>
                </div>
              ))
            )}
          </div>
        </>
      )}

      {/* 유저 배치 */}
      <h3 className="sec-title">③ 유저 배치</h3>
      <div className="op-row" style={{ marginBottom: 10 }}>
        <input
          placeholder="아이디"
          value={nu.username}
          onChange={(e) => setNu({ ...nu, username: e.target.value })}
        />
        <input
          placeholder="닉네임"
          value={nu.nickname}
          onChange={(e) => setNu({ ...nu, nickname: e.target.value })}
        />
        <input
          placeholder="비밀번호"
          value={nu.password}
          onChange={(e) => setNu({ ...nu, password: e.target.value })}
        />
        <button className="op-btn" disabled={busy} onClick={createUser}>
          참가자 추가
        </button>
      </div>
      <div className="admin-list">
        {users.map((u) => (
          <div key={u.id} className="admin-row">
            <span className="row-main">
              <b>{u.nickname}</b>
              <span className="muted">@{u.username}</span>
              {u.role === 'admin' && <span className="chip state">운영자</span>}
              <span className="muted" style={{ marginLeft: 'auto' }}>
                {teamName2(u.team_id)}
              </span>
            </span>
            <select
              className="assign"
              value={teams.some((x) => x.id === u.team_id) ? String(u.team_id) : ''}
              disabled={busy || seasonId == null}
              onChange={(e) => assignTeam(u.id, e.target.value)}
            >
              <option value="">미배정</option>
              {teams.map((tm) => (
                <option key={tm.id} value={tm.id}>
                  {tm.name}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
    </div>
  )
}
