import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Bookmark, CheckCircle2, FileUp, Plus, Scissors, ShoppingCart, Trash2 } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearch } from 'wouter'

import {
  checkFit,
  checkPlannedJob,
  closePlannedJob,
  getMaterials,
  getPlannedJobs,
  keepPlannedJob,
  reuseRemnants,
  type FitPlan,
  type FitUse,
} from '../../lib/api'
import { useCan } from '../../lib/auth'
import { fmtKg, fmtMm, fmtTnd, materialLabel } from '../../lib/format'
import { t } from '../../lib/i18n'

interface Row {
  length: string
  width: string
  qty: string
}

const field =
  'w-full rounded-xl border border-ink-700 bg-ink-900 px-3 py-2.5 text-[14px] text-ink-50 focus:border-brand-500 focus:outline-none'

/** The remnant to scale, with the coming job's parts placed on it. */
function RemnantDrawing({ use }: { use: FitUse }) {
  const { width_mm: w, height_mm: h } = use.piece
  const pad = Math.max(w, h) * 0.02
  return (
    <svg viewBox={`${-pad} ${-pad} ${w + 2 * pad} ${h + 2 * pad}`} className="max-h-56 w-full" role="img" aria-label={t('Remnant {code} with {count} parts', { code: use.piece.code, count: use.placements.length })}>
      <rect x={0} y={0} width={w} height={h} rx={Math.max(w, h) * 0.006} fill="#e9e4da" stroke="#bdb5a7" strokeWidth={Math.max(w, h) * 0.003} />
      {use.placements.map((p, i) => (
        <g key={i}>
          <rect x={p.x} y={h - p.y - p.height} width={p.width} height={p.height} fill="#66ca53" fillOpacity={0.85} stroke="#3f9a2e" strokeWidth={Math.max(w, h) * 0.003} />
          {Math.min(p.width, p.height) > Math.max(w, h) * 0.08 && (
            <text x={p.x + p.width / 2} y={h - p.y - p.height / 2} fontSize={Math.min(p.width, p.height) * 0.22} textAnchor="middle" dominantBaseline="middle" fill="#121212" fontFamily="IBM Plex Mono, monospace">
              {p.label}
            </text>
          )}
        </g>
      ))}
    </svg>
  )
}

export function FitPage() {
  const queryClient = useQueryClient()
  const catalog = useQuery({ queryKey: ['materials'], queryFn: getMaterials, staleTime: Infinity })
  const fileInput = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [material, setMaterial] = useState('')
  const [thickness, setThickness] = useState('')
  const [rows, setRows] = useState<Row[]>([])
  const [jobName, setJobName] = useState('')
  const canPlan = useCan('manager')
  const plannedFromLink = new URLSearchParams(useSearch()).get('planned')
  const planned = useQuery({ queryKey: ['planned'], queryFn: getPlannedJobs, enabled: canPlan })

  const inputs = () => ({
    file: file ?? undefined,
    material: material || undefined,
    thickness_mm: thickness ? Number(thickness.replace(',', '.')) : undefined,
    parts: rows
      .filter((r) => r.length && r.width)
      .map((r) => ({ length: Number(r.length), width: Number(r.width), qty: Number(r.qty || 1) })),
  })
  const run = useMutation({ mutationFn: () => checkFit(inputs()) })
  const runPlanned = useMutation({
    mutationFn: (id: string) => checkPlannedJob(id),
    onSuccess: (result) => {
      run.reset()
      setJobName(result.planned.name)
    },
  })
  const keep = useMutation({
    mutationFn: () => keepPlannedJob({ ...inputs(), name: jobName.trim() || file?.name || t('Next job') }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['planned'] }),
  })
  const close = useMutation({
    mutationFn: (id: string) => closePlannedJob(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['planned'] })
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
    },
  })

  // Opened from an alert: show that planned job's plan straight away.
  const { mutate: openPlanned } = runPlanned
  useEffect(() => {
    if (plannedFromLink) openPlanned(plannedFromLink)
  }, [plannedFromLink, openPlanned])
  const reuse = useMutation({
    mutationFn: (plan: FitPlan) =>
      reuseRemnants(
        plan.uses.map((u) => u.piece.id),
        jobName.trim() || file?.name || t('Next job'),
      ),
    onSuccess: () => {
      for (const key of ['stock', 'listings', 'job', 'jobs']) queryClient.invalidateQueries({ queryKey: [key] })
    },
  })
  const plan: FitPlan | undefined = run.data ?? runPlanned.data

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 md:px-10 md:py-12">
      <Link href="/stock" className="inline-flex items-center gap-1.5 text-[13px] text-ink-400 hover:text-ink-100">
        <ArrowLeft className="size-4 rtl:-scale-x-100" /> {t('Stock')}
      </Link>
      <p className="eyebrow mt-4">{t('Before you cut')}</p>
      <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">{t('Can the racks cut it?')}</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-ink-400">
        {t('Give Revalo the next job. It places the parts on remnants you already have, so you open a new sheet only for what does not fit.')}
      </p>

      {canPlan && (planned.data?.planned.length ?? 0) > 0 && (
        <section className="mt-6">
          <p className="eyebrow">{t('Planned jobs')}</p>
          <div className="mt-3 grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {planned.data!.planned.map((pj) => (
              <div key={pj.id} className="panel flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-ink-50">{pj.name}</p>
                  <p className="text-[12.5px] text-ink-400">
                    {materialLabel(pj.material_code)} {pj.thickness_mm} mm · {t('{count} part|{count} parts', { count: pj.part_count })}
                  </p>
                  <p className={pj.fits_in_stock ? 'text-[12.5px] font-medium text-reclaim-300' : 'text-[12.5px] text-ink-500'}>
                    {t('{count} fit the racks now', { count: pj.fits_in_stock })}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col gap-1.5">
                  <button
                    type="button"
                    onClick={() => runPlanned.mutate(pj.id)}
                    className="rounded-lg bg-brand-500 px-3 py-1.5 text-[12.5px] font-semibold text-ink-950 hover:bg-brand-400"
                  >
                    {t('Check now')}
                  </button>
                  <button
                    type="button"
                    onClick={() => close.mutate(pj.id)}
                    className="rounded-lg border border-ink-700 px-3 py-1.5 text-[12.5px] text-ink-300 hover:border-ink-500"
                  >
                    {t('Done')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="mt-8 grid gap-5 lg:grid-cols-[380px_1fr]">
        <section className="panel h-fit space-y-4 p-5">
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            className="flex w-full items-center gap-3 rounded-2xl border-2 border-dashed border-brand-500/40 px-4 py-4 text-start text-brand-500 hover:bg-brand-500/5"
          >
            <FileUp className="size-6 shrink-0" />
            <span className="min-w-0">
              <span className="block truncate text-[14.5px] font-semibold">{file ? file.name : t('Next job file')}</span>
              <span className="block text-[12px] text-ink-400">{t('Parts drawing (DXF), G-code or cut list')}</span>
            </span>
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".dxf,.nc,.gcode,.ngc,.tap,.csv,.tsv,.txt"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1.5 block text-[12.5px] font-medium text-ink-300">{t('Material')}</span>
              <select value={material} onChange={(e) => setMaterial(e.target.value)} className={field}>
                <option value="">{t('From file name')}</option>
                {catalog.data?.materials.map((m) => (
                  <option key={m.code} value={m.code}>
                    {materialLabel(m.code)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[12.5px] font-medium text-ink-300">{t('Thickness (mm)')}</span>
              <input value={thickness} onChange={(e) => setThickness(e.target.value)} inputMode="decimal" placeholder={t('auto')} className={field} />
            </label>
          </div>

          <div>
            <p className="mb-1.5 text-[12.5px] font-medium text-ink-300">{t('Or type part sizes (mm)')}</p>
            {rows.map((r, i) => (
              <div key={i} className="mb-2 grid grid-cols-[1fr_1fr_64px_32px] gap-2">
                {(['length', 'width', 'qty'] as const).map((k) => (
                  <input
                    key={k}
                    value={r[k]}
                    placeholder={k === 'qty' ? 'qty' : k}
                    inputMode="numeric"
                    onChange={(e) => setRows((all) => all.map((row, j) => (j === i ? { ...row, [k]: e.target.value } : row)))}
                    className={field}
                  />
                ))}
                <button type="button" aria-label={t('Remove')} onClick={() => setRows((all) => all.filter((_, j) => j !== i))} className="grid place-items-center text-ink-500 hover:text-alarm-400">
                  <Trash2 className="size-4" />
                </button>
              </div>
            ))}
            <button type="button" onClick={() => setRows((all) => [...all, { length: '', width: '', qty: '1' }])} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-500">
              <Plus className="size-4" /> {t('Add a part size')}
            </button>
          </div>

          <button
            type="button"
            onClick={() => run.mutate()}
            disabled={run.isPending || (!file && rows.length === 0)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-500 py-3 text-[15px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-50"
          >
            <Scissors className="size-4" /> {run.isPending ? t('Checking the racks…') : t('Check the stock')}
          </button>
          {(run.isError || runPlanned.isError) && (
            <p className="text-[13px] text-alarm-400">{(run.error ?? runPlanned.error)?.message}</p>
          )}
          {canPlan && !runPlanned.data && (file || rows.length > 0) && (
            <div className="border-t border-ink-800 pt-4">
              <p className="text-[12.5px] text-ink-400">
                {t('Not cutting it today? Keep it in mind: every new offcut will be checked against its parts.')}
              </p>
              <input
                value={jobName}
                onChange={(e) => setJobName(e.target.value)}
                placeholder={t('Job or order name')}
                aria-label={t('Job or order name')}
                className={`${field} mt-2`}
              />
              <button
                type="button"
                disabled={keep.isPending || keep.isSuccess}
                onClick={() => keep.mutate()}
                className="mt-2 inline-flex items-center gap-2 rounded-xl border border-ink-700 px-4 py-2 text-[13.5px] font-medium text-ink-100 hover:border-brand-500 disabled:opacity-60"
              >
                <Bookmark className="size-4 text-brand-500" />
                {keep.isSuccess ? t('Kept in mind') : t('Keep this job in mind')}
              </button>
              {keep.isError && <p className="mt-2 text-[13px] text-alarm-400">{keep.error.message}</p>}
            </div>
          )}
        </section>

        <section>
          {!plan ? (
            <div className="panel grid min-h-72 place-items-center p-8 text-center text-[14px] text-ink-400">
              {t('The plan appears here: each remnant drawn to scale with the parts it can hold.')}
            </div>
          ) : (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
              <div className="panel-brand p-6">
                <p className="eyebrow !text-ink-950/75">
                  {materialLabel(plan.material_code)} · {plan.thickness_mm} mm · {t('{count} remnant in stock|{count} remnants in stock', { count: plan.candidates })}
                </p>
                <p className="mt-3 font-display text-[28px] font-semibold leading-tight">
                  <span className="text-reclaim-400">
                    {t('{placed} of {count}', { placed: plan.placed_count, count: plan.part_count })}
                  </span>{' '}
                  {t('parts fit on {count} remnant|parts fit on {count} remnants', { count: plan.uses.length })}
                </p>
                <p className="mt-2 text-[14px] text-ink-950/85">
                  {plan.saved_tnd !== null
                    ? t('Saves {kg} kg of new material, about {amount}.', { kg: fmtKg(plan.saved_kg), amount: fmtTnd(plan.saved_tnd) })
                    : t('Saves {kg} kg of new material.', { kg: fmtKg(plan.saved_kg) })}
                  {plan.unplaced.length > 0 &&
                    ` ${t('{count} part still needs a new sheet.|{count} parts still need a new sheet.', { count: plan.unplaced.length })}`}
                </p>
              </div>

              {plan.uses.map((use) => (
                <div key={use.piece.id} className="panel grid gap-4 p-5 md:grid-cols-[1fr_220px] md:items-center">
                  <RemnantDrawing use={use} />
                  <div>
                    <p className="readout text-[13px] text-ink-400">{use.piece.code}</p>
                    <p className="readout mt-1 text-[17px] text-ink-50">
                      {fmtMm(use.piece.width_mm)} × {fmtMm(use.piece.height_mm)} mm
                    </p>
                    <p className="mt-1 text-[13px] text-ink-400">
                      {t('{count} part|{count} parts', { count: use.placements.length })} · {t('{pct}% used', { pct: Math.round(use.fill * 100) })}
                    </p>
                    <p className="mt-1 text-[13px] text-ink-400">{t('Rack: {location}', { location: use.piece.location ?? t('not set') })}</p>
                  </div>
                </div>
              ))}

              {(plan.offers?.length ?? 0) > 0 && (
                <div className="panel border-reclaim-400/50 p-5">
                  <p className="flex items-center gap-2 text-[14.5px] font-semibold text-ink-50">
                    <ShoppingCart className="size-4 text-reclaim-600" />
                    {t('Before opening a new sheet, these offers would hold the rest')}
                  </p>
                  <div className="mt-3 space-y-2">
                    {plan.offers!.map((o) => (
                      <div key={o.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ink-800 p-3">
                        <div className="min-w-0">
                          <p className="text-[14px] font-medium text-ink-50">
                            {o.organization ?? o.seller_name} · {o.governorate}
                            {o.distance_km !== null && ` · ${Math.round(o.distance_km)} km`}
                          </p>
                          <p className="readout mt-0.5 text-[12.5px] text-ink-400">
                            {o.quantity} × {fmtMm(o.width_mm)} × {fmtMm(o.height_mm)} mm · {fmtTnd(o.price_tnd)}
                            {o.saving_tnd !== null && o.saving_tnd > 0 && ` · ${t('{amount} less than new', { amount: fmtTnd(o.saving_tnd) })}`}
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="readout text-[13px] text-reclaim-600">
                            {t('holds {count} part|holds {count} parts', { count: o.placed_count ?? 0 })}
                          </span>
                          <Link href="/market?tab=buying" className="text-[13px] font-medium text-brand-500 hover:underline">
                            {t('See offer')}
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {plan.uses.length > 0 &&
                (reuse.isSuccess ? (
                  <div className="panel flex items-center gap-3 p-5 text-[14.5px] text-ink-100">
                    <CheckCircle2 className="size-6 text-reclaim-600" />{' '}
                    {t('{count} remnant taken out of stock for this job.|{count} remnants taken out of stock for this job.', { count: reuse.data.pieces.length })}
                  </div>
                ) : (
                  <div className="panel flex flex-wrap items-end gap-3 p-5">
                    <label className="block min-w-56 flex-1">
                      <span className="mb-1.5 block text-[12.5px] font-medium text-ink-300">{t('Job or order name')}</span>
                      <input value={jobName} onChange={(e) => setJobName(e.target.value)} placeholder={file?.name ?? t('Order 2026-131')} className={field} />
                    </label>
                    <button
                      type="button"
                      onClick={() => reuse.mutate(plan)}
                      disabled={reuse.isPending}
                      className="rounded-xl bg-reclaim-400 px-5 py-2.5 text-[14px] font-semibold text-ink-50 hover:bg-reclaim-500 disabled:opacity-60"
                    >
                      {t('Use this remnant|Use these {count} remnants', { count: plan.uses.length })}
                    </button>
                    {reuse.isError && <p className="w-full text-[13px] text-alarm-400">{reuse.error.message}</p>}
                  </div>
                ))}
            </motion.div>
          )}
        </section>
      </div>
    </div>
  )
}
