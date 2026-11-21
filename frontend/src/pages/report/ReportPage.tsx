import { useQuery } from '@tanstack/react-query'
import { Printer, Recycle, Repeat2, Tag } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { Wordmark } from '../../components/brand/Logo'
import { getMonthlyReport } from '../../lib/api'
import { fmtKg, fmtTnd } from '../../lib/format'

function monthLabel(month: string) {
  const [y, m] = month.split('-').map(Number)
  return new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' }).format(new Date(y, m - 1, 1))
}

function Outcome({ icon, title, value, lines }: { icon: ReactNode; title: string; value: string; lines: string[] }) {
  return (
    <div className="panel p-5">
      <p className="flex items-center gap-2 text-[14px] font-semibold text-ink-100">
        {icon} {title}
      </p>
      <p className="readout mt-2 text-[26px] text-ink-50">{value}</p>
      {lines.map((l) => (
        <p key={l} className="text-[12.5px] text-ink-400">
          {l}
        </p>
      ))}
    </div>
  )
}

/** One page for the owner, who pays: what the leftovers were worth this month. */
export function ReportPage() {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7))
  const report = useQuery({ queryKey: ['report', month], queryFn: () => getMonthlyReport(month) })
  const r = report.data

  return (
    <div className="report mx-auto max-w-[920px] px-4 py-8 md:px-10 md:py-12">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Owner report</p>
          <p className="mt-1 text-[14px] text-ink-400">Print it or save it as PDF to send to the owner.</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="rounded-xl border border-ink-700 bg-ink-900 px-3 py-2 text-[14px] focus:border-brand-500 focus:outline-none"
            aria-label="Month"
          />
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-[14px] font-semibold text-ink-950 hover:bg-brand-400"
          >
            <Printer className="size-4" /> Print / PDF
          </button>
        </div>
      </div>

      {report.isPending ? (
        <p className="font-mono text-sm text-ink-500">Preparing the report…</p>
      ) : report.isError || !r ? (
        <p className="text-sm text-alarm-400">{report.error?.message ?? 'No report.'}</p>
      ) : (
        <article className="print-area space-y-5">
          <header className="flex items-center justify-between border-b border-ink-700 pb-4">
            <Wordmark className="h-8" />
            <div className="text-right">
              <p className="font-display text-[18px] font-semibold">{r.workshop}</p>
              <p className="text-[13px] text-ink-400">Leftover report · {monthLabel(r.month)}</p>
            </div>
          </header>

          <section className="panel-brand p-7">
            <p className="eyebrow !text-ink-950/75">Recovered from leftovers</p>
            <p className="readout mt-3 text-[52px] leading-none text-reclaim-400">{fmtTnd(r.recovered_tnd)}</p>
            <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-ink-950/90">
              {r.return_on_plan !== null && r.recovered_tnd > 0
                ? `That is ${r.return_on_plan.toLocaleString('en-US', { maximumFractionDigits: 1 })}× the Revalo plan (${fmtTnd(r.plan_tnd)} a month). `
                : `Against a Revalo plan of ${fmtTnd(r.plan_tnd)} a month. `}
              {fmtKg(r.diverted_kg)} kg kept out of the bin and {fmtKg(r.co2_avoided_kg, 0)} kg of CO₂ avoided.
            </p>
          </section>

          <section className="grid gap-3 md:grid-cols-3">
            <Outcome
              icon={<Repeat2 className="size-4 text-reclaim-600" />}
              title="Reused in house"
              value={fmtTnd(r.outcomes.reused.tnd)}
              lines={[`${r.outcomes.reused.pieces} pieces · ${fmtKg(r.outcomes.reused.kg)} kg`, 'New material not bought']}
            />
            <Outcome
              icon={<Tag className="size-4 text-brand-500" />}
              title="Sold"
              value={fmtTnd(r.outcomes.sold.tnd)}
              lines={[`${r.outcomes.sold.pieces} pieces · ${fmtKg(r.outcomes.sold.kg)} kg`, `Marketplace fees ${fmtTnd(r.outcomes.sold.fees_tnd, 2)}`]}
            />
            <Outcome
              icon={<Recycle className="size-4 text-rust-400" />}
              title="Recycled"
              value={fmtTnd(r.outcomes.recycled.tnd)}
              lines={[`${r.outcomes.recycled.pickups} pickups · ${fmtKg(r.outcomes.recycled.kg)} kg`, 'Paid by recyclers']}
            />
          </section>

          <section className="grid gap-3 md:grid-cols-2">
            <div className="panel p-5">
              <p className="text-[14px] font-semibold text-ink-100">From the machines</p>
              <dl className="mt-3 grid grid-cols-2 gap-y-2 text-[13.5px]">
                <dt className="text-ink-400">Jobs</dt>
                <dd className="readout text-right">{r.production.jobs}</dd>
                <dt className="text-ink-400">Sheets · parts</dt>
                <dd className="readout text-right">
                  {r.production.sheets} · {r.production.parts}
                </dd>
                <dt className="text-ink-400">Remnants recorded</dt>
                <dd className="readout text-right">{fmtKg(r.production.remnant_kg)} kg</dd>
                <dt className="text-ink-400">Scrap recorded</dt>
                <dd className="readout text-right">{fmtKg(r.production.scrap_kg)} kg</dd>
              </dl>
            </div>
            <div className="panel p-5">
              <p className="text-[14px] font-semibold text-ink-100">On the racks now</p>
              <dl className="mt-3 grid grid-cols-2 gap-y-2 text-[13.5px]">
                <dt className="text-ink-400">Recoverable value</dt>
                <dd className="readout text-right">{fmtTnd(r.stock.value_tnd)}</dd>
                <dt className="text-ink-400">Remnants</dt>
                <dd className="readout text-right">
                  {r.stock.remnant_count} · {fmtKg(r.stock.remnant_kg)} kg
                </dd>
                <dt className="text-ink-400">Scrap waiting</dt>
                <dd className="readout text-right">{fmtKg(r.stock.scrap_kg)} kg</dd>
                <dt className="text-ink-400">Due for review</dt>
                <dd className="readout text-right">{r.stock.due_for_review}</dd>
              </dl>
            </div>
          </section>

          <p className="text-[11.5px] leading-relaxed text-ink-500">
            Reused value counts new material at the workshop's price book; sales are net of the 5% marketplace fee;
            recycling counts what recyclers paid at collection. CO₂ uses published factors where the price book has
            them (worldsteel for steel, ICE for MDF).
          </p>
        </article>
      )}
    </div>
  )
}
