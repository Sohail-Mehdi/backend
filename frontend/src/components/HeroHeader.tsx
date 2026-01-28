import type { UserSummary } from '../types'

interface HeroHeaderProps {
  user: UserSummary | null
  onLogout: () => void
}

export function HeroHeader({ user, onLogout }: HeroHeaderProps) {
  return (
    <header className="hero">
      <div>
        <p className="eyebrow">AI Marketing Command Center</p>
        <h1>Automation, analytics, and intelligence in a single pane of glass.</h1>
        <p className="subtitle">
          Monitor campaign health, trigger self-optimizing workflows, and act on AI insights instantly.
        </p>
      </div>
      <div className="hero-meta">
        <span className="badge">{user?.role?.toUpperCase()}</span>
        <p>{user?.name}</p>
        <button onClick={onLogout} className="ghost">
          Sign out
        </button>
      </div>
    </header>
  )
}
