import clsx from 'clsx'

import { statusLabel } from '../../lib/format'

const TONE: Record<string, string> = {
  draft: 'border-brand-500/40 bg-brand-500/10 text-brand-300',
  rejected: 'border-alarm-400/40 bg-alarm-400/10 text-alarm-400',
  in_stock: 'border-reclaim-400/40 bg-reclaim-400/10 text-reclaim-300',
  approved: 'border-reclaim-400/40 bg-reclaim-400/10 text-reclaim-300',
  reserved: 'border-ink-500 bg-ink-800 text-ink-100',
  reused: 'border-ink-600 bg-ink-800 text-ink-300',
  sold: 'border-ink-600 bg-ink-800 text-ink-300',
  recycled: 'border-rust-500/50 bg-rust-500/10 text-rust-400',
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10.5px] uppercase tracking-[0.1em]',
        TONE[status] ?? 'border-ink-700 text-ink-300',
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {statusLabel(status)}
    </span>
  )
}
