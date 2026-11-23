import clsx from 'clsx'
import { FileClock, Repeat } from 'lucide-react'
import { motion } from 'motion/react'

import type { RepeatRunQuestion } from '../../lib/api'
import { fmtDateTime, statusLabel } from '../../lib/format'
import { t } from '../../lib/i18n'

/**
 * A known file was sent again. Running the same program twice is normal, so
 * Revalo never refuses: it asks, with the likely answer first.
 */
export function RepeatRunPrompt({
  question,
  busy,
  onRepeat,
  onOpen,
}: {
  question: RepeatRunQuestion
  busy?: boolean
  onRepeat: () => void
  onOpen: (jobId: string) => void
}) {
  const latest = question.jobs[0]
  const sameFirst = question.suggest === 'same'
  const primary = 'bg-brand-500 text-ink-950 hover:bg-brand-400'
  const secondary = 'border border-ink-700 text-ink-100 hover:border-brand-500'

  const repeatButton = (
    <button
      key="repeat"
      type="button"
      disabled={busy}
      onClick={onRepeat}
      className={clsx('inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-[14px] font-semibold transition disabled:opacity-60', sameFirst ? secondary : primary)}
    >
      <Repeat className="size-4" /> {t('Yes, a new run')}
    </button>
  )
  const openButton = (
    <button
      key="open"
      type="button"
      onClick={() => onOpen(latest.id)}
      className={clsx('inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-[14px] font-semibold transition', sameFirst ? primary : secondary)}
    >
      <FileClock className="size-4" /> {t('No, same cut: open it')}
    </button>
  )

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      role="alertdialog"
      aria-label={question.message}
      className="panel mt-5 p-5"
    >
      <p className="font-display text-[18px] font-semibold text-ink-50">{question.message}</p>
      <p className="mt-2 text-[14px] text-ink-300">
        {t('{file} was recorded on {date} by {name} ({status}).', {
          file: latest.file_name,
          date: fmtDateTime(latest.created_at),
          name: latest.created_by ?? t('someone'),
          status: statusLabel(latest.status).toLowerCase(),
        })}{' '}
        {question.jobs.length > 1 && t('{count} run already recorded.|{count} runs already recorded.', { count: question.jobs.length })}
      </p>
      <p className="mt-1 text-[13px] text-ink-500">
        {sameFirst
          ? t('It arrived minutes ago and is still in review: probably sent twice.')
          : t('The earlier run is already done: probably cut again.')}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">{sameFirst ? [openButton, repeatButton] : [repeatButton, openButton]}</div>
    </motion.div>
  )
}
