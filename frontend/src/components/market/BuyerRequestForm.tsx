import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState, type FormEvent, type ReactNode } from 'react'

import {
  getGovernorates,
  getMaterials,
  postBuyerRequest,
  type BuyerKind,
  type BuyerRequestInput,
  type PublicListing,
} from '../../lib/api'
import { materialLabel } from '../../lib/format'
import { t } from '../../lib/i18n'

const field =
  'w-full rounded-xl border border-ink-700 bg-ink-900 px-3 py-2.5 text-[14px] text-ink-50 placeholder:text-ink-500 focus:border-brand-500 focus:outline-none'

function Label({ text, hint, children }: { text: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline justify-between text-[13px] font-medium text-ink-200">
        {text}
        {hint && <span className="font-mono text-[10.5px] font-normal text-ink-500">{hint}</span>}
      </span>
      {children}
    </label>
  )
}

const num = (v: string) => (v.trim() === '' ? undefined : Number(v.replace(',', '.')))

/** What a buyer needs. Used on the public page and by the workshop to add a known contact. */
export function BuyerRequestForm({
  onPosted,
  submitLabel = t('Post my request'),
}: {
  onPosted?: (matches: PublicListing[]) => void
  submitLabel?: string
}) {
  const catalog = useQuery({ queryKey: ['materials'], queryFn: getMaterials, staleTime: Infinity })
  const regions = useQuery({ queryKey: ['governorates'], queryFn: getGovernorates, staleTime: Infinity })
  const [kind, setKind] = useState<BuyerKind>('reuse')
  const [chosen, setChosen] = useState<string[]>([])
  const post = useMutation({
    mutationFn: postBuyerRequest,
    onSuccess: (res) => onPosted?.(res.matching_listings),
  })

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    const text = (k: string) => String(f.get(k) ?? '').trim()
    const body: BuyerRequestInput = {
      kind,
      name: text('name'),
      organization: text('organization') || undefined,
      phone: text('phone'),
      governorate: text('governorate'),
      materials: chosen,
      thickness_min_mm: num(text('tmin')),
      thickness_max_mm: num(text('tmax')),
      min_length_mm: kind === 'reuse' ? num(text('length')) : undefined,
      min_width_mm: kind === 'reuse' ? num(text('width')) : undefined,
      max_price_tnd_per_kg: kind === 'reuse' ? num(text('price')) : undefined,
      offered_tnd_per_kg: kind === 'recycler' ? num(text('offer')) : undefined,
      min_lot_kg: kind === 'recycler' ? num(text('minlot')) : undefined,
      pickup_note: kind === 'recycler' ? text('pickup') || undefined : undefined,
      note: text('note') || undefined,
      buys_lots: kind === 'reuse' ? f.get('lots') === 'on' : undefined,
    }
    post.mutate(body)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-2 gap-2 rounded-xl bg-ink-800 p-1">
        {([
          ['reuse', t('I reuse offcuts')],
          ['recycler', t('I buy scrap by weight')],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setKind(value)}
            className={clsx(
              'rounded-lg px-3 py-2 text-[13px] font-medium transition',
              kind === value ? 'bg-ink-900 text-brand-500 shadow-sm' : 'text-ink-400 hover:text-ink-100',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Label text={t('Your name')}>
          <input name="name" required minLength={2} className={field} placeholder={t('Karim')} />
        </Label>
        <Label text={t('Workshop or company')} hint={t('optional')}>
          <input name="organization" className={field} placeholder={t('Menuiserie Karim')} />
        </Label>
        <Label text={t('WhatsApp number')}>
          <input name="phone" required inputMode="tel" className={field} placeholder="22 123 456" />
        </Label>
        <Label text={t('Governorate')}>
          <select name="governorate" required defaultValue="" className={field}>
            <option value="" disabled>
              {t('Choose…')}
            </option>
            {regions.data?.governorates.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </Label>
      </div>

      <div>
        <p className="mb-1.5 text-[13px] font-medium text-ink-200">
          {t('Materials')} <span className="font-normal text-ink-500">{t('· none selected means any')}</span>
        </p>
        <div className="flex flex-wrap gap-1.5">
          {catalog.data?.materials.map((m) => {
            const on = chosen.includes(m.code)
            return (
              <button
                key={m.code}
                type="button"
                aria-pressed={on}
                onClick={() => setChosen((c) => (on ? c.filter((x) => x !== m.code) : [...c, m.code]))}
                className={clsx(
                  'rounded-full border px-3 py-1 text-[12.5px] transition',
                  on ? 'border-brand-500 bg-brand-500 text-ink-950' : 'border-ink-700 text-ink-300 hover:border-ink-500',
                )}
              >
                {materialLabel(m.code)}
              </button>
            )
          })}
        </div>
      </div>

      <div className={clsx('grid gap-3', kind === 'reuse' ? 'grid-cols-2 sm:grid-cols-5' : 'grid-cols-3')}>
        <Label text={t('Thickness from')} hint={t('mm')}>
          <input name="tmin" inputMode="decimal" className={field} />
        </Label>
        <Label text={t('to')} hint={t('mm')}>
          <input name="tmax" inputMode="decimal" className={field} />
        </Label>
        {kind === 'reuse' && (
          <>
            <Label text={t('Min. length')} hint={t('mm')}>
              <input name="length" inputMode="numeric" className={field} />
            </Label>
            <Label text={t('Min. width')} hint={t('mm')}>
              <input name="width" inputMode="numeric" className={field} />
            </Label>
          </>
        )}
        {kind === 'reuse' ? (
          <Label text={t('Max. price')} hint={t('TND/kg')}>
            <input name="price" inputMode="decimal" className={field} />
          </Label>
        ) : (
          <Label text={t('You pay')} hint={t('TND/kg')}>
            <input name="offer" inputMode="decimal" className={field} placeholder="0.27" />
          </Label>
        )}
      </div>

      {kind === 'recycler' && (
        <div className="grid gap-3 sm:grid-cols-[140px_1fr]">
          <Label text={t('Smallest lot')} hint={t('kg')}>
            <input name="minlot" inputMode="numeric" className={field} placeholder="200" />
          </Label>
          <Label text={t('Pickup terms')} hint={t('optional')}>
            <input name="pickup" className={field} placeholder={t('Tuesdays and Fridays, light truck')} />
          </Label>
        </div>
      )}

      {kind === 'reuse' && (
        <label className="flex items-center gap-2.5 rounded-xl border border-ink-700 bg-ink-900 px-3.5 py-3 text-[14px] text-ink-200">
          <input type="checkbox" name="lots" className="size-4 accent-[var(--color-brand-500)]" />
          {t('I can take whole lots of similar offcuts')}
        </label>
      )}

      <Label text={t('Anything else')} hint={t('optional')}>
        <input name="note" className={field} placeholder={t('Collected on Saturdays, light truck…')} />
      </Label>

      {post.isError && <p className="text-[13px] text-alarm-400">{post.error.message}</p>}
      <button
        type="submit"
        disabled={post.isPending}
        className="w-full rounded-xl bg-brand-500 py-3 text-[15px] font-semibold text-ink-950 shadow-[0_10px_30px_-12px_rgb(25_74_203_/_0.7)] transition hover:bg-brand-400 disabled:opacity-60"
      >
        {post.isPending ? t('Sending…') : submitLabel}
      </button>
    </form>
  )
}
