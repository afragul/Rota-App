import { useState } from 'react'
import { Icon } from '../components/Icon'

interface Props {
  question: string
  onAnswer: (answer: string) => void
  onBack: () => void
}

// Planlayıcı belirsiz bir istekte plan yerine tek bir netleştirme sorusu sorar.
// Stitch tasarımında bu ekran yok; ekran diliyle (kart + mercan buton) çizildi.
export function ClarifyScreen({ question, onAnswer, onBack }: Props) {
  const [answer, setAnswer] = useState('')
  const trimmed = answer.trim()

  return (
    <form
      className="flex flex-col gap-space-lg pt-space-lg"
      onSubmit={(e) => {
        e.preventDefault()
        if (trimmed) onAnswer(trimmed)
      }}
    >
      <div className="flex flex-col gap-1.5">
        <div className="inline-flex items-center gap-1.5 self-start px-3 py-1 rounded-full bg-weather-good-bg text-tertiary font-label-sm text-label-sm">
          <Icon name="auto_awesome" fill className="text-[16px] text-weather-good" />
          <span>Küçük bir sorum var</span>
        </div>
        <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-ink tracking-tight mt-1">Planı netleştirelim</h2>
      </div>

      <div className="bg-surface rounded-2xl p-5 shadow-sm flex flex-col gap-4">
        <p className="font-headline-md text-headline-md text-ink" role="status">
          {question}
        </p>
        <input
          type="text"
          autoFocus
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Cevabınızı yazın"
          aria-label="Cevap"
          className="w-full h-12 px-4 bg-surface-container-low text-ink font-body-md text-body-md rounded-xl placeholder:text-text-secondary/70 focus:outline-none focus:bg-surface"
        />
      </div>

      <div className="flex flex-col gap-space-sm">
        <button
          type="submit"
          disabled={!trimmed}
          className="w-full h-[52px] rounded-2xl bg-plan-a hover:bg-primary-strong text-on-primary font-label-lg text-label-lg flex items-center justify-center gap-2 shadow-sm active:scale-[0.99] transition-transform disabled:opacity-50"
        >
          <Icon name="auto_awesome" className="text-[20px]" />
          Devam Et
        </button>
        <button
          type="button"
          onClick={onBack}
          className="w-full h-12 rounded-xl bg-surface text-ink font-label-md text-label-md flex items-center justify-center gap-space-xs shadow-sm"
        >
          <Icon name="tune" className="text-[18px]" />
          Tercihleri Değiştir
        </button>
      </div>
    </form>
  )
}
