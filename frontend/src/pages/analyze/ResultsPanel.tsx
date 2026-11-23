import clsx from 'clsx'
import { AlertTriangle } from 'lucide-react'
import { motion } from 'motion/react'

import type { Analysis, SheetAnalysis } from '../../lib/api'
import { fmtKg, fmtM2, fmtMm, fmtPct } from '../../lib/format'
import { t } from '../../lib/i18n'

interface ResultsPanelProps {
  analysis: Analysis
  sheet: SheetAnalysis
  highlighted: string | null
  onHighlight: (id: string | null) => void
}

function Readout({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="rounded-xl border border-white/15 bg-white/10 px-4 py-3">
      <p className="eyebrow !text-[10px] !text-ink-950/75">{label}</p>
      <p className="readout mt-1.5 text-2xl text-ink-950">
        {value}
        {unit && <span className="ms-1 text-sm text-ink-950/70">{unit}</span>}
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
      <section className="panel-brand relative overflow-hidden p-6">
        <div
          aria-hidden
          className="pointer-events-none absolute -end-16 -top-20 size-56 rounded-full bg-reclaim-400/25 blur-3xl"
        />
        <p className="eyebrow !text-ink-950/75">{t('Reusable on this sheet')}</p>
        <motion.p
          key={`${analysis.source.name}-${sheet.index}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="readout mt-3 text-[52px] leading-none text-reclaim-400"
        >
          {weighed ? fmtKg(remnantWeight) : fmtM2(remnantArea)}
          <span className="ms-2 text-xl text-reclaim-400/80">{weighed ? 'kg' : 'm²'}</span>
        </motion.p>
        <p className="mt-2 text-[13px] text-ink-950/80">
          {t('{count} clean remnant|{count} clean remnants', { count: sheet.remnants.length })} · {fmtM2(remnantArea)} m²
          {weighed ? '' : ' · set the thickness to get weights'}
        </p>

        <div className="mt-5 grid grid-cols-3 gap-2.5">
          <Readout label={t('Parts')} value={String(sheet.part_count)} />
          <Readout label={t('Used')} value={fmtPct(sheet.utilization)} unit="%" />
          <Readout
            label={t('Scrap')}
            value={sheet.scrap_weight_kg !== null ? fmtKg(sheet.scrap_weight_kg) : fmtM2(sheet.scrap_area_m2)}
            unit={sheet.scrap_weight_kg !== null ? 'kg' : 'm²'}
          />
        </div>
      </section>

      <section className="panel overflow-hidden">
        <header className="flex items-center justify-between border-b border-ink-800 px-5 py-3.5">
          <h3 className="font-display text-[15px] font-semibold">{t('Remnants')}</h3>
          <span className="font-mono text-[11px] text-ink-500">{t('shorter side ≥ {size} mm', { size: fmtMm(analysis.min_side_mm) })}</span>
        </header>
        {sheet.remnants.length === 0 ? (
          <p className="px-5 py-6 text-[14px] text-ink-400">
            {t('No piece on this sheet is big enough to reuse. Everything left over is scrap.')}
          </p>
        ) : (
          <ul className="max-h-[300px] divide-y divide-ink-800/80 overflow-y-auto">
            {sheet.remnants.map((r) => (
              <li
                key={r.id}
                onMouseEnter={() => onHighlight(r.id)}
                onMouseLeave={() => onHighlight(null)}
                className={clsx(
                  'grid cursor-default grid-cols-[52px_1fr_auto] items-center gap-3 px-5 py-3 transition-colors',
                  highlighted === r.id ? 'bg-reclaim-400/10' : 'hover:bg-ink-850',
                )}
              >
                <span
                  className={clsx(
                    'readout rounded-md px-2 py-1 text-center text-[11px]',
                    highlighted === r.id ? 'bg-reclaim-400 text-ink-50' : 'bg-ink-800 text-reclaim-300',
                  )}
                >
                  {r.id.split('-').pop()}
                </span>
                <span className="readout text-[15px] text-ink-100">
                  {fmtMm(r.width)} <span className="text-ink-500">×</span> {fmtMm(r.height)}
                  <span className="ms-1 text-[11px] text-ink-500">{t('mm')}</span>
                </span>
                <span className="readout text-end text-[13px] text-ink-300">
                  {r.weight_kg !== null ? `${fmtKg(r.weight_kg)} kg` : `${fmtM2(r.area_m2, 3)} m²`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {analysis.warnings.length > 0 && (
        <section className="rounded-2xl border border-brand-500/25 bg-brand-500/[0.05] p-5">
          <h3 className="flex items-center gap-2 text-[13px] font-semibold text-brand-300">
            <AlertTriangle className="size-4" /> {t('Check before approving')}
          </h3>
          <ul className="mt-2.5 space-y-1.5 text-[13px] leading-relaxed text-ink-300">
            {analysis.warnings.map((w) => (
              <li key={w} className="flex gap-2">
                <span className="mt-[7px] size-1 shrink-0 rounded-full bg-brand-400" />
                {w}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
