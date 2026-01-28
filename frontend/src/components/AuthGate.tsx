import type { FormEvent } from 'react'

export type CredentialField = 'email' | 'password'

interface AuthGateProps {
  credentials: Record<CredentialField, string>
  onCredentialChange: (field: CredentialField, value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  errorMessage?: string | null
}

export function AuthGate({ credentials, onCredentialChange, onSubmit, errorMessage }: AuthGateProps) {
  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={onSubmit}>
        <p className="eyebrow">AI Marketing Control</p>
        <h1>Welcome Back</h1>
        <p>Sign in to access your marketing intelligence, automations, and analytics dashboard.</p>
        <label>
          Email
          <input
            type="email"
            required
            value={credentials.email}
            onChange={(event) => onCredentialChange('email', event.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            value={credentials.password}
            onChange={(event) => onCredentialChange('password', event.target.value)}
          />
        </label>
        <button type="submit">Sign In</button>
        {errorMessage && <span className="inline-error">{errorMessage}</span>}
      </form>
    </div>
  )
}
