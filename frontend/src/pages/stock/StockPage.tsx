import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { CalendarClock, PackageOpen } from 'lucide-react'
import { motion } from 'motion/react'
import { useState } from 'react'
import { Link } from 'wouter'

import { ACTION_ICON } from '../../components/decision/icons'
import { getStock, getStockSummary, type DecisionAction, type StockSummaryRow } from '../../lib/api'
import { actionLabel, fmtDate, fmtKg, fmtM2, fmtMm, fmtTnd, materialLabel } from '../../lib/format'

/* Chart series: the two brand colours, validated on the card surface (#fffdf9).
   Lightness, chroma and colour-blind separation pass; the green is under 3:1 against
   the card, so every bar also carries a legend, direct values and a table view. */
const SERIES = { remnant: '#66ca53', scrap: '#194acb' } as const

function Tile({ label, value, unit, hint, accent }: { label: string; value: string; unit?: string; hint?: string; accent?: boolean }) {
  return (
    <div className={clsx('p-5', accent ? 'panel-brand' : 'panel')}>
      <p className={clsx('eyebrow !text-[10px]', accent && '!text-ink-950/75')}>{label}</p>
      <p className={clsx('readout mt-2 text-[32px] leading-none', accent ? 'text-reclaim-400' : 'text-ink-50')}>
        {value}
        {unit && <span className={clsx('ml-1.5 text-base', accent ? 'text-ink-950/75' : 'text-ink-400')}>{unit}</span>}
      </p>
      {hint && <p className={clsx('mt-2 text-[12px]', accent ? 'text-ink-950/80' : 'text-ink-500')}>{hint}</p>}
    </div>
  )
}

function MaterialBars({ rows }: { rows: StockSummaryRow[] }) {
  const [hover, setHover] = useState<string | null>(null)
  const max = Math.max(...rows.map((r) => r.remnant_weight_kg + r.scrap_weight_kg), 1)
  return (
    <section className="panel p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">Stock by material</h2>
        <div className="flex items-center gap-4 font-mono text-[11px] text-ink-300" aria-label="Legend">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: SERIES.remnant }} /> Reusable remnants
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: SERIES.scrap }} /> Scrap lots
          </span>
        </div>
      </div>
      <ul className="mt-5 space-y-4">
        {rows.map((r) => {
          const key = r.material_code ?? 'unknown'
          const total = r.remnant_weight_kg + r.scrap_weight_kg
          const active = hover === key
          return (
            <li
              key={key}
              onMouseEnter={() => setHover(key)}
              onMouseLeave={() => setHover(null)}
              className="relative"
            >
              <div className="flex items-baseline justify-between gap-3 text-[13px]">
                <span className="font-medium text-ink-100">{materialLabel(r.material_code)}</span>
                <span className="readout text-ink-300">
                  {fmtKg(r.remnant_weight_kg)} kg reusable <span className="text-ink-600">·</span> {fmtKg(r.scrap_weight_kg)} kg scrap
                </span>
              </div>
              {/* Hit target taller than the bar. */}
              <div className="mt-2 flex h-6 items-center">
                <div className="flex h-3 w-full overflow-hidden rounded bg-ink-800/60">
                  <div
                    className="h-full rounded-l transition-[width] duration-700"
                    style={{ width: `${(r.remnant_weight_kg / max) * 100}%`, background: SERIES.remnant, opacity: hover && !active ? 0.45 : 1 }}
                  />
                  {r.scrap_weight_kg > 0 && (
                    <div
                      className="ml-[2px] h-full rounded-r transition-[width] duration-700"
                      style={{ width: `${(r.scrap_weight_kg / max) * 100}%`, background: SERIES.scrap, opacity: hover && !active ? 0.45 : 1 }}
                    />
                  )}
                </div>
              </div>
              {active && (
                <div className="pointer-events-none absolute right-0 top-full z-10 mt-1 rounded-lg border border-ink-700 bg-ink-950/95 px-3 py-2 font-mono text-[11px] text-ink-200 shadow-xl backdrop-blur">
                  <p>{r.remnant_count} remnants · {fmtM2(r.remnant_area_m2)} m²</p>
                  <p>{r.scrap_lots} scrap lot{r.scrap_lots === 1 ? '' : 's'} · {fmtKg(total)} kg total</p>
                  {r.unweighed > 0 && <p className="text-brand-300">{r.unweighed} without a weight</p>}
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function NextActions({ actions }: { actions: Record<DecisionAction, { count: number; value_tnd: number }> }) {
  const order: DecisionAction[] = ['reuse', 'sell', 'recycle']
  const hint = {
    reuse: 'Keep for your next jobs',
    sell: 'Not reused in time: list them',
    recycle: 'Scrap lots and pieces past their time',
  }
  return (
    <section className="mt-5 grid gap-3 md:grid-cols-3">
      {order.map((a) => {
        const Icon = ACTION_ICON[a]
        return (
          <div key={a} className="panel flex items-center gap-4 p-5">
            <span className="grid size-11 place-items-center rounded-xl border border-ink-700 bg-ink-850">
              <Icon className="size-5 text-reclaim-300" strokeWidth={1.75} />
            </span>
            <div className="min-w-0">
              <p className="text-[14px] font-medium text-ink-100">
                {actionLabel(a)} <span className="readout text-ink-400">· {actions[a].count}</span>
              </p>
              <p className="readout text-[18px] text-ink-50">{fmtTnd(actions[a].value_tnd)}</p>
              <p className="truncate text-[12px] text-ink-500">{hint[a]}</p>
            </div>
          </div>
        )
      })}
    </section>
  )
}

const FILTERS = [
  ['all', 'All'],
  ['remnant', 'Remnants'],
  ['scrap', 'Scrap lots'],
] as const

export function StockPage() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>('all')
  const summary = useQuery({ queryKey: ['stock', 'summary'], queryFn: getStockSummary })
  const pieces = useQuery({
    queryKey: ['stock', 'pieces', filter],
    queryFn: () => getStock(filter === 'all' ? undefined : filter),
  })
  const totals = summary.data?.totals

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-8 md:px-10 md:py-12">
      <p className="eyebrow">Stock</p>
      <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">What is on the racks</h1>
      <p className="mt-2 text-[15px] text-ink-400">Approved leftovers, waiting to be reused, sold or recycled.</p>

      <div className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Recoverable value" value={fmtTnd(totals?.value_tnd ?? 0).replace(' TND', '')} unit="TND" accent hint={`${fmtKg(totals?.co2_kg ?? 0, 0)} kg CO₂ avoided if each piece follows its recommendation`} />
        <Tile label="Reusable in stock" value={fmtKg(totals?.remnant_weight_kg ?? 0)} unit="kg" hint={`${totals?.remnant_count ?? 0} remnants · ${fmtM2(totals?.remnant_area_m2 ?? 0)} m²`} />
        <Tile label="Scrap waiting" value={fmtKg(totals?.scrap_weight_kg ?? 0)} unit="kg" hint={`${totals?.scrap_lots ?? 0} lots for recyclers`} />
        <Tile label="Due for review" value={String(totals?.due_for_review ?? 0)} hint="Past their review date" />
      </div>

      {summary.data && summary.data.materials.length > 0 && <NextActions actions={summary.data.actions} />}

      {summary.data && summary.data.materials.length > 0 && (
        <div className="mt-5">
          <MaterialBars rows={summary.data.materials} />
        </div>
      )}

      <section className="panel mt-5 overflow-hidden">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-800 px-6 py-4">
          <h2 className="font-display text-lg font-semibold">Pieces in stock</h2>
          <div className="flex rounded-xl border border-ink-700 p-1">
            {FILTERS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={clsx(
                  'rounded-lg px-3 py-1.5 text-[13px] font-medium transition',
                  filter === value ? 'bg-ink-700 text-ink-50' : 'text-ink-400 hover:text-ink-100',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </header>
        {pieces.data && pieces.data.pieces.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <PackageOpen className="size-8 text-ink-500" strokeWidth={1.5} />
            <p className="font-display text-lg font-semibold">Nothing in stock yet</p>
            <p className="max-w-sm text-[14px] text-ink-400">
              Approve a job's records and its remnants and scrap lots appear here.
            </p>
            <Link href="/jobs" className="mt-1 text-[14px] font-medium text-brand-400 hover:text-brand-300">
              Go to jobs
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead>
                <tr className="border-b border-ink-800 font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
                  <th className="px-6 py-3 font-normal">Code</th>
                  <th className="px-3 py-3 font-normal">Piece</th>
                  <th className="px-3 py-3 font-normal">Material</th>
                  <th className="px-3 py-3 text-right font-normal">Weight</th>
                  <th className="px-3 py-3 font-normal">Next step</th>
                  <th className="px-3 py-3 font-normal">Location</th>
                  <th className="px-3 py-3 font-normal">Review</th>
                </tr>
              </thead>
              <tbody>
                {(pieces.data?.pieces ?? []).map((p, i) => {
                  const due = p.due_for_review
                  return (
                    <motion.tr
                      key={p.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: Math.min(i * 0.02, 0.4) }}
                      className="border-b border-ink-800/70 last:border-0 hover:bg-ink-850"
                    >
                      <td className="px-6 py-3">
                        <Link href={`/p/${p.code}`} className="readout text-[13px] text-ink-100 hover:text-brand-300">
                          {p.code}
                        </Link>
                      </td>
                      <td className="readout px-3 py-3 text-[14px] text-ink-100">
                        {p.kind === 'remnant' ? (
                          <>
                            {fmtMm(p.width_mm ?? 0)} <span className="text-ink-500">×</span> {fmtMm(p.height_mm ?? 0)}
                          </>
                        ) : (
                          <span className="font-sans text-rust-400">Scrap lot</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-[13px] text-ink-300">
                        {materialLabel(p.material_code)}
                        {p.thickness_mm ? ` · ${p.thickness_mm} mm` : ''}
                      </td>
                      <td className="readout px-3 py-3 text-right text-[13px] text-ink-200">
                        {p.weight_kg !== null ? `${fmtKg(p.weight_kg)} kg` : '—'}
                      </td>
                      <td className="px-3 py-3 text-[13px] text-ink-200">
                        {p.decision.recommended ? (
                          <span className="inline-flex items-center gap-1.5">
                            {actionLabel(p.decision.recommended)}
                            <span className="readout text-ink-500">
                              {fmtTnd(p.decision.options.find((o) => o.action === p.decision.recommended)?.value_tnd)}
                            </span>
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="px-3 py-3 text-[13px] text-ink-400">{p.location ?? '—'}</td>
                      <td className="px-3 py-3">
                        {p.review_date ? (
                          <span className={clsx('inline-flex items-center gap-1.5 font-mono text-[12px]', due ? 'text-brand-300' : 'text-ink-400')}>
                            {due && <CalendarClock className="size-3.5" />}
                            {fmtDate(p.review_date)}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                    </motion.tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
