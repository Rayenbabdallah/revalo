import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Pencil, RotateCcw, X } from 'lucide-react'
import { useState } from 'react'

import { useActor } from '../../lib/actor'
import { getMaterials, getPrices, putPrice, resetPrice, type PriceRow } from '../../lib/api'
import { fmtDate } from '../../lib/format'

const PANEL_M3 = 2.44 * 1.22 * 0.018

/** How the trade quotes it: wood per 18 mm panel, metal per tonne. */
function tradeHint(row: PriceRow, density: number | undefined) {
  if (row.new_tnd_per_kg === null) return null
  if (row.family === 'wood' && density) {
    const panel = row.new_tnd_per_kg * PANEL_M3 * density
    return `≈ ${panel.toFixed(0)} TND per 2440×1220×18 panel`
  }
  return `≈ ${(row.new_tnd_per_kg * 1000).toLocaleString('en-US', { maximumFractionDigits: 0 })} TND per tonne`
}

const inputClass =
  'w-full rounded-lg border border-ink-700 bg-ink-950/70 px-2.5 py-2 font-mono text-[13px] text-ink-100 focus:border-brand-500 focus:outline-none'

function Editor({ row, onClose }: { row: PriceRow; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [actor] = useActor()
  const [newPrice, setNewPrice] = useState(row.new_tnd_per_kg?.toString() ?? '')
  const [scrap, setScrap] = useState(row.scrap_tnd_per_kg?.toString() ?? '0')
  const [resale, setResale] = useState(row.resale_factor ? String(Math.round(row.resale_factor * 100)) : '40')
  const [source, setSource] = useState(row.custom ? (row.source ?? '') : '')
  const save = useMutation({
    mutationFn: () =>
      putPrice(row.material_code, {
        new_tnd_per_kg: Number(newPrice.replace(',', '.')),
        scrap_tnd_per_kg: Number(scrap.replace(',', '.')),
        resale_factor: Number(resale) / 100,
        source,
        actor,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prices'] })
      queryClient.invalidateQueries({ queryKey: ['job'] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      onClose()
    },
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate()
      }}
      className="grid gap-3 border-t border-ink-800 bg-ink-950/40 px-6 py-4 md:grid-cols-[repeat(3,minmax(0,140px))_1fr_auto]"
    >
      <label className="block">
        <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">New TND/kg</span>
        <input className={inputClass} inputMode="decimal" required value={newPrice} onChange={(e) => setNewPrice(e.target.value)} />
      </label>
      <label className="block">
        <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">Scrap TND/kg</span>
        <input className={inputClass} inputMode="decimal" required value={scrap} onChange={(e) => setScrap(e.target.value)} />
      </label>
      <label className="block">
        <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">Resale %</span>
        <input className={inputClass} inputMode="numeric" required value={resale} onChange={(e) => setResale(e.target.value)} />
      </label>
      <label className="block">
        <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">Source</span>
        <input
          className={inputClass + ' font-sans'}
          placeholder="Supplier quote, scrap dealer, date…"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        />
      </label>
      <div className="flex items-end gap-2">
        <button
          type="submit"
          disabled={save.isPending}
          className="h-[38px] rounded-lg bg-brand-500 px-4 text-[13px] font-semibold text-ink-950 transition hover:bg-brand-400 disabled:opacity-60"
        >
          Save
        </button>
        <button type="button" onClick={onClose} aria-label="Cancel" className="grid h-[38px] w-[38px] place-items-center rounded-lg border border-ink-700 text-ink-400 hover:text-ink-100">
          <X className="size-4" />
        </button>
      </div>
      {save.isError && <p className="text-[12px] text-alarm-400 md:col-span-5">{save.error.message}</p>}
    </form>
  )
}

export function PricesPage() {
  const queryClient = useQueryClient()
  const prices = useQuery({ queryKey: ['prices'], queryFn: getPrices })
  const catalog = useQuery({ queryKey: ['materials'], queryFn: getMaterials, staleTime: Infinity })
  const [editing, setEditing] = useState<string | null>(null)
  const reset = useMutation({
    mutationFn: resetPrice,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prices'] })
      queryClient.invalidateQueries({ queryKey: ['stock'] })
      queryClient.invalidateQueries({ queryKey: ['job'] })
    },
  })
  const density = new Map(catalog.data?.materials.map((m) => [m.code, m.density_kg_m3]))
  const rows = prices.data?.prices ?? []
  const missing = rows.filter((r) => r.new_tnd_per_kg === null).length

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-8 md:px-10 md:py-12">
      <p className="eyebrow">Price book</p>
      <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">The numbers behind every decision</h1>
      <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-400">
        Revalo compares reusing, selling and recycling each piece with these prices. Defaults come from published
        sources; replace them with your own supplier and scrap-dealer quotes.
        {missing > 0 && ` ${missing} materials have no price yet: their pieces are kept for reuse until you add one.`}
      </p>

      <section className="panel mt-8 overflow-hidden">
        <div className="hidden grid-cols-[1.3fr_0.8fr_0.8fr_0.6fr_0.8fr_1.6fr_auto] gap-4 border-b border-ink-800 px-6 py-3 font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500 lg:grid">
          <span>Material</span>
          <span className="text-right">New</span>
          <span className="text-right">Scrap</span>
          <span className="text-right">Resale</span>
          <span className="text-right">CO₂ / kg</span>
          <span>Source</span>
          <span className="w-[76px]" />
        </div>
        {rows.map((row) => (
          <div key={row.material_code} className="border-b border-ink-800/70 last:border-0">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 px-6 py-4 lg:grid-cols-[1.3fr_0.8fr_0.8fr_0.6fr_0.8fr_1.6fr_auto] lg:items-center">
              <div className="col-span-2 lg:col-span-1">
                <p className="font-medium text-ink-100">{row.name.en}</p>
                <p className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-500">
                  {row.family}
                  {row.custom ? (
                    <span className="ml-2 text-reclaim-300">your price</span>
                  ) : row.new_tnd_per_kg === null ? (
                    <span className="ml-2 text-brand-300">no price</span>
                  ) : (
                    <span className="ml-2">default</span>
                  )}
                </p>
              </div>
              <div className="readout text-[14px] text-ink-100 lg:text-right">
                {row.new_tnd_per_kg !== null ? `${row.new_tnd_per_kg} TND/kg` : '—'}
                <p className="font-sans text-[11px] text-ink-500">{tradeHint(row, density.get(row.material_code))}</p>
              </div>
              <div className="readout text-[14px] text-ink-300 lg:text-right">
                {row.scrap_tnd_per_kg !== null ? `${row.scrap_tnd_per_kg} TND/kg` : '—'}
              </div>
              <div className="readout text-[14px] text-ink-300 lg:text-right">
                {row.resale_factor !== null ? `${Math.round(row.resale_factor * 100)}%` : '—'}
              </div>
              <div className="readout text-[14px] text-ink-300 lg:text-right" title={row.co2_source ?? 'No published factor yet'}>
                {row.co2_primary_kg_per_kg !== null ? `${row.co2_primary_kg_per_kg} kg` : '—'}
              </div>
              <p className="col-span-2 text-[12px] leading-snug text-ink-500 lg:col-span-1">
                {row.source ?? '—'}
                {row.custom && row.updated_by && row.updated_at && (
                  <span className="block font-mono text-[10.5px] text-ink-600">
                    {row.updated_by} · {fmtDate(row.updated_at)}
                  </span>
                )}
              </p>
              <div className="col-span-2 flex justify-end gap-1.5 lg:col-span-1">
                <button
                  type="button"
                  onClick={() => setEditing(editing === row.material_code ? null : row.material_code)}
                  className={clsx(
                    'inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-[12px] font-medium transition',
                    editing === row.material_code
                      ? 'border-brand-500/60 text-brand-300'
                      : 'border-ink-700 text-ink-300 hover:border-ink-500',
                  )}
                >
                  <Pencil className="size-3.5" /> {row.new_tnd_per_kg === null ? 'Add' : 'Edit'}
                </button>
                {row.custom && (
                  <button
                    type="button"
                    onClick={() => reset.mutate(row.material_code)}
                    title="Back to the default price"
                    className="grid size-8 place-items-center rounded-lg border border-ink-700 text-ink-400 transition hover:text-ink-100"
                  >
                    <RotateCcw className="size-3.5" />
                  </button>
                )}
              </div>
            </div>
            {editing === row.material_code && <Editor row={row} onClose={() => setEditing(null)} />}
          </div>
        ))}
      </section>
    </div>
  )
}
