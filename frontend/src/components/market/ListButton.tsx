import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Store } from 'lucide-react'
import { Link } from 'wouter'

import { createListing, type Piece } from '../../lib/api'
import { fmtTnd } from '../../lib/format'
import { t } from '../../lib/i18n'

/** Put an in-stock piece on the marketplace at its suggested price, or show where it is. */
export function ListButton({ piece, className }: { piece: Piece; className?: string }) {
  const queryClient = useQueryClient()
  const list = useMutation({
    mutationFn: () => createListing(piece.id),
    onSuccess: () => {
      for (const key of ['job', 'jobs', 'stock', 'listings']) queryClient.invalidateQueries({ queryKey: [key] })
    },
  })

  const active = piece.listing && (piece.listing.status === 'open' || piece.listing.status === 'reserved')
  if (active) {
    return (
      <Link
        href="/market"
        className={clsx('inline-flex items-center gap-1.5 text-[12.5px] font-medium text-brand-500 hover:underline', className)}
      >
        <Store className="size-3.5" />
        {piece.listing!.status === 'reserved' ? t('Reserved') : t('Listed')} · {fmtTnd(piece.listing!.price_tnd)}
      </Link>
    )
  }
  if (piece.status !== 'in_stock') return null
  return (
    <span className={clsx('inline-flex flex-col items-start', className)}>
      <button
        type="button"
        onClick={() => list.mutate()}
        disabled={list.isPending}
        className="inline-flex items-center gap-1.5 rounded-lg border border-brand-500/40 px-2.5 py-1 text-[12.5px] font-medium text-brand-500 transition hover:bg-brand-500 hover:text-ink-950 disabled:opacity-60"
      >
        <Store className="size-3.5" /> {list.isPending ? t('Listing…') : t('List for sale')}
      </button>
      {list.isError && <span className="mt-1 text-[11.5px] text-alarm-400">{list.error.message}</span>}
    </span>
  )
}
