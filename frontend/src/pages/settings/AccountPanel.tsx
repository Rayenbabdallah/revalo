import { useMutation } from '@tanstack/react-query'
import { Check } from 'lucide-react'
import { useState } from 'react'

import { changePassword } from '../../lib/api'
import { ROLE_HINT, ROLE_LABEL, useUser } from '../../lib/auth'
import { t } from '../../lib/i18n'

const INPUT =
  'mt-1.5 w-full rounded-xl border border-ink-700 bg-ink-950 px-3 py-2 text-[14px] text-ink-50 focus:border-brand-500 focus:outline-none'

/** The signed-in person's own account. */
export function AccountPanel() {
  const user = useUser()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const save = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => {
      setCurrent('')
      setNext('')
      setAgain('')
    },
  })
  const mismatch = again.length > 0 && next !== again

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="panel p-6">
        <p className="eyebrow">{t('Signed in as')}</p>
        <p className="mt-3 font-display text-2xl font-semibold text-ink-50">{user.name}</p>
        <p className="text-[14px] text-ink-400">{user.email}</p>
        <p className="mt-4 text-[14px] text-ink-200">
          <span className="font-semibold">{ROLE_LABEL[user.role]}.</span> {ROLE_HINT[user.role]}
        </p>
        <p className="mt-2 text-[12.5px] text-ink-500">{t('Your name goes on every record you approve or change.')}</p>
      </section>

      <form
        className="panel space-y-4 p-6"
        onSubmit={(e) => {
          e.preventDefault()
          if (!mismatch) save.mutate()
        }}
      >
        <p className="text-[15px] font-semibold text-ink-100">{t('Change your password')}</p>
        <label className="block text-[13px] font-medium text-ink-200">
          {t('Current password')}
          <input
            type="password"
            required
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            className={INPUT}
          />
        </label>
        <label className="block text-[13px] font-medium text-ink-200">
          {t('New password')}
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className={INPUT}
          />
        </label>
        <label className="block text-[13px] font-medium text-ink-200">
          {t('New password again')}
          <input
            type="password"
            required
            autoComplete="new-password"
            value={again}
            onChange={(e) => setAgain(e.target.value)}
            aria-invalid={mismatch}
            className={INPUT}
          />
        </label>
        {mismatch && <p className="text-[13px] text-alarm-400">{t('The two new passwords differ.')}</p>}
        {save.isError && <p className="text-[13px] text-alarm-400">{save.error.message}</p>}
        {save.isSuccess && (
          <p className="inline-flex items-center gap-1.5 text-[13px] text-reclaim-300">
            <Check className="size-4" /> {t('Password changed.')}
          </p>
        )}
        <button
          type="submit"
          disabled={save.isPending || mismatch}
          className="block rounded-xl bg-brand-500 px-4 py-2.5 text-[14px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60"
        >
          {t('Save password')}
        </button>
      </form>
    </div>
  )
}
