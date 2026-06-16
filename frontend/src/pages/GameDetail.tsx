import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type Game,
  type GameResult,
  type GameSession,
  type GameState,
  type ScoreSummaryItem,
  type Team,
  type TimetableEntry,
} from '../api'
import { useAuth } from '../auth'
import { useLive } from '../live'
import OperatorPanel from '../components/OperatorPanel'

interface Props {
  entry: TimetableEntry
  session: GameSession | null
  game: Game | null
  seasonId: number
  onBack: () => void
  onSessionChanged: () => void
}

const STATE_LABEL: Record<GameState, string> = {
  idle: '대기',
  ready: '준비',
  in_progress: '진행중',
  scoring: '채점중',
  reward: '보상',
  done: '종료',
}

export default function GameDetail({
  entry,
  session,
  game,
  seasonId,
  onBack,
  onSessionChanged,
}: Props) {
  const { token, user } = useAuth()
  const t = token as string
  const { lastEvent } = useLive()
  const isAdmin = user?.role === 'admin'

  const [sessionId, setSessionId] = useState<number | null>(session?.id ?? null)
  const [state, setState] = useState<GameState | null>((session?.state as GameState) ?? null)
  const [summary, setSummary] = useState<ScoreSummaryItem[]>([])
  const [results, setResults] = useState<GameResult[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.teams(t, seasonId).then(setTeams).catch(() => setTeams([]))
  }, [t, seasonId])

  const teamName = (id: number) => teams.find((x) => x.id === id)?.name ?? `팀 #${id}`
  const subjectLabel = (type: string, id: number) =>
    type === 'team' ? teamName(id) : `유저 #${id}`

  const refresh = useCallback(() => {
    if (sessionId == null) {
      setSummary([])
      setResults([])
      return
    }
    api.scoreSummary(t, sessionId).then(setSummary).catch(() => setSummary([]))
    api.results(t, sessionId).then(setResults).catch(() => setResults([]))
  }, [t, sessionId])

  useEffect(refresh, [refresh])
  useEffect(() => {
    const sid = lastEvent?.session_id as number | undefined
    if (sid === sessionId) refresh()
  }, [lastEvent, sessionId, refresh])

  const createSession = async () => {
    setBusy(true)
    try {
      const s = await api.createSession(t, entry.id)
      setSessionId(s.id)
      setState(s.state as GameState)
      onSessionChanged()
    } finally {
      setBusy(false)
    }
  }

  const isLive = state === 'in_progress' || state === 'scoring' || state === 'reward'
  const badgeCls = isLive ? 'live' : state === 'done' ? 'done' : 'idle'
  const maxScore = summary.length > 0 ? summary[0].total_score : 1

  return (
    <div className="detail-page">
      {/* 히어로 */}
      <div className="detail-hero">
        <button className="detail-back" onClick={onBack}>‹ 진행 목록</button>
        <p className="detail-gym-label">GYM BATTLE · {entry.order_index}번 체육관</p>
        <h2 className="detail-gym-name">
          {entry.label ?? game?.title ?? `게임 #${entry.game_id}`}
        </h2>
        {game?.description && (
          <p className="detail-gym-desc">{game.description}</p>
        )}
        {state && (
          <span className={`detail-state-badge ${badgeCls}`}>
            {isLive ? '● ' : ''}{STATE_LABEL[state]}
          </span>
        )}
      </div>

      {/* 본문 */}
      <div className="detail-body">
        {sessionId == null ? (
          <div className="detail-no-session">
            <p style={{ marginBottom: isAdmin ? 12 : 0 }}>아직 세션이 시작되지 않았습니다.</p>
            {isAdmin && (
              <button className="op-btn" disabled={busy} onClick={createSession}>
                세션 생성
              </button>
            )}
          </div>
        ) : (
          <>
            <p className="detail-section-label">scoreboard</p>
            {summary.length === 0 ? (
              <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14 }}>
                아직 기록된 점수가 없습니다.
              </p>
            ) : (
              <ol className="score-list">
                {summary.map((s, i) => {
                  const barPct = maxScore > 0 ? (s.total_score / maxScore) * 100 : 0
                  const cls = i === 0 ? ' r1' : i === 1 ? ' r2' : i === 2 ? ' r3' : ''
                  return (
                    <li key={`${s.subject_type}-${s.subject_id}`} className={`score-row${cls}`}>
                      <div className="score-top">
                        <span className="score-rank">{i + 1}</span>
                        <span className="score-name">{subjectLabel(s.subject_type, s.subject_id)}</span>
                        <span className="score-pts">{s.total_score}</span>
                      </div>
                      <div className="score-bar-wrap">
                        <div className="score-bar" style={{ width: `${barPct}%` }} />
                      </div>
                    </li>
                  )
                })}
              </ol>
            )}

            {results.length > 0 && (
              <div className="detail-winner">
                🏆 {results.map((r) => subjectLabel(r.subject_type, r.subject_id)).join(', ')} 우승!
              </div>
            )}

            {isAdmin && state && (
              <OperatorPanel
                key={sessionId}
                token={t}
                sessionId={sessionId}
                state={state}
                teams={teams}
                onStateChange={setState}
                onScored={refresh}
              />
            )}
          </>
        )}
      </div>
    </div>
  )
}
