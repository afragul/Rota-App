import type { Session } from '@supabase/supabase-js'
import { useEffect, useState } from 'react'
import { supabase } from './supabase'

export interface Auth {
  session: Session | null
  loading: boolean
  /** Kullanıcı şifre sıfırlama e-postasındaki linke tıklayıp geri döndüğünde true olur. */
  recovery: boolean
  clearRecovery: () => void
}

// Supabase oturumunu izler; giriş isteğe bağlı olduğu için uygulama bu hook'u
// beklemeden de render edilir (bkz. App.tsx'teki loading kullanımı).
export function useAuth(): Auth {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [recovery, setRecovery] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data: subscription } = supabase.auth.onAuthStateChange((event, next) => {
      setSession(next)
      if (event === 'PASSWORD_RECOVERY') setRecovery(true)
    })
    return () => subscription.subscription.unsubscribe()
  }, [])

  return { session, loading, recovery, clearRecovery: () => setRecovery(false) }
}
