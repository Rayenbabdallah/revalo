import { ScanLine } from 'lucide-react'
import { useState } from 'react'

import { AppShell, type NavItem } from './components/shell/AppShell'

const NAV: NavItem[] = [{ id: 'analyze', label: 'Analyze', icon: ScanLine }]

export default function App() {
  const [page, setPage] = useState('analyze')
  return (
    <AppShell nav={NAV} active={page} onNavigate={setPage}>
      <div className="mx-auto max-w-[1480px] px-4 py-8 md:px-10">
        <p className="eyebrow">Leftover engine</p>
        <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">Analyze a job</h1>
      </div>
    </AppShell>
  )
}
