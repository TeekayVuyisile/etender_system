import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { AuthProvider } from './auth/AuthProvider'
import { GuestOnly, RequireAuth, RequireCompanyProfile } from './auth/RouteGuards'
import { AppLayout } from './components/AppLayout'
import { ServerWakeNotice } from './components/ServerWakeNotice'
import { useHealth } from './lib/health'
import { ApiAccessPage } from './pages/ApiAccessPage'
import { CompanyProfilePage } from './pages/CompanyProfilePage'
import { DashboardPage } from './pages/DashboardPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { PlanPage } from './pages/PlanPage'
import { TenderDetailPage } from './pages/TenderDetailPage'
import { TendersPage } from './pages/TendersPage'
import { WorkspaceEntryPage } from './pages/WorkspaceEntryPage'
import { WorkspacePage } from './pages/WorkspacePage'
import { RegisterPage } from './pages/RegisterPage'

// Pings the API as soon as any page opens. On free hosting this starts waking a sleeping
// server while the visitor is still reading the landing page, and the request is tracked,
// so ServerWakeNotice explains the wait if it's slow. Shares its cache with ApiStatus.
function WakeServer() {
  useHealth()
  return null
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<GuestOnly />}>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Route>

          <Route element={<RequireAuth />}>
            <Route path="/onboarding" element={<OnboardingPage />} />

            <Route element={<RequireCompanyProfile />}>
              <Route element={<AppLayout />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/company-profile" element={<CompanyProfilePage />} />
                <Route path="/plan" element={<PlanPage />} />
                <Route path="/developers" element={<ApiAccessPage />} />
                <Route path="/tenders" element={<TendersPage />} />
                <Route path="/tenders/:tenderId" element={<TenderDetailPage />} />
                <Route path="/workspace" element={<WorkspacePage />} />
                <Route path="/workspace/:entryId" element={<WorkspaceEntryPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <WakeServer />
        <ServerWakeNotice />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
