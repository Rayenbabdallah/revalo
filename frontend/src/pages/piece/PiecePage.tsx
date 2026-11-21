import { useQuery } from '@tanstack/react-query'
import { MapPin, Scale, Ruler, CalendarClock, FileText } from 'lucide-react'
import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { Link } from 'wouter'

import { Wordmark } from '../../components/brand/Logo'
import { OptionGrid } from '../../components/decision/Decision'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { getPieceByCode } from '../../lib/api'
import { fmtDate, fmtDateTime, fmtKg, fmtM2, fmtMm, materialLabel } from '../../lib/format'

const ACTION_LABEL: Record<string, string> = {
  created: 'Recorded from the cut file',
  corrected: 'Corrected',
  approved: 'Approved into stock',
}

function Fact({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-graphite-800 bg-graphite-900/60 px-4 py-3">
      <span className="mt-0.5 text-graphite-500">{icon}</span>
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-graphite-500">{label}</p>
        <p className="mt-0.5 text-[15px] text-graphite-100">{children}</p>
      </div>
    </div>
  )
}

/** What a QR label opens: built for a phone held at the rack. */
export function PiecePage({ code }: { code: string }) {
  const piece = useQuery({ queryKey: ['piece', code], queryFn: () => getPieceByCode(code) })
  const p = piece.data

  return (
    <div className="mx-auto min-h-full max-w-xl px-4 py-6">
      <header className="flex items-center justify-between">
        <Wordmark />
        <span className="font-mono text-[11px] text-graphite-500">leftover record</span>
      </header>

      {piece.isPending ? (
        <p className="mt-16 text-center font-mono text-sm text-graphite-500">Looking up {code}…</p>
      ) : piece.isError || !p ? (
        <div className="panel mt-10 p-8 text-center">
          <p className="font-display text-xl font-semibold">No piece with code {code}</p>
          <p className="mt-2 text-[14px] text-graphite-400">Check the label, or the piece may have been removed.</p>
        </div>
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <section className="panel relative mt-6 overflow-hidden p-6">
            <div aria-hidden className="pointer-events-none absolute -right-10 -top-16 size-48 rounded-full bg-reclaim-400/10 blur-3xl" />
            <div className="flex items-center justify-between">
              <p className="readout text-[13px] text-graphite-400">{p.code}</p>
              <StatusBadge status={p.status} />
            </div>
            <p className="mt-4 font-display text-[34px] font-semibold leading-tight tracking-tight">
              {p.kind === 'remnant' ? (
                <span className="readout">
                  {fmtMm(p.width_mm ?? 0)} <span className="text-graphite-500">×</span> {fmtMm(p.height_mm ?? 0)}
                  <span className="ml-1.5 text-lg text-graphite-400">mm</span>
                </span>
              ) : (
                'Scrap lot'
              )}
            </p>
            <p className="mt-1 text-[15px] text-graphite-300">
              {materialLabel(p.material_code)}
              {p.thickness_mm ? ` · ${p.thickness_mm} mm` : ''}
            </p>
          </section>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Fact icon={<Scale className="size-4" />} label={p.weight_actual_kg !== null ? 'Weighed' : 'Estimated weight'}>
              {p.weight_kg !== null ? `${fmtKg(p.weight_kg)} kg` : 'Not known'}
            </Fact>
            <Fact icon={<Ruler className="size-4" />} label="Area">
              {fmtM2(p.area_m2, 3)} m²
            </Fact>
            <Fact icon={<MapPin className="size-4" />} label="Location">
              {p.location ?? 'Not set'}
            </Fact>
            <Fact icon={<CalendarClock className="size-4" />} label="Review date">
              {p.review_date ? fmtDate(p.review_date) : '—'}
            </Fact>
          </div>
          {p.condition_note && (
            <p className="mt-3 rounded-xl border border-ember-500/25 bg-ember-500/5 px-4 py-3 text-[14px] text-graphite-200">
              {p.condition_note}
            </p>
          )}

          {p.decision.recommended && (
            <section className="mt-6">
              <p className="eyebrow">What to do with it</p>
              <div className="mt-3">
                <OptionGrid decision={p.decision} />
              </div>
              <ul className="mt-3 space-y-1.5 text-[14px] leading-relaxed text-graphite-300">
                {p.decision.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </section>
          )}

          <section className="mt-6">
            <p className="eyebrow">History</p>
            <ol className="mt-3 border-l border-graphite-700 pl-5">
              {p.events.map((e, i) => (
                <li key={i} className="relative pb-4 last:pb-0">
                  <span className="absolute -left-[25px] top-1.5 size-2 rounded-full bg-graphite-500 ring-4 ring-graphite-950" />
                  <p className="text-[14px] text-graphite-100">{ACTION_LABEL[e.action] ?? e.action}</p>
                  <p className="font-mono text-[11px] text-graphite-500">
                    {fmtDateTime(e.at)} · {e.actor}
                  </p>
                </li>
              ))}
            </ol>
          </section>

          <Link
            href={`/jobs/${p.job.id}`}
            className="mt-8 flex items-center gap-2 rounded-xl border border-graphite-800 px-4 py-3 text-[13px] text-graphite-300 transition hover:border-graphite-600"
          >
            <FileText className="size-4 text-graphite-500" /> From job <span className="truncate text-graphite-100">{p.job.file_name}</span>
          </Link>
        </motion.div>
      )}
    </div>
  )
}
