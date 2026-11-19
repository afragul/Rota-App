import type { Session } from '../auth'
import { useEffect, useState } from 'react'
import { fetchApproach, fetchLegs, fetchPlaceLocation, type LatLng } from '../api'
import { Icon } from '../components/Icon'
import { PlaceSearch } from '../components/PlaceSearch'
import { RouteMap } from '../components/RouteMap'
import { addFavoritePlace, listFavoritePlaces, removeFavoritePlace } from '../favoritePlaces'
import { TRAVEL_MODES, THEMES, THEME_TYPES, formatCost, formatDistance, formatHours, mapsUrl, planStyle } from '../meta'
import { deleteSavedPlan, saveFavoritePlan } from '../savedPlans'
import type { ApproachRoute, DayPlan, Place, PlaceWithoutLocation, PlanAlternative, PlanStop, RouteLeg, TravelMode } from '../types'
import { recordVisit } from '../visitedPlaces'

export type UserLocation =
  | { status: 'idle' | 'loading' | 'denied' }
  | { status: 'ready'; coords: LatLng }

export interface AlternativePatch {
  index: number
  stops: PlanStop[]
  legs: RouteLeg[]
  routesAvailable: boolean
}

interface Props {
  plan: DayPlan
  index: number
  travelMode: TravelMode
  userLoc: UserLocation
  onRequestLocation: () => void
  onSelect: (index: number) => void
  onPrefs: () => void
  onStartNavigation: (approach: ApproachRoute) => void
  session: Session | null
  onRequireAccount: () => void
  onAlternativesChange: (patches: AlternativePatch[]) => void
}

type Approach = { state: 'idle' } | { state: 'loading' } | { state: 'error' } | { state: 'ready'; route: ApproachRoute }
type FavoriteState = 'idle' | 'saving' | 'saved' | 'error'

function stopFromPlace(place: Place, order: number, base?: Pick<PlanStop, 'arrival_time' | 'duration_minutes' | 'estimated_cost'>): PlanStop {
  return {
    place_id: place.place_id,
    order,
    arrival_time: base?.arrival_time ?? '-',
    duration_minutes: base?.duration_minutes ?? 60,
    estimated_cost: base?.estimated_cost ?? 0,
    activity: `${place.name} keşfi`,
    recommendation: 'Detaylar için Google Maps linkine bakabilirsin.',
    name: place.name,
    latitude: place.latitude,
    longitude: place.longitude,
  }
}

// Favorileme/ziyaret kaydı için durağı Place'e çevirir — pool'da varsa tam
// veriyi (adres, tür) kullanır, yoksa durağın kendi alanlarından sadeleşir.
function placeFromStop(stop: PlanStop, pool: Place[]): Place {
  const fromPool = pool.find((p) => p.place_id === stop.place_id)
  if (fromPool) return fromPool
  return {
    place_id: stop.place_id,
    name: stop.name ?? stop.activity,
    address: null,
    latitude: stop.latitude ?? 0,
    longitude: stop.longitude ?? 0,
    rating: null,
    user_rating_count: null,
    types: [],
  }
}

async function legsFor(
  stops: PlanStop[],
  travelMode: TravelMode,
  accessToken?: string,
): Promise<{ legs: RouteLeg[]; ok: boolean }> {
  const withCoords = stops.filter((st) => st.latitude != null && st.longitude != null)
  if (withCoords.length < 2) return { legs: [], ok: true }
  try {
    const legs = await fetchLegs(
      withCoords.map((st) => ({ order: st.order, latitude: st.latitude!, longitude: st.longitude! })),
      travelMode,
      undefined,
      accessToken,
    )
    return { legs, ok: legs.length > 0 }
  } catch {
    return { legs: [], ok: false }
  }
}

interface StopEditSheetProps {
  mode: 'replace' | 'add'
  stop: PlanStop | null // mode 'replace' iken değiştirilen durak
  pool: Place[]
  /** Mekan aramasında sonuçların yakınında toplanacağı nokta (planın bölgesi). */
  near: LatLng
  accessToken?: string
  favoritePlaces: PlaceWithoutLocation[]
  usedIds: Set<string>
  alternatives: PlanAlternative[]
  currentIndex: number
  canTransferOut: boolean
  onPickPlace: (place: Place) => void
  onTransferOut?: (targetIndex: number) => void
  onTransferIn?: (fromIndex: number, stop: PlanStop) => void
  onClose: () => void
}

// Durak değiştirme/ekleme sayfası: havuzdan (ücretsiz, kategoriye göre
// filtrelenmiş) bir mekan seçme, ya da bir durağı başka bir alternatife
// taşıma/başka bir alternatiften alma. Tam ekran — altta kısık kalmasın diye.
function StopEditSheet({
  mode,
  stop,
  pool,
  near,
  accessToken,
  favoritePlaces,
  usedIds,
  alternatives,
  currentIndex,
  canTransferOut,
  onPickPlace,
  onTransferOut,
  onTransferIn,
  onClose,
}: StopEditSheetProps) {
  const [tab, setTab] = useState<'category' | 'other' | 'favorites' | 'search'>('category')
  const [category, setCategory] = useState<string | null>(null)
  const favoriteCandidates = favoritePlaces.filter((p) => !usedIds.has(p.place_id))
  // favorite_places koordinat tutmuyor (bkz. favoritePlaces.ts); bir favori rotaya
  // durak olarak eklenmek istendiğinde güncel konum anlık çekilir.
  const [locatingFavoriteId, setLocatingFavoriteId] = useState<string | null>(null)
  const [favoriteLocateError, setFavoriteLocateError] = useState(false)

  const pickFavorite = async (p: PlaceWithoutLocation) => {
    if (locatingFavoriteId) return
    setFavoriteLocateError(false)
    setLocatingFavoriteId(p.place_id)
    try {
      const { latitude, longitude } = await fetchPlaceLocation(p.place_id, accessToken)
      onPickPlace({ ...p, latitude, longitude })
    } catch {
      setFavoriteLocateError(true)
    } finally {
      setLocatingFavoriteId(null)
    }
  }

  const candidates = pool.filter((p) => {
    if (usedIds.has(p.place_id)) return false
    if (!category) return true
    return p.types.some((t) => (THEME_TYPES[category] ?? []).includes(t))
  })

  const otherAlternatives = alternatives.filter((_, i) => i !== currentIndex)

  return (
    <div className="fixed inset-0 z-[70] bg-background overflow-y-auto">
      <div className="max-w-md mx-auto px-margin pt-safe pb-space-lg flex flex-col w-full gap-space-md">
        <div className="flex items-center justify-between py-space-md">
          <div className="flex flex-col min-w-0">
            <h3 className="font-headline-lg-mobile text-headline-lg-mobile text-ink">
              {mode === 'replace' ? 'Durağı değiştir' : 'Durak ekle'}
            </h3>
            {stop && <span className="font-body-sm text-body-sm text-text-secondary truncate">{stop.name ?? stop.activity}</span>}
          </div>
          <button onClick={onClose} aria-label="Kapat" className="w-10 h-10 rounded-full flex items-center justify-center text-ink flex-shrink-0">
            <Icon name="close" className="text-[22px]" />
          </button>
        </div>

        <div className="flex gap-space-xs">
          <button
            type="button"
            onClick={() => setTab('category')}
            className={`flex-1 min-h-11 py-2 px-1 rounded-xl font-label-sm text-label-sm leading-tight ${
              tab === 'category' ? 'bg-plan-a text-on-primary' : 'bg-surface-container-low text-ink'
            }`}
          >
            {mode === 'replace' ? 'Havuzdan seç' : 'Havuzdan ekle'}
          </button>
          <button
            type="button"
            onClick={() => setTab('search')}
            className={`flex-1 min-h-11 py-2 px-1 rounded-xl font-label-sm text-label-sm leading-tight ${
              tab === 'search' ? 'bg-plan-a text-on-primary' : 'bg-surface-container-low text-ink'
            }`}
          >
            Mekan ara
          </button>
          <button
            type="button"
            onClick={() => setTab('favorites')}
            className={`flex-1 min-h-11 py-2 px-1 rounded-xl font-label-sm text-label-sm leading-tight ${
              tab === 'favorites' ? 'bg-plan-a text-on-primary' : 'bg-surface-container-low text-ink'
            }`}
          >
            Favorilerimden ekle
          </button>
          <button
            type="button"
            onClick={() => setTab('other')}
            disabled={mode === 'replace' ? !canTransferOut : otherAlternatives.length === 0}
            className={`flex-1 min-h-11 py-2 px-1 rounded-xl font-label-sm text-label-sm leading-tight disabled:opacity-40 ${
              tab === 'other' ? 'bg-plan-a text-on-primary' : 'bg-surface-container-low text-ink'
            }`}
          >
            {mode === 'replace' ? 'Başka plana taşı' : 'Başka plandan al'}
          </button>
        </div>

        {tab === 'search' ? (
          <PlaceSearch near={near} accessToken={accessToken} usedIds={usedIds} onPick={onPickPlace} />
        ) : tab === 'category' ? (
          <div className="flex flex-col gap-space-sm">
            <div className="flex gap-space-xs overflow-x-auto py-space-xs">
              <button
                type="button"
                onClick={() => setCategory(null)}
                className={`h-9 px-3 rounded-full flex-shrink-0 font-label-sm text-label-sm ${
                  !category ? 'bg-ink text-background' : 'bg-surface-container-low text-ink'
                }`}
              >
                Tümü
              </button>
              {THEMES.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setCategory(t.key)}
                  className={`h-9 px-3 rounded-full flex-shrink-0 flex items-center gap-1 font-label-sm text-label-sm ${
                    category === t.key ? 'bg-ink text-background' : 'bg-surface-container-low text-ink'
                  }`}
                >
                  <Icon name={t.icon} className="text-[16px]" />
                  {t.label}
                </button>
              ))}
            </div>
            {candidates.length === 0 ? (
              <p className="font-body-sm text-body-sm text-text-secondary py-space-md text-center">
                Bu kategoride havuzda uygun mekan yok.
              </p>
            ) : (
              <div className="flex flex-col gap-space-xs">
                {candidates.map((p) => (
                  <button
                    key={p.place_id}
                    type="button"
                    onClick={() => onPickPlace(p)}
                    className="text-left p-space-sm rounded-xl bg-surface-container-low hover:bg-surface-container flex flex-col"
                  >
                    <span className="font-label-md text-label-md text-ink">{p.name}</span>
                    {p.rating != null && (
                      <span className="font-body-sm text-body-sm text-text-secondary">⭐ {p.rating.toFixed(1)}</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : tab === 'favorites' ? (
          <div className="flex flex-col gap-space-xs">
            {favoriteLocateError && (
              <p className="font-body-sm text-body-sm text-red-600 text-center">
                Mekanın konumu alınamadı, tekrar dener misin?
              </p>
            )}
            {favoriteCandidates.length === 0 ? (
              <p className="font-body-sm text-body-sm text-text-secondary py-space-md text-center">
                {favoritePlaces.length === 0 ? 'Henüz favorilediğin bir mekan yok.' : 'Favorilediğin mekanlar zaten rotada.'}
              </p>
            ) : (
              favoriteCandidates.map((p) => (
                <button
                  key={p.place_id}
                  type="button"
                  disabled={locatingFavoriteId !== null}
                  onClick={() => void pickFavorite(p)}
                  className="text-left p-space-sm rounded-xl bg-surface-container-low hover:bg-surface-container flex items-center justify-between gap-space-sm disabled:opacity-60"
                >
                  <span className="flex flex-col min-w-0">
                    <span className="font-label-md text-label-md text-ink">{p.name}</span>
                    {p.address && <span className="font-body-sm text-body-sm text-text-secondary">{p.address}</span>}
                  </span>
                  {locatingFavoriteId === p.place_id && (
                    <Icon name="progress_activity" className="text-[18px] text-text-secondary animate-spin flex-shrink-0" />
                  )}
                </button>
              ))
            )}
          </div>
        ) : mode === 'replace' ? (
          <div className="flex flex-col gap-space-xs">
            {alternatives.map((a, i) =>
              i === currentIndex ? null : (
                <button
                  key={a.title}
                  type="button"
                  onClick={() => onTransferOut?.(i)}
                  className="text-left p-space-sm rounded-xl bg-surface-container-low hover:bg-surface-container flex items-center gap-space-sm"
                >
                  <span className={`w-2 h-2 rounded-full ${planStyle(i).bg}`} />
                  <span className="font-label-md text-label-md text-ink">
                    {planStyle(i).name} · {a.theme}
                  </span>
                </button>
              ),
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-space-md">
            {alternatives.map((a, i) => {
              if (i === currentIndex) return null
              return (
                <div key={a.title} className="flex flex-col gap-space-xs">
                  <div className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${planStyle(i).bg}`} />
                    <span className="font-label-md text-label-md text-ink font-semibold">
                      {planStyle(i).name} · {a.theme}
                    </span>
                  </div>
                  {[...a.stops].sort((x, y) => x.order - y.order).map((st) => (
                    <button
                      key={st.order}
                      type="button"
                      onClick={() => onTransferIn?.(i, st)}
                      disabled={a.stops.length <= 1}
                      className="text-left p-space-sm rounded-xl bg-surface-container-low hover:bg-surface-container disabled:opacity-40 flex flex-col"
                    >
                      <span className="font-label-md text-label-md text-ink">{st.name ?? st.activity}</span>
                      {a.stops.length <= 1 && (
                        <span className="font-body-sm text-body-sm text-text-secondary">Tek durağı, taşınamaz</span>
                      )}
                    </button>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export function DetailScreen({
  plan,
  index,
  travelMode,
  userLoc,
  onRequestLocation,
  onSelect,
  onPrefs,
  onStartNavigation,
  session,
  onRequireAccount,
  onAlternativesChange,
}: Props) {
  const alt = plan.alternatives[index]
  const s = planStyle(index)
  const stops = [...alt.stops].sort((a, b) => a.order - b.order)
  const minutes = stops.reduce((sum, st) => sum + st.duration_minutes, 0)
  const cost = stops.reduce((sum, st) => sum + st.estimated_cost, 0)
  const [arrived, setArrived] = useState<Set<number>>(new Set())
  const [shared, setShared] = useState(false)
  const [favorite, setFavorite] = useState<FavoriteState>('idle')
  const [savedId, setSavedId] = useState<string | null>(null)
  const [recalculating, setRecalculating] = useState(false)
  const [swapFor, setSwapFor] = useState<PlanStop | null>(null)
  const [adding, setAdding] = useState(false)
  const [favoritePlaces, setFavoritePlaces] = useState<PlaceWithoutLocation[]>([])
  // Mekan aramasının önceliklendireceği nokta: planın kendi bölgesi (ilk koordinatlı durak,
  // yoksa havuzdaki ilk mekan). Hiçbiri yoksa Türkiye'nin ortası: yalnızca öncelik, sınır değil.
  const anchorStop = stops.find((st) => st.latitude != null && st.longitude != null)
  const firstPooled = plan.place_pool?.[0]
  const searchCenter: LatLng = anchorStop
    ? { latitude: anchorStop.latitude!, longitude: anchorStop.longitude! }
    : firstPooled
      ? { latitude: firstPooled.latitude, longitude: firstPooled.longitude }
      : { latitude: 39.0, longitude: 35.0 }
  const w = plan.weather

  // Sekme değişince (başka bir alternatife geçilince) önceki plana ait
  // "kaydedildi" durumu yanlışlıkla taşınmasın.
  useEffect(() => {
    setSavedId(null)
    setFavorite('idle')
  }, [index])

  // Mekan bazlı favoriler (rota değil) — oturum değişince yeniden yüklenir.
  useEffect(() => {
    if (!session) return setFavoritePlaces([])
    listFavoritePlaces(session.access_token).then(({ data }) => setFavoritePlaces(data ?? []))
  }, [session])

  const isFavoritePlace = (placeId: string) => favoritePlaces.some((p) => p.place_id === placeId)

  // Tekil bir mekanı favoriler/favorilerden çıkarır — rota favorilemeden
  // (toggleFavorite) ayrı bir kavram, StopEditSheet'in "Favorilerimden ekle"
  // sekmesini de besler.
  const toggleFavoritePlace = async (stop: PlanStop) => {
    if (!session) return onRequireAccount()
    if (isFavoritePlace(stop.place_id)) {
      setFavoritePlaces((prev) => prev.filter((p) => p.place_id !== stop.place_id))
      await removeFavoritePlace(stop.place_id, session.access_token)
    } else {
      const place = placeFromStop(stop, plan.place_pool ?? [])
      setFavoritePlaces((prev) => [...prev, place])
      await addFavoritePlace(place, session.access_token)
    }
  }

  // Durak silindiğinde/sırası/mekanı değiştiğinde ayakları yeniden hesaplatır;
  // sonucu App.tsx'teki plan'a geri bildirir (tek doğruluk kaynağı orada kalır,
  // bu ekran kendi kopyasını tutmaz — favori kaydetme/navigasyon hep güncel veriyi görsün).
  const applyStopEdit = async (nextStops: PlanStop[]) => {
    const renumbered = nextStops.map((st, i) => ({ ...st, order: i + 1 }))
    setArrived(new Set())
    setRecalculating(true)
    const { legs, ok } = await legsFor(renumbered, travelMode, session?.access_token)
    onAlternativesChange([{ index, stops: renumbered, legs, routesAvailable: ok }])
    setRecalculating(false)
  }

  const moveStop = (order: number, dir: -1 | 1) => {
    const i = stops.findIndex((st) => st.order === order)
    const j = i + dir
    if (i < 0 || j < 0 || j >= stops.length) return
    const next = [...stops]
    ;[next[i], next[j]] = [next[j], next[i]]
    void applyStopEdit(next)
  }

  const removeStop = (order: number) => {
    if (stops.length <= 1) return
    void applyStopEdit(stops.filter((st) => st.order !== order))
  }

  // Havuzdan seçilen mekanla mevcut bir durağı değiştirir.
  const swapPlace = (place: Place) => {
    if (!swapFor) return
    const next = stops.map((st) => (st.order === swapFor.order ? stopFromPlace(place, st.order, st) : st))
    setSwapFor(null)
    void applyStopEdit(next)
  }

  // Havuzdan seçilen mekanı mevcut alternatife yeni bir durak olarak ekler.
  const addPlace = (place: Place) => {
    const next = [...stops, stopFromPlace(place, stops.length + 1)]
    setAdding(false)
    void applyStopEdit(next)
  }

  // Bir durağı `fromIndex` alternatifinden çıkarıp `toIndex` alternatifinin
  // sonuna ekler; ikisi birden değiştiği için onAlternativesChange'e tek
  // seferde iki patch verilir.
  const transferStopBetween = async (fromIndex: number, stop: PlanStop, toIndex: number) => {
    const fromAlt = plan.alternatives[fromIndex]
    if (fromAlt.stops.length <= 1) return
    const fromNext = fromAlt.stops.filter((st) => st.order !== stop.order).map((st, i) => ({ ...st, order: i + 1 }))
    const toAlt = plan.alternatives[toIndex]
    const toNext = [...toAlt.stops, stop].map((st, i) => ({ ...st, order: i + 1 }))
    setArrived(new Set())
    setRecalculating(true)
    const [from, to] = await Promise.all([
      legsFor(fromNext, travelMode, session?.access_token),
      legsFor(toNext, travelMode, session?.access_token),
    ])
    onAlternativesChange([
      { index: fromIndex, stops: fromNext, legs: from.legs, routesAvailable: from.ok },
      { index: toIndex, stops: toNext, legs: to.legs, routesAvailable: to.ok },
    ])
    setRecalculating(false)
  }

  const transferOut = (targetIndex: number) => {
    if (!swapFor) return
    const stop = swapFor
    setSwapFor(null)
    void transferStopBetween(index, stop, targetIndex)
  }

  const transferIn = (fromIndex: number, stop: PlanStop) => {
    setAdding(false)
    void transferStopBetween(fromIndex, stop, index)
  }

  // Rotayı favoriler/favorilerden çıkarır — basit bir toggle: yıldız dolu
  // halde kalır (kaydedildi), tekrar basınca kaydı siler ve yıldız söner.
  const toggleFavorite = async () => {
    if (!session) return onRequireAccount()
    setFavorite('saving')
    if (savedId) {
      await deleteSavedPlan(savedId, session.access_token)
      setSavedId(null)
      setFavorite('idle')
      return
    }
    const { data, error } = await saveFavoritePlan(alt, session.access_token)
    if (error || !data) {
      setFavorite('error')
      setTimeout(() => setFavorite('idle'), 2000)
      return
    }
    setSavedId(data.id)
    setFavorite('idle')
  }

  // Konum plan çıkınca, ilk kez detay açıldığında istenir (başlangıçta değil).
  // Tarayıcı izni daha önce hiç sorulmadıysa (durum "prompt"), doğrudan tarayıcı
  // diyaloğunu açmak yerine önce kısa bir açıklama kartı gösteriyoruz
  // (bkz. ROADMAP.md "Konum için bilgilendirme/rıza metni"); izin zaten
  // verilmiş/reddedilmişse tarayıcı zaten karar vermiş demektir, yeniden
  // açıklamaya gerek yok, doğrudan isteriz (gerçek bir diyalog açılmaz).
  const [locationExplain, setLocationExplain] = useState(false)
  useEffect(() => {
    if (userLoc.status !== 'idle') return
    let cancelled = false
    if (!navigator.permissions?.query) {
      setLocationExplain(true)
      return
    }
    navigator.permissions
      .query({ name: 'geolocation' })
      .then((result) => {
        if (cancelled) return
        if (result.state === 'prompt') setLocationExplain(true)
        else onRequestLocation()
      })
      .catch(() => {
        if (!cancelled) setLocationExplain(true)
      })
    return () => {
      cancelled = true
    }
  }, [userLoc.status, onRequestLocation])

  const useLocation = () => {
    setLocationExplain(false)
    onRequestLocation()
  }

  // Kullanıcının konumundan ilk durağa rota.
  const first = stops.find((st) => st.latitude != null && st.longitude != null)
  const origin = userLoc.status === 'ready' ? userLoc.coords : null
  const dest: LatLng | null = first ? { latitude: first.latitude!, longitude: first.longitude! } : null
  const [approach, setApproach] = useState<Approach>({ state: 'idle' })

  useEffect(() => {
    if (!origin || !dest) return
    const controller = new AbortController()
    setApproach({ state: 'loading' })
    fetchApproach(origin, dest, travelMode, controller.signal)
      .then((route) => setApproach({ state: 'ready', route }))
      .catch((err) => {
        if (!(err instanceof DOMException && err.name === 'AbortError')) setApproach({ state: 'error' })
      })
    return () => controller.abort()
    // origin/dest nesneleri her render yeni olur; değerleri bağımlılık olarak veriyoruz
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origin?.latitude, origin?.longitude, dest?.latitude, dest?.longitude, travelMode])

  const approachRoute = approach.state === 'ready' ? approach.route : null

  // "Ulaşıldı" işaretlenince (sadece false->true geçişinde, geri alırken
  // değil) ve oturum varsa sunucuya ziyaret kaydı düşer — "sık gidilen
  // yerler" (ana sayfa) buradan besleniyor. Kritik değil, await'siz.
  const toggleArrived = (stop: PlanStop) =>
    setArrived((prev) => {
      const next = new Set(prev)
      if (next.delete(stop.order)) return next
      next.add(stop.order)
      if (session) void recordVisit(placeFromStop(stop, plan.place_pool ?? []), session.access_token)
      return next
    })

  const share = async () => {
    const text = `${alt.title}\n${stops.map((st) => `${st.arrival_time} ${st.name ?? st.activity}`).join('\n')}`
    try {
      if (navigator.share) await navigator.share({ title: alt.title, text })
      else {
        await navigator.clipboard.writeText(text)
        setShared(true)
        setTimeout(() => setShared(false), 2000)
      }
    } catch {
      /* paylaşım iptal edildi */
    }
  }

  return (
    <div className="flex flex-col w-full pb-24">
      <div role="tablist" className="flex items-center gap-space-xs mb-space-lg overflow-x-auto py-space-xs">
        {plan.alternatives.map((a, i) => {
          const st = planStyle(i)
          const on = i === index
          return (
            <button
              key={a.title}
              role="tab"
              aria-selected={on}
              onClick={() => onSelect(i)}
              className={`h-10 px-space-md rounded-full flex items-center gap-space-xs shadow-sm flex-shrink-0 transition-transform active:scale-95 ${
                on ? `${st.bg} text-on-primary` : 'bg-surface text-ink hover:bg-surface-container-low'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${on ? 'bg-on-primary' : st.bg}`} />
              <span className="font-label-md text-label-md whitespace-nowrap">
                {st.name} · {a.theme}
              </span>
            </button>
          )
        })}
      </div>

      <div className="bg-surface rounded-xl p-space-md shadow-sm mb-space-lg">
        <div className="flex items-center justify-between gap-space-xs mb-space-xs">
          {w ? (
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full font-label-sm text-label-sm ${
                w.is_bad ? 'bg-weather-bad-bg text-ink' : 'bg-weather-good-bg text-tertiary'
              }`}
            >
              <Icon
                name={w.is_bad ? 'rainy' : 'wb_sunny'}
                fill
                className={`text-[16px] ${w.is_bad ? 'text-weather-bad' : 'text-weather-good'}`}
              />
              <span className="capitalize">{w.condition}</span> • {Math.round(w.temperature)}°C
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-weather-unknown-bg text-weather-unknown font-label-sm text-label-sm">
              <Icon name="cloud_off" className="text-[16px]" />
              Hava bilgisi yok
            </span>
          )}
          <div className="flex items-center gap-space-xs">
            <span className="font-label-sm text-label-sm text-text-secondary bg-surface-container px-2.5 py-1 rounded-full">
              Toplam {formatHours(minutes)}
            </span>
            <button
              type="button"
              onClick={toggleFavorite}
              disabled={favorite === 'saving'}
              aria-label={savedId ? 'Kaydedilenlerden çıkar' : 'Kaydet'}
              className={`w-9 h-9 rounded-full flex items-center justify-center transition-colors ${
                savedId ? 'text-weather-good' : favorite === 'error' ? 'text-error' : 'text-ink hover:text-primary'
              }`}
            >
              <Icon name="star" fill={!!savedId} className="text-[20px]" />
            </button>
          </div>
        </div>
        {favorite === 'error' && (
          <p className="font-body-sm text-body-sm text-error -mt-1 mb-space-xs">Kaydedilemedi, tekrar dene.</p>
        )}
        <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-ink mb-space-xs">{alt.title}</h2>
        <p className="font-body-md text-body-md text-text-secondary leading-relaxed">
          {alt.summary} • Kişi başı {formatCost(cost)}
        </p>
      </div>

      <div className="bg-surface-container rounded-xl p-space-sm shadow-sm mb-space-xl">
        {recalculating && (
          <p className="font-body-sm text-body-sm text-text-secondary text-center pb-space-xs">Rota güncelleniyor…</p>
        )}
        <RouteMap alternative={alt} color={s.hex} origin={origin} approach={approachRoute} arrivedOrders={arrived} />
        {!alt.routes_available && (
          <p className="font-body-sm text-[11px] text-text-secondary text-center pt-space-xs">
            Rota çizgisi alınamadı, yalnızca duraklar gösteriliyor.
          </p>
        )}
      </div>

      <div className="bg-surface rounded-xl p-space-md shadow-sm mb-space-lg flex flex-col gap-space-md" aria-live="polite">
        <div className="flex items-center gap-space-sm">
          <div className="w-9 h-9 rounded-full bg-primary-fixed/50 flex items-center justify-center shrink-0">
            <Icon name="near_me" fill className="text-primary text-[20px]" />
          </div>
          <div className="flex flex-col min-w-0 flex-1">
            <span className="font-label-md text-label-md text-ink font-semibold">
              Konumunuzdan {first ? '1. durağa' : 'ilk durağa'}
            </span>
            {approach.state === 'ready' && (
              <span className="font-body-sm text-body-sm text-text-secondary">
                {TRAVEL_MODES[approach.route.travel_mode].emoji} {approach.route.duration_minutes} dk{' '}
                {TRAVEL_MODES[approach.route.travel_mode].verb} ({formatDistance(approach.route.distance_meters)})
              </span>
            )}
            {locationExplain && userLoc.status === 'idle' && (
              <span className="font-body-sm text-body-sm text-text-secondary">
                Yalnızca bulunduğunuz yerden ilk durağa olan mesafeyi hesaplamak için kullanılır,
                hiçbir yerde saklanmaz.
              </span>
            )}
            {!locationExplain &&
              (userLoc.status === 'idle' || userLoc.status === 'loading' || approach.state === 'loading') && (
                <span className="font-body-sm text-body-sm text-text-secondary">
                  Konumunuz alınıyor, rota hesaplanıyor…
                </span>
              )}
            {userLoc.status === 'denied' && (
              <span className="font-body-sm text-body-sm text-text-secondary">
                Konum izni verilmedi; rotayı başlatmak için konum gerekli.
              </span>
            )}
            {userLoc.status === 'ready' && approach.state === 'error' && (
              <span className="font-body-sm text-body-sm text-text-secondary">Konumunuzdan rota alınamadı.</span>
            )}
          </div>
        </div>
        {userLoc.status === 'denied' || (locationExplain && userLoc.status === 'idle') ? (
          <button
            type="button"
            onClick={useLocation}
            className="w-full h-12 rounded-xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-md text-label-md flex items-center justify-center gap-space-xs"
          >
            <Icon name="my_location" className="text-[18px]" />
            Konumumu Kullan
          </button>
        ) : (
          <button
            type="button"
            disabled={approach.state !== 'ready'}
            onClick={() => approach.state === 'ready' && onStartNavigation(approach.route)}
            className="w-full h-[52px] rounded-2xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-lg text-label-lg flex items-center justify-center gap-2 shadow-sm active:scale-[0.99] transition-transform disabled:opacity-50"
          >
            <Icon name="navigation" fill className="text-[22px]" />
            Rotayı Başlat
          </button>
        )}
      </div>

      <ol className="relative pl-6 mb-space-xl">
        <div className="absolute left-[13px] top-4 bottom-6 w-0.5 bg-surface-variant" />
        {stops.map((stop, i) => {
          const leg = alt.legs.find((l) => l.from_order === stop.order)
          const done = arrived.has(stop.order)
          return (
            <li key={stop.order} className="relative">
              <div
                className={`absolute -left-6 top-1.5 w-7 h-7 rounded-full ${s.bg} text-on-primary flex items-center justify-center font-label-md text-label-md shadow-sm ring-4 ring-background`}
              >
                {stop.order}
              </div>
              <div className={`bg-surface rounded-xl p-space-md shadow-sm ml-2 transition-opacity ${done ? 'opacity-50' : ''}`}>
                <div className="flex items-center justify-between gap-1.5 mb-space-xs">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className={`font-label-md text-label-md ${s.text}`}>{stop.order}. Durak</span>
                    <span className="text-text-secondary text-xs">•</span>
                    <span className="font-label-sm text-label-sm text-text-secondary">
                      {stop.arrival_time} ({stop.duration_minutes} dk)
                    </span>
                  </div>
                  <div className="flex items-center gap-0.5 flex-shrink-0">
                    <button
                      type="button"
                      onClick={() => moveStop(stop.order, -1)}
                      disabled={i === 0 || recalculating}
                      aria-label="Yukarı taşı"
                      className="w-7 h-7 rounded-full flex items-center justify-center text-text-secondary hover:text-ink disabled:opacity-30"
                    >
                      <Icon name="arrow_upward" className="text-[16px]" />
                    </button>
                    <button
                      type="button"
                      onClick={() => moveStop(stop.order, 1)}
                      disabled={i === stops.length - 1 || recalculating}
                      aria-label="Aşağı taşı"
                      className="w-7 h-7 rounded-full flex items-center justify-center text-text-secondary hover:text-ink disabled:opacity-30"
                    >
                      <Icon name="arrow_downward" className="text-[16px]" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setSwapFor(stop)}
                      disabled={recalculating}
                      aria-label="Durağı değiştir"
                      className="w-7 h-7 rounded-full flex items-center justify-center text-text-secondary hover:text-ink disabled:opacity-30"
                    >
                      <Icon name="swap_horiz" className="text-[16px]" />
                    </button>
                    <button
                      type="button"
                      onClick={() => void toggleFavoritePlace(stop)}
                      disabled={recalculating}
                      aria-label={isFavoritePlace(stop.place_id) ? 'Mekanı favorilerden çıkar' : 'Mekanı favorile'}
                      className={`w-7 h-7 rounded-full flex items-center justify-center disabled:opacity-30 ${
                        isFavoritePlace(stop.place_id) ? 'text-plan-a' : 'text-text-secondary hover:text-ink'
                      }`}
                    >
                      <Icon name="favorite" fill={isFavoritePlace(stop.place_id)} className="text-[16px]" />
                    </button>
                    <button
                      type="button"
                      onClick={() => removeStop(stop.order)}
                      disabled={stops.length <= 1 || recalculating}
                      aria-label="Durağı sil"
                      className="w-7 h-7 rounded-full flex items-center justify-center text-error disabled:opacity-30"
                    >
                      <Icon name="delete" className="text-[16px]" />
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 mb-space-xs">
                  <h3 className="font-headline-md text-headline-md text-ink">{stop.name ?? stop.activity}</h3>
                  <a
                    href={mapsUrl(stop)}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Google Maps'te gör (gerçek fotoğraflar ve yorumlar)"
                    className="text-text-secondary hover:text-primary flex-shrink-0"
                  >
                    <Icon name="open_in_new" className="text-[16px]" />
                  </a>
                </div>
                <div className="bg-surface-container-low rounded-lg p-2.5 mt-space-xs mb-space-xs flex flex-col gap-1.5">
                  <p className="font-body-md text-body-md text-on-surface-variant">{stop.activity}</p>
                  <p className="font-body-md text-body-md text-on-surface-variant">💡 {stop.recommendation}</p>
                </div>
                <div className="flex items-center justify-between pt-space-xs">
                  <span className="inline-flex items-center gap-1 font-label-sm text-label-sm text-ink bg-surface-container px-2 py-1 rounded-full">
                    💰 {formatCost(stop.estimated_cost)} / kişi
                  </span>
                  <button
                    type="button"
                    aria-pressed={done}
                    onClick={() => toggleArrived(stop)}
                    className={`flex items-center gap-1 text-xs font-label-sm transition-colors ${
                      done ? 'text-success' : 'text-text-secondary hover:text-ink'
                    }`}
                  >
                    <Icon name="check_circle" fill={done} className="text-[18px]" />
                    <span>Ulaşıldı</span>
                  </button>
                </div>
              </div>

              {leg && i < stops.length - 1 && (
                <div className="relative ml-2 my-space-sm pl-4 flex items-center gap-2 py-1">
                  <div className="inline-flex self-start items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-highest text-ink font-label-sm text-label-sm">
                    <span aria-hidden>{TRAVEL_MODES[leg.travel_mode].emoji}</span>
                    <span>
                      {leg.duration_minutes} dk {TRAVEL_MODES[leg.travel_mode].verb} ({formatDistance(leg.distance_meters)})
                    </span>
                  </div>
                </div>
              )}
              {i < stops.length - 1 && !leg && <div className="h-space-lg" />}
            </li>
          )
        })}
      </ol>

      <button
        type="button"
        onClick={() => setAdding(true)}
        disabled={recalculating}
        className="mb-space-xl h-12 rounded-xl border-2 border-dashed border-outline-variant text-text-secondary hover:text-ink hover:border-ink font-label-md text-label-md flex items-center justify-center gap-1.5 disabled:opacity-40"
      >
        <Icon name="add" className="text-[18px]" />
        Durak ekle
      </button>

      <div className="fixed bottom-16 left-0 right-0 z-40 bg-gradient-to-t from-background via-background/95 to-transparent pt-4 pb-3 px-margin">
        <div className="max-w-md mx-auto flex gap-space-sm">
          <button
            type="button"
            onClick={onPrefs}
            className="flex-1 h-12 rounded-xl bg-surface text-ink font-label-md text-label-md flex items-center justify-center gap-space-xs shadow-sm"
          >
            <Icon name="tune" className="text-[18px]" />
            Tercihleri Değiştir
          </button>
          <button
            type="button"
            onClick={share}
            className="flex-1 h-12 rounded-xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-md text-label-md flex items-center justify-center gap-space-xs shadow-sm"
          >
            <Icon name={shared ? 'check' : 'share'} className="text-[18px]" />
            {shared ? 'Kopyalandı' : 'Bu Planı Paylaş'}
          </button>
        </div>
      </div>

      {(swapFor || adding) && (
        <StopEditSheet
          mode={swapFor ? 'replace' : 'add'}
          stop={swapFor}
          pool={plan.place_pool ?? []}
          near={searchCenter}
          accessToken={session?.access_token}
          favoritePlaces={favoritePlaces}
          usedIds={new Set(plan.alternatives.flatMap((a) => a.stops.map((st) => st.place_id)))}
          alternatives={plan.alternatives}
          currentIndex={index}
          canTransferOut={stops.length > 1}
          onPickPlace={swapFor ? swapPlace : addPlace}
          onTransferOut={transferOut}
          onTransferIn={transferIn}
          onClose={() => {
            setSwapFor(null)
            setAdding(false)
          }}
        />
      )}
    </div>
  )
}
