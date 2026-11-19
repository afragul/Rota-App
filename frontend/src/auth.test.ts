import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// auth.ts modül yüklenirken oturumu okur ve zamanlayıcı/olay dinleyicisi kurar: her testte
// ortamı (localStorage, window, navigator, fetch) kurup modülü SIFIRDAN yüklüyoruz.

const SESSION_KEY = 'bugunluk.session'
const HINT_KEY = 'bugunluk.hint'
const USER = { id: 'u1', email: 'ada@example.com', username: 'ada' }

const fetchMock = vi.fn()
type Listener = (e?: unknown) => void

function tokenBody(token: string, expiresIn = 900) {
  return { access_token: token, expires_in: expiresIn, user: USER }
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function storedSession(token: string, expiresInMs: number) {
  return JSON.stringify({ access_token: token, expires_at: Date.now() + expiresInMs, user: USER })
}

async function loadAuth(opts: { storage?: Record<string, string>; webLocks?: boolean } = {}) {
  vi.resetModules()
  const store = new Map(Object.entries(opts.storage ?? {}))
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  })
  const windowListeners: Record<string, Listener[]> = {}
  const documentListeners: Record<string, Listener[]> = {}
  vi.stubGlobal('window', {
    addEventListener: (t: string, l: Listener) => (windowListeners[t] ??= []).push(l),
  })
  const doc = {
    visibilityState: 'visible',
    addEventListener: (t: string, l: Listener) => (documentListeners[t] ??= []).push(l),
  }
  vi.stubGlobal('document', doc)
  const lockRequest = vi.fn(async (_name: string, cb: () => Promise<void>) => cb())
  vi.stubGlobal('navigator', opts.webLocks === false ? {} : { locks: { request: lockRequest } })
  vi.stubGlobal('fetch', fetchMock)

  const auth = await import('./auth')
  return {
    auth,
    store,
    lockRequest,
    fireWindow: (type: string, e?: unknown) => windowListeners[type]?.forEach((l) => l(e)),
    fireDocument: (type: string) => documentListeners[type]?.forEach((l) => l()),
    setVisibility: (v: string) => (doc.visibilityState = v),
  }
}

const refreshCalls = () => fetchMock.mock.calls.filter(([url]) => url === '/api/auth/refresh')
const flush = () => vi.advanceTimersByTimeAsync(0)

beforeEach(() => {
  vi.useFakeTimers()
  fetchMock.mockReset()
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('açılış (siteye tekrar girme)', () => {
  it('hiç giriş yapılmamış misafir: oturum yok, yükleniyor değil, hiç istek yok', async () => {
    const { auth } = await loadAuth()
    await flush()

    expect(auth.getSession()).toBeNull()
    expect(auth.isAuthLoading()).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('geçerli token kayıtlıysa oturum anında gelir ve istek atılmaz', async () => {
    const { auth } = await loadAuth({ storage: { [SESSION_KEY]: storedSession('tkn', 600_000), [HINT_KEY]: '1' } })

    expect(auth.getSession()?.access_token).toBe('tkn')
    expect(auth.isAuthLoading()).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('süresi dolmuş token + giriş ipucu: açılışta TEK refresh isteği, oturum geri gelir', async () => {
    // Yanıtı elle bitiriyoruz: "yükleniyor" durumu refresh sürerken gözlemlenebilsin.
    let finish!: (r: Response) => void
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => (finish = resolve)))
    const { auth, store } = await loadAuth({
      storage: { [SESSION_KEY]: storedSession('eski', -1000), [HINT_KEY]: '1' },
    })
    await flush()

    expect(auth.getSession()).toBeNull()
    expect(auth.isAuthLoading()).toBe(true) // bu sürede UI "misafir" kararı vermemeli
    expect(refreshCalls()).toHaveLength(1)

    finish(json(tokenBody('yeni')))
    await flush()

    expect(refreshCalls()).toHaveLength(1)
    expect(auth.getSession()?.access_token).toBe('yeni')
    expect(auth.isAuthLoading()).toBe(false)
    expect(JSON.parse(store.get(SESSION_KEY)!).access_token).toBe('yeni')
  })

  it('refresh 401 (çerez süresi doldu): oturum ve ipucu temizlenir, tekrar denenmez', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'Oturum süresi doldu' }, 401))
    const { auth, store } = await loadAuth({ storage: { [HINT_KEY]: '1' } })
    await flush()

    expect(auth.getSession()).toBeNull()
    expect(auth.isAuthLoading()).toBe(false)
    expect(store.has(HINT_KEY)).toBe(false)

    await vi.advanceTimersByTimeAsync(10 * 60_000)
    expect(refreshCalls()).toHaveLength(1)
  })

  it('refresh sırasında ağ hatası: yükleniyor biter, ipucu korunur (çıkış sayılmaz)', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const { auth, store } = await loadAuth({ storage: { [HINT_KEY]: '1' } })
    await flush()

    expect(auth.isAuthLoading()).toBe(false)
    expect(store.get(HINT_KEY)).toBe('1')
  })

  it('bozuk kayıtlı oturum JSON\'u misafir gibi açılır, hata fırlatmaz', async () => {
    const { auth } = await loadAuth({ storage: { [SESSION_KEY]: '{bozuk' } })

    expect(auth.getSession()).toBeNull()
  })
})

describe('sessiz yenileme', () => {
  it('süre dolmadan 60 sn önce yenilenir', async () => {
    fetchMock.mockResolvedValue(json(tokenBody('yeni')))
    const { auth } = await loadAuth({ storage: { [SESSION_KEY]: storedSession('eski', 300_000) } })

    await vi.advanceTimersByTimeAsync(239_000)
    expect(refreshCalls()).toHaveLength(0)
    await vi.advanceTimersByTimeAsync(2_000)

    expect(refreshCalls()).toHaveLength(1)
    expect(auth.getSession()?.access_token).toBe('yeni')
  })

  it('yenileme bir sonrakini planlar (oturum sürekli taze kalır)', async () => {
    fetchMock.mockImplementation(async () => json(tokenBody(`t${fetchMock.mock.calls.length}`, 900)))
    await loadAuth({ storage: { [SESSION_KEY]: storedSession('eski', 100_000) } })

    await vi.advanceTimersByTimeAsync(45 * 60_000)

    expect(refreshCalls().length).toBeGreaterThanOrEqual(3)
  })

  it('oturum açıkken ağ hatası: oturum korunur, 30 sn sonra tekrar dener', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('x')).mockResolvedValue(json(tokenBody('yeni')))
    const { auth } = await loadAuth({ storage: { [SESSION_KEY]: storedSession('eski', 61_000) } })

    await vi.advanceTimersByTimeAsync(5_000) // minimum gecikme sonrası ilk deneme (başarısız)
    expect(refreshCalls()).toHaveLength(1)
    expect(auth.getSession()?.access_token).toBe('eski')

    await vi.advanceTimersByTimeAsync(30_000)
    expect(refreshCalls()).toHaveLength(2)
    expect(auth.getSession()?.access_token).toBe('yeni')
  })

  it('oturum açıkken 401: yerel oturum kapanır', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'x' }, 401))
    const { auth, store } = await loadAuth({
      storage: { [SESSION_KEY]: storedSession('eski', 61_000), [HINT_KEY]: '1' },
    })

    await vi.advanceTimersByTimeAsync(10_000)

    expect(auth.getSession()).toBeNull()
    expect(store.has(SESSION_KEY)).toBe(false)
    expect(store.has(HINT_KEY)).toBe(false)
  })

  it('Web Locks yoksa da yenileme çalışır; varsa kilit altında çağrılır', async () => {
    fetchMock.mockResolvedValue(json(tokenBody('yeni')))
    const without = await loadAuth({ webLocks: false, storage: { [SESSION_KEY]: storedSession('e', 61_000) } })
    await vi.advanceTimersByTimeAsync(10_000)
    expect(without.auth.getSession()?.access_token).toBe('yeni')

    const withLocks = await loadAuth({ storage: { [SESSION_KEY]: storedSession('e', 61_000) } })
    await vi.advanceTimersByTimeAsync(10_000)
    expect(withLocks.lockRequest).toHaveBeenCalledWith('bugunluk-refresh', expect.any(Function))
  })

  it('başka sekme az önce yeniledi: taze token alınır, tekrar yenilenmez', async () => {
    const { auth, store } = await loadAuth({ storage: { [SESSION_KEY]: storedSession('eski', 61_000) } })
    // Zamanlayıcı dolmadan başka sekme localStorage'a taze bir token yazdı
    store.set(SESSION_KEY, storedSession('diger-sekme', 900_000))

    await vi.advanceTimersByTimeAsync(10_000)

    expect(refreshCalls()).toHaveLength(0)
    expect(auth.getSession()?.access_token).toBe('diger-sekme')
  })
})

describe('sekme olayları', () => {
  it('gizli sekme görünür olunca süre azsa hemen yeniler, çoksa yenilemez', async () => {
    fetchMock.mockResolvedValue(json(tokenBody('yeni')))
    const env = await loadAuth({ storage: { [SESSION_KEY]: storedSession('eski', 30_000) } })

    env.fireDocument('visibilitychange')
    await flush()
    expect(refreshCalls()).toHaveLength(1)

    fetchMock.mockClear()
    env.fireDocument('visibilitychange') // artık 15 dk'lık taze token var
    await flush()
    expect(refreshCalls()).toHaveLength(0)
  })

  it('sekme hâlâ gizliyse yenilemez', async () => {
    const env = await loadAuth({ storage: { [SESSION_KEY]: storedSession('eski', 30_000) } })
    env.setVisibility('hidden')

    env.fireDocument('visibilitychange')
    await flush()

    expect(refreshCalls()).toHaveLength(0)
  })

  it('başka sekmedeki giriş/çıkış (storage olayı) bu sekmeye yansır', async () => {
    const env = await loadAuth()
    env.store.set(SESSION_KEY, storedSession('baska-sekme', 600_000))
    env.fireWindow('storage', { key: SESSION_KEY })
    expect(env.auth.getSession()?.access_token).toBe('baska-sekme')

    env.store.delete(SESSION_KEY)
    env.fireWindow('storage', { key: SESSION_KEY })
    expect(env.auth.getSession()).toBeNull()
  })

  it('ilgisiz anahtarın storage olayı oturumu etkilemez', async () => {
    const env = await loadAuth({ storage: { [SESSION_KEY]: storedSession('tkn', 600_000) } })
    env.store.delete(SESSION_KEY)

    env.fireWindow('storage', { key: 'baska.anahtar' })

    expect(env.auth.getSession()?.access_token).toBe('tkn')
  })
})

describe('giriş / çıkış / hesap işlemleri', () => {
  it('signIn oturumu kurar ve localStorage + ipucuna yazar', async () => {
    fetchMock.mockResolvedValue(json(tokenBody('girdi')))
    const { auth, store } = await loadAuth()

    await auth.signIn('ada@example.com', 'sifre-1234')

    expect(auth.getSession()?.user).toEqual(USER)
    expect(JSON.parse(store.get(SESSION_KEY)!).access_token).toBe('girdi')
    expect(store.get(HINT_KEY)).toBe('1')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ email: 'ada@example.com', password: 'sifre-1234' })
  })

  it('yanlış şifrede signIn fırlatır ve oturum açılmaz', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'E-posta veya şifre hatalı' }, 401))
    const { auth } = await loadAuth()

    await expect(auth.signIn('a@b.co', 'x')).rejects.toMatchObject({ status: 401 })
    expect(auth.getSession()).toBeNull()
  })

  it('signUp kayıt sonrası doğrudan oturum açar', async () => {
    fetchMock.mockResolvedValue(json(tokenBody('kayit'), 201))
    const { auth } = await loadAuth()

    await auth.signUp('ada@example.com', 'ada', 'sifre-1234')

    expect(auth.getSession()?.access_token).toBe('kayit')
  })

  it('signOut yerel oturumu hemen kapatır, sunucuya logout gider; sunucu hatası yutulur', async () => {
    fetchMock.mockRejectedValue(new TypeError('ağ yok'))
    const { auth, store } = await loadAuth({
      storage: { [SESSION_KEY]: storedSession('tkn', 600_000), [HINT_KEY]: '1' },
    })

    auth.signOut()
    await flush()

    expect(auth.getSession()).toBeNull()
    expect(store.has(SESSION_KEY)).toBe(false)
    expect(store.has(HINT_KEY)).toBe(false)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/logout')
  })

  it('updateUsername kullanıcı adını günceller, token aynı kalır', async () => {
    fetchMock.mockResolvedValue(json({ ...USER, username: 'yeni-ad' }))
    const { auth } = await loadAuth({ storage: { [SESSION_KEY]: storedSession('tkn', 600_000) } })

    await auth.updateUsername('yeni-ad')

    expect(auth.getSession()?.user.username).toBe('yeni-ad')
    expect(auth.getSession()?.access_token).toBe('tkn')
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer tkn')
  })

  it('oturum yokken updateUsername / changePassword / deleteAccount hiçbir istek atmaz', async () => {
    const { auth } = await loadAuth()

    await auth.updateUsername('x')
    await auth.changePassword('a', 'b')
    await auth.deleteAccount('p')

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('deleteAccount başarıda oturumu kapatır; yanlış şifrede fırlatır ve oturum açık kalır', async () => {
    const { auth } = await loadAuth({ storage: { [SESSION_KEY]: storedSession('tkn', 600_000) } })

    fetchMock.mockResolvedValueOnce(json({ detail: 'Şifre hatalı' }, 403))
    await expect(auth.deleteAccount('yanlis')).rejects.toMatchObject({ status: 403 })
    expect(auth.getSession()).not.toBeNull()

    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await auth.deleteAccount('dogru')
    expect(auth.getSession()).toBeNull()
  })

  it('changePassword oturumu bozmaz (backend bu cihaza yeni çerez verir)', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    const { auth } = await loadAuth({ storage: { [SESSION_KEY]: storedSession('tkn', 600_000) } })

    await auth.changePassword('eski', 'yeni-sifre-1')

    expect(auth.getSession()?.access_token).toBe('tkn')
  })
})

describe('token beklenenden önce geçersiz olursa', () => {
  it('korumalı istek 401 alınca otomatik refresh denenir ve oturum yenilenir', async () => {
    const { auth } = await loadAuth({ storage: { [SESSION_KEY]: storedSession('eski', 600_000) } })
    fetchMock
      .mockResolvedValueOnce(json({ detail: 'Geçersiz' }, 401)) // PATCH /me
      .mockResolvedValueOnce(json(tokenBody('taze'))) // /auth/refresh

    await expect(auth.updateUsername('x')).rejects.toMatchObject({ status: 401 })
    await flush()

    expect(refreshCalls()).toHaveLength(1)
    expect(auth.getSession()?.access_token).toBe('taze')
  })
})
