import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { AuthProvider } from './auth/AuthProvider'
import { GuestOnly, RequireAuth, RequireCompanyProfile } from './auth/RouteGuards'
import { AppLayout } from './components/AppLayout'
import { CompanyProfilePage } from './pages/CompanyProfilePage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { TenderDetailPage } from './pages/TenderDetailPage'
import { TendersPage } from './pages/TendersPage'
import { WorkspaceEntryPage } from './pages/WorkspaceEntryPage'
import { WorkspacePage } from './pages/WorkspacePage'
import { RegisterPage } from './pages/RegisterPage'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<GuestOnly />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Route>

          <Route element={<RequireAuth />}>
            <Route path="/onboarding" element={<OnboardingPage />} />

            <Route element={<RequireCompanyProfile />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/company-profile" element={<CompanyProfilePage />} />
                <Route path="/tenders" element={<TendersPage />} />
                <Route path="/tenders/:tenderId" element={<TenderDetailPage />} />
                <Route path="/workspace" element={<WorkspacePage />} />
                <Route path="/workspace/:entryId" element={<WorkspaceEntryPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
