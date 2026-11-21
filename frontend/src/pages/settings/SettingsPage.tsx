import clsx from 'clsx'
import { useState } from 'react'
import { useSearch } from 'wouter'

import { PricesPage } from '../prices/PricesPage'
import { MachinesPanel } from './MachinesPanel'

const TABS = [
  ['machines', 'Machines'],
  ['prices', 'Price book'],
] as const

type Tab = (typeof TABS)[number][0]

export function SettingsPage() {
  const search = useSearch()
  const [tab, setTab] = useState<Tab>(new URLSearchParams(search).get('tab') === 'prices' ? 'prices' : 'machines')

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-8 md:px-10 md:py-12">
      <p className="eyebrow">Settings</p>
      <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">Your workshop</h1>
      <div className="mt-6 flex w-fit rounded-xl border border-ink-700 bg-ink-900 p-1">
        {TABS.map(([value, label]) => (
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
      <div className="mt-6">{tab === 'machines' ? <MachinesPanel /> : <PricesPage embedded />}</div>
    </div>
  )
}
