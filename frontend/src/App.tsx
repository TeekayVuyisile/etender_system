import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { AuthProvider } from './auth/AuthProvider'
import { GuestOnly, RequireAuth, RequireCompanyProfile } from './auth/RouteGuards'
import { AppLayout } from './components/AppLayout'
import { CompanyProfilePage } from './pages/CompanyProfilePage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { OnboardingPage } from './pages/OnboardingPage'
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
