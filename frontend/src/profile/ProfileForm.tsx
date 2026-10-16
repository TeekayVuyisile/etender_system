import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, type ReactNode, useState } from 'react'

import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { CheckboxGroup } from '../components/ui/CheckboxGroup'
import { Select } from '../components/ui/Select'
import { Spinner } from '../components/ui/Spinner'
import { TagInput } from '../components/ui/TagInput'
import { TextField } from '../components/ui/TextField'
import { apiRequest, getErrorMessage } from '../lib/api'
import type {
  CidbGrading,
  CompanyProfile,
  CompanyProfileInput,
  CurrentUser,
  ProfileOptions,
} from '../lib/types'
import { companyProfileKey, useProfileOptions } from './queries'

// Number fields are kept as strings while editing, so inputs can be temporarily empty.
type FormState = Omit<
  CompanyProfileInput,
  'years_of_experience' | 'bbbee_level' | 'website' | 'physical_address'
> & {
  years_of_experience: string
  bbbee_level: string
  website: string
  physical_address: string
}

function toFormState(profile: CompanyProfile | null, user: CurrentUser): FormState {
  if (!profile) {
    return {
      industry_sector: '',
      services: [],
      cidb_gradings: [],
      bbbee_level: '',
      certifications: [],
      provinces: [],
      years_of_experience: '',
      contact_name: user.full_name,
      contact_email: user.email,
      contact_phone: '',
      website: '',
      physical_address: '',
    }
  }
  return {
    ...profile,
    years_of_experience: String(profile.years_of_experience),
    bbbee_level: profile.bbbee_level === null ? '' : String(profile.bbbee_level),
    website: profile.website ?? '',
    physical_address: profile.physical_address ?? '',
  }
}

function toInput(form: FormState): CompanyProfileInput {
  return {
    ...form,
    years_of_experience: Number(form.years_of_experience),
    bbbee_level: form.bbbee_level === '' ? null : Number(form.bbbee_level),
    website: form.website.trim() || null,
    physical_address: form.physical_address.trim() || null,
  }
}

type ProfileFormProps = {
  user: CurrentUser
  profile: CompanyProfile | null
  submitLabel: string
  onSaved: () => void
  onCancel?: () => void
}

export function ProfileForm(props: ProfileFormProps) {
  const optionsQuery = useProfileOptions()

  if (optionsQuery.isPending) {
    return <Spinner />
  }
  if (optionsQuery.isError) {
    return <ErrorAlert message={getErrorMessage(optionsQuery.error)} />
  }
  return <ProfileFormFields {...props} options={optionsQuery.data} />
}

function ProfileFormFields({
  user,
  profile,
  submitLabel,
  onSaved,
  onCancel,
  options,
}: ProfileFormProps & { options: ProfileOptions }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<FormState>(() => toFormState(profile, user))
  const [validationError, setValidationError] = useState<string | null>(null)

  const saveProfile = useMutation({
    mutationFn: (input: CompanyProfileInput) =>
      apiRequest<CompanyProfile>('/company-profile', { method: 'PUT', json: input }),
    onSuccess: (saved) => {
      queryClient.setQueryData(companyProfileKey, saved)
      onSaved()
    },
  })

  function update<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (form.services.length === 0) {
      setValidationError('Add at least one service your company provides.')
      return
    }
    if (form.provinces.length === 0) {
      setValidationError('Select at least one province you operate in.')
      return
    }
    setValidationError(null)
    saveProfile.mutate(toInput(form))
  }

  const suggested = options.certification_suggestions
  const selectedSuggestions = form.certifications.filter((c) => suggested.includes(c))
  const customCertifications = form.certifications.filter((c) => !suggested.includes(c))
  const errorMessage =
    validationError ?? (saveProfile.isError ? getErrorMessage(saveProfile.error) : null)

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      <FormSection title="Business details" description="What your company does.">
        <Select
          label="Industry sector"
          required
          placeholder="Select a sector"
          options={options.industry_sectors.map((s) => ({ value: s, label: s }))}
          value={form.industry_sector}
          onChange={(e) => update('industry_sector', e.target.value)}
        />
        <TagInput
          label="Services provided"
          values={form.services}
          onChange={(values) => update('services', values)}
          placeholder="e.g. Road construction, Paving"
          hint="Press Enter after each service. These are matched against tender descriptions."
        />
        <TextField
          label="Years of experience"
          type="number"
          required
          min={0}
          max={150}
          value={form.years_of_experience}
          onChange={(e) => update('years_of_experience', e.target.value)}
        />
      </FormSection>

      <FormSection
        title="Compliance and certifications"
        description="Tenders often set minimum CIDB grades and B-BBEE levels."
      >
        <CidbEditor
          gradings={form.cidb_gradings}
          onChange={(gradings) => update('cidb_gradings', gradings)}
          options={options}
        />
        <Select
          label="B-BBEE level"
          options={options.bbbee_levels.map((level) => ({
            value: String(level),
            label: `Level ${level}`,
          }))}
          placeholder="Not rated / non-compliant"
          value={form.bbbee_level}
          onChange={(e) => update('bbbee_level', e.target.value)}
        />
        <CheckboxGroup
          legend="Certifications and registrations"
          options={suggested}
          selected={selectedSuggestions}
          onChange={(values) => update('certifications', [...values, ...customCertifications])}
        />
        <TagInput
          label="Other certifications"
          values={customCertifications}
          onChange={(values) => update('certifications', [...selectedSuggestions, ...values])}
          placeholder="e.g. NHBRC Registration"
        />
      </FormSection>

      <FormSection title="Geographic coverage" description="Provinces where you can deliver work.">
        <CheckboxGroup
          legend="Provinces"
          options={options.provinces}
          selected={form.provinces}
          onChange={(values) => update('provinces', values)}
          showSelectAll
        />
      </FormSection>

      <FormSection title="Contact details" description="Who buyers and your team should contact.">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Contact person"
            required
            minLength={2}
            value={form.contact_name}
            onChange={(e) => update('contact_name', e.target.value)}
          />
          <TextField
            label="Contact email"
            type="email"
            required
            value={form.contact_email}
            onChange={(e) => update('contact_email', e.target.value)}
          />
          <TextField
            label="Phone number"
            type="tel"
            required
            minLength={7}
            pattern="^\+?[0-9 ()\-]+$"
            placeholder="+27 11 555 0100"
            value={form.contact_phone}
            onChange={(e) => update('contact_phone', e.target.value)}
          />
          <TextField
            label="Website (optional)"
            type="url"
            placeholder="https://"
            value={form.website}
            onChange={(e) => update('website', e.target.value)}
          />
        </div>
        <TextField
          label="Physical address (optional)"
          value={form.physical_address}
          onChange={(e) => update('physical_address', e.target.value)}
        />
      </FormSection>

      {errorMessage && <ErrorAlert message={errorMessage} />}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" isLoading={saveProfile.isPending}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}

function FormSection({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: ReactNode
}) {
  return (
    <section className="grid gap-6 border-b border-slate-100 pb-8 md:grid-cols-3">
      <div>
        <h2 className="font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      <div className="space-y-5 md:col-span-2">{children}</div>
    </section>
  )
}

function CidbEditor({
  gradings,
  onChange,
  options,
}: {
  gradings: CidbGrading[]
  onChange: (gradings: CidbGrading[]) => void
  options: ProfileOptions
}) {
  const usedCodes = gradings.map((g) => g.class_code)
  const nextCode = options.cidb_classes.find((c) => !usedCodes.includes(c.value))?.value

  function updateRow(index: number, changes: Partial<CidbGrading>) {
    onChange(gradings.map((g, i) => (i === index ? { ...g, ...changes } : g)))
  }

  return (
    <div>
      <p className="text-sm font-medium text-slate-700">CIDB gradings</p>
      <p className="text-xs text-slate-500">Leave empty if you're not CIDB registered.</p>
      <div className="mt-2 space-y-2">
        {gradings.map((grading, index) => (
          <div key={grading.class_code} className="flex items-end gap-2">
            <div className="flex-1">
              <Select
                label="Class of works"
                options={options.cidb_classes.filter(
                  (c) => c.value === grading.class_code || !usedCodes.includes(c.value),
                )}
                value={grading.class_code}
                onChange={(e) => updateRow(index, { class_code: e.target.value })}
              />
            </div>
            <div className="w-28">
              <Select
                label="Grade"
                options={options.cidb_grades.map((g) => ({ value: String(g), label: String(g) }))}
                value={String(grading.grade)}
                onChange={(e) => updateRow(index, { grade: Number(e.target.value) })}
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={() => onChange(gradings.filter((_, i) => i !== index))}
              aria-label={`Remove ${grading.class_code} grading`}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>
      {nextCode && (
        <button
          type="button"
          onClick={() => onChange([...gradings, { class_code: nextCode, grade: 1 }])}
          className="mt-2 text-sm font-medium text-emerald-700 hover:text-emerald-800"
        >
          + Add CIDB grading
        </button>
      )}
    </div>
  )
}
