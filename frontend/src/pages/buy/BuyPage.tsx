import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, MapPin, MessageCircle } from 'lucide-react'
import { motion } from 'motion/react'
import { useState } from 'react'

import { Wordmark } from '../../components/brand/Logo'
import { BuyerRequestForm } from '../../components/market/BuyerRequestForm'
import { getMarket, type PublicListing } from '../../lib/api'
import { fmtKg, fmtMm, fmtTnd } from '../../lib/format'

function ListingTile({ listing, index }: { listing: PublicListing; index: number }) {
  const p = listing.piece
  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.04, 0.4) }}
      className="panel flex flex-col p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-[17px] font-semibold text-ink-50">
            {p.material_name?.en ?? 'Material'}
            {p.thickness_mm ? ` · ${p.thickness_mm} mm` : ''}
          </p>
          <p className="readout mt-1 text-[15px] text-ink-200">
            {p.kind === 'remnant' ? `${fmtMm(p.width_mm ?? 0)} × ${fmtMm(p.height_mm ?? 0)} mm` : 'Scrap lot'}
          </p>
        </div>
        <span className="readout rounded-lg bg-brand-500 px-2.5 py-1.5 text-[15px] text-ink-950">{fmtTnd(listing.price_tnd)}</span>
      </div>
      <p className="readout mt-3 text-[12.5px] text-ink-400">
        {fmtKg(p.weight_kg)} kg
        {listing.price_tnd_per_kg !== null && ` · ${listing.price_tnd_per_kg} TND/kg`}
      </p>
      {p.condition_note && <p className="mt-1 text-[12.5px] text-ink-400">{p.condition_note}</p>}
      <div className="mt-auto flex items-center justify-between gap-3 pt-4">
        <span className="flex items-center gap-1 text-[12.5px] text-ink-400">
          <MapPin className="size-3.5" /> {listing.governorate ?? 'Tunisia'}
        </span>
        {listing.contact_url ? (
          <a
            href={listing.contact_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg bg-reclaim-400 px-3 py-2 text-[13px] font-semibold text-ink-50 transition hover:bg-reclaim-500"
          >
            <MessageCircle className="size-4" /> Contact
          </a>
        ) : (
          <span className="readout text-[11.5px] text-ink-500">{p.code}</span>
        )}
      </div>
    </motion.article>
  )
}

/** The public side of the marketplace: what is on offer, and a way to say what you need. */
export function BuyPage() {
  const market = useQuery({ queryKey: ['market'], queryFn: getMarket })
  const [posted, setPosted] = useState<PublicListing[] | null>(null)
  const listings = market.data?.listings ?? []

  return (
    <div className="mx-auto min-h-full max-w-[1180px] px-4 py-6 md:px-8">
      <header className="flex items-center justify-between">
        <Wordmark className="h-8" />
        <span className="font-mono text-[11px] text-ink-500">offcuts marketplace</span>
      </header>

      <section className="panel-brand relative mt-6 overflow-hidden p-7 md:p-10">
        <div aria-hidden className="pointer-events-none absolute -right-20 -top-24 size-72 rounded-full bg-reclaim-400/25 blur-3xl" />
        <p className="eyebrow !text-ink-950/75">From workshops near you</p>
        <h1 className="mt-3 max-w-2xl font-display text-[34px] font-semibold leading-[1.08] md:text-[48px]">
          Measured offcuts, <span className="text-reclaim-400">ready to use.</span>
        </h1>
        <p className="mt-4 max-w-xl text-[15.5px] leading-relaxed text-ink-950/85">
          Steel, stainless, aluminium and wood panels left over from CNC jobs. Every piece is measured from the cut file
          and checked by the workshop, so the size and weight are right.
        </p>
      </section>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_400px]">
        <section>
          <h2 className="font-display text-xl font-semibold">On offer now</h2>
          {market.isPending ? (
            <p className="mt-4 font-mono text-sm text-ink-500">Loading…</p>
          ) : listings.length === 0 ? (
            <p className="panel mt-4 px-6 py-10 text-center text-[14px] text-ink-400">
              Nothing on offer right now. Post what you need and the workshop will contact you.
            </p>
          ) : (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {listings.map((l, i) => (
                <ListingTile key={l.id} listing={l} index={i} />
              ))}
            </div>
          )}
        </section>

        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="panel p-5">
            {posted === null ? (
              <>
                <h2 className="font-display text-xl font-semibold">Tell us what you need</h2>
                <p className="mb-4 mt-1 text-[13.5px] text-ink-400">
                  We match your request with new offcuts as they come off the machines.
                </p>
                <BuyerRequestForm onPosted={setPosted} />
              </>
            ) : (
              <div className="py-4 text-center">
                <CheckCircle2 className="mx-auto size-10 text-reclaim-400" />
                <p className="mt-3 font-display text-xl font-semibold">Request saved</p>
                <p className="mt-1 text-[14px] text-ink-400">
                  {posted.length
                    ? `${posted.length} piece${posted.length === 1 ? '' : 's'} on offer already match${posted.length === 1 ? 'es' : ''} it.`
                    : 'Nothing matches yet. The workshop will contact you on WhatsApp when it does.'}
                </p>
                <button type="button" onClick={() => setPosted(null)} className="mt-4 text-[13.5px] font-medium text-brand-500 hover:underline">
                  Post another request
                </button>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
