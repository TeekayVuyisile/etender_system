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

export type CidbGrading = {
  class_code: string
  grade: number
}

export type CompanyProfileInput = {
  industry_sector: string
  services: string[]
  cidb_gradings: CidbGrading[]
  bbbee_level: number | null
  certifications: string[]
  provinces: string[]
  years_of_experience: number
  contact_name: string
  contact_email: string
  contact_phone: string
  website: string | null
  physical_address: string | null
}

export type CompanyProfile = CompanyProfileInput & {
  id: number
  team_id: number
  created_at: string
  updated_at: string
}

export type Option = {
  value: string
  label: string
}

export type ProfileOptions = {
  industry_sectors: string[]
  provinces: string[]
  cidb_classes: Option[]
  cidb_grades: number[]
  bbbee_levels: number[]
  certification_suggestions: string[]
}
