import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { AlertTriangle, ArrowLeft, CheckCircle2, FileSpreadsheet, Plus, Printer, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'wouter'

import { addExistingPieces, checkExistingPieces, getMaterials, type IntakeCheck, type IntakeRow } from '../../lib/api'
import { materialLabel } from '../../lib/format'
import { EMPTY_ROW, num, parseList } from '../../lib/intakeList'
import { t } from '../../lib/i18n'

const FIELD =
  'w-full rounded-lg border border-ink-700 bg-ink-950/70 px-2.5 py-2 text-[13.5px] text-ink-100 focus:border-brand-500 focus:outline-none'

export function IntakePage() {
  const queryClient = useQueryClient()
  const catalog = useQuery({ queryKey: ['materials'], queryFn: getMaterials, staleTime: Infinity })
  const [name, setName] = useState('')
  const [rows, setRows] = useState<IntakeRow[]>([{ ...EMPTY_ROW }])
  const [checked, setChecked] = useState<{ key: string; rows: IntakeCheck[] } | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const key = JSON.stringify(rows)
  const fresh = checked?.key === key ? checked.rows : null

  const check = useMutation({
    mutationFn: () => checkExistingPieces(rows),
    onSuccess: (result) => setChecked({ key, rows: result.rows }),
  })
  const add = useMutation({
    mutationFn: () => addExistingPieces(rows, name || undefined),
    onSuccess: () => {
      for (const k of ['stock', 'jobs', 'alerts']) queryClient.invalidateQueries({ queryKey: [k] })
    },
  })

  const total = rows.reduce((n, r) => n + (r.quantity || 0), 0)
  const warnings = fresh?.filter((r) => r.similar_in_stock > 0).length ?? 0
  const set = (i: number, patch: Partial<IntakeRow>) => setRows((all) => all.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  if (add.data) {
    return (
      <div className="mx-auto max-w-xl px-4 py-12">
        <div className="panel-brand p-7 text-center">
          <CheckCircle2 className="mx-auto size-12 text-reclaim-400" />
          <p className="mt-3 font-display text-2xl font-semibold">
            {t('{count} piece added to stock.|{count} pieces added to stock.', { count: add.data.pieces.length })}
          </p>
          <p className="mt-1 text-[14.5px] text-ink-950/85">{add.data.file_name}</p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <Link href={`/jobs/${add.data.id}/labels`} className="inline-flex items-center gap-2 rounded-xl bg-ink-950 px-5 py-3 text-[15px] font-semibold text-brand-500">
              <Printer className="size-4" /> {t('Print labels')}
            </Link>
            <button
              type="button"
              onClick={() => {
                add.reset()
                setChecked(null)
                setName('')
                setRows([{ ...EMPTY_ROW }])
              }}
              className="rounded-xl border border-white/30 px-5 py-3 text-[15px] font-medium"
            >
              {t('Add more pieces')}
            </button>
            <Link href="/stock" className="rounded-xl border border-white/30 px-5 py-3 text-[15px] font-medium">
              {t('Go to stock')}
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 md:px-10 md:py-12">
      <Link href="/stock" className="inline-flex items-center gap-1.5 text-[13px] text-ink-400 hover:text-ink-100">
        <ArrowLeft className="size-4 rtl:-scale-x-100" /> {t('Stock')}
      </Link>
      <p className="eyebrow mt-4">{t('First week')}</p>
      <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">{t('Add what is already on the racks')}</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-ink-400">
        {t('Offcuts from before Revalo: type them, or import the list you already keep. Each row is compared with the stock first, so nothing is entered twice.')}
      </p>

      <div className="mt-6 flex flex-wrap items-end gap-3">
        <label className="text-[13px] font-medium text-ink-200">
          {t('Name of this intake')}
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('Racks A and B')} className={clsx(FIELD, 'mt-1.5 w-72')} />
        </label>
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="inline-flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-900 px-4 py-2.5 text-[14px] font-medium text-ink-100 hover:border-brand-500"
        >
          <FileSpreadsheet className="size-4 text-brand-500" /> {t('Import a CSV list')}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".csv,.tsv,.txt"
          className="hidden"
          onChange={async (e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (!file) return
            const imported = parseList(await file.text())
            if (imported.length) setRows((all) => [...all.filter((r) => r.material || r.width_mm), ...imported])
          }}
        />
        <span className="text-[12px] text-ink-500">{t('Columns: material, thickness, width, height, quantity, rack')}</span>
      </div>

      <datalist id="intake-materials">
        {catalog.data?.materials.map((m) => (
          <option key={m.code} value={m.code} label={materialLabel(m.code)} />
        ))}
      </datalist>

      <div className="panel mt-5 overflow-x-auto p-0">
        <table className="w-full min-w-[900px] text-start text-[13px]">
          <thead className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-500">
            <tr className="border-b border-ink-800">
              {[t('Material'), t('Thickness (mm)'), t('Kind'), t('Width mm'), t('Height mm'), t('Weight (kg)'), t('Quantity'), t('Rack'), t('Check'), ''].map((h, i) => (
                <th key={i} className="px-3 py-3 text-start font-normal">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const result = fresh?.[i]
              const scrap = r.kind === 'scrap'
              return (
                <tr key={i} className="border-b border-ink-800/60 last:border-0">
                  <td className="px-3 py-2">
                    <input list="intake-materials" value={r.material} onChange={(e) => set(i, { material: e.target.value })} placeholder="steel_mild" className={FIELD} />
                  </td>
                  <td className="px-3 py-2">
                    <input inputMode="decimal" value={r.thickness_mm || ''} onChange={(e) => set(i, { thickness_mm: num(e.target.value) ?? 0 })} className={FIELD} />
                  </td>
                  <td className="px-3 py-2">
                    <select value={r.kind} onChange={(e) => set(i, { kind: e.target.value as IntakeRow['kind'] })} className={FIELD}>
                      <option value="remnant">{t('Remnant')}</option>
                      <option value="scrap">{t('Scrap lot')}</option>
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <input inputMode="decimal" disabled={scrap} value={r.width_mm ?? ''} onChange={(e) => set(i, { width_mm: num(e.target.value) })} className={FIELD} />
                  </td>
                  <td className="px-3 py-2">
                    <input inputMode="decimal" disabled={scrap} value={r.height_mm ?? ''} onChange={(e) => set(i, { height_mm: num(e.target.value) })} className={FIELD} />
                  </td>
                  <td className="px-3 py-2">
                    <input inputMode="decimal" value={r.weight_kg ?? ''} placeholder={scrap ? '' : t('auto')} onChange={(e) => set(i, { weight_kg: num(e.target.value) })} className={FIELD} />
                  </td>
                  <td className="px-3 py-2">
                    <input inputMode="numeric" value={r.quantity} onChange={(e) => set(i, { quantity: Math.max(1, Math.round(num(e.target.value) ?? 1)) })} className={clsx(FIELD, 'w-16')} />
                  </td>
                  <td className="px-3 py-2">
                    <input value={r.location ?? ''} onChange={(e) => set(i, { location: e.target.value })} placeholder="A1" className={clsx(FIELD, 'w-24')} />
                  </td>
                  <td className="px-3 py-2 text-[12px]">
                    {result &&
                      (result.similar_in_stock > 0 ? (
                        <span className="inline-flex items-center gap-1 text-rust-400" title={result.similar.map((s) => `${s.code} ${s.location ?? ''}`).join(', ')}>
                          <AlertTriangle className="size-3.5" />
                          {t('{count} similar in stock', { count: result.similar_in_stock })}
                        </span>
                      ) : (
                        <span className="text-reclaim-300">{t('New')}</span>
                      ))}
                  </td>
                  <td className="px-2 py-2">
                    <button type="button" aria-label={t('Remove')} onClick={() => setRows((all) => all.filter((_, j) => j !== i))} className="text-ink-500 hover:text-alarm-400">
                      <Trash2 className="size-4" />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <button type="button" onClick={() => setRows((all) => [...all, { ...EMPTY_ROW }])} className="mt-3 inline-flex items-center gap-1.5 text-[13.5px] font-medium text-brand-500">
        <Plus className="size-4" /> {t('Add a row')}
      </button>

      {(check.isError || add.isError) && <p className="mt-4 text-[13.5px] text-alarm-400">{(check.error ?? add.error)?.message}</p>}
      {fresh && warnings > 0 && (
        <p className="mt-4 rounded-xl bg-rust-400/10 px-4 py-3 text-[13.5px] text-ink-100">
          {t('{count} row looks like pieces already in stock. Check the racks named in the warning before adding.|{count} rows look like pieces already in stock. Check the racks named in the warnings before adding.', { count: warnings })}
        </p>
      )}
      <div className="mt-5 flex flex-wrap gap-2">
        {fresh ? (
          <button
            type="button"
            disabled={add.isPending}
            onClick={() => add.mutate()}
            className="rounded-xl bg-brand-500 px-5 py-3 text-[15px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60"
          >
            {warnings > 0
              ? t('Add {count} piece anyway|Add {count} pieces anyway', { count: total })
              : t('Add {count} piece to stock|Add {count} pieces to stock', { count: total })}
          </button>
        ) : (
          <button
            type="button"
            disabled={check.isPending || rows.length === 0}
            onClick={() => check.mutate()}
            className="rounded-xl bg-brand-500 px-5 py-3 text-[15px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60"
          >
            {check.isPending ? t('Checking the racks…') : t('Check against stock')}
          </button>
        )}
      </div>
    </div>
  )
}
