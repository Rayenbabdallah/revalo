import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ExternalLink, MapPin, MessageCircle, PackageOpen, UserPlus, Users, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { Link, useLocation, useSearch } from 'wouter'

import { BuyerRequestForm } from '../../components/market/BuyerRequestForm'
import { RecyclingTab } from './RecyclingTab'
import { StatusBadge } from '../../components/ui/StatusBadge'
import { useActor } from '../../lib/actor'
import {
  actOnListing,
  getBuyerRequests,
  getListings,
  toggleBuyerRequest,
  type BuyerMatch,
  type BuyerRequest,
  type ListingAction,
  type WorkshopListing,
} from '../../lib/api'
import { fmtDate, fmtKg, fmtMm, fmtTnd, materialLabel } from '../../lib/format'

function pieceLine(l: WorkshopListing) {
  const p = l.piece
  const size = p.kind === 'remnant' ? `${fmtMm(p.width_mm ?? 0)} × ${fmtMm(p.height_mm ?? 0)} mm` : 'Scrap lot'
  return `${size} · ${materialLabel(p.material_code)}${p.thickness_mm ? ` ${p.thickness_mm} mm` : ''}`
}

function needLine(r: BuyerRequest) {
  const parts = [
    r.materials.length ? r.materials.map(materialLabel).join(', ') : 'Any material',
    r.thickness_min_mm || r.thickness_max_mm
      ? `${r.thickness_min_mm ?? '…'}–${r.thickness_max_mm ?? '…'} mm`
      : null,
    r.min_length_mm || r.min_width_mm ? `min ${r.min_length_mm ?? 0} × ${r.min_width_mm ?? 0} mm` : null,
    r.max_price_tnd_per_kg ? `≤ ${r.max_price_tnd_per_kg} TND/kg` : null,
  ]
  return parts.filter(Boolean).join(' · ')
}

function MatchRow({ match, onReserve, busy }: { match: BuyerMatch; onReserve: () => void; busy: boolean }) {
  const r = match.request
  return (
    <div className="grid gap-3 rounded-xl border border-ink-800 bg-ink-950/60 p-3 sm:grid-cols-[1fr_auto] sm:items-center">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="readout grid size-9 shrink-0 place-items-center rounded-lg bg-brand-500 text-[13px] text-ink-950">
            {match.score}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[14px] font-medium text-ink-50">
              {r.name}
              {r.organization && <span className="font-normal text-ink-400"> · {r.organization}</span>}
            </p>
            <p className="flex items-center gap-1 text-[12px] text-ink-400">
              <MapPin className="size-3" /> {r.governorate}
              {match.distance_km !== null && ` · ${Math.round(match.distance_km)} km`}
              {r.kind === 'recycler' && ' · recycler'}
            </p>
          </div>
        </div>
        <p className="mt-2 text-[12px] leading-relaxed text-ink-300">{match.reasons.join(' ')}</p>
      </div>
      <div className="flex gap-2">
        <a
          href={match.whatsapp_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg bg-reclaim-400 px-3 py-2 text-[13px] font-semibold text-ink-50 transition hover:bg-reclaim-500"
        >
          <MessageCircle className="size-4" /> WhatsApp
        </a>
        <button
          type="button"
          disabled={busy}
          onClick={onReserve}
          className="rounded-lg border border-ink-700 px-3 py-2 text-[13px] font-medium text-ink-200 transition hover:border-brand-500 hover:text-brand-500 disabled:opacity-60"
        >
          Reserve
        </button>
      </div>
    </div>
  )
}

function ListingCard({ listing }: { listing: WorkshopListing }) {
  const queryClient = useQueryClient()
  const [actor] = useActor()
  const [price, setPrice] = useState<string | null>(null)
  const act = useMutation({
    mutationFn: (body: { action: ListingAction; price_tnd?: number; buyer_request_id?: string }) =>
      actOnListing(listing.id, { ...body, actor }),
    onSuccess: () => {
      for (const key of ['listings', 'stock', 'job', 'jobs']) queryClient.invalidateQueries({ queryKey: [key] })
      setPrice(null)
    },
  })
  const open = listing.status === 'open'
  const reserved = listing.status === 'reserved'
  const priceValue = price === null ? listing.price_tnd : Number(price.replace(',', '.'))

  return (
    <article className="panel p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <StatusBadge status={listing.status} />
            <Link href={`/p/${listing.piece.code}`} className="readout text-[12px] text-ink-400 hover:text-brand-500">
              {listing.piece.code}
            </Link>
          </div>
          <p className="mt-2 font-display text-[17px] font-semibold text-ink-50">{pieceLine(listing)}</p>
          <p className="readout mt-0.5 text-[12px] text-ink-400">
            {fmtKg(listing.piece.weight_kg)} kg
            {listing.price_tnd_per_kg !== null && ` · ${listing.price_tnd_per_kg} TND/kg`}
            {listing.piece.condition_note && ` · ${listing.piece.condition_note}`}
          </p>
        </div>
        <div className="text-right">
          {open ? (
            <label className="flex items-center gap-2">
              <input
                value={price ?? String(listing.price_tnd)}
                onChange={(e) => setPrice(e.target.value)}
                onBlur={() => {
                  if (price !== null && priceValue > 0 && priceValue !== listing.price_tnd)
                    act.mutate({ action: 'reprice', price_tnd: priceValue })
                }}
                inputMode="decimal"
                aria-label="Asking price"
                className="readout w-24 rounded-lg border border-ink-700 bg-ink-900 px-2.5 py-1.5 text-right text-[18px] text-ink-50 focus:border-brand-500 focus:outline-none"
              />
              <span className="text-[13px] text-ink-400">TND</span>
            </label>
          ) : (
            <p className="readout text-[20px] text-ink-50">{fmtTnd(listing.sold_price_tnd ?? listing.price_tnd)}</p>
          )}
          {listing.status === 'sold' && listing.fee_tnd !== null && (
            <p className="mt-1 text-[11.5px] text-ink-400">Revalo fee {fmtTnd(listing.fee_tnd, 2)}</p>
          )}
        </div>
      </header>

      {reserved && listing.buyer && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-brand-500/8 p-3">
          <p className="text-[13.5px] text-ink-100">
            Reserved for <strong>{listing.buyer.name}</strong>
            {listing.buyer.organization && ` (${listing.buyer.organization})`} · {listing.buyer.governorate}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => act.mutate({ action: 'sell', price_tnd: listing.price_tnd })}
              className="rounded-lg bg-brand-500 px-3 py-2 text-[13px] font-semibold text-ink-950 hover:bg-brand-400"
            >
              Mark sold · {fmtTnd(listing.price_tnd)}
            </button>
            <button
              type="button"
              onClick={() => act.mutate({ action: 'reopen' })}
              className="rounded-lg border border-ink-700 px-3 py-2 text-[13px] text-ink-300 hover:border-ink-500"
            >
              Reopen
            </button>
          </div>
        </div>
      )}

      {open && (
        <div className="mt-4 space-y-2">
          <p className="text-[12.5px] font-medium text-ink-300">
            {listing.match_count
              ? `${listing.match_count} buyer${listing.match_count === 1 ? '' : 's'} match this piece`
              : 'No buyer matches yet. Share the public page in your WhatsApp groups.'}
          </p>
          {listing.top_matches?.map((m) => (
            <MatchRow
              key={m.request.id}
              match={m}
              busy={act.isPending}
              onReserve={() => act.mutate({ action: 'reserve', buyer_request_id: m.request.id })}
            />
          ))}
        </div>
      )}

      {(open || reserved) && (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={() => act.mutate({ action: 'withdraw' })}
            className="inline-flex items-center gap-1 text-[12.5px] text-ink-400 hover:text-alarm-400"
          >
            <X className="size-3.5" /> Withdraw from sale
          </button>
        </div>
      )}
      {act.isError && <p className="mt-2 text-[12.5px] text-alarm-400">{act.error.message}</p>}
    </article>
  )
}

function BuyersTab() {
  const queryClient = useQueryClient()
  const requests = useQuery({ queryKey: ['buyer-requests'], queryFn: getBuyerRequests })
  const [adding, setAdding] = useState(false)
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => toggleBuyerRequest(id, active),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['buyer-requests'] })
      queryClient.invalidateQueries({ queryKey: ['listings'] })
    },
  })
  const rows = requests.data?.requests ?? []

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => setAdding((a) => !a)}
          className="inline-flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-900 px-4 py-2.5 text-[13.5px] font-medium text-ink-100 hover:border-brand-500"
        >
          <UserPlus className="size-4" /> Add a buyer you know
        </button>
      </div>
      <AnimatePresence>
        {adding && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="panel p-5">
              <BuyerRequestForm
                submitLabel="Save buyer"
                onPosted={() => {
                  setAdding(false)
                  queryClient.invalidateQueries({ queryKey: ['buyer-requests'] })
                  queryClient.invalidateQueries({ queryKey: ['listings'] })
                }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {rows.length === 0 ? (
        <div className="panel flex flex-col items-center gap-2 px-6 py-12 text-center">
          <Users className="size-8 text-ink-500" strokeWidth={1.5} />
          <p className="font-display text-lg font-semibold">No buyers yet</p>
          <p className="max-w-sm text-[14px] text-ink-400">
            Add the artisans and scrap dealers you already work with, or share the public page so they post their needs.
          </p>
        </div>
      ) : (
        rows.map((r) => (
          <div key={r.id} className={clsx('panel flex flex-wrap items-center justify-between gap-4 p-4', !r.active && 'opacity-55')}>
            <div className="min-w-0">
              <p className="text-[14.5px] font-medium text-ink-50">
                {r.name}
                {r.organization && <span className="font-normal text-ink-400"> · {r.organization}</span>}
                <span className="ml-2 rounded-full bg-ink-800 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-400">
                  {r.kind === 'recycler' ? 'recycler' : 'reuse'}
                </span>
              </p>
              <p className="mt-0.5 text-[12.5px] text-ink-400">
                {r.governorate} · {needLine(r)} · since {fmtDate(r.created_at)}
              </p>
            </div>
            <div className="flex items-center gap-3">
              {r.active && (
                <span className="readout text-[12.5px] text-ink-300">
                  {r.match_count} match{r.match_count === 1 ? '' : 'es'}
                </span>
              )}
              <a
                href={`https://wa.me/${r.phone.replace('+', '')}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-[12.5px] font-medium text-reclaim-300 hover:underline"
              >
                <MessageCircle className="size-3.5" /> {r.phone}
              </a>
              <button
                type="button"
                onClick={() => toggle.mutate({ id: r.id, active: !r.active })}
                className="rounded-lg border border-ink-700 px-2.5 py-1 text-[12px] text-ink-300 hover:border-ink-500"
              >
                {r.active ? 'Pause' : 'Resume'}
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  )
}

type Tab = 'listings' | 'buyers' | 'recycling'

function tabFrom(search: string): Tab {
  const t = new URLSearchParams(search).get('tab')
  return t === 'buyers' || t === 'recycling' ? t : 'listings'
}

export function MarketPage() {
  const search = useSearch()
  const [, navigate] = useLocation()
  // The tab lives in the URL, so alert links can open any tab directly.
  const tab = tabFrom(search)
  const setTab = (t: Tab) => navigate(t === 'listings' ? '/market' : `/market?tab=${t}`, { replace: true })
  const data = useQuery({ queryKey: ['listings'], queryFn: getListings })
  const summary = data.data?.summary
  const listings = data.data?.listings ?? []
  const active = listings.filter((l) => l.status === 'open' || l.status === 'reserved')
  const closed = listings.filter((l) => l.status === 'sold' || l.status === 'withdrawn')

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 md:px-10 md:py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Marketplace</p>
          <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">Sell what you will not reuse</h1>
          <p className="mt-2 max-w-xl text-[15px] text-ink-400">
            Each listing is matched with buyers by material, size, price and distance. Contact them on WhatsApp in one
            tap.
          </p>
        </div>
        <a
          href="/buy"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-900 px-4 py-2.5 text-[13.5px] font-medium text-ink-100 hover:border-brand-500"
        >
          <ExternalLink className="size-4" /> Public page for buyers
        </a>
      </div>

      <div className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="panel-brand p-5">
          <p className="eyebrow !text-[10px] !text-ink-950/75">On sale</p>
          <p className="readout mt-2 text-[30px] leading-none text-reclaim-400">{fmtTnd(summary?.open_value_tnd ?? 0)}</p>
          <p className="mt-2 text-[12px] text-ink-950/80">{summary?.open ?? 0} open listings</p>
        </div>
        <div className="panel p-5">
          <p className="eyebrow !text-[10px]">Reserved</p>
          <p className="readout mt-2 text-[30px] leading-none text-ink-50">{summary?.reserved ?? 0}</p>
          <p className="mt-2 text-[12px] text-ink-500">Waiting for pickup</p>
        </div>
        <div className="panel p-5">
          <p className="eyebrow !text-[10px]">Sold</p>
          <p className="readout mt-2 text-[30px] leading-none text-ink-50">{fmtTnd(summary?.sales_tnd ?? 0)}</p>
          <p className="mt-2 text-[12px] text-ink-500">{summary?.sold ?? 0} deals · fees {fmtTnd(summary?.fees_tnd ?? 0, 2)}</p>
        </div>
        <div className="panel p-5">
          <p className="eyebrow !text-[10px]">Buyers looking</p>
          <p className="readout mt-2 text-[30px] leading-none text-ink-50">{summary?.active_requests ?? 0}</p>
          <p className="mt-2 text-[12px] text-ink-500">Active requests</p>
        </div>
      </div>

      <div className="mt-8 flex w-fit rounded-xl border border-ink-700 bg-ink-900 p-1">
        {([
          ['listings', `Listings${active.length ? ` · ${active.length}` : ''}`],
          ['buyers', 'Buyers'],
          ['recycling', 'Recycling'],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            className={clsx(
              'rounded-lg px-4 py-2 text-[13.5px] font-medium transition',
              tab === value ? 'bg-brand-500 text-ink-950' : 'text-ink-400 hover:text-ink-100',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === 'recycling' ? (
          <RecyclingTab />
        ) : tab === 'buyers' ? (
          <BuyersTab />
        ) : active.length === 0 && closed.length === 0 ? (
          <div className="panel flex flex-col items-center gap-2 px-6 py-14 text-center">
            <PackageOpen className="size-8 text-ink-500" strokeWidth={1.5} />
            <p className="font-display text-lg font-semibold">Nothing on sale yet</p>
            <p className="max-w-sm text-[14px] text-ink-400">
              From stock or a job review, use “List for sale” on a piece. The asking price starts at its sale value.
            </p>
            <Link href="/stock" className="mt-1 text-[14px] font-medium text-brand-500 hover:underline">
              Go to stock
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {active.map((l) => (
              <ListingCard key={l.id} listing={l} />
            ))}
            {closed.length > 0 && (
              <details className="panel p-5">
                <summary className="cursor-pointer text-[14px] font-medium text-ink-200">
                  Closed · {closed.length}
                </summary>
                <div className="mt-4 space-y-3">
                  {closed.map((l) => (
                    <ListingCard key={l.id} listing={l} />
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
