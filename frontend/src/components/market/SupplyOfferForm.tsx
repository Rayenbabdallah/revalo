import { useMutation, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent, type ReactNode } from 'react'

import { getGovernorates, getMaterials, postSupplyOffer, type SupplyOfferInput } from '../../lib/api'
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

const num = (v: string) => Number(v.replace(',', '.'))

/** Offcuts someone offers to sell to the workshop: on the public page, or typed in by a manager. */
export function SupplyOfferForm({
  onPosted,
  submitLabel = t('Send my offer'),
}: {
  onPosted?: () => void
  submitLabel?: string
}) {
  const catalog = useQuery({ queryKey: ['materials'], queryFn: getMaterials, staleTime: Infinity })
  const regions = useQuery({ queryKey: ['governorates'], queryFn: getGovernorates, staleTime: Infinity })
  const [form, setForm] = useState<HTMLFormElement | null>(null)
  const post = useMutation({
    mutationFn: postSupplyOffer,
    onSuccess: () => {
      form?.reset()
      onPosted?.()
    },
  })

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setForm(e.currentTarget)
    const f = new FormData(e.currentTarget)
    const text = (k: string) => String(f.get(k) ?? '').trim()
    const body: SupplyOfferInput = {
      seller_name: text('name'),
      organization: text('organization') || undefined,
      phone: text('phone'),
      governorate: text('governorate'),
      material_code: text('material'),
      thickness_mm: num(text('thickness')),
      width_mm: num(text('length')),
      height_mm: num(text('width')),
      quantity: Math.max(1, Math.round(num(text('quantity') || '1'))),
      price_tnd: num(text('price')),
      note: text('note') || undefined,
    }
    post.mutate(body)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Label text={t('Your name')}>
          <input name="name" required minLength={2} className={field} placeholder={t('Nabil')} />
        </Label>
        <Label text={t('Workshop or company')} hint={t('optional')}>
          <input name="organization" className={field} placeholder={t('Atelier Nabil')} />
        </Label>
        <Label text={t('WhatsApp number')}>
          <input name="phone" required inputMode="tel" className={field} placeholder="55 111 222" />
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

      <div className="grid gap-3 sm:grid-cols-[1fr_110px]">
        <Label text={t('Material')}>
          <select name="material" required defaultValue="" className={field}>
            <option value="" disabled>
              {t('Choose…')}
            </option>
            {catalog.data?.materials.map((m) => (
              <option key={m.code} value={m.code}>
                {materialLabel(m.code)}
              </option>
            ))}
          </select>
        </Label>
        <Label text={t('Thickness')} hint={t('mm')}>
          <input name="thickness" required inputMode="decimal" className={field} placeholder="3" />
        </Label>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Label text={t('Length')} hint={t('mm')}>
          <input name="length" required inputMode="numeric" className={field} placeholder="500" />
        </Label>
        <Label text={t('Width')} hint={t('mm')}>
          <input name="width" required inputMode="numeric" className={field} placeholder="300" />
        </Label>
        <Label text={t('Pieces')}>
          <input name="quantity" inputMode="numeric" defaultValue="1" className={field} />
        </Label>
        <Label text={t('Price for all')} hint="TND">
          <input name="price" required inputMode="decimal" className={field} placeholder="20" />
        </Label>
      </div>

      <Label text={t('Anything else')} hint={t('optional')}>
        <input name="note" className={field} placeholder={t('Clean edges, collect in Sousse…')} />
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
