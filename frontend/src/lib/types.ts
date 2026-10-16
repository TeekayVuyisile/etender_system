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

export type TenderDocument = {
  id: string | null
  title: string
  url: string
  format: string | null
}

export type TenderListItem = {
  id: number
  tender_number: string
  title: string
  buyer_name: string
  province: string | null
  category: string | null
  procurement_category: string | null
  procurement_method: string | null
  published_at: string | null
  closing_at: string | null
  estimated_value: number | null
  briefing_compulsory: boolean
  document_count: number
}

export type TenderDetail = TenderListItem & {
  documents: TenderDocument[]
  ocid: string
  etenders_id: number
  province_source: string | null
  delivery_location: string | null
  briefing_session: boolean
  briefing_at: string | null
  briefing_venue: string | null
  special_conditions: string | null
  contact_person: string | null
  contact_email: string | null
  contact_phone: string | null
  updated_at: string
}

export type TenderSearchResponse = {
  items: TenderListItem[]
  total: number
  page: number
  page_size: number
  province_counts: Record<string, number>
}

export type BuyerOption = {
  name: string
  open_tenders: number
}
