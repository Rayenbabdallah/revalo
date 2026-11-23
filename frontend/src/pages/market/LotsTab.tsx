import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Boxes, ClipboardList, MessageCircle, PackageCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'wouter'

import { StatusBadge } from '../../components/ui/StatusBadge'
import {
  actOnLot,
  createLot,
  getLots,
  getLotSuggestions,
  type LotAction,
  type LotSize,
  type LotSuggestion,
  type WorkshopLot,
} from '../../lib/api'
import { fmtKg, fmtMm, fmtTnd } from '../../lib/format'
import { t } from '../../lib/i18n'

const refresh = ['lots', 'lot-suggestions', 'listings', 'stock', 'market', 'alerts']

export function SizeList({ sizes }: { sizes: LotSize[] }) {
  return (
    <p className="readout text-[12.5px] text-ink-300">
      {sizes
        .slice(0, 4)
        .map((s) => `${s.count} × ${fmtMm(s.length_mm)} × ${fmtMm(s.width_mm)}`)
        .join(' · ')}
      {sizes.length > 4 && ' …'}
    </p>
  )
}

function Suggestion({ group }: { group: LotSuggestion }) {
  const queryClient = useQueryClient()
  const make = useMutation({
    mutationFn: () => createLot({ piece_ids: group.piece_ids, price_tnd: group.suggested_price_tnd }),
    onSuccess: () => refresh.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] })),
  })
  return (
    <div className="panel flex flex-col p-5">
      <p className="font-semibold text-ink-50">{group.title}</p>
      <div className="mt-1.5">
        <SizeList sizes={group.sizes} />
      </div>
      <p className="mt-2 text-[13px] text-ink-400">
        {fmtKg(group.weight_kg)} kg · {t('worth {amount} one by one', { amount: fmtTnd(group.value_tnd) })}
      </p>
      <div className="mt-auto flex items-center justify-between gap-3 pt-4">
        <span className="readout text-[18px] text-ink-50">{fmtTnd(group.suggested_price_tnd)}</span>
        <button
          type="button"
          disabled={make.isPending}
          onClick={() => make.mutate()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-2 text-[13px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60"
        >
          <Boxes className="size-4" /> {t('Make a lot')}
        </button>
      </div>
      {make.isError && <p className="mt-2 text-[12.5px] text-alarm-400">{make.error.message}</p>}
    </div>
  )
}

export function LotCard({ lot }: { lot: WorkshopLot }) {
  const queryClient = useQueryClient()
  const [buyer, setBuyer] = useState('')
  const act = useMutation({
    mutationFn: (action: LotAction) => actOnLot(lot.id, { action, buyer_request_id: buyer || undefined }),
    onSuccess: () => refresh.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] })),
  })
  const open = lot.status === 'open'
  const reserved = lot.status === 'reserved'
  const matches = lot.matches ?? []

  return (
    <div className="panel p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="readout text-[12px] text-ink-400">{lot.code}</p>
          <p className="truncate font-semibold text-ink-50">{lot.title}</p>
          <div className="mt-1">
            <SizeList sizes={lot.sizes} />
          </div>
          <p className="mt-1 text-[13px] text-ink-400">
            {t('{count} piece|{count} pieces', { count: lot.count })} · {fmtKg(lot.weight_kg)} kg
            {lot.buyer && ` · ${t('for {name}', { name: lot.buyer.name })}`}
          </p>
        </div>
        <div className="text-end">
          <StatusBadge status={lot.status} />
          <p className="readout mt-2 text-[18px] text-ink-50">{fmtTnd(lot.sold_price_tnd ?? lot.price_tnd)}</p>
        </div>
      </div>

      {(open || reserved) && matches.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {matches.slice(0, 3).map((m) => (
            <li key={m.id} className="flex items-center justify-between gap-2 rounded-lg bg-ink-850/60 px-3 py-2 text-[13px]">
              <span className="min-w-0 truncate text-ink-200">
                {m.name}
                {m.buys_lots && <span className="ms-2 rounded bg-reclaim-400/15 px-1.5 py-0.5 text-[11px] text-reclaim-300">{t('takes whole lots')}</span>}
              </span>
              <a href={m.whatsapp_url} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1 font-medium text-reclaim-600 hover:underline">
                <MessageCircle className="size-3.5" /> WhatsApp
              </a>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Link href={`/lots/${lot.id}`} className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 px-3 py-1.5 text-[12.5px] text-ink-200 hover:border-brand-500">
          <ClipboardList className="size-3.5" /> {t('Pick list')}
        </Link>
        {open && matches.length > 0 && (
          <>
            <select value={buyer} onChange={(e) => setBuyer(e.target.value)} aria-label={t('Buyer')} className="rounded-lg border border-ink-700 bg-ink-900 px-2 py-1.5 text-[12.5px]">
              <option value="">{t('Choose a buyer…')}</option>
              {matches.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            <button type="button" disabled={!buyer || act.isPending} onClick={() => act.mutate('reserve')} className="rounded-lg border border-ink-700 px-3 py-1.5 text-[12.5px] text-ink-200 hover:border-brand-500 disabled:opacity-50">
              {t('Reserve')}
            </button>
          </>
        )}
        {(open || reserved) && (
          <>
            <button type="button" disabled={act.isPending} onClick={() => act.mutate('sell')} className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-1.5 text-[12.5px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60">
              <PackageCheck className="size-3.5" /> {t('Sold')}
            </button>
            {reserved && (
              <button type="button" onClick={() => act.mutate('reopen')} className="rounded-lg border border-ink-700 px-3 py-1.5 text-[12.5px] text-ink-300 hover:border-ink-500">
                {t('Reopen')}
              </button>
            )}
            <button type="button" onClick={() => act.mutate('withdraw')} className="rounded-lg px-2 py-1.5 text-[12.5px] text-ink-400 hover:text-alarm-400">
              {t('Withdraw from sale')}
            </button>
          </>
        )}
      </div>
      {act.isError && <p className="mt-2 text-[12.5px] text-alarm-400">{act.error.message}</p>}
    </div>
  )
}

/** Similar offcuts sold as one deal, for buyers who take many at once. */
export function LotsTab() {
  const suggested = useQuery({ queryKey: ['lot-suggestions'], queryFn: getLotSuggestions })
  const lots = useQuery({ queryKey: ['lots'], queryFn: getLots })
  const all = lots.data?.lots ?? []
  const active = all.filter((l) => l.status === 'open' || l.status === 'reserved')
  const sold = all.filter((l) => l.status === 'sold')
  const groups = suggested.data?.groups ?? []

  return (
    <div className="space-y-8">
      <p className="max-w-3xl text-[14.5px] text-ink-400">
        {t('Similar offcuts sell better together: one price, one buyer, one pickup. Revalo groups them by material, thickness and size; a buyer can take the whole lot or part of it.')}
      </p>

      <section>
        <p className="eyebrow">{t('Suggested lots')}</p>
        {suggested.isPending ? (
          <p className="mt-3 font-mono text-sm text-ink-500">{t('Loading…')}</p>
        ) : groups.length === 0 ? (
          <p className="panel mt-3 px-6 py-8 text-center text-[14px] text-ink-400">
            {t('No group of three or more similar offcuts in stock right now.')}
          </p>
        ) : (
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {groups.map((g) => (
              <Suggestion key={`${g.material_code}-${g.thickness_mm}-${g.band}`} group={g} />
            ))}
          </div>
        )}
      </section>

      <section>
        <p className="eyebrow">{t('Lots on sale')}</p>
        {active.length === 0 ? (
          <p className="mt-3 text-[14px] text-ink-400">{t('No lot on sale yet.')}</p>
        ) : (
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {active.map((lot) => (
              <LotCard key={lot.id} lot={lot} />
            ))}
          </div>
        )}
      </section>

      {sold.length > 0 && (
        <section>
          <p className="eyebrow">{t('Sold lots')}</p>
          <ul className="panel mt-3 divide-y divide-ink-800 p-0">
            {sold.map((lot) => (
              <li key={lot.id} className="flex items-center justify-between gap-3 px-5 py-3 text-[13.5px]">
                <Link href={`/lots/${lot.id}`} className="min-w-0 truncate text-ink-100 hover:text-brand-500">
                  <span className="readout me-2 text-ink-400">{lot.code}</span>
                  {lot.title}
                </Link>
                <span className="readout shrink-0 text-ink-200">
                  {fmtTnd(lot.sold_price_tnd)}
                  {lot.buyer && ` · ${lot.buyer.name}`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
