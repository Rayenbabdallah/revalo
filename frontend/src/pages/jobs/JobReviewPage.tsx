import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, Box, CheckCheck, Printer, Scan, UserRound } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { Link } from 'wouter'

import { StatusBadge } from '../../components/ui/StatusBadge'
import type { ViewMode } from '../../components/viewer/SheetViewer'
import { useActor } from '../../lib/actor'
import { approveJob, getJob, type JobDetail, type SheetAnalysis } from '../../lib/api'
import { fmtDateTime, fmtKg, fmtTnd, formatLabel, materialLabel, processLabel } from '../../lib/format'
import { PieceCard } from './PieceCard'

const SheetViewer = lazy(() => import('../../components/viewer/SheetViewer'))

/** The viewer shows what the manager decided: corrected sizes and weights, not the raw engine output. */
function sheetWithRecords(job: JobDetail, index: number): SheetAnalysis {
  const sheet = job.analysis.sheets[index]
  const byLabel = new Map(job.pieces.map((p) => [p.label, p]))
  return {
    ...sheet,
    remnants: sheet.remnants.map((r) => {
      const piece = byLabel.get(r.id)
      return piece
        ? { ...r, width: piece.width_mm ?? r.width, height: piece.height_mm ?? r.height, weight_kg: piece.weight_kg }
        : r
    }),
  }
}

function ActorChip({ actor, onChange }: { actor: string; onChange: (name: string) => void }) {
  const [editing, setEditing] = useState(false)
  return editing ? (
    <input
      autoFocus
      defaultValue={actor}
      onBlur={(e) => {
        onChange(e.target.value)
        setEditing(false)
      }}
      onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
      className="w-40 rounded-lg border border-ember-500 bg-graphite-950 px-3 py-2 text-sm text-graphite-50 focus:outline-none"
    />
  ) : (
    <button
      type="button"
      onClick={() => setEditing(true)}
      title="Who is reviewing on this device"
      className="inline-flex items-center gap-2 rounded-lg border border-graphite-700 px-3 py-2 text-sm text-graphite-200 transition hover:border-graphite-500"
    >
      <UserRound className="size-4 text-graphite-400" /> {actor}
    </button>
  )
}

export function JobReviewPage({ id }: { id: string }) {
  const queryClient = useQueryClient()
  const job = useQuery({ queryKey: ['job', id], queryFn: () => getJob(id) })
  const [actor, setActor] = useActor()
  const [sheetIndex, setSheetIndex] = useState(0)
  const [highlighted, setHighlighted] = useState<string | null>(null)
  const [mode, setMode] = useState<ViewMode>('3d')

  const approve = useMutation({
    mutationFn: () => approveJob(id, actor),
    onSuccess: (updated) => {
      queryClient.setQueryData(['job', id], updated)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
    },
  })

  const data = job.data
  const sheet = useMemo(() => (data ? sheetWithRecords(data, Math.min(sheetIndex, data.sheet_count - 1)) : null), [data, sheetIndex])
  const rejected = useMemo(
    () => new Set(data?.pieces.filter((p) => p.status === 'rejected').map((p) => p.label) ?? []),
    [data],
  )

  if (job.isPending) return <p className="px-10 py-16 font-mono text-sm text-graphite-500">Loading job…</p>
  if (job.isError || !data || !sheet)
    return <p className="px-10 py-16 text-sm text-alarm-400">{job.error?.message ?? 'Job not found.'}</p>

  const sheetPieces = data.pieces.filter((p) => p.sheet_index === sheet.index)
  const drafts = data.pieces.filter((p) => p.status === 'draft')
  const keptWeight = data.pieces
    .filter((p) => p.kind === 'remnant' && p.status !== 'rejected')
    .reduce((sum, p) => sum + (p.weight_kg ?? 0), 0)
  const approved = data.status === 'approved'

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-8 md:px-10 md:py-10">
      <Link href="/jobs" className="inline-flex items-center gap-1.5 text-[13px] text-graphite-400 transition hover:text-graphite-100">
        <ArrowLeft className="size-4" /> All jobs
      </Link>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <StatusBadge status={data.status} />
            <span className="font-mono text-[11px] text-graphite-500">
              {formatLabel(data.file_format)} · saved {fmtDateTime(data.created_at)}
            </span>
          </div>
          <h1 className="mt-2 truncate font-display text-3xl font-semibold tracking-tight md:text-4xl">{data.file_name}</h1>
          <p className="mt-1.5 text-[14px] text-graphite-400">
            {materialLabel(data.material_code)}
            {data.thickness_mm && ` · ${data.thickness_mm} mm`} · {processLabel(data.process)} · {data.part_count} parts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ActorChip actor={actor} onChange={setActor} />
          {approved && (
            <Link
              href={`/jobs/${id}/labels`}
              className="inline-flex items-center gap-2 rounded-xl bg-reclaim-400 px-4 py-2.5 text-sm font-semibold text-graphite-950 transition hover:bg-reclaim-300"
            >
              <Printer className="size-4" /> Print labels
            </Link>
          )}
        </div>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-12">
        <section className="panel relative h-[420px] overflow-hidden md:h-[600px] lg:sticky lg:top-6 lg:col-span-7">
          <Suspense fallback={<div className="grid h-full place-items-center font-mono text-sm text-graphite-500">Loading 3D view…</div>}>
            <SheetViewer
              key={`${id}-${sheet.index}`}
              sheet={sheet}
              family={data.analysis.material?.family ?? null}
              thicknessMm={data.thickness_mm}
              highlighted={highlighted}
              onHighlight={setHighlighted}
              mode={mode}
              rejected={rejected}
            />
          </Suspense>
          <div className="pointer-events-none absolute inset-x-4 top-4 flex items-start justify-between gap-3">
            <div className="pointer-events-auto flex rounded-xl border border-graphite-700 bg-graphite-950/80 p-1 backdrop-blur-md">
              {([
                ['3d', '3D', Box],
                ['top', 'Top', Scan],
              ] as const).map(([value, label, Icon]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMode(value)}
                  className={clsx(
                    'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition',
                    mode === value ? 'bg-graphite-700 text-graphite-50' : 'text-graphite-400 hover:text-graphite-100',
                  )}
                >
                  <Icon className="size-3.5" /> {label}
                </button>
              ))}
            </div>
            {data.sheet_count > 1 && (
              <div className="pointer-events-auto flex flex-wrap justify-end gap-1 rounded-xl border border-graphite-700 bg-graphite-950/80 p-1 backdrop-blur-md">
                {data.analysis.sheets.map((s) => (
                  <button
                    key={s.index}
                    type="button"
                    onClick={() => setSheetIndex(s.index)}
                    className={clsx(
                      'rounded-lg px-3 py-1.5 font-mono text-[12px] transition',
                      s.index === sheet.index ? 'bg-graphite-700 text-graphite-50' : 'text-graphite-400 hover:text-graphite-100',
                    )}
                  >
                    Sheet {s.index + 1}
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        <div className="flex flex-col gap-3 lg:col-span-5">
          <div className="rounded-xl border border-graphite-800 bg-graphite-900/60 px-4 py-3 text-[13px] leading-relaxed text-graphite-300">
            {approved ? (
              <>
                Approved by <strong className="text-graphite-100">{data.approved_by}</strong>
                {data.approved_at && ` on ${fmtDateTime(data.approved_at)}`}. Records are locked; location can still be
                updated from stock.
              </>
            ) : (
              <>
                The file shows what <em>should</em> remain. Check each piece against the real sheet: trim a damaged
                edge, enter a weighed value, or reject what cannot be used.
              </>
            )}
          </div>
          {sheetPieces.map((piece) => (
            <PieceCard
              key={piece.id}
              piece={piece}
              jobId={id}
              actor={actor}
              highlighted={highlighted === piece.label}
              onHighlight={setHighlighted}
              locked={approved}
            />
          ))}

          <AnimatePresence>
            {!approved && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="sticky bottom-20 z-10 mt-2 flex items-center justify-between gap-4 rounded-2xl border border-graphite-700 bg-graphite-900/95 p-4 shadow-2xl backdrop-blur-xl md:bottom-4"
              >
                <div>
                  <p className="readout text-lg text-reclaim-400">
                    {data.recovered.priced_pieces > 0 ? fmtTnd(data.recovered.value_tnd) : `${fmtKg(keptWeight)} kg`}
                    <span className="ml-2 text-[12px] text-graphite-500">
                      {fmtKg(keptWeight)} kg · {fmtKg(data.recovered.co2_kg, 0)} kg CO₂
                    </span>
                  </p>
                  <p className="text-[12px] text-graphite-400">
                    {drafts.length} record{drafts.length === 1 ? '' : 's'} go to stock
                  </p>
                </div>
                <button
                  type="button"
                  disabled={approve.isPending || drafts.length === 0}
                  onClick={() => approve.mutate()}
                  className="inline-flex items-center gap-2 rounded-xl bg-ember-500 px-5 py-3 text-sm font-semibold text-graphite-950 shadow-[0_10px_30px_-10px_rgb(255_106_43_/_0.9)] transition hover:bg-ember-400 disabled:opacity-60"
                >
                  <CheckCheck className="size-4" /> {approve.isPending ? 'Approving…' : 'Approve batch'}
                </button>
              </motion.div>
            )}
          </AnimatePresence>
          {approve.isError && <p className="text-[13px] text-alarm-400">{approve.error.message}</p>}
        </div>
      </div>
    </div>
  )
}
