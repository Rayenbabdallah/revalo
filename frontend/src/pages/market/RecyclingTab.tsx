import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { MapPin, MessageCircle, Recycle, Truck } from 'lucide-react'
import { useState } from 'react'

import { StatusBadge } from '../../components/ui/StatusBadge'
import { useActor } from '../../lib/actor'
import {
  actOnPickup,
  createPickup,
  getPickups,
  getRecycleQueue,
  type Pickup,
  type RecycleGroup,
} from '../../lib/api'
import { fmtDate, fmtKg, fmtMm, fmtTnd } from '../../lib/format'

const field =
  'rounded-lg border border-ink-700 bg-ink-900 px-2.5 py-1.5 text-[13px] text-ink-50 focus:border-brand-500 focus:outline-none'

function invalidate(queryClient: ReturnType<typeof useQueryClient>) {
  for (const key of ['recycle-queue', 'pickups', 'stock', 'listings', 'job', 'jobs']) {
    queryClient.invalidateQueries({ queryKey: [key] })
  }
}

function GroupCard({ group }: { group: RecycleGroup }) {
  const queryClient = useQueryClient()
  const [actor] = useActor()
  const [selected, setSelected] = useState<string[]>(group.pieces.map((p) => p.id))
  const [recycler, setRecycler] = useState<string | null>(
    group.recyclers.find((r) => r.lot_ok)?.recycler.id ?? null,
  )
  const create = useMutation({
    mutationFn: () => createPickup(recycler!, selected, actor),
    onSuccess: (pickup) => {
      window.open(pickup.whatsapp_url, '_blank', 'noopener')
      invalidate(queryClient)
    },
  })
  const kg = group.pieces.filter((p) => selected.includes(p.id)).reduce((s, p) => s + (p.weight_kg ?? 0), 0)

  return (
    <article className="panel p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-display text-[17px] font-semibold">{group.material_name?.en ?? 'Unknown material'}</h3>
        <p className="readout text-[13px] text-ink-400">
          {selected.length} of {group.pieces.length} pieces · {fmtKg(kg)} kg
        </p>
      </header>
      <ul className="mt-3 divide-y divide-ink-800 rounded-xl border border-ink-800">
        {group.pieces.map((p) => (
          <li key={p.id}>
            <label className="flex cursor-pointer items-center gap-3 px-3 py-2 text-[13.5px]">
              <input
                type="checkbox"
                checked={selected.includes(p.id)}
                onChange={(e) =>
                  setSelected((s) => (e.target.checked ? [...s, p.id] : s.filter((x) => x !== p.id)))
                }
                className="size-4 accent-[#194acb]"
              />
              <span className="readout w-24 text-ink-400">{p.code}</span>
              <span className="flex-1 text-ink-100">
                {p.kind === 'scrap' ? 'Scrap lot' : `${fmtMm(p.width_mm ?? 0)} × ${fmtMm(p.height_mm ?? 0)} mm`}
              </span>
              <span className="readout text-ink-300">{fmtKg(p.weight_kg)} kg</span>
            </label>
          </li>
        ))}
      </ul>

      <p className="mt-4 text-[12.5px] font-medium text-ink-300">Recyclers who take it</p>
      {group.recyclers.length === 0 ? (
        <p className="mt-1 text-[13px] text-ink-400">
          No recycler for this material yet. Add one in the Buyers tab or share the public page.
        </p>
      ) : (
        <div className="mt-2 space-y-2">
          {group.recyclers.map((r) => (
            <label
              key={r.recycler.id}
              className={clsx(
                'flex cursor-pointer flex-wrap items-center gap-3 rounded-xl border p-3',
                recycler === r.recycler.id ? 'border-brand-500 bg-brand-500/5' : 'border-ink-800',
                !r.lot_ok && 'opacity-60',
              )}
            >
              <input
                type="radio"
                name={`recycler-${group.material_code}`}
                checked={recycler === r.recycler.id}
                onChange={() => setRecycler(r.recycler.id)}
                className="accent-[#194acb]"
              />
              <span className="min-w-0 flex-1">
                <span className="block text-[14px] font-medium text-ink-50">{r.recycler.name}</span>
                <span className="flex flex-wrap items-center gap-x-2 text-[12px] text-ink-400">
                  <MapPin className="size-3" /> {r.recycler.governorate}
                  {r.distance_km !== null && ` · ${Math.round(r.distance_km)} km`}
                  {r.recycler.pickup_note && ` · ${r.recycler.pickup_note}`}
                  {!r.lot_ok && r.recycler.min_lot_kg && ` · needs ${r.recycler.min_lot_kg} kg`}
                </span>
              </span>
              <span className="readout text-right text-[13px] text-ink-200">
                {r.recycler.offered_tnd_per_kg ? `${r.recycler.offered_tnd_per_kg} TND/kg` : 'price to agree'}
                {r.recycler.offered_tnd_per_kg && (
                  <span className="block text-[11.5px] text-ink-400">≈ {fmtTnd(kg * r.recycler.offered_tnd_per_kg, 1)}</span>
                )}
              </span>
            </label>
          ))}
        </div>
      )}
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          disabled={!recycler || selected.length === 0 || create.isPending}
          onClick={() => create.mutate()}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-[14px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-50"
        >
          <Truck className="size-4" /> Request pickup on WhatsApp
        </button>
      </div>
      {create.isError && <p className="mt-2 text-[13px] text-alarm-400">{create.error.message}</p>}
    </article>
  )
}

function PickupRow({ pickup }: { pickup: Pickup }) {
  const queryClient = useQueryClient()
  const [actor] = useActor()
  const [date, setDate] = useState('')
  const [kg, setKg] = useState('')
  const act = useMutation({
    mutationFn: (body: Parameters<typeof actOnPickup>[1]) => actOnPickup(pickup.id, { ...body, actor }),
    onSuccess: () => invalidate(queryClient),
  })
  const open = pickup.status === 'requested' || pickup.status === 'scheduled'

  return (
    <div className="panel flex flex-wrap items-center justify-between gap-4 p-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <StatusBadge status={pickup.status} />
          <span className="text-[14px] font-medium text-ink-50">{pickup.recycler.name}</span>
        </div>
        <p className="mt-1 text-[12.5px] text-ink-400">
          {pickup.pieces.length} pieces · {fmtKg(pickup.weighed_kg ?? pickup.estimated_kg)} kg
          {pickup.weighed_kg !== null ? ' weighed' : ' estimated'}
          {pickup.scheduled_for && ` · pickup ${fmtDate(pickup.scheduled_for)}`}
          {pickup.paid_tnd !== null && ` · paid ${fmtTnd(pickup.paid_tnd, 2)}`}
        </p>
      </div>
      {open && (
        <div className="flex flex-wrap items-center gap-2">
          <a href={pickup.whatsapp_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[12.5px] font-medium text-reclaim-300">
            <MessageCircle className="size-3.5" /> Message
          </a>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={field} aria-label="Pickup date" />
          <button type="button" disabled={!date} onClick={() => act.mutate({ action: 'schedule', scheduled_for: date })} className="rounded-lg border border-ink-700 px-3 py-1.5 text-[12.5px] text-ink-200 hover:border-brand-500 disabled:opacity-50">
            Schedule
          </button>
          <input value={kg} onChange={(e) => setKg(e.target.value)} inputMode="decimal" placeholder="kg on ticket" className={clsx(field, 'w-28')} aria-label="Weighed kg" />
          <button type="button" disabled={!kg} onClick={() => act.mutate({ action: 'collect', weighed_kg: Number(kg.replace(',', '.')) })} className="rounded-lg bg-brand-500 px-3 py-1.5 text-[12.5px] font-semibold text-ink-950 disabled:opacity-50">
            Collected
          </button>
          <button type="button" onClick={() => act.mutate({ action: 'cancel' })} className="text-[12.5px] text-ink-400 hover:text-alarm-400">
            Cancel
          </button>
        </div>
      )}
      {act.isError && <p className="w-full text-[12.5px] text-alarm-400">{act.error.message}</p>}
    </div>
  )
}

export function RecyclingTab() {
  const queue = useQuery({ queryKey: ['recycle-queue'], queryFn: getRecycleQueue })
  const pickups = useQuery({ queryKey: ['pickups'], queryFn: getPickups })
  const groups = queue.data?.groups ?? []
  const list = pickups.data?.pickups ?? []

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <p className="max-w-2xl text-[14px] leading-relaxed text-ink-400">
          Scrap lots, and remnants that were not reused or sold in time, wait here. Send them to the recycler who pays
          the most for the material, nearby, as one sorted lot.
        </p>
        {groups.length === 0 ? (
          <div className="panel flex flex-col items-center gap-2 px-6 py-10 text-center">
            <Recycle className="size-8 text-ink-500" strokeWidth={1.5} />
            <p className="text-[14px] text-ink-400">Nothing to recycle right now.</p>
          </div>
        ) : (
          groups.map((g) => <GroupCard key={g.material_code ?? 'unknown'} group={g} />)
        )}
      </section>
      {list.length > 0 && (
        <section className="space-y-2">
          <h3 className="font-display text-lg font-semibold">Pickups</h3>
          {list.map((p) => (
            <PickupRow key={p.id} pickup={p} />
          ))}
        </section>
      )}
    </div>
  )
}
