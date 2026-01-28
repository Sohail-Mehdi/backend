export interface TokenPayload {
  tokens: {
    access: string
    refresh: string
  }
  user: UserSummary
}

export interface UserSummary {
  id: string
  name: string
  email: string
  role: string
}

export interface DashboardPayload {
  summary: {
    products: number
    content_generated: number
    content_edited: number
    content_ready: number
  }
  campaign_summary: {
    total: number
    status: Record<string, number>
    messages: Record<string, number>
    revenue: number
    top_campaigns: Array<{
      id: string
      name: string
      status: string
      metrics: Record<string, number>
    }>
  }
  notifications: NotificationPayload[]
  products: ProductSnapshot[]
  ai_suggestions: AISuggestion[]
  churn_risk: CustomerProfile[]
  automation_rules_active: number
}

export interface ProductSnapshot {
  id: string
  name: string
  category: string
  created_at: string
  latest_status: string
}

export interface NotificationPayload {
  id: string
  title: string
  body: string
  level: string
  status: string
  created_at: string
  read_at?: string | null
}

export interface AISuggestion {
  id: string
  suggestion_type: string
  payload: Record<string, unknown>
  score: number
  status: string
  created_at: string
  acted_at?: string | null
}

export interface AnalyticsSnapshot {
  window_days: number
  metrics: Record<string, number>
  variants: Array<{
    campaign_id: string
    label: string
    metrics: Record<string, number>
    is_winner: boolean
  }>
}

export interface ChurnCustomer {
  id: string
  email: string
  engagement_score: number
  interest_score: number
  churn_risk_score: number
  preferred_language: string
  categories_of_interest: string[]
}

export interface CustomerProfile extends ChurnCustomer {}

export interface AutomationRulePayload {
  id: string
  name: string
  description: string
  rule_type: string
  schedule_expression: string
  config: Record<string, unknown>
  is_active: boolean
  last_run_at?: string | null
  created_at: string
}

export interface CampaignPaymentPayload {
  id: string
  campaign: string
  provider: string
  amount: string
  currency: string
  transaction_id: string
  status: string
  processed_at: string
  created_at: string
}

export type EventPayload = {
  customer_id: string
  event_type: string
  payload: Record<string, unknown>
}
