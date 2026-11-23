import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { getHealth } from '../../lib/api'
import { LogoMark, Wordmark } from '../brand/Logo'
import { AlertsBell } from './AlertsBell'
import { UserMenu } from './UserMenu'
import { t } from '../../lib/i18n'

export interface NavItem {
  id: string
  label: string
  icon: LucideIcon
}

interface AppShellProps {
  nav: NavItem[]
  active: string | null
  onNavigate: (id: string) => void
  children: ReactNode
}

function ServerStatus({ compact = false }: { compact?: boolean }) {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, refetchInterval: 15_000 })
  const online = health.isSuccess
  const label = health.isPending ? t('Connecting') : online ? t('Engine online') : t('Engine offline')
  return (
    <div className="flex items-center gap-2" title={label}>
      <span className="relative flex size-2">
        {online && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-reclaim-400 opacity-50" />
        )}
        <span
          className={clsx(
            'relative inline-flex size-2 rounded-full',
            online ? 'bg-reclaim-400' : health.isPending ? 'bg-ink-400' : 'bg-alarm-400',
          )}
        />
      </span>
      {!compact && <span className="eyebrow !tracking-[0.12em]">{label}</span>}
    </div>
  )
}

export function AppShell({ nav, active, onNavigate, children }: AppShellProps) {
  return (
    <div className="flex min-h-full">
      {/* Side rail on wide screens */}
      <aside className="sticky top-0 hidden h-screen w-[76px] shrink-0 flex-col items-center border-e border-ink-800/80 bg-ink-900/85 py-5 backdrop-blur-xl md:flex">
        <LogoMark className="size-8" />
        <nav className="mt-10 flex flex-1 flex-col items-center gap-2">
          {nav.map((item) => {
            const Icon = item.icon
            const isActive = item.id === active
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className={clsx(
                  'group relative flex w-14 flex-col items-center gap-1 rounded-xl py-2.5 transition-colors',
                  isActive
                    ? 'bg-ink-800 text-ink-50'
                    : 'text-ink-400 hover:bg-ink-900 hover:text-ink-100',
                )}
              >
                {isActive && (
                  <span className="absolute -start-[11px] top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-e bg-brand-500 shadow-[0_0_12px_rgb(25_74_203_/_0.8)]" />
                )}
                <Icon className="size-[19px]" strokeWidth={1.75} />
                <span className="text-[10px] font-medium">{item.label}</span>
              </button>
            )
          })}
        </nav>
        <AlertsBell />
        <div className="mt-3">
          <UserMenu />
        </div>
        <div className="mt-4">
          <ServerStatus compact />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar on small screens */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-800/80 bg-ink-950/70 px-4 py-3 backdrop-blur-xl md:hidden">
          <Wordmark />
          <div className="flex items-center gap-2">
            <ServerStatus compact />
            <AlertsBell placement="header" />
            <UserMenu placement="header" />
          </div>
        </header>

        <main className="flex-1 pb-24 md:pb-0">{children}</main>

        {/* Bottom tabs on small screens */}
        <nav className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t border-ink-800 bg-ink-950/90 px-2 pb-[max(env(safe-area-inset-bottom),8px)] pt-2 backdrop-blur-xl md:hidden">
          {nav.map((item) => {
            const Icon = item.icon
            const isActive = item.id === active
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className={clsx(
                  'flex min-w-0 flex-1 flex-col items-center gap-1 rounded-lg px-1 py-1.5',
                  isActive ? 'text-brand-400' : 'text-ink-400',
                )}
              >
                <Icon className="size-5" strokeWidth={1.75} />
                <span className="truncate text-[10.5px] font-medium">{item.label}</span>
              </button>
            )
          })}
        </nav>
      </div>
    </div>
  )
}
