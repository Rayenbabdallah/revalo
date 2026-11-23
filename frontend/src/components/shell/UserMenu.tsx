import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { KeyRound, LogOut, Users } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'wouter'

import { signOut, type Me } from '../../lib/api'
import { ROLE_LABEL, useUser } from '../../lib/auth'

function initials(name: string) {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

/** Who is signed in, with their account and sign-out. */
export function UserMenu({ placement = 'rail' }: { placement?: 'rail' | 'header' }) {
  const user = useUser()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const leave = async () => {
    try {
      await signOut()
    } finally {
      const me = queryClient.getQueryData<Me>(['me'])
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
      if (me) queryClient.setQueryData<Me>(['me'], { ...me, user: null })
      else queryClient.invalidateQueries({ queryKey: ['me'] })
    }
  }

  const item = 'flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-[13.5px] text-ink-200 transition hover:bg-ink-850'

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={`Account: ${user.name}`}
        aria-expanded={open}
        className="grid size-9 place-items-center rounded-full bg-brand-500 font-display text-[12.5px] font-semibold text-ink-950 ring-2 ring-transparent transition hover:ring-brand-500/30"
      >
        {initials(user.name)}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            transition={{ duration: 0.15 }}
            className={clsx(
              'panel absolute z-50 w-64 p-2',
              placement === 'rail' ? 'bottom-0 start-12' : 'end-0 top-12',
            )}
          >
            <div className="px-3 pb-2 pt-2">
              <p className="truncate text-[14px] font-semibold text-ink-50">{user.name}</p>
              <p className="truncate text-[12px] text-ink-400">{user.email}</p>
              <span className="eyebrow mt-2 inline-block rounded-md bg-ink-850 px-2 py-0.5 !text-[10px]">
                {ROLE_LABEL[user.role]}
              </span>
            </div>
            <div className="border-t border-ink-800 pt-1">
              <Link href="/settings?tab=account" onClick={() => setOpen(false)} className={item}>
                <KeyRound className="size-4 text-ink-400" /> Account and password
              </Link>
              {user.role === 'owner' && (
                <Link href="/settings?tab=team" onClick={() => setOpen(false)} className={item}>
                  <Users className="size-4 text-ink-400" /> Team
                </Link>
              )}
              <button type="button" onClick={leave} className={clsx(item, 'w-full')}>
                <LogOut className="size-4 text-ink-400" /> Sign out
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
