import clsx from 'clsx'
import { AlertTriangle } from 'lucide-react'
import { motion } from 'motion/react'

import type { Analysis, SheetAnalysis } from '../../lib/api'
import { fmtKg, fmtM2, fmtMm, fmtPct } from '../../lib/format'

interface ResultsPanelProps {
  analysis: Analysis
  sheet: SheetAnalysis
  highlighted: string | null
  onHighlight: (id: string | null) => void
}

function Readout({ label, value, unit, tone = 'neutral' }: { label: string; value: string; unit?: string; tone?: 'neutral' | 'scrap' }) {
  return (
    <div className="rounded-xl border border-graphite-800 bg-graphite-950/50 px-4 py-3">
      <p className="eyebrow !text-[10px]">{label}</p>
      <p className={clsx('readout mt-1.5 text-2xl', tone === 'scrap' ? 'text-rust-400' : 'text-graphite-50')}>
        {value}
        {unit && <span className="ml-1 text-sm text-graphite-400">{unit}</span>}
      </p>
    </div>
  )
}

export function ResultsPanel({ analysis, sheet, highlighted, onHighlight }: ResultsPanelProps) {
  const weighed = analysis.totals.remnant_weight_kg !== null
  const remnantArea = sheet.remnants.reduce((sum, r) => sum + r.area_m2, 0)
  const remnantWeight = sheet.remnants.reduce((sum, r) => sum + (r.weight_kg ?? 0), 0)

  return (
    <div className="flex flex-col gap-4">
      <section className="panel relative overflow-hidden p-6">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-16 -top-20 size-56 rounded-full bg-reclaim-400/10 blur-3xl"
        />
        <p className="eyebrow">Reusable on this sheet</p>
        <motion.p
          key={`${analysis.source.name}-${sheet.index}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="readout mt-3 text-[52px] leading-none text-reclaim-400 [text-shadow:0_0_40px_rgb(200_241_105_/_0.35)]"
        >
          {weighed ? fmtKg(remnantWeight) : fmtM2(remnantArea)}
          <span className="ml-2 text-xl text-reclaim-300/70">{weighed ? 'kg' : 'm²'}</span>
        </motion.p>
        <p className="mt-2 text-[13px] text-graphite-400">
          {sheet.remnants.length} clean remnant{sheet.remnants.length === 1 ? '' : 's'} · {fmtM2(remnantArea)} m²
          {weighed ? '' : ' · set the thickness to get weights'}
        </p>

        <div className="mt-5 grid grid-cols-3 gap-2.5">
          <Readout label="Parts" value={String(sheet.part_count)} />
          <Readout label="Used" value={fmtPct(sheet.utilization)} unit="%" />
          <Readout
            label="Scrap"
            tone="scrap"
            value={sheet.scrap_weight_kg !== null ? fmtKg(sheet.scrap_weight_kg) : fmtM2(sheet.scrap_area_m2)}
            unit={sheet.scrap_weight_kg !== null ? 'kg' : 'm²'}
          />
        </div>
      </section>

      <section className="panel overflow-hidden">
        <header className="flex items-center justify-between border-b border-graphite-800 px-5 py-3.5">
          <h3 className="font-display text-[15px] font-semibold">Remnants</h3>
          <span className="font-mono text-[11px] text-graphite-500">shorter side ≥ {fmtMm(analysis.min_side_mm)} mm</span>
        </header>
        {sheet.remnants.length === 0 ? (
          <p className="px-5 py-6 text-[14px] text-graphite-400">
            No piece on this sheet is big enough to reuse. Everything left over is scrap.
          </p>
        ) : (
          <ul className="max-h-[300px] divide-y divide-graphite-800/80 overflow-y-auto">
            {sheet.remnants.map((r) => (
              <li
                key={r.id}
                onMouseEnter={() => onHighlight(r.id)}
                onMouseLeave={() => onHighlight(null)}
                className={clsx(
                  'grid cursor-default grid-cols-[52px_1fr_auto] items-center gap-3 px-5 py-3 transition-colors',
                  highlighted === r.id ? 'bg-reclaim-400/10' : 'hover:bg-graphite-850',
                )}
              >
                <span
                  className={clsx(
                    'readout rounded-md px-2 py-1 text-center text-[11px]',
                    highlighted === r.id ? 'bg-reclaim-400 text-graphite-950' : 'bg-graphite-800 text-reclaim-300',
                  )}
                >
                  {r.id.split('-').pop()}
                </span>
                <span className="readout text-[15px] text-graphite-100">
                  {fmtMm(r.width)} <span className="text-graphite-500">×</span> {fmtMm(r.height)}
                  <span className="ml-1 text-[11px] text-graphite-500">mm</span>
                </span>
                <span className="readout text-right text-[13px] text-graphite-300">
                  {r.weight_kg !== null ? `${fmtKg(r.weight_kg)} kg` : `${fmtM2(r.area_m2, 3)} m²`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {analysis.warnings.length > 0 && (
        <section className="rounded-2xl border border-ember-500/25 bg-ember-500/[0.05] p-5">
          <h3 className="flex items-center gap-2 text-[13px] font-semibold text-ember-300">
            <AlertTriangle className="size-4" /> Check before approving
          </h3>
          <ul className="mt-2.5 space-y-1.5 text-[13px] leading-relaxed text-graphite-300">
            {analysis.warnings.map((w) => (
              <li key={w} className="flex gap-2">
                <span className="mt-[7px] size-1 shrink-0 rounded-full bg-ember-400" />
                {w}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
