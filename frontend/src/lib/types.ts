// Types mirroring the backend's response schemas (backend/app/schemas).

export type HealthResponse = {
  status: string
  app: string
  environment: string
}

export type TokenResponse = {
  access_token: string
  token_type: string
}

export type Plan = 'free' | 'basic' | 'pro'
export type UserRole = 'owner' | 'member'

export type Team = {
  id: number
  name: string
  plan: Plan
  created_at: string
}

export type User = {
  id: number
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export type CurrentUser = User & {
  team: Team
}

export type RegisterData = {
  company_name: string
  full_name: string
  email: string
  password: string
}

export type MemberCreateData = {
  full_name: string
  email: string
  password: string
}
