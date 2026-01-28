import type { ReactNode } from 'react'

interface PanelProps {
  title: string
  accent?: string
  actionSlot?: ReactNode
  children: ReactNode
}

export function Panel({ title, accent, actionSlot, children }: PanelProps) {
  return (
    <article className="panel">
      <div className="panel-heading">
        <div>
          {accent && <p className="panel-eyebrow">{accent}</p>}
          <h2>{title}</h2>
        </div>
        {actionSlot}
      </div>
      {children}
    </article>
  )
}
