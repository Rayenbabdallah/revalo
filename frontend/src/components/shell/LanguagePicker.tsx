import clsx from 'clsx'
import { Languages } from 'lucide-react'

import { getLocale, LOCALES, setLocale, t } from '../../lib/i18n'

/** English, French or Arabic. Each name is written in its own language. */
export function LanguagePicker({ className }: { className?: string }) {
  const current = getLocale()
  return (
    <div role="group" aria-label={t('Language')} className={clsx('flex items-center gap-1', className)}>
      <Languages className="me-1 size-4 text-ink-400" aria-hidden="true" />
      {LOCALES.map(({ id, name }) => (
        <button
          key={id}
          type="button"
          lang={id}
          onClick={() => setLocale(id)}
          aria-pressed={current === id}
          className={clsx(
            'rounded-lg px-2 py-1 text-[12.5px] font-medium transition',
            current === id ? 'bg-brand-500 text-ink-950' : 'text-ink-300 hover:bg-ink-850 hover:text-ink-50',
          )}
        >
          {name}
        </button>
      ))}
    </div>
  )
}
