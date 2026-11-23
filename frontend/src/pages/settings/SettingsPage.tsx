import clsx from 'clsx'
import { useLocation, useSearch } from 'wouter'

import type { Role } from '../../lib/api'
import { atLeast, useUser } from '../../lib/auth'
import { PricesPage } from '../prices/PricesPage'
import { AccountPanel } from './AccountPanel'
import { MachinesPanel } from './MachinesPanel'
import { TeamPanel } from './TeamPanel'
import { t } from '../../lib/i18n'

const TABS = [
  { id: 'machines', label: t('Machines'), min: 'manager' },
  { id: 'prices', label: t('Price book'), min: 'manager' },
  { id: 'team', label: t('Team'), min: 'owner' },
  { id: 'account', label: t('Account'), min: 'operator' },
] as const satisfies readonly { id: string; label: string; min: Role }[]

type Tab = (typeof TABS)[number]['id']

export function SettingsPage() {
  const user = useUser()
  const search = useSearch()
  const [, navigate] = useLocation()
  const tabs = TABS.filter((t) => atLeast(user.role, t.min))
  // The tab lives in the URL, so menus and alerts can link straight to it.
  const asked = new URLSearchParams(search).get('tab')
  const tab: Tab = tabs.find((t) => t.id === asked)?.id ?? tabs[0].id

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-8 md:px-10 md:py-12">
      <p className="eyebrow">{t('Settings')}</p>
      <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">{t('Your workshop')}</h1>
      {tabs.length > 1 && (
        <div className="mt-6 flex w-fit rounded-xl border border-ink-700 bg-ink-900 p-1">
          {tabs.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => navigate(`/settings?tab=${id}`, { replace: true })}
              className={clsx(
                'rounded-lg px-4 py-2 text-[13.5px] font-medium transition',
                tab === id ? 'bg-brand-500 text-ink-950' : 'text-ink-400 hover:text-ink-100',
              )}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="mt-6">
        {tab === 'machines' && <MachinesPanel />}
        {tab === 'prices' && <PricesPage embedded />}
        {tab === 'team' && <TeamPanel />}
        {tab === 'account' && <AccountPanel />}
      </div>
    </div>
  )
}
