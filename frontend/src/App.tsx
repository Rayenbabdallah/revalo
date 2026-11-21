import { Coins, Layers, ScanLine, Store, Warehouse } from 'lucide-react'
import { Redirect, Route, Switch, useLocation } from 'wouter'

import { AppShell, type NavItem } from './components/shell/AppShell'
import { AnalyzePage } from './pages/analyze/AnalyzePage'
import { BuyPage } from './pages/buy/BuyPage'
import { JobReviewPage } from './pages/jobs/JobReviewPage'
import { JobsPage } from './pages/jobs/JobsPage'
import { LabelsPage } from './pages/jobs/LabelsPage'
import { MarketPage } from './pages/market/MarketPage'
import { PiecePage } from './pages/piece/PiecePage'
import { PricesPage } from './pages/prices/PricesPage'
import { StockPage } from './pages/stock/StockPage'

const NAV: NavItem[] = [
  { id: '/analyze', label: 'Analyze', icon: ScanLine },
  { id: '/jobs', label: 'Jobs', icon: Layers },
  { id: '/stock', label: 'Stock', icon: Warehouse },
  { id: '/market', label: 'Market', icon: Store },
  { id: '/prices', label: 'Prices', icon: Coins },
]

export default function App() {
  const [location, navigate] = useLocation()
  const active = NAV.find((item) => location.startsWith(item.id))?.id ?? null

  return (
    <Switch>
      {/* Opened from a QR label, often on a phone: no app chrome. */}
      <Route path="/p/:code">{(params) => <PiecePage code={params.code} />}</Route>
      <Route path="/buy" component={BuyPage} />
      <Route>
        <AppShell nav={NAV} active={active} onNavigate={navigate}>
          <Switch>
            <Route path="/analyze" component={AnalyzePage} />
            <Route path="/jobs" component={JobsPage} />
            <Route path="/stock" component={StockPage} />
            <Route path="/market" component={MarketPage} />
            <Route path="/prices" component={PricesPage} />
            <Route path="/jobs/:id/labels">{(params) => <LabelsPage id={params.id} />}</Route>
            <Route path="/jobs/:id">{(params) => <JobReviewPage id={params.id} />}</Route>
            <Route>
              <Redirect to="/analyze" />
            </Route>
          </Switch>
        </AppShell>
      </Route>
    </Switch>
  )
}
