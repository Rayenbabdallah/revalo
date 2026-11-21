import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle2, FileUp, Plus, Scissors, Trash2 } from 'lucide-react'
import { motion } from 'motion/react'
import { useRef, useState } from 'react'
import { Link } from 'wouter'

import { checkFit, getMaterials, reuseRemnants, type FitPlan, type FitUse } from '../../lib/api'
import { fmtKg, fmtMm, fmtTnd } from '../../lib/format'

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
    <svg viewBox={`${-pad} ${-pad} ${w + 2 * pad} ${h + 2 * pad}`} className="max-h-56 w-full" role="img" aria-label={`Remnant ${use.piece.code} with ${use.placements.length} parts`}>
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

  const run = useMutation({
    mutationFn: () =>
      checkFit({
        file: file ?? undefined,
        material: material || undefined,
        thickness_mm: thickness ? Number(thickness.replace(',', '.')) : undefined,
        parts: rows
          .filter((r) => r.length && r.width)
          .map((r) => ({ length: Number(r.length), width: Number(r.width), qty: Number(r.qty || 1) })),
      }),
  })
  const reuse = useMutation({
    mutationFn: (plan: FitPlan) =>
      reuseRemnants(
        plan.uses.map((u) => u.piece.id),
        jobName.trim() || file?.name || 'Next job',
      ),
    onSuccess: () => {
      for (const key of ['stock', 'listings', 'job', 'jobs']) queryClient.invalidateQueries({ queryKey: [key] })
    },
  })
  const plan = run.data

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 md:px-10 md:py-12">
      <Link href="/stock" className="inline-flex items-center gap-1.5 text-[13px] text-ink-400 hover:text-ink-100">
        <ArrowLeft className="size-4" /> Stock
      </Link>
      <p className="eyebrow mt-4">Before you cut</p>
      <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">Can the racks cut it?</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-ink-400">
        Give Revalo the next job. It places the parts on remnants you already have, so you open a new sheet only for
        what does not fit.
      </p>

      <div className="mt-8 grid gap-5 lg:grid-cols-[380px_1fr]">
        <section className="panel h-fit space-y-4 p-5">
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            className="flex w-full items-center gap-3 rounded-2xl border-2 border-dashed border-brand-500/40 px-4 py-4 text-left text-brand-500 hover:bg-brand-500/5"
          >
            <FileUp className="size-6 shrink-0" />
            <span className="min-w-0">
              <span className="block truncate text-[14.5px] font-semibold">{file ? file.name : 'Next job file'}</span>
              <span className="block text-[12px] text-ink-400">Parts drawing (DXF), G-code or cut list</span>
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
              <span className="mb-1.5 block text-[12.5px] font-medium text-ink-300">Material</span>
              <select value={material} onChange={(e) => setMaterial(e.target.value)} className={field}>
                <option value="">From file name</option>
                {catalog.data?.materials.map((m) => (
                  <option key={m.code} value={m.code}>
                    {m.name.en}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[12.5px] font-medium text-ink-300">Thickness (mm)</span>
              <input value={thickness} onChange={(e) => setThickness(e.target.value)} inputMode="decimal" placeholder="auto" className={field} />
            </label>
          </div>

          <div>
            <p className="mb-1.5 text-[12.5px] font-medium text-ink-300">Or type part sizes (mm)</p>
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
                <button type="button" aria-label="Remove" onClick={() => setRows((all) => all.filter((_, j) => j !== i))} className="grid place-items-center text-ink-500 hover:text-alarm-400">
                  <Trash2 className="size-4" />
                </button>
              </div>
            ))}
            <button type="button" onClick={() => setRows((all) => [...all, { length: '', width: '', qty: '1' }])} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand-500">
              <Plus className="size-4" /> Add a part size
            </button>
          </div>

          <button
            type="button"
            onClick={() => run.mutate()}
            disabled={run.isPending || (!file && rows.length === 0)}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-500 py-3 text-[15px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-50"
          >
            <Scissors className="size-4" /> {run.isPending ? 'Checking the racks…' : 'Check the stock'}
          </button>
          {run.isError && <p className="text-[13px] text-alarm-400">{run.error.message}</p>}
        </section>

        <section>
          {!plan ? (
            <div className="panel grid min-h-72 place-items-center p-8 text-center text-[14px] text-ink-400">
              The plan appears here: each remnant drawn to scale with the parts it can hold.
            </div>
          ) : (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
              <div className="panel-brand p-6">
                <p className="eyebrow !text-ink-950/75">
                  {plan.material_name.en} · {plan.thickness_mm} mm · {plan.candidates} remnants in stock
                </p>
                <p className="mt-3 font-display text-[28px] font-semibold leading-tight">
                  <span className="text-reclaim-400">
                    {plan.placed_count} of {plan.part_count}
                  </span>{' '}
                  parts fit on {plan.uses.length} remnant{plan.uses.length === 1 ? '' : 's'}
                </p>
                <p className="mt-2 text-[14px] text-ink-950/85">
                  Saves {fmtKg(plan.saved_kg)} kg of new material
                  {plan.saved_tnd !== null && <>, about {fmtTnd(plan.saved_tnd)}</>}.
                  {plan.unplaced.length > 0 && ` ${plan.unplaced.length} part${plan.unplaced.length === 1 ? '' : 's'} still need a new sheet.`}
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
                      {use.placements.length} part{use.placements.length === 1 ? '' : 's'} · {Math.round(use.fill * 100)}% used
                    </p>
                    <p className="mt-1 text-[13px] text-ink-400">Rack: {use.piece.location ?? 'not set'}</p>
                  </div>
                </div>
              ))}

              {plan.uses.length > 0 &&
                (reuse.isSuccess ? (
                  <div className="panel flex items-center gap-3 p-5 text-[14.5px] text-ink-100">
                    <CheckCircle2 className="size-6 text-reclaim-600" /> {reuse.data.pieces.length} remnant
                    {reuse.data.pieces.length === 1 ? '' : 's'} taken out of stock for this job.
                  </div>
                ) : (
                  <div className="panel flex flex-wrap items-end gap-3 p-5">
                    <label className="block min-w-56 flex-1">
                      <span className="mb-1.5 block text-[12.5px] font-medium text-ink-300">Job or order name</span>
                      <input value={jobName} onChange={(e) => setJobName(e.target.value)} placeholder={file?.name ?? 'Order 2026-131'} className={field} />
                    </label>
                    <button
                      type="button"
                      onClick={() => reuse.mutate(plan)}
                      disabled={reuse.isPending}
                      className="rounded-xl bg-reclaim-400 px-5 py-2.5 text-[14px] font-semibold text-ink-50 hover:bg-reclaim-500 disabled:opacity-60"
                    >
                      Use these {plan.uses.length} remnants
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
