import { type FormEvent, useState } from 'react'
import { Link } from 'react-router'

import { DemoButton } from '../auth/DemoButton'
import { useAuth } from '../auth/useAuth'
import { AuthLayout } from '../components/AuthLayout'
import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { TextField } from '../components/ui/TextField'
import { getErrorMessage } from '../lib/api'
import type { RegisterData } from '../lib/types'

const emptyForm: RegisterData = { company_name: '', full_name: '', email: '', password: '' }

export function RegisterPage() {
  const { register } = useAuth()
  const [form, setForm] = useState<RegisterData>(emptyForm)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function updateField(field: keyof RegisterData, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await register(form)
    } catch (err) {
      setError(getErrorMessage(err))
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout
      title="Create your team account"
      subtitle="You'll be the owner of your company's workspace and can invite teammates later."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-emerald-700 hover:text-emerald-800">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {error && <ErrorAlert message={error} />}
        <TextField
          label="Company name"
          autoComplete="organization"
          required
          minLength={2}
          value={form.company_name}
          onChange={(e) => updateField('company_name', e.target.value)}
        />
        <TextField
          label="Your full name"
          autoComplete="name"
          required
          minLength={2}
          value={form.full_name}
          onChange={(e) => updateField('full_name', e.target.value)}
        />
        <TextField
          label="Work email"
          type="email"
          autoComplete="email"
          required
          value={form.email}
          onChange={(e) => updateField('email', e.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          hint="At least 8 characters."
          value={form.password}
          onChange={(e) => updateField('password', e.target.value)}
        />
        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          Create account
        </Button>
      </form>
      <DemoButton />
    </AuthLayout>
  )
}
