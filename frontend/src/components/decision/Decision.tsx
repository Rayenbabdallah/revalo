import clsx from 'clsx'
import { ChevronDown } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'

import type { Decision } from '../../lib/api'
import { actionLabel, fmtKg, fmtTnd } from '../../lib/format'
import { ACTION_ICON } from './icons'

const STAGE_LABEL = {
  new: null,
  review: 'Review date passed',
  overdue: 'Overdue',
} as const

/** One row per record: what to do and what it is worth, with the reasons one click away. */
export function DecisionStrip({ decision }: { decision: Decision }) {
  const [open, setOpen] = useState(false)
  const best = decision.options.find((o) => o.action === decision.recommended)
  if (!decision.recommended || !best) return null
  const Icon = ACTION_ICON[decision.recommended]
  const stage = STAGE_LABEL[decision.stage]

  return (
    <div className="mt-3 rounded-lg border border-ink-800 bg-ink-950/50">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-3 py-2 text-left"
      >
        <span className="inline-flex items-center gap-1.5 rounded-md bg-reclaim-400/12 px-2 py-1 text-[12px] font-semibold text-reclaim-300">
          <Icon className="size-3.5" /> {actionLabel(decision.recommended)}
        </span>
        <span className="readout text-[13px] text-ink-100">
          {best.value_tnd !== null ? fmtTnd(best.value_tnd) : 'not priced'}
        </span>
        {best.co2_kg !== null && (
          <span className="readout text-[12px] text-ink-500">· {fmtKg(best.co2_kg, 0)} kg CO₂</span>
        )}
        {stage && <span className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-brand-300">{stage}</span>}
        <ChevronDown className={clsx('ml-auto size-4 text-ink-500 transition', open && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="border-t border-ink-800 px-3 pb-3 pt-2">
              <OptionGrid decision={decision} compact />
              <ul className="mt-2.5 space-y-1 text-[12.5px] leading-relaxed text-ink-300">
                {decision.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/** The three routes side by side, the recommended one lit. */
export function OptionGrid({ decision, compact = false }: { decision: Decision; compact?: boolean }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {decision.options.map((o) => {
        const Icon = ACTION_ICON[o.action]
        const chosen = o.action === decision.recommended
        return (
          <div
            key={o.action}
            title={o.note}
            className={clsx(
              'rounded-lg border',
              compact ? 'px-2.5 py-2' : 'px-3.5 py-3',
              chosen
                ? 'border-reclaim-400/60 bg-reclaim-400/[0.07]'
                : 'border-ink-800 bg-ink-900/50',
              !o.available && 'opacity-45',
            )}
          >
            <p
              className={clsx(
                'flex items-center gap-1.5 font-medium',
                compact ? 'text-[12px]' : 'text-[13px]',
                chosen ? 'text-reclaim-300' : 'text-ink-300',
              )}
            >
              <Icon className="size-3.5" /> {actionLabel(o.action)}
            </p>
            <p className={clsx('readout mt-1 text-ink-50', compact ? 'text-[14px]' : 'text-[18px]')}>
              {o.available ? (o.value_tnd !== null ? fmtTnd(o.value_tnd) : '—') : 'n/a'}
            </p>
            <p className="readout text-[11px] text-ink-500">
              {o.available && o.co2_kg !== null ? `${fmtKg(o.co2_kg, 0)} kg CO₂` : o.available ? 'CO₂ not known' : ''}
            </p>
            {!compact && <p className="mt-1.5 text-[11.5px] leading-snug text-ink-400">{o.note}</p>}
          </div>
        )
      })}
    </div>
  )
}
