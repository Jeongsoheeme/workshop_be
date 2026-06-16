import { useCallback, useEffect, useRef, useState } from 'react'
import {
  api,
  type Game,
  type GameSession,
  type GameState,
  type ScoreSummaryItem,
  type Team,
  type TimetableEntry,
} from '../api'
import { useAuth } from '../auth'
import { useSeason } from '../season'
import { useLive } from '../live'
import GameDetail from './GameDetail'

// const STATE_PILL: Record<GameState, { cls: string; label: string }> = {
//   idle: { cls: 's-idle', label: '대기' },
//   ready: { cls: 's-idle', label: '준비' },
//   in_progress: { cls: 's-live', label: '진행중' },
//   scoring: { cls: 's-live', label: '채점중' },
//   reward: { cls: 's-live', label: '보상' },
//   done: { cls: 's-done', label: '종료' },
// }

// order_index 1(맨 아래) → 8(맨 위)
const GYM_POSITIONS: { x: string; y: string }[] = [
  { x: '75%', y: '95%' }, // 1 - First Gym
  { x: '22%', y: '86%' }, // 2 - Ice Mountain Gym
  { x: '56%', y: '75%' }, // 3 - Forest Gym
  { x: '80%', y: '64%' }, // 4 - Coastal Gym
  { x: '30%', y: '54%' }, // 5 - Power Gym
  { x: '78%', y: '46%' }, // 6 - Volcano Gym
  { x: '30%', y: '35%' }, // 7 - Dojo Gym
  { x: '76%', y: '26%' }, // 8 - Final Gym
]

export default function MainPage() {
  const { token } = useAuth()
  const t = token as string
  const { seasonId } = useSeason()
  const { lastEvent } = useLive()

  const [entries, setEntries] = useState<TimetableEntry[]>([])
  const [games, setGames] = useState<Record<number, Game>>({})
  const [sessions, setSessions] = useState<Record<number, GameSession | null>>({})
  const [selected, setSelected] = useState<TimetableEntry | null>(null)
  const [doneSelected, setDoneSelected] = useState<TimetableEntry | null>(null)
  const [doneScores, setDoneScores] = useState<ScoreSummaryItem[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [mapOffset, setMapOffset] = useState(0)

  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<HTMLDivElement>(null)

  // 게임 목록 (id → 제목)
  useEffect(() => {
    api
      .games(t)
      .then((list) => setGames(Object.fromEntries(list.map((g) => [g.id, g]))))
      .catch(() => setGames({}))
  }, [t])

  // 팀 목록
  useEffect(() => {
    if (seasonId == null) return
    api.teams(t, seasonId).then(setTeams).catch(() => setTeams([]))
  }, [t, seasonId])

  // done 체육관 스코어 fetch
  useEffect(() => {
    if (!doneSelected) { setDoneScores([]); return }
    const sessionId = sessions[doneSelected.id]?.id
    if (!sessionId) return
    api.scoreSummary(t, sessionId).then(setDoneScores).catch(() => setDoneScores([]))
  }, [doneSelected, sessions, t])

  // 타임테이블 + 각 항목의 최신 세션
  const loadEntries = useCallback(() => {
    if (seasonId == null) return
    api
      .timetable(t, seasonId)
      .then(async (list) => {
        const sorted = [...list].sort((a, b) => a.order_index - b.order_index)
        setEntries(sorted)
        const pairs = await Promise.all(
          sorted.map(async (e) => {
            const ss = await api.sessions(t, e.id).catch(() => [])
            return [e.id, ss.length ? ss[ss.length - 1] : null] as const
          }),
        )
        setSessions(Object.fromEntries(pairs))
      })
      .catch(() => setEntries([]))
  }, [t, seasonId])

  useEffect(loadEntries, [loadEntries])
  useEffect(() => {
    if (lastEvent?.type === 'session_state_changed') loadEntries()
  }, [lastEvent, loadEntries])

  // done인 마지막 체육관이 화면 중앙에 오도록 맵 오프셋 계산
  useEffect(() => {
    if (!mapRef.current || !containerRef.current) return

    const lastDoneEntry = entries
      .filter((e) => sessions[e.id]?.state === 'done')
      .sort((a, b) => b.order_index - a.order_index)[0]

    if (!lastDoneEntry) {
      setMapOffset(0)
      return
    }

    const pos = GYM_POSITIONS[lastDoneEntry.order_index - 1]
    if (!pos) return

    const mapHeight = mapRef.current.offsetHeight
    const containerHeight = containerRef.current.offsetHeight
    const gymY = (parseFloat(pos.y) / 100) * mapHeight
    const ideal = -(gymY - containerHeight / 2)
    const clamped = Math.min(0, Math.max(containerHeight - mapHeight, ideal))
    setMapOffset(clamped)
  }, [sessions, entries])

  const title = (e: TimetableEntry) => e.label ?? games[e.game_id]?.title ?? `게임 #${e.game_id}`
  const teamName = (type: string, id: number) =>
    type === 'team' ? (teams.find((x) => x.id === id)?.name ?? `팀 #${id}`) : `유저 #${id}`

  if (selected) {
    return (
      <GameDetail
        entry={selected}
        session={sessions[selected.id] ?? null}
        game={games[selected.game_id] ?? null}
        seasonId={seasonId as number}
        onBack={() => setSelected(null)}
        onSessionChanged={loadEntries}
      />
    )
  }

  return (
    <div ref={containerRef} className="main-container">
      <div
        ref={mapRef}
        className="map-canvas"
        style={{ transform: `translateY(${mapOffset}px)` }}
      >
        {entries.map((e) => {
          const pos = GYM_POSITIONS[e.order_index - 1]
          if (!pos) return null
          const s = sessions[e.id]
          const st = (s?.state as GameState) ?? null
          const done = st === 'done'
          const live = st === 'in_progress' || st === 'scoring' || st === 'reward'
          return (
            <div
              key={e.id}
              className={`gym-marker${done ? ' done' : ''}${live ? ' live' : ''}`}
              style={{ left: pos.x, top: pos.y, cursor: live || done ? 'pointer' : 'default' }}
              onClick={() => {
                if (live) setSelected(e)
                else if (done) setDoneSelected(e)
              }}
            >
              <span className="gym-title">{games[e.game_id]?.title ?? title(e)}</span>
            </div>
          )
        })}
      </div>

      {doneSelected && (
        <div className="modal" onClick={() => setDoneSelected(null)}>
          <div className="score-modal-card" onClick={(e) => e.stopPropagation()}>
            {/* 히어로 */}
            <div className="score-modal-hero">
              <h3 className="score-modal-title">{title(doneSelected)}</h3>
              <p className="score-modal-sub">Final Score</p>
            </div>

            {/* 스코어 */}
            <div className="score-modal-body">
              {doneScores.length === 0 ? (
                <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, textAlign: 'center', padding: '12px 0' }}>
                  기록된 점수가 없습니다.
                </p>
              ) : (() => {
                const maxScore = doneScores[0].total_score
                return (
                  <ol className="score-list">
                    {doneScores.map((s, i) => {
                      const cls = i === 0 ? ' r1' : i === 1 ? ' r2' : i === 2 ? ' r3' : ''
                      const barPct = maxScore > 0 ? (s.total_score / maxScore) * 100 : 0
                      return (
                        <li key={`${s.subject_type}-${s.subject_id}`} className={`score-row${cls}`}>
                          <div className="score-top">
                            <span className="score-rank">{i + 1}</span>
                            <span className="score-name">{teamName(s.subject_type, s.subject_id)}</span>
                            <span className="score-pts">{s.total_score}</span>
                          </div>
                          <div className="score-bar-wrap">
                            <div className="score-bar" style={{ width: `${barPct}%` }} />
                          </div>
                        </li>
                      )
                    })}
                  </ol>
                )
              })()}
            </div>

            <button className="score-modal-close" onClick={() => setDoneSelected(null)}>
              닫기
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
