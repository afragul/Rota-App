import type { ReactNode } from 'react'
import type { Theme } from '../theme'
import { Icon } from './Icon'
import { Logo } from './Logo'

export type NavKey = 'discover' | 'plans' | 'preferences'

interface Props {
  title: string
  nav: NavKey | null
  plansEnabled: boolean
  onNav: (key: NavKey) => void
  onBack?: () => void
  theme: Theme
  onToggleTheme: () => void
  children: ReactNode
}

const NAV: { key: NavKey; label: string; icon: string }[] = [
  { key: 'discover', label: 'Keşfet', icon: 'explore' },
  { key: 'plans', label: 'Planlar', icon: 'alt_route' },
  { key: 'preferences', label: 'Tercihler', icon: 'tune' },
]

// Stitch ekranlarının ortak iskeleti: üstte logo + başlık, altta sekme çubuğu.
// Tasarımdaki "Kayıtlar" sekmesi ve profil rozeti backend karşılığı olmadığı için yok.
export function Shell({ title, nav, plansEnabled, onNav, onBack, theme, onToggleTheme, children }: Props) {
  return (
    <>
      <header className="fixed top-0 w-full z-50 bg-background/85 backdrop-blur-xl pt-safe shadow-[0_1px_8px_rgba(0,0,0,0.03)]">
        <div className="max-w-md mx-auto h-16 px-margin flex items-center justify-between gap-space-sm">
          <div className="flex items-center gap-space-sm min-w-0">
            {onBack ? (
              <button
                aria-label="Geri"
                onClick={onBack}
                className="w-10 h-10 -ml-2 rounded-full flex items-center justify-center text-ink hover:text-primary transition-colors"
              >
                <Icon name="arrow_back" className="text-[24px]" />
              </button>
            ) : (
              <Logo className="h-8 w-auto flex-shrink-0" />
            )}
            <div className="flex flex-col min-w-0">
              {!onBack && (
                <span className="font-label-sm text-label-sm text-text-secondary uppercase tracking-wider truncate">
                  Rota AI
                </span>
              )}
              <h1 className="font-headline-md text-headline-md text-ink truncate leading-tight">{title}</h1>
            </div>
          </div>
          <button
            aria-label={theme === 'dark' ? 'Aydınlık temaya geç' : 'Koyu temaya geç'}
            onClick={onToggleTheme}
            className="w-10 h-10 rounded-full flex items-center justify-center text-ink hover:text-primary transition-colors flex-shrink-0"
          >
            <Icon name={theme === 'dark' ? 'light_mode' : 'dark_mode'} className="text-[22px]" />
          </button>
        </div>
      </header>

      <main className="flex-1 flex flex-col relative w-full max-w-md mx-auto px-margin pt-16 pb-24 bg-background min-h-screen">
        {children}
      </main>

      <nav className="fixed bottom-0 w-full z-50 pb-safe bg-surface/90 backdrop-blur-xl shadow-[0_-4px_16px_-2px_rgba(31,42,68,0.05)]">
        <div className="max-w-md mx-auto h-16 px-space-md flex items-center justify-around">
          {NAV.map((item) => {
            const active = nav === item.key
            const disabled = item.key === 'plans' && !plansEnabled
            return (
              <button
                key={item.key}
                disabled={disabled}
                aria-current={active ? 'page' : undefined}
                onClick={() => onNav(item.key)}
                className={`flex flex-col items-center justify-center gap-space-xs w-16 h-12 transition-colors disabled:opacity-40 ${
                  active ? 'text-primary font-label-md' : 'text-text-secondary hover:text-ink'
                }`}
              >
                <Icon name={item.icon} fill={active} className="text-[24px]" />
                <span className="font-label-sm text-label-sm">{item.label}</span>
              </button>
            )
          })}
        </div>
      </nav>
    </>
  )
}
