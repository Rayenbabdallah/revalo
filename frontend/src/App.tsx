import { ScanLine } from 'lucide-react'
import { useState } from 'react'

import { AppShell, type NavItem } from './components/shell/AppShell'
import { AnalyzePage } from './pages/analyze/AnalyzePage'

const NAV: NavItem[] = [{ id: 'analyze', label: 'Analyze', icon: ScanLine }]

export default function App() {
  const [page, setPage] = useState('analyze')
  return (
    <AppShell nav={NAV} active={page} onNavigate={setPage}>
      {page === 'analyze' && <AnalyzePage />}
    </AppShell>
  )
}
