import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Ban, Check, Loader2, RotateCcw } from 'lucide-react'
import { useState, type KeyboardEvent } from 'react'

import { DecisionStrip } from '../../components/decision/Decision'
import { ListButton } from '../../components/market/ListButton'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { patchPiece, type JobDetail, type Piece, type PiecePatch } from '../../lib/api'
import { fmtKg, fmtM2, fmtMm } from '../../lib/format'

interface PieceCardProps {
  piece: Piece
  jobId: string
  highlighted: boolean
  onHighlight: (label: string | null) => void
  /** The job is approved: records are final. */
  locked: boolean
}

const inputClass =
  'w-full rounded-lg border border-ink-700 bg-ink-950/70 px-2.5 py-2 font-mono text-[13px] text-ink-100 placeholder:text-ink-600 transition focus:border-brand-500 focus:outline-none disabled:opacity-60'

/** Number input that saves on blur or Enter, and only when the value changed. */
function NumberField({
  label,
  value,
  placeholder,
  disabled,
  onCommit,
}: {
  label: string
  value: number | null
  placeholder?: string
  disabled: boolean
  onCommit: (value: number | null) => void
}) {
  const [draft, setDraft] = useState<string | null>(null)
  const shown = draft ?? (value === null ? '' : String(value))
  const commit = () => {
    if (draft === null) return
    const trimmed = draft.trim().replace(',', '.')
    const next = trimmed === '' ? null : Number(trimmed)
    setDraft(null)
    if (next !== null && (!Number.isFinite(next) || next <= 0)) return
    if (next !== value) onCommit(next)
  }
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">{label}</span>
      <input
        className={inputClass}
        inputMode="decimal"
        placeholder={placeholder}
        disabled={disabled}
        value={shown}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
      />
    </label>
  )
}

export function PieceCard({ piece, jobId, highlighted, onHighlight, locked }: PieceCardProps) {
  const queryClient = useQueryClient()
  const [noteDraft, setNoteDraft] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: (patch: PiecePatch) => patchPiece(piece.id, patch),
    onSuccess: (updated) => {
      queryClient.setQueryData<JobDetail>(['job', jobId], (job) =>
        job ? { ...job, pieces: job.pieces.map((p) => (p.id === updated.id ? updated : p)) } : job,
      )
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const editable = piece.status === 'draft' && !locked
  const rejected = piece.status === 'rejected'
  const isRemnant = piece.kind === 'remnant'
  const short = isRemnant ? piece.label.split('-').pop() : 'Lot'

  return (
    <article
      onMouseEnter={() => onHighlight(isRemnant ? piece.label : null)}
      onMouseLeave={() => onHighlight(null)}
      className={clsx(
        'rounded-xl border p-4 transition-colors',
        highlighted ? 'border-reclaim-400/60 bg-reclaim-400/[0.06]' : 'border-ink-800 bg-ink-900/60',
        rejected && 'opacity-60',
      )}
    >
      <header className="flex items-center gap-3">
        <span
          className={clsx(
            'readout min-w-10 rounded-md px-2 py-1 text-center text-[11px]',
            isRemnant ? 'bg-ink-800 text-reclaim-300' : 'bg-rust-500/15 text-rust-400',
          )}
        >
          {short}
        </span>
        <div className="min-w-0 flex-1">
          <p className="readout truncate text-[15px] text-ink-50">
            {isRemnant ? (
              <>
                {fmtMm(piece.width_mm ?? 0)} <span className="text-ink-500">×</span> {fmtMm(piece.height_mm ?? 0)}
                <span className="ms-1 text-[11px] text-ink-500">mm</span>
              </>
            ) : (
              <>
                Scrap skeleton <span className="text-[12px] text-ink-500">· sheet {piece.sheet_index + 1}</span>
              </>
            )}
          </p>
          <p className="font-mono text-[11px] text-ink-500">
            {piece.code} · {fmtM2(piece.area_m2, 3)} m²
            {piece.weight_est_kg !== null && ` · est. ${fmtKg(piece.weight_est_kg)} kg`}
          </p>
        </div>
        {save.isPending ? (
          <Loader2 className="size-4 animate-spin text-ink-400" />
        ) : save.isSuccess ? (
          <Check className="size-4 text-reclaim-600" />
        ) : null}
        <StatusBadge status={piece.status} />
      </header>

      <div className={clsx('mt-4 grid gap-3', isRemnant ? 'grid-cols-3' : 'grid-cols-1 sm:grid-cols-3')}>
        {isRemnant && (
          <>
            <NumberField
              label="Width mm"
              value={piece.width_mm}
              disabled={!editable}
              onCommit={(v) => v !== null && save.mutate({ width_mm: v })}
            />
            <NumberField
              label="Height mm"
              value={piece.height_mm}
              disabled={!editable}
              onCommit={(v) => v !== null && save.mutate({ height_mm: v })}
            />
          </>
        )}
        <NumberField
          label="Weighed kg"
          value={piece.weight_actual_kg}
          placeholder={piece.weight_est_kg !== null ? fmtKg(piece.weight_est_kg) : 'kg'}
          disabled={!editable}
          onCommit={(v) => save.mutate(v === null ? { clear_weight: true } : { weight_actual_kg: v })}
        />
      </div>

      <div className="mt-3 flex items-end gap-2">
        <label className="block flex-1">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">Condition</span>
          <input
            className={inputClass + ' font-sans'}
            placeholder="Scratched corner, bent edge…"
            value={noteDraft ?? piece.condition_note ?? ''}
            onChange={(e) => setNoteDraft(e.target.value)}
            onBlur={() => {
              if (noteDraft !== null && noteDraft !== (piece.condition_note ?? '')) save.mutate({ condition_note: noteDraft })
              setNoteDraft(null)
            }}
            onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
          />
        </label>
        {!locked && (editable || rejected) && (
          <button
            type="button"
            onClick={() => save.mutate({ rejected: !rejected })}
            className={clsx(
              'inline-flex h-[38px] items-center gap-1.5 rounded-lg border px-3 text-[13px] font-medium transition',
              rejected
                ? 'border-ink-600 text-ink-200 hover:border-ink-400'
                : 'border-ink-700 text-ink-400 hover:border-alarm-400/60 hover:text-alarm-400',
            )}
          >
            {rejected ? <RotateCcw className="size-3.5" /> : <Ban className="size-3.5" />}
            {rejected ? 'Restore' : 'Reject'}
          </button>
        )}
      </div>
      {!rejected && <DecisionStrip decision={piece.decision} />}
      {locked && !rejected && (
        <div className="mt-3 flex justify-end">
          <ListButton piece={piece} />
        </div>
      )}
      {save.isError && <p className="mt-2 text-[12px] text-alarm-400">{save.error.message}</p>}
    </article>
  )
}
