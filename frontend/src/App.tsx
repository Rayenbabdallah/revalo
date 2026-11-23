import { FileBarChart, Layers, ScanLine, Settings, Store, Upload, Warehouse } from 'lucide-react'
import { Redirect, Route, Switch, useLocation } from 'wouter'

import { AuthGate } from './components/auth/AuthGate'
import { RequireRole } from './components/auth/RequireRole'
import { AppShell, type NavItem } from './components/shell/AppShell'
import type { Role } from './lib/api'
import { atLeast, useUser } from './lib/auth'
import { t } from './lib/i18n'
import { AnalyzePage } from './pages/analyze/AnalyzePage'
import { BuyPage } from './pages/buy/BuyPage'
import { JobReviewPage } from './pages/jobs/JobReviewPage'
import { JobsPage } from './pages/jobs/JobsPage'
import { LabelsPage } from './pages/jobs/LabelsPage'
import { LotPage } from './pages/market/LotPage'
import { MarketPage } from './pages/market/MarketPage'
import { PiecePage } from './pages/piece/PiecePage'
import { ReportPage } from './pages/report/ReportPage'
import { SettingsPage } from './pages/settings/SettingsPage'
import { FitPage } from './pages/stock/FitPage'
import { IntakePage } from './pages/stock/IntakePage'
import { StockPage } from './pages/stock/StockPage'
import { UploadPage } from './pages/upload/UploadPage'

const NAV: (NavItem & { min: Role })[] = [
  { id: '/upload', label: t('Upload'), icon: Upload, min: 'operator' },
  { id: '/analyze', label: t('Analyze'), icon: ScanLine, min: 'operator' },
  { id: '/jobs', label: t('Jobs'), icon: Layers, min: 'operator' },
  { id: '/stock', label: t('Stock'), icon: Warehouse, min: 'operator' },
  { id: '/market', label: t('Market'), icon: Store, min: 'manager' },
  { id: '/report', label: t('Report'), icon: FileBarChart, min: 'manager' },
  { id: '/settings', label: t('Settings'), icon: Settings, min: 'operator' },
]

/** The signed-in app: navigation and pages follow the person's role. */
function Workspace() {
  const [location, navigate] = useLocation()
  const user = useUser()
  const nav = NAV.filter((item) => atLeast(user.role, item.min))
  const active = nav.find((item) => location.startsWith(item.id))?.id ?? null

  return (
    <AppShell nav={nav} active={active} onNavigate={navigate}>
      <Switch>
        <Route path="/analyze" component={AnalyzePage} />
        <Route path="/jobs" component={JobsPage} />
        <Route path="/stock/fit" component={FitPage} />
        <Route path="/stock/add">
          <RequireRole min="manager">
            <IntakePage />
          </RequireRole>
        </Route>
        <Route path="/stock" component={StockPage} />
        <Route path="/market">
          <RequireRole min="manager">
            <MarketPage />
          </RequireRole>
        </Route>
        <Route path="/lots/:id">
          {(params) => (
            <RequireRole min="manager">
              <LotPage id={params.id} />
            </RequireRole>
          )}
        </Route>
        <Route path="/report">
          <RequireRole min="manager">
            <ReportPage />
          </RequireRole>
        </Route>
        <Route path="/upload" component={UploadPage} />
        <Route path="/settings" component={SettingsPage} />
        <Route path="/prices">
          <Redirect to="/settings?tab=prices" />
        </Route>
        <Route path="/jobs/:id/labels">{(params) => <LabelsPage id={params.id} />}</Route>
        <Route path="/jobs/:id">{(params) => <JobReviewPage id={params.id} />}</Route>
        <Route>
          <Redirect to={user.role === 'operator' ? '/upload' : '/analyze'} />
        </Route>
      </Switch>
    </AppShell>
  )
}

export default function App() {
  return (
    <Switch>
      {/* Public: what buyers see. */}
      <Route path="/buy" component={BuyPage} />
      {/* Opened from a QR label, often on a phone: no app chrome. */}
      <Route path="/p/:code">
        {(params) => (
          <AuthGate>
            <PiecePage code={params.code} />
          </AuthGate>
        )}
      </Route>
      <Route>
        <AuthGate>
          <Workspace />
        </AuthGate>
      </Route>
    </Switch>
  )
}
