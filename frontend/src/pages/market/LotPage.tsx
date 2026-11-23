import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Printer } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'wouter'

import { QrCode } from '../../components/ui/QrCode'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { actOnLot, getLot } from '../../lib/api'
import { fmtKg, fmtMm, fmtTnd, materialLabel } from '../../lib/format'
import { t } from '../../lib/i18n'
import { SizeList } from './LotsTab'

/** A lot's contents: the pick list for the floor, its QR label, and part sales. */
export function LotPage({ id }: { id: string }) {
  const queryClient = useQueryClient()
  const lot = useQuery({ queryKey: ['lot', id], queryFn: () => getLot(id) })
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [price, setPrice] = useState('')

  const sellPart = useMutation({
    mutationFn: () =>
      actOnLot(id, {
        action: 'sell',
        piece_ids: [...picked],
        price_tnd: price ? Number(price.replace(',', '.')) : undefined,
      }),
    onSuccess: () => {
      setPicked(new Set())
      setPrice('')
      for (const key of ['lot', 'lots', 'lot-suggestions', 'stock', 'market']) queryClient.invalidateQueries({ queryKey: [key] })
    },
  })

  if (lot.isPending) return <p className="px-10 py-16 font-mono text-sm text-ink-500">{t('Loading…')}</p>
  if (lot.isError || !lot.data) return <p className="px-10 py-16 text-sm text-alarm-400">{lot.error?.message}</p>
  const l = lot.data
  const active = l.status === 'open' || l.status === 'reserved'
  const share = l.count ? picked.size / l.count : 0

  const toggle = (pieceId: string) =>
    setPicked((s) => {
      const next = new Set(s)
      if (next.has(pieceId)) next.delete(pieceId)
      else next.add(pieceId)
      return next
    })

  return (
    <div className="report mx-auto max-w-[980px] px-4 py-8 md:px-10 md:py-12">
      <div className="no-print flex items-center justify-between">
        <Link href="/market?tab=lots" className="inline-flex items-center gap-1.5 text-[13px] text-ink-400 hover:text-ink-100">
          <ArrowLeft className="size-4 rtl:-scale-x-100" /> {t('Lots')}
        </Link>
        <button
          type="button"
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-[14px] font-semibold text-ink-950 hover:bg-brand-400"
        >
          <Printer className="size-4" /> {t('Print pick list')}
        </button>
      </div>

      <article className="print-area mt-6 space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <p className="readout text-[13px] text-ink-400">{l.code}</p>
            <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight">{l.title}</h1>
            <p className="mt-1.5 text-[14px] text-ink-400">
              {materialLabel(l.material_code)} {l.thickness_mm} mm · {t('{count} piece|{count} pieces', { count: l.count })} ·{' '}
              {fmtKg(l.weight_kg)} kg · {fmtTnd(l.sold_price_tnd ?? l.price_tnd)}
            </p>
            <div className="mt-2">
              <SizeList sizes={l.sizes} />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <StatusBadge status={l.status} />
              {l.buyer && <span className="text-[13px] text-ink-300">{t('for {name}', { name: l.buyer.name })}</span>}
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-ink-700 bg-white p-3 text-black">
            <QrCode value={l.label_url} className="size-28" />
            <div className="text-[11px] leading-tight">
              <p className="font-mono text-[13px] font-semibold">{l.code}</p>
              <p>{t('{count} piece|{count} pieces', { count: l.count })}</p>
              <p>{fmtKg(l.weight_kg)} kg</p>
            </div>
          </div>
        </header>

        <section className="panel overflow-hidden p-0">
          <p className="border-b border-ink-800 px-5 py-3 text-[14px] font-semibold text-ink-100">
            {t('Pick list, sorted by rack')}
          </p>
          <table className="w-full text-start text-[13.5px]">
            <thead className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-500">
              <tr className="border-b border-ink-800">
                {active && <th className="no-print w-10 px-4 py-2" />}
                <th className="px-4 py-2 text-start font-normal">{t('Rack')}</th>
                <th className="px-4 py-2 text-start font-normal">{t('Code')}</th>
                <th className="px-4 py-2 text-start font-normal">{t('Piece')}</th>
                <th className="px-4 py-2 text-end font-normal">{t('Weight')}</th>
              </tr>
            </thead>
            <tbody>
              {l.items.map((p) => (
                <tr key={p.id} className="border-b border-ink-800/60 last:border-0">
                  {active && (
                    <td className="no-print px-4 py-2">
                      <input
                        type="checkbox"
                        checked={picked.has(p.id)}
                        onChange={() => toggle(p.id)}
                        aria-label={t('Select {code}', { code: p.code })}
                      />
                    </td>
                  )}
                  <td className="px-4 py-2 font-semibold text-ink-100">{p.location ?? t('Not set')}</td>
                  <td className="readout px-4 py-2 text-ink-300">
                    <Link href={`/p/${p.code}`} className="hover:text-brand-500">
                      {p.code}
                    </Link>
                  </td>
                  <td className="readout px-4 py-2 text-ink-200">
                    {fmtMm(p.width_mm ?? 0)} × {fmtMm(p.height_mm ?? 0)} mm
                  </td>
                  <td className="readout px-4 py-2 text-end text-ink-200">{fmtKg(p.weight_kg)} kg</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {active && picked.size > 0 && picked.size < l.count && (
          <section className="no-print panel flex flex-wrap items-end gap-3 p-5">
            <p className="w-full text-[14px] text-ink-200">
              {t('Sell {count} piece of this lot. The rest stays on sale.|Sell {count} pieces of this lot. The rest stays on sale.', { count: picked.size })}
            </p>
            <label className="text-[13px] text-ink-300">
              {t('Price (TND)')}
              <input
                inputMode="decimal"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder={String(Math.round(l.price_tnd * share))}
                className="mt-1 block w-32 rounded-lg border border-ink-700 bg-ink-950 px-3 py-2 text-[14px]"
              />
            </label>
            <button
              type="button"
              disabled={sellPart.isPending}
              onClick={() => sellPart.mutate()}
              className="rounded-xl bg-brand-500 px-4 py-2.5 text-[14px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60"
            >
              {t('Record the sale')}
            </button>
            {sellPart.isError && <p className="w-full text-[13px] text-alarm-400">{sellPart.error.message}</p>}
          </section>
        )}
      </article>
    </div>
  )
}
