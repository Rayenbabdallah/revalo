import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Hammer, MapPin, Printer, Scale, Trash2, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'wouter'

import { ListButton } from '../../components/market/ListButton'
import { patchPiece, reuseRemnants, scrapPiece, type PieceWithHistory } from '../../lib/api'
import { useCan } from '../../lib/auth'
import { t } from '../../lib/i18n'

type Action = 'move' | 'take' | 'weigh' | 'scrap'

const FIELD =
  'w-full rounded-xl border border-ink-700 bg-ink-950 px-3.5 py-3 text-[16px] text-ink-50 focus:border-brand-500 focus:outline-none'

/** What a scan lets you do at the rack: one tap each, recorded with your name. */
export function ScanActions({ piece, jobId }: { piece: PieceWithHistory; jobId: string }) {
  const queryClient = useQueryClient()
  const canSell = useCan('manager')
  const [open, setOpen] = useState<Action | null>(null)
  const [value, setValue] = useState('')

  const act = useMutation({
    mutationFn: async (action: Action) => {
      const text = value.trim()
      if (action === 'move') return patchPiece(piece.id, { location: text })
      if (action === 'weigh') return patchPiece(piece.id, { weight_actual_kg: Number(text.replace(',', '.')) })
      if (action === 'take') return reuseRemnants([piece.id], text || t('Next job'))
      return scrapPiece(piece.id, text)
    },
    onSuccess: () => {
      setOpen(null)
      setValue('')
      for (const key of ['piece', 'stock', 'listings', 'alerts']) queryClient.invalidateQueries({ queryKey: [key] })
    },
  })

  const inStock = piece.status === 'in_stock'
  const kept = inStock || piece.status === 'reserved'
  if (!kept) return null

  const buttons: { id: Action; label: string; icon: typeof MapPin; show: boolean; danger?: boolean }[] = [
    { id: 'move', label: t('Move to a rack'), icon: MapPin, show: true },
    { id: 'take', label: t('Take for a job'), icon: Hammer, show: inStock && piece.kind === 'remnant' },
    { id: 'weigh', label: t('Weigh'), icon: Scale, show: true },
    { id: 'scrap', label: t('Damaged: scrap it'), icon: Trash2, show: inStock && piece.kind === 'remnant', danger: true },
  ]

  const prompts: Record<Action, { label: string; placeholder: string; inputMode?: 'decimal'; confirm: string }> = {
    move: { label: t('New rack or place'), placeholder: t('Rack B2'), confirm: t('Move') },
    take: { label: t('Job or order name'), placeholder: t('Order 2026-131'), confirm: t('Take it') },
    weigh: { label: t('Weight on the scale (kg)'), placeholder: '12.4', inputMode: 'decimal', confirm: t('Save weight') },
    scrap: { label: t('What is wrong with it?'), placeholder: t('Bent edge, deep scratch…'), confirm: t('Send to scrap') },
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (open) act.mutate(open)
  }

  return (
    <section className="mt-6">
      <p className="eyebrow">{t('On the rack')}</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {buttons
          .filter((b) => b.show)
          .map(({ id, label, icon: Icon, danger }) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                setOpen(open === id ? null : id)
                setValue(id === 'move' ? (piece.location ?? '') : '')
                act.reset()
              }}
              aria-expanded={open === id}
              className={clsx(
                'flex min-h-14 items-center gap-2.5 rounded-xl border px-4 py-3 text-start text-[15px] font-medium transition',
                open === id
                  ? 'border-brand-500 bg-brand-500 text-ink-950'
                  : danger
                    ? 'border-ink-700 bg-ink-900 text-ink-100 hover:border-alarm-400'
                    : 'border-ink-700 bg-ink-900 text-ink-100 hover:border-brand-500',
              )}
            >
              <Icon className={clsx('size-5 shrink-0', open === id ? '' : danger ? 'text-alarm-400' : 'text-brand-500')} />
              {label}
            </button>
          ))}
        <Link
          href={`/jobs/${jobId}/labels?code=${piece.code}`}
          className="flex min-h-14 items-center gap-2.5 rounded-xl border border-ink-700 bg-ink-900 px-4 py-3 text-[15px] font-medium text-ink-100 transition hover:border-brand-500"
        >
          <Printer className="size-5 shrink-0 text-brand-500" /> {t('Reprint label')}
        </Link>
        {canSell && inStock && (
          <div className="flex min-h-14 items-center rounded-xl border border-ink-700 bg-ink-900 px-4 py-3">
            <ListButton piece={piece} />
          </div>
        )}
      </div>

      {open && (
        <form onSubmit={submit} className="panel mt-3 space-y-3 p-4">
          <div className="flex items-center justify-between">
            <label htmlFor="scan-action" className="text-[14px] font-medium text-ink-200">
              {prompts[open].label}
            </label>
            <button type="button" onClick={() => setOpen(null)} aria-label={t('Cancel')} className="text-ink-400 hover:text-ink-100">
              <X className="size-4" />
            </button>
          </div>
          <input
            id="scan-action"
            autoFocus
            required={open !== 'take'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            inputMode={prompts[open].inputMode}
            placeholder={prompts[open].placeholder}
            className={FIELD}
          />
          {act.isError && <p className="text-[13px] text-alarm-400">{act.error.message}</p>}
          <button
            type="submit"
            disabled={act.isPending}
            className={clsx(
              'w-full rounded-xl px-4 py-3 text-[15px] font-semibold transition disabled:opacity-60',
              open === 'scrap' ? 'bg-alarm-400 text-ink-950' : 'bg-brand-500 text-ink-950 hover:bg-brand-400',
            )}
          >
            {prompts[open].confirm}
          </button>
        </form>
      )}
    </section>
  )
}
