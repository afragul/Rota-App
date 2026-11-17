import { useEffect, useRef, useState } from 'react'
import { ApiError, searchPlaces, type LatLng } from '../api'
import type { Place } from '../types'
import { Icon } from './Icon'

interface Props {
  /** Sonuçlarda bu noktaya yakın olanlar öne çıkar (yalnızca öncelik, sınır değil). */
  near: LatLng
  accessToken?: string
  /** Zaten rotada olan mekanlar sonuçlardan çıkarılır. */
  usedIds: Set<string>
  onPick: (place: Place) => void
}

function errorText(err: unknown): string {
  if (!(err instanceof ApiError)) return 'Arama yapılamadı, tekrar dene.'
  if (err.userLimit) return 'Bugünkü arama hakkın doldu, yarın tekrar deneyebilirsin.'
  if (err.guestLimit) return 'Günlük misafir arama hakkın doldu. Giriş yapıp devam edebilirsin.'
  if (err.status === 429) return 'Çok fazla arama yapıldı, biraz bekleyip tekrar dene.'
  if (err.status === 0) return 'Bağlantı hatası, internetini kontrol et.'
  return err.message
}

// Serbest metinle herhangi bir mekanı arayıp rotaya ekleme. Her arama ücretli bir Google
// çağrısıdır: otomatik (yazdıkça) arama yok, yalnızca "Ara"ya basınca istek gider.
export function PlaceSearch({ near, accessToken, usedIds, onPick }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Place[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => () => abort.current?.abort(), [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = query.trim()
    if (q.length < 2 || loading) return
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    setLoading(true)
    setError(null)
    try {
      setResults(await searchPlaces(q, near, controller.signal, accessToken))
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setResults(null)
      setError(errorText(err))
    } finally {
      if (abort.current === controller) setLoading(false)
    }
  }

  const visible = results?.filter((p) => !usedIds.has(p.place_id)) ?? null

  return (
    <div className="flex flex-col gap-space-sm">
      <form onSubmit={submit} className="flex gap-space-xs">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          maxLength={100}
          placeholder="Mekan adı ya da tarif (örn. Kozahan)"
          aria-label="Mekan ara"
          className="flex-1 min-w-0 h-12 px-4 bg-surface-container-low text-ink font-body-md text-body-md rounded-xl placeholder:text-text-secondary/70 focus:outline-none focus:bg-surface"
        />
        <button
          type="submit"
          disabled={loading || query.trim().length < 2}
          aria-label="Ara"
          className="h-12 w-12 rounded-xl bg-plan-a text-on-primary flex items-center justify-center disabled:opacity-50 flex-shrink-0"
        >
          <Icon name="search" className="text-[22px]" />
        </button>
      </form>

      {loading && <p className="font-body-sm text-body-sm text-text-secondary text-center py-space-sm">Aranıyor…</p>}

      {error && (
        <div className="bg-error-container/60 rounded-xl p-space-sm" role="alert">
          <p className="font-body-sm text-body-sm text-on-error-container">{error}</p>
        </div>
      )}

      {!loading && visible && visible.length === 0 && (
        <p className="font-body-sm text-body-sm text-text-secondary py-space-md text-center">
          {results && results.length > 0 ? 'Bulunan mekanlar zaten rotada.' : 'Sonuç bulunamadı, farklı bir arama dene.'}
        </p>
      )}

      {!loading && visible && visible.length > 0 && (
        <div className="flex flex-col gap-space-xs">
          {visible.map((p) => (
            <button
              key={p.place_id}
              type="button"
              onClick={() => onPick(p)}
              className="text-left p-space-sm rounded-xl bg-surface-container-low hover:bg-surface-container flex flex-col"
            >
              <span className="font-label-md text-label-md text-ink">{p.name}</span>
              {p.address && <span className="font-body-sm text-body-sm text-text-secondary">{p.address}</span>}
              {p.rating != null && (
                <span className="font-body-sm text-body-sm text-text-secondary">⭐ {p.rating.toFixed(1)}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
