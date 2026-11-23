import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Bookmark, CheckCircle2, MapPin, MessageCircle, PackagePlus, ShoppingCart } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { Link } from 'wouter'

import { SupplyOfferForm } from '../../components/market/SupplyOfferForm'
import { actOnSupplyOffer, getSupplyOffers, type SupplyOffer } from '../../lib/api'
import { fmtDate, fmtKg, fmtMm, fmtTnd, materialLabel } from '../../lib/format'
import { t } from '../../lib/i18n'

function invalidate(queryClient: ReturnType<typeof useQueryClient>) {
  for (const key of ['supply-offers', 'stock', 'jobs', 'alerts']) queryClient.invalidateQueries({ queryKey: [key] })
}

function OfferCard({ offer }: { offer: SupplyOffer }) {
  const queryClient = useQueryClient()
  const [price, setPrice] = useState(String(offer.price_tnd))
  const act = useMutation({
    mutationFn: (body: Parameters<typeof actOnSupplyOffer>[1]) => actOnSupplyOffer(offer.id, body),
    onSuccess: () => invalidate(queryClient),
  })
  const open = offer.status === 'open'
  const worth = offer.saving_tnd !== null && offer.saving_tnd > 0
  const seller = offer.organization ?? offer.seller_name

  return (
    <article className={clsx('panel p-5', offer.status === 'declined' && 'opacity-60')}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[13px] text-ink-400">
            <span className="font-medium text-ink-100">{seller}</span>
            {offer.organization && ` · ${offer.seller_name}`}
            <span className="ms-2 inline-flex items-center gap-1">
              <MapPin className="size-3" /> {offer.governorate}
              {offer.distance_km !== null && ` · ${Math.round(offer.distance_km)} km`}
            </span>
          </p>
          <p className="mt-2 font-display text-[17px] font-semibold text-ink-50">
            {offer.quantity} × {fmtMm(offer.width_mm)} × {fmtMm(offer.height_mm)} mm · {materialLabel(offer.material_code)} {offer.thickness_mm} mm
          </p>
          <p className="readout mt-0.5 text-[12px] text-ink-400">
            {fmtKg(offer.weight_kg)} kg
            {offer.price_tnd_per_kg !== null && ` · ${offer.price_tnd_per_kg} TND/kg`}
            {' · '}
            {t('since {date}', { date: fmtDate(offer.created_at) })}
            {offer.source === 'workshop' && ` · ${t('entered by the workshop')}`}
          </p>
          {offer.note && <p className="mt-1 text-[12.5px] text-ink-300">{offer.note}</p>}
        </div>
        <div className="text-end">
          <p className="readout text-[22px] leading-none text-ink-50">{fmtTnd(offer.bought_price_tnd ?? offer.price_tnd)}</p>
          {offer.new_tnd !== null && (
            <p className={clsx('mt-1.5 text-[12.5px]', worth ? 'text-reclaim-600' : 'text-ink-400')}>
              {worth
                ? t('{amount} less than new', { amount: fmtTnd(offer.saving_tnd ?? 0) })
                : t('New costs {amount}', { amount: fmtTnd(offer.new_tnd) })}
            </p>
          )}
        </div>
      </header>

      {open && (offer.planned?.length ?? 0) > 0 && (
        <div className="mt-4 space-y-1.5 rounded-xl bg-reclaim-400/10 p-3">
          {offer.planned!.map((p) => (
            <p key={p.id} className="flex items-center gap-2 text-[13.5px] text-ink-100">
              <Bookmark className="size-4 shrink-0 text-reclaim-600" />
              {t('Holds {extra} parts of {name} that your racks cannot ({placed} of {total} covered).', {
                extra: p.extra_parts,
                name: p.name,
                placed: p.placed,
                total: p.total,
              })}
            </p>
          ))}
        </div>
      )}

      {open && (
        <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
          <a
            href={offer.whatsapp_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 px-3 py-2 text-[13px] font-medium text-reclaim-300 hover:border-reclaim-400"
          >
            <MessageCircle className="size-4" /> {t('Ask the seller')}
          </a>
          <button
            type="button"
            onClick={() => act.mutate({ action: 'decline' })}
            className="rounded-lg px-3 py-2 text-[13px] text-ink-400 hover:text-alarm-400"
          >
            {t('Decline')}
          </button>
          <label className="flex items-center gap-2">
            <input
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              inputMode="decimal"
              aria-label={t('Price paid')}
              className="readout w-20 rounded-lg border border-ink-700 bg-ink-900 px-2.5 py-1.5 text-end text-[15px] text-ink-50 focus:border-brand-500 focus:outline-none"
            />
            <span className="text-[13px] text-ink-400">TND</span>
          </label>
          <button
            type="button"
            disabled={act.isPending}
            onClick={() => act.mutate({ action: 'buy', price_tnd: Number(price.replace(',', '.')) || undefined })}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-[13.5px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60"
          >
            <ShoppingCart className="size-4" /> {t('Bought, add to stock')}
          </button>
        </div>
      )}

      {offer.status === 'bought' && (
        <p className="mt-4 flex flex-wrap items-center gap-2 text-[13.5px] text-ink-200">
          <CheckCircle2 className="size-4 text-reclaim-600" />
          {t('Bought by {name}, in stock with labels to print.', { name: offer.closed_by ?? '' })}
          {offer.intake_job_id && (
            <Link href={`/jobs/${offer.intake_job_id}/labels`} className="font-medium text-brand-500 hover:underline">
              {t('Print labels')}
            </Link>
          )}
        </p>
      )}
      {offer.status === 'declined' && (
        <div className="mt-3 flex justify-end">
          <button type="button" onClick={() => act.mutate({ action: 'reopen' })} className="text-[12.5px] text-ink-400 hover:text-brand-500">
            {t('Reopen')}
          </button>
        </div>
      )}
      {act.isError && <p className="mt-2 text-[12.5px] text-alarm-400">{act.error.message}</p>}
    </article>
  )
}

/** Offcuts others offer to sell to us, valued against new material and checked against coming jobs. */
export function BuyingTab() {
  const queryClient = useQueryClient()
  const data = useQuery({ queryKey: ['supply-offers'], queryFn: getSupplyOffers })
  const [adding, setAdding] = useState(false)
  const offers = data.data?.offers ?? []
  const summary = data.data?.summary
  // Offers that would hold a coming job first, then the biggest saving.
  const open = offers
    .filter((o) => o.status === 'open')
    .sort((a, b) => (b.planned?.length ?? 0) - (a.planned?.length ?? 0) || (b.saving_tnd ?? -1e9) - (a.saving_tnd ?? -1e9))
  const closed = offers.filter((o) => o.status !== 'open')

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-[14px] leading-relaxed text-ink-400">
          {t('Other workshops and suppliers offer their offcuts here, from the public page or through you. Each offer is compared with new material and with your coming jobs.')}
        </p>
        <button
          type="button"
          onClick={() => setAdding((a) => !a)}
          className="inline-flex items-center gap-2 rounded-xl border border-ink-700 bg-ink-900 px-4 py-2.5 text-[13.5px] font-medium text-ink-100 hover:border-brand-500"
        >
          <PackagePlus className="size-4" /> {t('Record an offer you received')}
        </button>
      </div>

      {summary && summary.bought > 0 && (
        <p className="text-[13px] text-ink-300">
          {t('{count} offer bought|{count} offers bought', { count: summary.bought })} · {t('spent {amount}', { amount: fmtTnd(summary.spent_tnd) })} ·{' '}
          <span className="font-medium text-reclaim-600">{t('{amount} saved against new', { amount: fmtTnd(summary.saved_tnd) })}</span>
        </p>
      )}

      <AnimatePresence>
        {adding && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="panel p-5">
              <SupplyOfferForm
                submitLabel={t('Save offer')}
                onPosted={() => {
                  setAdding(false)
                  invalidate(queryClient)
                }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {open.length === 0 ? (
        <div className="panel flex flex-col items-center gap-2 px-6 py-12 text-center">
          <ShoppingCart className="size-8 text-ink-500" strokeWidth={1.5} />
          <p className="font-display text-lg font-semibold">{t('No offers to buy right now')}</p>
          <p className="max-w-sm text-[14px] text-ink-400">
            {t('Share the public page with workshops nearby: they can offer you their offcuts there.')}
          </p>
        </div>
      ) : (
        open.map((o) => <OfferCard key={o.id} offer={o} />)
      )}

      {closed.length > 0 && (
        <details className="panel p-5">
          <summary className="cursor-pointer text-[14px] font-medium text-ink-200">
            {t('Closed')} · {closed.length}
          </summary>
          <div className="mt-4 space-y-3">
            {closed.map((o) => (
              <OfferCard key={o.id} offer={o} />
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
