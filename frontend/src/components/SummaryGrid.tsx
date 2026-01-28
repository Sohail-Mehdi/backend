interface SummaryItem {
  label: string
  value: string | number
}

interface SummaryGridProps {
  items: SummaryItem[]
}

export function SummaryGrid({ items }: SummaryGridProps) {
  if (!items.length) return null
  return (
    <section className="summary-grid">
      {items.map((item) => (
        <article key={item.label} className="metric-card">
          <p className="metric-label">{item.label}</p>
          <p className="metric-value">{item.value}</p>
        </article>
      ))}
    </section>
  )
}
