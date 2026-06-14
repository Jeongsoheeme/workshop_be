import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { api, type Season } from './api'
import { useAuth } from './auth'

interface SeasonState {
  seasons: Season[]
  seasonId: number | null
  season: Season | null
  setSeasonId: (id: number) => void
  refresh: () => Promise<void>
  loading: boolean
}

const SeasonContext = createContext<SeasonState | null>(null)

/** 시즌 목록을 로드하고, 활성(active) 시즌을 기본 선택한다. */
export function SeasonProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  const [seasons, setSeasons] = useState<Season[]>([])
  const [seasonId, setSeasonId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const list = await api.seasons(token)
      setSeasons(list)
      // 현재 선택이 사라졌으면 active 우선, 없으면 가장 최근 시즌으로
      setSeasonId((prev) => {
        if (prev != null && list.some((s) => s.id === prev)) return prev
        const active = list.find((s) => s.status === 'active')
        const fallback = list.length ? list[list.length - 1] : null
        return (active ?? fallback)?.id ?? null
      })
    } catch {
      setSeasons([])
    }
  }, [token])

  useEffect(() => {
    if (!token) return
    setLoading(true)
    refresh().finally(() => setLoading(false))
  }, [token, refresh])

  const season = seasons.find((s) => s.id === seasonId) ?? null

  return (
    <SeasonContext.Provider
      value={{ seasons, seasonId, season, setSeasonId, refresh, loading }}
    >
      {children}
    </SeasonContext.Provider>
  )
}

export function useSeason(): SeasonState {
  const ctx = useContext(SeasonContext)
  if (!ctx) throw new Error('useSeason must be used within SeasonProvider')
  return ctx
}
