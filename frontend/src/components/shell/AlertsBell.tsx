import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Bell } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'wouter'

import { getAlerts } from '../../lib/api'
import { t } from '../../lib/i18n'

/** The manager's to-do list, worked out by the server from the current state. */
export function AlertsBell({ placement = 'rail' }: { placement?: 'rail' | 'header' }) {
  const alerts = useQuery({ queryKey: ['alerts'], queryFn: getAlerts, refetchInterval: 30_000 })
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const list = alerts.data?.alerts ?? []

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={`${list.length} alerts`}
        aria-expanded={open}
        className="relative grid size-10 place-items-center rounded-xl text-ink-300 transition hover:bg-ink-850 hover:text-ink-50"
      >
        <Bell className="size-[19px]" strokeWidth={1.75} />
        {list.length > 0 && (
          <span className="readout absolute end-1 top-1 grid min-w-4 place-items-center rounded-full bg-brand-500 px-1 text-[10px] leading-4 text-ink-950">
            {list.length}
          </span>
        )}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            transition={{ duration: 0.15 }}
            className={clsx(
              'panel absolute z-50 w-80 p-2',
              placement === 'rail' ? 'bottom-0 start-12' : 'end-0 top-12',
            )}
          >
            <p className="px-3 pb-1 pt-2 text-[13px] font-semibold text-ink-100">{t('Needs your attention')}</p>
            {list.length === 0 ? (
              <p className="px-3 py-4 text-[13px] text-ink-400">{t('All clear.')}</p>
            ) : (
              <ul className="max-h-96 overflow-y-auto">
                {list.map((a, i) => (
                  <li key={i}>
                    <Link
                      href={a.link}
                      onClick={() => setOpen(false)}
                      className="block rounded-xl px-3 py-2.5 transition hover:bg-ink-850"
                    >
                      <p className="text-[13.5px] font-medium text-ink-50">{a.title}</p>
                      <p className="text-[12px] leading-snug text-ink-400">{a.detail}</p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
