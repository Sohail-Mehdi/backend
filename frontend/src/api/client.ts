import type {
  AISuggestion,
  AnalyticsSnapshot,
  AutomationRulePayload,
  CustomerProfile,
  DashboardPayload,
  NotificationPayload,
  TokenPayload,
} from '../types'

interface RequestOptions {
  method?: string
  token?: string
  body?: Record<string, unknown> | FormData
}

export class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  private buildUrl(path: string) {
    const sanitized = path.startsWith('/') ? path.slice(1) : path
    return `${this.baseUrl}/${sanitized}`
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', token, body } = options
    const headers: Record<string, string> = {
      Accept: 'application/json',
    }
    let payload: BodyInit | undefined
    if (body instanceof FormData) {
      payload = body
    } else if (body) {
      headers['Content-Type'] = 'application/json'
      payload = JSON.stringify(body)
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    try {
      const response = await fetch(this.buildUrl(path), {
        method,
        headers,
        body: payload,
      })

      if (!response.ok) {
        const detail = await this.safeParse(response)

        // Provide specific error messages based on status code
        if (response.status === 401) {
          throw new Error(detail?.detail || 'Invalid email or password. Please try again.')
        } else if (response.status === 403) {
          throw new Error(detail?.detail || 'Access denied. Please check your permissions.')
        } else if (response.status === 404) {
          throw new Error(detail?.detail || 'Resource not found.')
        } else if (response.status >= 500) {
          throw new Error('Server error. Please try again later.')
        }

        throw new Error(detail?.detail || detail?.message || 'Request failed. Please try again.')
      }

      if (response.status === 204) {
        return null as T
      }
      return (await response.json()) as T
    } catch (error) {
      // Handle network errors
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('Network error. Please check your connection and try again.')
      }
      throw error
    }
  }

  private async safeParse(response: Response): Promise<any> {
    try {
      return await response.json()
    } catch (_err) {
      return null
    }
  }

  login(email: string, password: string) {
    return this.request<TokenPayload>('login', {
      method: 'POST',
      body: { email, password },
    })
  }

  getDashboard(token: string) {
    return this.request<DashboardPayload>('dashboard', { token })
  }

  getRealtimeAnalytics(token: string) {
    return this.request<AnalyticsSnapshot>('analytics/realtime', { token })
  }

  getChurn(token: string, limit = 6) {
    return this.request<CustomerProfile[]>('analytics/churn?limit=' + limit, { token })
  }

  getSuggestions(token: string) {
    return this.request<AISuggestion[]>('ai/suggestions', { token })
  }

  actOnSuggestion(token: string, id: string, action: 'accept' | 'dismiss') {
    return this.request(`ai/suggestions/${id}/action`, {
      method: 'POST',
      token,
      body: { action },
    })
  }

  getAutomationRules(token: string) {
    return this.request<AutomationRulePayload[]>('automation/rules', { token })
  }

  createAutomationRule(token: string, payload: Record<string, unknown>) {
    return this.request<AutomationRulePayload>('automation/rules', {
      method: 'POST',
      token,
      body: payload,
    })
  }

  runAutomation(token: string) {
    return this.request<{ detail: string }>('automation/run', {
      method: 'POST',
      token,
    })
  }

  getNotifications(token: string) {
    return this.request<NotificationPayload[]>('notifications', { token })
  }

  markNotification(token: string, id: string) {
    return this.request('notifications/' + id + '/read', {
      method: 'POST',
      token,
    })
  }

  ingestEvent(token: string, customerId: string, payload: Record<string, unknown>) {
    return this.request(`customers/${customerId}/events`, {
      method: 'POST',
      token,
      body: payload,
    })
  }

  createPayment(
    token: string,
    campaignId: string,
    payload: { amount: number; currency: string; provider: string },
  ) {
    return this.request(`campaigns/${campaignId}/payments`, {
      method: 'POST',
      token,
      body: payload,
    })
  }
}
