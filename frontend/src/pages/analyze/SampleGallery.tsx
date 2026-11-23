import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, FileCode2, FileSpreadsheet, Shapes } from 'lucide-react'
import { motion } from 'motion/react'

import { getSamples, type Sample } from '../../lib/api'
import { fmtBytes, processLabel } from '../../lib/format'
import { t } from '../../lib/i18n'

function iconFor(name: string) {
  if (name.endsWith('.csv')) return FileSpreadsheet
  if (name.endsWith('.dxf')) return Shapes
  return FileCode2
}

export function SampleGallery({ disabled, onPick }: { disabled: boolean; onPick: (s: Sample) => void }) {
  const samples = useQuery({ queryKey: ['samples'], queryFn: getSamples, staleTime: Infinity })
  if (!samples.data?.samples.length) return null

  return (
    <section className="mt-14">
      <div className="flex items-end justify-between gap-6">
        <div>
          <p className="eyebrow">{t('No file at hand?')}</p>
          <h2 className="mt-2 font-display text-2xl font-semibold">{t('Try a real job')}</h2>
        </div>
        <p className="hidden max-w-sm text-end text-[13px] text-ink-400 md:block">
          {t('Workshop-style samples, plus real files from open-source projects with their licences.')}
        </p>
      </div>
      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {samples.data.samples.map((sample, i) => {
          const Icon = iconFor(sample.name)
          return (
            <motion.button
              key={sample.id}
              type="button"
              disabled={disabled}
              onClick={() => onPick(sample)}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.04 * i, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="panel group flex flex-col items-start gap-3 !rounded-xl p-4 text-start transition hover:-translate-y-0.5 hover:border-ink-600 disabled:pointer-events-none disabled:opacity-50"
            >
              <div className="flex w-full items-center justify-between">
                <Icon className="size-[18px] text-ink-300 transition group-hover:text-brand-400" strokeWidth={1.6} />
                <ArrowUpRight className="size-4 text-ink-600 transition group-hover:text-brand-400" />
              </div>
              <p className="text-[14px] font-medium leading-snug text-ink-100">{sample.title}</p>
              <div className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[10.5px] text-ink-500">
                <span>{sample.process ? processLabel(sample.process) : t('Drawing')}</span>
                <span>·</span>
                <span>{fmtBytes(sample.size)}</span>
                {sample.licence && (
                  <span className="rounded border border-ink-700 px-1.5 py-px text-ink-400">{sample.licence}</span>
                )}
              </div>
            </motion.button>
          )
        })}
      </div>
    </section>
  )
}
