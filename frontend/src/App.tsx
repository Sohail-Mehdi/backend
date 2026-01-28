import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import './App.css'
import { ApiClient } from './api/client'
import { AuthGate } from './components/AuthGate'
import { HeroHeader } from './components/HeroHeader'
import { Panel } from './components/Panel'
import { StatusToast } from './components/StatusToast'
import { SummaryGrid } from './components/SummaryGrid'
import type {
  AISuggestion,
  AnalyticsSnapshot,
  AutomationRulePayload,
  CustomerProfile,
  DashboardPayload,
  NotificationPayload,
  UserSummary,
} from './types'

type AutomationFormState = {
  name: string
  description: string
  rule_type: string
  schedule_expression: string
  product_id: string
  segment_id: string
}

type EventFormState = {
  customer_id: string
  event_type: string
  payload: string
}

type PaymentFormState = {
  campaign_id: string
  amount: string
  currency: string
  provider: string
}

const DEFAULT_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

function App() {
  const api = useMemo(() => new ApiClient(DEFAULT_BASE_URL), [])
  const [credentials, setCredentials] = useState({ email: '', password: '' })
  const [token, setToken] = useState<string>(() => localStorage.getItem('token') || '')
  const [user, setUser] = useState<UserSummary | null>(() => {
    const raw = localStorage.getItem('user')
    return raw ? (JSON.parse(raw) as UserSummary) : null
  })
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsSnapshot | null>(null)
  const [churn, setChurn] = useState<CustomerProfile[]>([])
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([])
  const [automationRules, setAutomationRules] = useState<AutomationRulePayload[]>([])
  const [notifications, setNotifications] = useState<NotificationPayload[]>([])
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [automationForm, setAutomationForm] = useState<AutomationFormState>({
    name: '',
    description: '',
    rule_type: 'create_campaign',
    schedule_expression: '@daily',
    product_id: '',
    segment_id: '',
  })
  const [eventForm, setEventForm] = useState<EventFormState>({
    customer_id: '',
    event_type: 'purchase',
    payload: '{"value": 1}',
  })
  const [paymentForm, setPaymentForm] = useState<PaymentFormState>({
    campaign_id: '',
    amount: '',
    currency: 'USD',
    provider: 'stripe',
  })

  const clearStatus = useCallback(() => {
    setTimeout(() => {
      setStatusMessage(null)
      setErrorMessage(null)
    }, 3500)
  }, [])

  const handleCredentialChange = useCallback(
    (field: 'email' | 'password', value: string) =>
      setCredentials((previous) => ({ ...previous, [field]: value })),
    [],
  )

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      const payload = await api.login(credentials.email, credentials.password)
      const access = payload.tokens.access
      setToken(access)
      setUser(payload.user)
      localStorage.setItem('token', access)
      localStorage.setItem('user', JSON.stringify(payload.user))
      setStatusMessage('Authenticated. Loading intelligence...')
      clearStatus()
    } catch (error) {
      setErrorMessage((error as Error).message)
      clearStatus()
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setToken('')
    setUser(null)
    setDashboard(null)
    setAutomationRules([])
    setSuggestions([])
    setNotifications([])
  }

  const hydrate = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const [dash, analyticsSnapshot, churnList, suggestionList, rules, notices] = await Promise.all([
        api.getDashboard(token),
        api.getRealtimeAnalytics(token),
        api.getChurn(token),
        api.getSuggestions(token),
        api.getAutomationRules(token),
        api.getNotifications(token),
      ])
      setDashboard(dash)
      setAnalytics(analyticsSnapshot)
      setChurn(churnList)
      setSuggestions(suggestionList)
      setAutomationRules(rules)
      setNotifications(notices)
      setStatusMessage('Data refreshed with the latest telemetry.')
    } catch (error) {
      setErrorMessage((error as Error).message)
    } finally {
      setLoading(false)
      clearStatus()
    }
  }, [api, token, clearStatus])

  useEffect(() => {
    hydrate()
  }, [hydrate])

  const handleSuggestionAction = async (id: string, action: 'accept' | 'dismiss') => {
    try {
      await api.actOnSuggestion(token, id, action)
      setStatusMessage('Suggestion updated.')
      hydrate()
    } catch (error) {
      setErrorMessage((error as Error).message)
    } finally {
      clearStatus()
    }
  }

  const handleAutomationSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      await api.createAutomationRule(token, {
        ...automationForm,
        config: {
          product_id: automationForm.product_id || undefined,
          segment_id: automationForm.segment_id || undefined,
        },
      })
      setAutomationForm({
        name: '',
        description: '',
        rule_type: 'create_campaign',
        schedule_expression: '@daily',
        product_id: '',
        segment_id: '',
      })
      setStatusMessage('Automation rule queued.')
      hydrate()
    } catch (error) {
      setErrorMessage((error as Error).message)
    } finally {
      clearStatus()
    }
  }

  const handleRunAutomation = async () => {
    try {
      await api.runAutomation(token)
      setStatusMessage('Automation run triggered.')
      hydrate()
    } catch (error) {
      setErrorMessage((error as Error).message)
    } finally {
      clearStatus()
    }
  }

  const handleEventSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      const parsed = eventForm.payload ? JSON.parse(eventForm.payload) : {}
      await api.ingestEvent(token, eventForm.customer_id, {
        event_type: eventForm.event_type,
        payload: parsed,
      })
      setStatusMessage('Customer signal ingested.')
      setEventForm({ customer_id: '', event_type: 'purchase', payload: '{"value": 1}' })
      hydrate()
    } catch (error) {
      setErrorMessage((error as Error).message)
    } finally {
      clearStatus()
    }
  }

  const handlePaymentSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      await api.createPayment(token, paymentForm.campaign_id, {
        amount: Number(paymentForm.amount),
        currency: paymentForm.currency,
        provider: paymentForm.provider,
      })
      setStatusMessage('Payment reserved for campaign execution.')
      setPaymentForm({ campaign_id: '', amount: '', currency: 'USD', provider: 'stripe' })
    } catch (error) {
      setErrorMessage((error as Error).message)
    } finally {
      clearStatus()
    }
  }

  const handleNotificationRead = async (id: string) => {
    try {
      await api.markNotification(token, id)
      hydrate()
    } catch (error) {
      setErrorMessage((error as Error).message)
      clearStatus()
    }
  }

  const summaryCards = dashboard
    ? [
        { label: 'Products Tracked', value: dashboard.summary.products },
        { label: 'Content Generated', value: dashboard.summary.content_generated },
        { label: 'Content Edited', value: dashboard.summary.content_edited },
        { label: 'Content Ready', value: dashboard.summary.content_ready },
        { label: 'Campaigns Live', value: dashboard.campaign_summary.total },
        {
          label: 'Messages Sent (30d)',
          value: dashboard.campaign_summary.messages?.sent || 0,
        },
        { label: 'Revenue Captured', value: `$${dashboard.campaign_summary.revenue.toFixed(2)}` },
        { label: 'Automation Programs', value: dashboard.automation_rules_active },
      ]
    : []

  if (!token) {
    return (
      <AuthGate
        credentials={credentials}
        onCredentialChange={handleCredentialChange}
        onSubmit={handleLogin}
        errorMessage={errorMessage}
      />
    )
  }

  const feedbackMessage = errorMessage || statusMessage

  return (
    <div className="app-shell">
      <HeroHeader user={user} onLogout={logout} />

      {feedbackMessage && <StatusToast message={feedbackMessage} tone={errorMessage ? 'error' : 'success'} />}

      <SummaryGrid items={summaryCards} />

      <section className="panel-grid">
        <Panel title="Realtime Analytics" accent={`${analytics?.window_days ?? 30}-day window`}>
          <div className="metrics-row">
            {analytics &&
              Object.entries(analytics.metrics).map(([key, value]) => (
                <div key={key} className="mini-stat">
                  <p>{key}</p>
                  <strong>{value}</strong>
                </div>
              ))}
          </div>
          <div className="list-block">
            <h3>Variant Performance</h3>
            <ul>
              {(analytics?.variants ?? []).map((variant) => (
                <li key={`${variant.campaign_id}-${variant.label}`}>
                  <span>
                    {variant.label} · sent {variant.metrics.sent || 0}
                  </span>
                  {variant.is_winner && <span className="badge success">Winner</span>}
                </li>
              ))}
            </ul>
          </div>
        </Panel>

        <Panel title="AI Suggestions" accent={`${suggestions.length} ready`}>
          <ul className="suggestion-list">
            {suggestions.map((suggestion) => (
              <li key={suggestion.id}>
                <div>
                  <p className="suggestion-type">{suggestion.suggestion_type}</p>
                  <p className="suggestion-detail">{JSON.stringify(suggestion.payload)}</p>
                </div>
                <div className="suggestion-actions">
                  <button onClick={() => handleSuggestionAction(suggestion.id, 'accept')}>Accept</button>
                  <button className="ghost" onClick={() => handleSuggestionAction(suggestion.id, 'dismiss')}>
                    Dismiss
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Churn Watchlist" accent="High-risk customers">
          <ul className="churn-list">
            {churn.map((customer: any) => (
              <li key={customer.id}>
                <div>
                  <p>{customer.email}</p>
                  <small>
                    Risk {customer.churn_risk_score.toFixed(1)} · Engagement {customer.engagement_score.toFixed(1)}
                  </small>
                </div>
                <span className="badge warning">{customer.preferred_language}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel
          title="Automation Programs"
          accent="Live playbooks"
          actionSlot={
            <button onClick={handleRunAutomation}>
              Run Now
            </button>
          }
        >
          <ul className="automation-list">
            {automationRules.map((rule) => (
              <li key={rule.id}>
                <div>
                  <p>{rule.name}</p>
                  <small>
                    {rule.rule_type} · {rule.schedule_expression}
                  </small>
                </div>
                <span className={`badge ${rule.is_active ? 'success' : 'warning'}`}>
                  {rule.is_active ? 'Active' : 'Paused'}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      </section>

      <section className="panel-grid">
        <Panel
          title="Top Campaigns"
          accent="Performance overview"
          actionSlot={loading ? <span className="pulse">Refreshing...</span> : null}
        >
          <ul className="campaign-list">
            {(dashboard?.campaign_summary.top_campaigns ?? []).map((campaign) => (
              <li key={campaign.id}>
                <div>
                  <p>{campaign.name}</p>
                  <small>Status: {campaign.status}</small>
                </div>
                <span>{campaign.metrics.clicked || 0} clicks</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Notifications" accent={`${notifications.length} updates`}>
          <ul className="notification-list">
            {notifications.map((notice) => (
              <li key={notice.id}>
                <div>
                  <p>{notice.title}</p>
                  <small>{notice.body}</small>
                </div>
                {notice.status !== 'read' && (
                  <button className="ghost" onClick={() => handleNotificationRead(notice.id)}>
                    Mark read
                  </button>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </section>

      <section className="tools-grid">
        <form className="panel form-panel" onSubmit={handleAutomationSubmit}>
          <h2>Create Automation</h2>
          <label>
            Name
            <input
              value={automationForm.name}
              required
              onChange={(event) => setAutomationForm({ ...automationForm, name: event.target.value })}
            />
          </label>
          <label>
            Description
            <textarea
              value={automationForm.description}
              onChange={(event) => setAutomationForm({ ...automationForm, description: event.target.value })}
            />
          </label>
          <label>
            Rule Type
            <select
              value={automationForm.rule_type}
              onChange={(event) => setAutomationForm({ ...automationForm, rule_type: event.target.value })}
            >
              <option value="create_campaign">Create Campaign</option>
              <option value="schedule_campaign">Schedule Campaign</option>
              <option value="send_campaign">Send Campaign</option>
            </select>
          </label>
          <label>
            Schedule
            <select
              value={automationForm.schedule_expression}
              onChange={(event) =>
                setAutomationForm({ ...automationForm, schedule_expression: event.target.value })
              }
            >
              <option value="@hourly">Hourly</option>
              <option value="@daily">Daily</option>
              <option value="@weekly">Weekly</option>
            </select>
          </label>
          <label>
            Product ID
            <input
              value={automationForm.product_id}
              placeholder="Optional"
              onChange={(event) => setAutomationForm({ ...automationForm, product_id: event.target.value })}
            />
          </label>
          <label>
            Segment ID
            <input
              value={automationForm.segment_id}
              placeholder="Optional"
              onChange={(event) => setAutomationForm({ ...automationForm, segment_id: event.target.value })}
            />
          </label>
          <button type="submit">Save Automation</button>
        </form>

        <form className="panel form-panel" onSubmit={handleEventSubmit}>
          <h2>Ingest Customer Event</h2>
          <label>
            Customer ID
            <input
              value={eventForm.customer_id}
              required
              onChange={(event) => setEventForm({ ...eventForm, customer_id: event.target.value })}
            />
          </label>
          <label>
            Event Type
            <select
              value={eventForm.event_type}
              onChange={(event) => setEventForm({ ...eventForm, event_type: event.target.value })}
            >
              <option value="purchase">Purchase</option>
              <option value="click">Click</option>
              <option value="email_open">Email Open</option>
              <option value="whatsapp_reply">WhatsApp Reply</option>
            </select>
          </label>
          <label>
            Payload JSON
            <textarea
              value={eventForm.payload}
              onChange={(event) => setEventForm({ ...eventForm, payload: event.target.value })}
            />
          </label>
          <button type="submit">Record Event</button>
        </form>

        <form className="panel form-panel" onSubmit={handlePaymentSubmit}>
          <h2>Reserve Campaign Budget</h2>
          <label>
            Campaign ID
            <input
              value={paymentForm.campaign_id}
              required
              onChange={(event) => setPaymentForm({ ...paymentForm, campaign_id: event.target.value })}
            />
          </label>
          <label>
            Amount
            <input
              type="number"
              min="0"
              step="0.01"
              value={paymentForm.amount}
              required
              onChange={(event) => setPaymentForm({ ...paymentForm, amount: event.target.value })}
            />
          </label>
          <label>
            Currency
            <select
              value={paymentForm.currency}
              onChange={(event) => setPaymentForm({ ...paymentForm, currency: event.target.value })}
            >
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
            </select>
          </label>
          <label>
            Provider
            <select
              value={paymentForm.provider}
              onChange={(event) => setPaymentForm({ ...paymentForm, provider: event.target.value })}
            >
              <option value="stripe">Stripe</option>
              <option value="adyen">Adyen</option>
              <option value="razorpay">Razorpay</option>
            </select>
          </label>
          <button type="submit">Create Payment Intent</button>
        </form>
      </section>
    </div>
  )
}

export default App
