import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, Box, CheckCheck, Printer, Repeat, Scan, Sparkles } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { Link } from 'wouter'

import { StatusBadge } from '../../components/ui/StatusBadge'
import type { ViewMode } from '../../components/viewer/SheetViewer'
import {
  approveJob,
  copyCorrections,
  getJob,
  getOpportunities,
  type JobDetail,
  type Opportunities,
  type SheetAnalysis,
} from '../../lib/api'
import { useCan } from '../../lib/auth'
import { fmtDateTime, fmtKg, fmtTnd, formatLabel, materialLabel, processLabel } from '../../lib/format'
import { PieceCard } from './PieceCard'
import { t } from '../../lib/i18n'

const SheetViewer = lazy(() => import('../../components/viewer/SheetViewer'))

/** The viewer shows what the manager decided: corrected sizes and weights, not the raw engine output. */
function sheetWithRecords(job: JobDetail, index: number, run: number): SheetAnalysis {
  const sheet = job.analysis.sheets[index]
  const byLabel = new Map(job.pieces.filter((p) => p.run_index === run).map((p) => [p.label, p]))
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

/** One line per buyer, with the offcuts they would take. */
function byBuyer(wanted: Opportunities['buyers']): [string, string[]][] {
  const groups = new Map<string, string[]>()
  for (const w of wanted) for (const b of w.buyers) groups.set(b.name, [...(groups.get(b.name) ?? []), w.code])
  return [...groups.entries()].sort((a, b) => b[1].length - a[1].length)
}

/** Pieces entered from the racks: no drawing, just the list and its labels. */
function IntakeJobView({ job }: { job: JobDetail }) {
  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 md:px-10 md:py-10">
      <Link href="/jobs" className="inline-flex items-center gap-1.5 text-[13px] text-ink-400 transition hover:text-ink-100">
        <ArrowLeft className="size-4 rtl:-scale-x-100" /> {t('All jobs')}
      </Link>
      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">{t('Existing stock')}</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">{job.file_name}</h1>
          <p className="mt-1.5 text-[14px] text-ink-400">
            {t('Entered by {name} on {date}', { name: job.created_by ?? '', date: fmtDateTime(job.created_at) })} ·{' '}
            {t('{count} piece|{count} pieces', { count: job.pieces.length })}
          </p>
        </div>
        <Link
          href={`/jobs/${job.id}/labels`}
          className="inline-flex items-center gap-2 rounded-xl bg-reclaim-400 px-4 py-2.5 text-sm font-semibold text-ink-50 hover:bg-reclaim-300"
        >
          <Printer className="size-4" /> {t('Print labels')}
        </Link>
      </div>
      <ul className="panel mt-6 divide-y divide-ink-800 p-0">
        {job.pieces.map((p) => (
          <li key={p.id} className="grid grid-cols-[8rem_1fr_auto] items-center gap-3 px-5 py-3 text-[14px]">
            <Link href={`/p/${p.code}`} className="readout text-brand-500 hover:underline">
              {p.code}
            </Link>
            <span className="text-ink-200">
              {p.kind === 'remnant' ? `${fmtKg(p.width_mm ?? 0, 0)} × ${fmtKg(p.height_mm ?? 0, 0)} mm` : t('Scrap lot')} ·{' '}
              {materialLabel(p.material_code)} {p.thickness_mm} mm · {fmtKg(p.weight_kg)} kg
            </span>
            <span className="text-[12.5px] text-ink-400">{p.location ?? t('Not set')}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function JobReviewPage({ id }: { id: string }) {
  const queryClient = useQueryClient()
  const job = useQuery({ queryKey: ['job', id], queryFn: () => getJob(id) })
  const canApprove = useCan('manager')
  const [sheetIndex, setSheetIndex] = useState(0)
  const [run, setRun] = useState(0)
  const [highlighted, setHighlighted] = useState<string | null>(null)
  const [mode, setMode] = useState<ViewMode>('3d')

  const approvedNow = job.data?.status === 'approved'
  const wanted = useQuery({
    queryKey: ['opportunities', id],
    queryFn: () => getOpportunities(id),
    enabled: approvedNow && canApprove && (job.data?.analysis.sheets.length ?? 0) > 0,
  })

  const copy = useMutation({
    mutationFn: () => copyCorrections(id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['job', id], updated)
    },
  })

  const approve = useMutation({
    mutationFn: () => approveJob(id),
    onSuccess: (updated) => {
      queryClient.setQueryData(['job', id], updated)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
    },
  })

  const data = job.data
  const sheet = useMemo(
    () => (data ? sheetWithRecords(data, Math.min(sheetIndex, data.analysis.sheets.length - 1), run) : null),
    [data, sheetIndex, run],
  )
  const rejected = useMemo(
    () =>
      new Set(data?.pieces.filter((p) => p.status === 'rejected' && p.run_index === run).map((p) => p.label) ?? []),
    [data, run],
  )

  if (job.isPending) return <p className="px-10 py-16 font-mono text-sm text-ink-500">{t('Loading job…')}</p>
  if (data && data.analysis.sheets.length === 0) return <IntakeJobView job={data} />
  if (job.isError || !data || !sheet)
    return <p className="px-10 py-16 text-sm text-alarm-400">{job.error?.message ?? t('Job not found.')}</p>

  const sheetPieces = data.pieces.filter((p) => p.sheet_index === sheet.index && p.run_index === run)
  const drafts = data.pieces.filter((p) => p.status === 'draft')
  const keptWeight = data.pieces
    .filter((p) => p.kind === 'remnant' && p.status !== 'rejected')
    .reduce((sum, p) => sum + (p.weight_kg ?? 0), 0)
  const approved = data.status === 'approved'

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-8 md:px-10 md:py-10">
      <Link href="/jobs" className="inline-flex items-center gap-1.5 text-[13px] text-ink-400 transition hover:text-ink-100">
        <ArrowLeft className="size-4 rtl:-scale-x-100" /> {t('All jobs')}
      </Link>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <StatusBadge status={data.status} />
            <span className="font-mono text-[11px] text-ink-500">
              {formatLabel(data.file_format)} · {t('saved {date}', { date: fmtDateTime(data.created_at) })}
            </span>
          </div>
          <h1 className="mt-2 truncate font-display text-3xl font-semibold tracking-tight md:text-4xl">{data.file_name}</h1>
          <p className="mt-1.5 text-[14px] text-ink-400">
            {materialLabel(data.material_code)}
            {data.thickness_mm && ` · ${data.thickness_mm} mm`} · {processLabel(data.process)} · {data.part_count} parts
          </p>
        </div>
        <div className="flex items-center gap-2">
          {approved && (
            <Link
              href={`/jobs/${id}/labels`}
              className="inline-flex items-center gap-2 rounded-xl bg-reclaim-400 px-4 py-2.5 text-sm font-semibold text-ink-50 transition hover:bg-reclaim-300"
            >
              <Printer className="size-4" /> {t('Print labels')}
            </Link>
          )}
        </div>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-12">
        <section className="stage relative h-[420px] overflow-hidden md:h-[600px] lg:sticky lg:top-6 lg:col-span-7">
          <Suspense fallback={<div className="grid h-full place-items-center font-mono text-sm text-ink-500">{t('Loading 3D view…')}</div>}>
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
            <div className="pointer-events-auto flex rounded-xl border border-ink-700 bg-ink-950/80 p-1 backdrop-blur-md">
              {([
                ['3d', '3D', Box],
                ['top', t('Top'), Scan],
              ] as const).map(([value, label, Icon]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMode(value)}
                  className={clsx(
                    'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition',
                    mode === value ? 'bg-ink-700 text-ink-50' : 'text-ink-400 hover:text-ink-100',
                  )}
                >
                  <Icon className="size-3.5" /> {label}
                </button>
              ))}
            </div>
            {data.analysis.sheets.length > 1 && (
              <div className="pointer-events-auto flex flex-wrap justify-end gap-1 rounded-xl border border-ink-700 bg-ink-950/80 p-1 backdrop-blur-md">
                {data.analysis.sheets.map((s) => (
                  <button
                    key={s.index}
                    type="button"
                    onClick={() => setSheetIndex(s.index)}
                    className={clsx(
                      'rounded-lg px-3 py-1.5 font-mono text-[12px] transition',
                      s.index === sheet.index ? 'bg-ink-700 text-ink-50' : 'text-ink-400 hover:text-ink-100',
                    )}
                  >
                    {t('Sheet {n}', { n: s.index + 1 })}
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        <div className="flex flex-col gap-3 lg:col-span-5">
          {wanted.data && (wanted.data.planned.length > 0 || wanted.data.buyers.length > 0) && (
            <div className="rounded-xl border border-reclaim-400/50 bg-reclaim-400/[0.08] px-4 py-3 text-[13.5px] text-ink-200">
              <p className="flex items-center gap-2 font-semibold text-ink-50">
                <Sparkles className="size-4 text-reclaim-600" /> {t('Already wanted')}
              </p>
              <ul className="mt-2 space-y-1.5">
                {wanted.data.planned.map((pj) => (
                  <li key={pj.id}>
                    <Link href={`/stock/fit?planned=${pj.id}`} className="text-brand-500 hover:underline">
                      {t('{placed} of {total} parts of {name} fit these offcuts', { placed: pj.placed, total: pj.total, name: pj.name })}
                    </Link>
                  </li>
                ))}
                {byBuyer(wanted.data.buyers).map(([name, codes]) => (
                  <li key={name}>
                    {t('{name}: {count} of these offcuts matches|{name}: {count} of these offcuts match', { name, count: codes.length })}{' '}
                    {codes.slice(0, 3).map((code) => (
                      <Link key={code} href={`/p/${code}`} className="readout me-1.5 text-brand-500 hover:underline">
                        {code}
                      </Link>
                    ))}
                    {codes.length > 3 && <span className="text-ink-500">…</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.repeat_of_id && (
            <div className="rounded-xl border border-brand-500/40 bg-brand-500/[0.06] px-4 py-3 text-[13.5px] text-ink-200">
              <p className="flex items-center gap-2 font-semibold text-ink-50">
                <Repeat className="size-4 text-brand-500" /> {t('Repeat run of a program already recorded')}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <Link href={`/jobs/${data.repeat_of_id}`} className="text-brand-500 hover:underline">
                  {t('Open the earlier run')}
                </Link>
                {!approved && canApprove && (
                  <button
                    type="button"
                    disabled={copy.isPending}
                    onClick={() => copy.mutate()}
                    className="rounded-lg bg-brand-500 px-3 py-1.5 text-[13px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60"
                  >
                    {t("Copy last run's corrections")}
                  </button>
                )}
              </div>
              {copy.isSuccess && (
                <p className="mt-2 text-reclaim-300">
                  {t('{count} piece updated.|{count} pieces updated.', { count: copy.data.copied })}
                </p>
              )}
              {copy.isError && <p className="mt-2 text-alarm-400">{copy.error.message}</p>}
            </div>
          )}
          {data.runs > 1 && (
            <div className="flex flex-wrap items-center gap-1 rounded-xl border border-ink-700 bg-ink-900 p-1">
              <span className="px-2 text-[12.5px] text-ink-400">{t('{count} sheets cut', { count: data.runs })}</span>
              {Array.from({ length: data.runs }, (_, r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRun(r)}
                  aria-pressed={run === r}
                  className={clsx(
                    'rounded-lg px-3 py-1.5 font-mono text-[12px] transition',
                    run === r ? 'bg-brand-500 text-ink-950' : 'text-ink-400 hover:text-ink-100',
                  )}
                >
                  {t('Run {n}', { n: r + 1 })}
                </button>
              ))}
            </div>
          )}
          <div className="rounded-xl border border-ink-800 bg-ink-900/60 px-4 py-3 text-[13px] leading-relaxed text-ink-300">
            {approved ? (
              <>
                {t('Approved by')} <strong className="text-ink-100">{data.approved_by}</strong>
                {data.approved_at && ` ${t('on {date}', { date: fmtDateTime(data.approved_at) })}`}.{' '}
                {t('Records are locked; location can still be updated from stock.')}
              </>
            ) : (
              <>
                {t('The file shows what should remain. Check each piece against the real sheet: trim a damaged edge, enter a weighed value, or reject what cannot be used.')}
              </>
            )}
          </div>
          {sheetPieces.map((piece) => (
            <PieceCard
              key={piece.id}
              piece={piece}
              jobId={id}
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
                className="sticky bottom-20 z-10 mt-2 flex items-center justify-between gap-4 rounded-2xl border border-ink-700 bg-ink-900/95 p-4 shadow-2xl backdrop-blur-xl md:bottom-4"
              >
                <div>
                  <p className="readout text-lg text-reclaim-300">
                    {data.recovered.priced_pieces > 0 ? fmtTnd(data.recovered.value_tnd) : `${fmtKg(keptWeight)} kg`}
                    <span className="ms-2 text-[12px] text-ink-500">
                      {fmtKg(keptWeight)} kg · {fmtKg(data.recovered.co2_kg, 0)} kg CO₂
                    </span>
                  </p>
                  <p className="text-[12px] text-ink-400">
                    {t('{count} record goes to stock|{count} records go to stock', { count: drafts.length })}
                  </p>
                </div>
                {canApprove ? (
                  <button
                    type="button"
                    disabled={approve.isPending || drafts.length === 0}
                    onClick={() => approve.mutate()}
                    className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-3 text-sm font-semibold text-ink-950 shadow-[0_10px_30px_-10px_rgb(25_74_203_/_0.9)] transition hover:bg-brand-400 disabled:opacity-60"
                  >
                    <CheckCheck className="size-4" /> {approve.isPending ? t('Approving…') : t('Approve batch')}
                  </button>
                ) : (
                  <p className="max-w-[180px] text-end text-[12.5px] leading-snug text-ink-400">
                    {t('A manager approves this batch before it goes to stock.')}
                  </p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
          {approve.isError && <p className="text-[13px] text-alarm-400">{approve.error.message}</p>}
        </div>
      </div>
    </div>
  )
}
