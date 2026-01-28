# AI Marketing Tool Backend

Phase 2 backend for the AI Marketing Tool, built with Django 6, Django REST Framework, and MySQL. It now covers advanced campaign orchestration, segmentation, bulk messaging, AI content suggestions, dashboards, and audit logging.

## Features
- Email/password signup + login with JWT authentication and role support (store owner / agency)
- Product CRUD foundation, multilingual AI content generation (social/email/WhatsApp) using OpenAI with regeneration + language override
- Customer management with CSV/Excel import, automatic validation, tagging, segmentation, and localization preferences
- Dynamic campaign builder: AI-suggested titles/subjects/hashtags/summaries, scheduling with timezone support, dashboard notifications, PDF/CSV exports
- Bulk email + WhatsApp dispatching with rate limiting, retry logic, per-message logging, and campaign performance tracking (sent/opened/clicked)
- Activity & notification feeds, audit logs, admin analytics, and optional email alerts for campaign completion/failure events
- Environment-driven settings for database, security, JWT lifetimes, AI model selection, messaging rate limits, and provider credentials

## Tech Stack
- Django 6.0
- Django REST Framework + Simple JWT
- MySQL (via `mysqlclient`)
- OpenAI Python SDK
- python-dotenv + dj-database-url for configuration

## Getting Started
1. **Install system prerequisites**
   ```bash
   sudo apt install python3-dev default-libmysqlclient-dev build-essential
   ```
2. **Create & activate a virtual environment**
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # edit .env with DB creds, OPENAI_API_KEY, email/Twilio settings, etc.
   ```
5. **Apply migrations & create a superuser (optional)**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```
6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

## API Overview (all routes prefixed with `/api`)
| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/signup` | Register a new user (returns JWT pair) |
| POST | `/login` | Obtain JWT access/refresh tokens |
| POST/GET | `/products` | Upload + list products with multilingual AI content |
| POST | `/products/{product_id}/generate_content` | Generate/refresh AI content (supports `language_code`) |
| GET | `/products/{product_id}/content` | Fetch AI content for a product |
| PUT | `/products/{product_id}/content/{content_id}` | Edit AI content text/status |
| GET | `/dashboard` | Dashboard summary, campaign metrics, notifications |
| GET | `/logs` | Paginated activity logs |
| GET/POST | `/customers` | Manage individual customers |
| POST | `/customers/upload` | Upload CSV/Excel customer lists |
| GET | `/segments` | List customer segments |
| POST | `/segments` | Create a segment (filters + tags) |
| GET/POST | `/campaigns` | List/create AI-ready campaigns |
| POST | `/campaigns/{id}/suggestions` | Generate AI suggestions for a campaign |
| POST | `/campaigns/{id}/suggestions/{suggestion_id}` | Approve/reject suggestions |
| POST | `/campaigns/{id}/schedule` | Schedule campaign run |
| POST | `/campaigns/{id}/send` | Generate content + dispatch bulk messages |
| GET | `/campaigns/{id}/messages` | Message delivery log |
| GET | `/campaigns/{id}/logs` | Campaign lifecycle events |
| GET | `/campaigns/export` | Export campaign analytics (CSV/PDF via `format=`) |
| GET | `/notifications` | Fetch dashboard notifications |
| POST | `/token/refresh` | Refresh JWT access token |

All endpoints except `/signup`, `/login`, and `/token/refresh` require the `Authorization: Bearer <access_token>` header.

## OpenAI Integration
- `marketing/ai_engine.py` now supports multilingual product content plus campaign assets (summary, titles, hashtags, channel copy).
- Configure `OPENAI_API_KEY`/`OPENAI_MODEL` and optional `ALLOWED_CAMPAIGN_LANGUAGES` in `.env`.
- Errors are surfaced with `502 Bad Gateway` responses; language defaults to `DEFAULT_CAMPAIGN_LANGUAGE`.

## Bulk Messaging & Automation
- `marketing/services.py` ships `CustomerImportService`, `BulkMessenger`, and `CampaignOrchestrator` for CSV/Excel ingestion, throttled SMTP/Twilio dispatch, retries, and metrics.
- Configure SMTP + Twilio credentials via `.env` (see `.env.example`) along with rate limits `BULK_EMAIL_RATE_LIMIT_PER_MIN` / `BULK_WHATSAPP_RATE_LIMIT_PER_MIN`.
- Sample helper scripts (after setting `DJANGO_SETTINGS_MODULE=backend_project.settings`):
   - `python scripts/generate_campaign_assets.py`
   - `python scripts/sample_bulk_messaging.py`

## Logging, Notifications & Admin
- `marketing/services.py` also handles campaign completion/failure notifications (dashboard + optional admin email), activity logs, and delivery tracing.
- The Django admin (`/admin`) exposes dashboards for users, products, campaigns, messages, suggestions, and notifications with search & filters.

## Testing
Use the DRF browsable API or REST clients (Insomnia/Postman). To process queued campaigns without hitting the API, run `python manage.py sample_bulk_send --campaign-id <uuid>` after preparing AI content.
