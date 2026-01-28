"""Domain services for the marketing backend."""
from __future__ import annotations

import csv
import io
import logging
import os
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from datetime import timedelta

import numpy as np
import openpyxl
import pandas as pd
import phonenumbers
from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import EmailValidator
from django.db import transaction
from django.db.models import Avg, Count, F, Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from sklearn.linear_model import LinearRegression
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from .ai_engine import AIContentGenerator, AIContentGeneratorError
from decimal import Decimal

from .models import (
    AISuggestion,
    AutomationRule,
    ActivityLog,
    Campaign,
    CampaignLog,
    CampaignMessage,
    CampaignPayment,
    CampaignVariant,
    Customer,
    CustomerEvent,
    CustomerTag,
    Notification,
    Product,
    User,
)


def log_activity(
    *,
    user: User,
    action: str,
    product: Optional[Product] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> ActivityLog:
    """Persist a user activity log entry within a transaction."""

    with transaction.atomic():
        return ActivityLog.objects.create(
            user=user,
            action=action,
            product=product,
            metadata=metadata or {},
        )


LOGGER = logging.getLogger(__name__)

EMAIL_VALIDATOR = EmailValidator(message='Invalid email address')


class CampaignExecutionError(RuntimeError):
    """Raised when automated campaign execution fails."""


@dataclass
class ParsedCustomer:
    email: str
    phone_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: str = 'UTC'
    preferred_language: str = 'en'
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        self.tags = self.tags or []
        self.metadata = self.metadata or {}


class CustomerImportService:
    """Parse CSV/Excel uploads into structured customer records."""

    def __init__(self, *, user: User):
        self.user = user

    def parse(self, uploaded_file) -> list[ParsedCustomer]:
        filename = uploaded_file.name.lower()
        raw = uploaded_file.read()
        if filename.endswith('.csv'):
            text = raw.decode('utf-8')
            return self._parse_csv(text)
        if filename.endswith(('.xlsx', '.xlsm')):
            return self._parse_excel(raw)
        raise ValueError('Only CSV or Excel uploads are supported')

    def _parse_csv(self, text: str) -> list[ParsedCustomer]:
        reader = csv.DictReader(io.StringIO(text))
        return [self._build_customer(row) for row in reader if row.get('email')]

    def _parse_excel(self, raw: bytes) -> list[ParsedCustomer]:
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(value).strip().lower() for value in rows[0] if value is not None]
        customers: list[ParsedCustomer] = []
        for row in rows[1:]:
            data = {headers[idx]: (cell or '') for idx, cell in enumerate(row) if idx < len(headers)}
            if data.get('email'):
                customers.append(self._build_customer(data))
        return customers

    def _build_customer(self, row: dict[str, Any]) -> ParsedCustomer:
        email = (row.get('email') or '').strip().lower()
        if not email:
            raise ValueError('Email is required for each customer row')
        EMAIL_VALIDATOR(email)
        phone = self._normalize_phone(row.get('phone') or row.get('phone_number'))
        tags_raw = row.get('tags') or ''
        tags = [tag.strip() for tag in tags_raw.split(',') if tag.strip()]
        metadata = {k: v for k, v in row.items() if k not in {'email', 'phone', 'phone_number', 'tags'}}
        return ParsedCustomer(
            email=email,
            phone_number=phone,
            first_name=(row.get('first_name') or '').strip() or None,
            last_name=(row.get('last_name') or '').strip() or None,
            timezone=(row.get('timezone') or 'UTC').strip() or 'UTC',
            preferred_language=(row.get('language') or 'en').strip() or 'en',
            tags=tags,
            metadata=metadata,
        )

    def _normalize_phone(self, value: Any) -> Optional[str]:
        if not value:
            return None
        try:
            parsed = phonenumbers.parse(str(value), None)
        except phonenumbers.NumberParseException as exc:
            raise ValueError('Invalid phone number provided') from exc
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError('Invalid phone number provided')
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    def upsert_customers(self, customers: Sequence[ParsedCustomer]) -> dict[str, int]:
        created = 0
        updated = 0
        for parsed in customers:
            defaults = {
                'phone_number': parsed.phone_number or '',
                'first_name': parsed.first_name or '',
                'last_name': parsed.last_name or '',
                'timezone': parsed.timezone,
                'preferred_language': parsed.preferred_language,
                'metadata': parsed.metadata,
            }
            customer, was_created = Customer.objects.update_or_create(
                user=self.user,
                email=parsed.email,
                defaults=defaults,
            )
            if parsed.tags:
                tag_objects = [
                    CustomerTag.objects.get_or_create(
                        user=self.user,
                        slug=self._unique_slug(tag_name),
                        defaults={'name': tag_name},
                    )[0]
                    for tag_name in parsed.tags
                ]
                customer.tags.add(*tag_objects)
            created += 1 if was_created else 0
            updated += 0 if was_created else 1
        return {'created': created, 'updated': updated}

    def _unique_slug(self, value: str) -> str:
        base = slugify(value) or slugify(self.user.email)
        slug = base
        idx = 1
        while CustomerTag.objects.filter(user=self.user, slug=slug).exists():
            slug = f"{base}-{idx}"
            idx += 1
        return slug


class RateLimiter:
    """Simple in-memory rate limiter to respect provider quotas."""

    def __init__(self, per_minute: int):
        self.per_minute = max(per_minute, 1)
        self._window_start = time.monotonic()
        self._sent = 0

    def wait_for_slot(self):
        window = 60.0
        now = time.monotonic()
        if now - self._window_start >= window:
            self._window_start = now
            self._sent = 0
        if self._sent < self.per_minute:
            self._sent += 1
            return
        sleep_for = window - (now - self._window_start)
        if sleep_for > 0:
            time.sleep(sleep_for)
        self._window_start = time.monotonic()
        self._sent = 1


class BulkMessenger:
    """Dispatch email + WhatsApp messages with retry logging."""

    def __init__(self):
        email_rate = int(getattr(settings, 'BULK_EMAIL_RATE_LIMIT_PER_MIN', 60))
        whatsapp_rate = int(getattr(settings, 'BULK_WHATSAPP_RATE_LIMIT_PER_MIN', 30))
        sms_rate = int(getattr(settings, 'BULK_SMS_RATE_LIMIT_PER_MIN', 30))
        self.email_limiter = RateLimiter(email_rate)
        self.whatsapp_limiter = RateLimiter(whatsapp_rate)
        self.sms_limiter = RateLimiter(sms_rate)
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.twilio_from = os.getenv('TWILIO_WHATSAPP_FROM')
        self.twilio_client: Optional[TwilioClient] = None
        if account_sid and auth_token:
            self.twilio_client = TwilioClient(account_sid, auth_token)
        self.sms_api_key = os.getenv('SMS_PROVIDER_API_KEY')
        self.sms_sender_id = os.getenv('SMS_PROVIDER_SENDER_ID', 'AI-MKT')

    @dataclass
    class DispatchResult:
        status: str
        metadata: dict[str, Any]
        external_id: Optional[str] = None

    def dispatch_message(self, message: CampaignMessage) -> 'BulkMessenger.DispatchResult':
        if message.channel == CampaignMessage.Channel.EMAIL:
            return self._send_email(message)
        if message.channel == CampaignMessage.Channel.WHATSAPP:
            return self._send_whatsapp(message)
        if message.channel == CampaignMessage.Channel.SMS:
            return self._send_sms(message)
        if message.channel in {
            CampaignMessage.Channel.FACEBOOK,
            CampaignMessage.Channel.INSTAGRAM,
            CampaignMessage.Channel.TWITTER,
        }:
            return self._send_social(message)
        return BulkMessenger.DispatchResult(
            status=CampaignMessage.Status.SENT,
            metadata={'note': 'Social asset ready'},
        )

    def _send_email(self, message: CampaignMessage) -> 'BulkMessenger.DispatchResult':
        self.email_limiter.wait_for_slot()
        subject = (
            message.metadata.get('subject_line')
            or message.campaign.subject_line
            or message.campaign.name
        )
        send_mail(
            subject=subject,
            message=message.content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
            recipient_list=[message.customer.email],
            fail_silently=False,
        )
        return BulkMessenger.DispatchResult(
            status=CampaignMessage.Status.SENT,
            metadata={'channel': 'email'},
        )

    def _send_whatsapp(self, message: CampaignMessage) -> 'BulkMessenger.DispatchResult':
        if not self.twilio_client or not self.twilio_from:
            raise RuntimeError('WhatsApp provider is not configured')
        if not message.customer.phone_number:
            raise RuntimeError('Customer does not have a WhatsApp-compatible number')
        self.whatsapp_limiter.wait_for_slot()
        try:
            resp = self.twilio_client.messages.create(
                body=message.content,
                from_=self.twilio_from,
                to=f"whatsapp:{message.customer.phone_number}",
            )
        except TwilioRestException as exc:
            raise RuntimeError(f'WhatsApp send failed: {exc.msg}') from exc
        return BulkMessenger.DispatchResult(
            status=CampaignMessage.Status.SENT,
            metadata={'channel': 'whatsapp'},
            external_id=resp.sid,
        )

    def _send_sms(self, message: CampaignMessage) -> 'BulkMessenger.DispatchResult':
        if not self.sms_api_key:
            raise RuntimeError('SMS provider is not configured')
        if not message.customer.phone_number:
            raise RuntimeError('Customer does not have a SMS-compatible number')
        self.sms_limiter.wait_for_slot()
        # Placeholder for external SMS provider
        LOGGER.info('Sending SMS via provider %s', self.sms_sender_id)
        return BulkMessenger.DispatchResult(
            status=CampaignMessage.Status.SENT,
            metadata={'channel': 'sms'},
            external_id=f'sms-{message.id}',
        )

    def _send_social(self, message: CampaignMessage) -> 'BulkMessenger.DispatchResult':
        # Integrate with actual APIs (Facebook/Instagram/Twitter) as needed
        LOGGER.info('Queued social post for %s', message.channel)
        return BulkMessenger.DispatchResult(
            status=CampaignMessage.Status.SENT,
            metadata={'channel': message.channel},
        )


class NotificationService:
    """Persist dashboard notifications and optional email alerts."""

    def __init__(self, *, user: User):
        self.user = user
        self.notification_channels = [
            channel.strip()
            for channel in os.getenv('ADMIN_NOTIFICATION_CHANNELS', 'email').split(',')
            if channel.strip()
        ]
        self.admin_phone = os.getenv('ADMIN_ALERT_PHONE')
        self.sms_sender_id = os.getenv('SMS_PROVIDER_SENDER_ID', 'AI-MKT')
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.twilio_client: Optional[TwilioClient] = None
        if account_sid and auth_token:
            self.twilio_client = TwilioClient(account_sid, auth_token)
        self.twilio_from = os.getenv('TWILIO_WHATSAPP_FROM')
        self.sms_api_key = os.getenv('SMS_PROVIDER_API_KEY')

    def notify_campaign_status(self, *, campaign: Campaign, status: str, details: str = '') -> Notification:
        body = f"Campaign '{campaign.name}' is now {status}. {details}".strip()
        notification = Notification.objects.create(
            user=self.user,
            title=f"Campaign {campaign.name} {status}",
            body=body,
            level=Notification.Level.INFO if status == Campaign.Status.COMPLETED else Notification.Level.WARNING,
            status=Notification.Status.PENDING,
        )
        admin_email = getattr(settings, 'ADMIN_ALERT_EMAIL', os.getenv('ADMIN_ALERT_EMAIL'))
        if admin_email:
            context = {
                'campaign': campaign,
                'status': status,
                'details': details,
                'dashboard_url': getattr(settings, 'FRONTEND_DASHBOARD_URL', 'http://localhost:5173'),
            }
            rendered = render_to_string('emails/campaign_status_email.txt', context)
            send_mail(
                subject=f"Campaign {campaign.name} {status}",
                message=rendered,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=[admin_email],
                fail_silently=True,
            )
        self._dispatch_alert(body)
        notification.status = Notification.Status.SENT
        notification.save(update_fields=('status',))
        return notification

    def _dispatch_alert(self, body: str):
        for channel in self.notification_channels:
            if channel == 'whatsapp':
                self._send_whatsapp(body)
            elif channel == 'sms':
                self._send_sms(body)

    def _send_whatsapp(self, body: str):
        if not self.twilio_client or not self.twilio_from or not self.admin_phone:
            return
        try:
            self.twilio_client.messages.create(
                body=body,
                from_=self.twilio_from,
                to=f"whatsapp:{self.admin_phone}",
            )
        except TwilioRestException as exc:  # pragma: no cover - external API
            LOGGER.warning('WhatsApp alert failed: %s', exc.msg)

    def _send_sms(self, body: str):
        if not self.admin_phone or not self.sms_api_key:
            return
        LOGGER.info('Sending SMS alert via %s to %s', self.sms_sender_id, self.admin_phone)


class CampaignOrchestrator:
    """Bundle utilities for campaign personalization and delivery."""

    def __init__(self, *, campaign: Campaign):
        self.campaign = campaign
        self.messenger = BulkMessenger()
        self.notifications = NotificationService(user=campaign.user)

    def build_messages(
        self,
        *,
        customers: Iterable[Customer],
        content: dict[str, Any],
        variant: CampaignVariant | None = None,
    ) -> int:
        created = 0
        now = timezone.now()
        for customer in customers:
            channels = self._resolve_channels(customer)
            for channel in channels:
                template_key = self._template_key(channel)
                base_content = self._variant_content(content, template_key, variant)
                if not base_content:
                    continue
                personalized = self._personalize(base_content, customer, channel)
                defaults = {
                    'content': personalized,
                    'status': CampaignMessage.Status.PENDING,
                    'metadata': {
                        'language_code': self.campaign.language_code,
                        'subject_line': content.get('subject_line') or self.campaign.subject_line,
                        'title': content.get('title') or self.campaign.title,
                        'hashtags': content.get('hashtags', []),
                        'fallback_channels': self._fallback_channels(channel, customer),
                        'variant_label': variant.label if variant else None,
                    },
                    'variant': variant,
                }
                CampaignMessage.objects.update_or_create(
                    campaign=self.campaign,
                    customer=customer,
                    channel=channel,
                    defaults=defaults,
                )
                created += 1
        CampaignLog.objects.create(
            campaign=self.campaign,
            action='Messages prepared',
            metadata={'created': created, 'timestamp': now.isoformat(), 'variant': getattr(variant, 'label', None)},
        )
        return created

    def send_pending_messages(self, *, force: bool = False) -> dict[str, int]:
        if not force and self.campaign.status == Campaign.Status.DRAFT:
            raise ValueError('Campaign must be scheduled or running before dispatch')
        pending_statuses = [
            CampaignMessage.Status.PENDING,
            CampaignMessage.Status.SCHEDULED,
        ]
        queryset = (
            self.campaign.messages.select_related('customer')
            .filter(status__in=pending_statuses)
            .order_by('created_at')
        )
        counts = {'sent': 0, 'failed': 0}
        if not queryset.exists():
            return counts
        self.campaign.status = Campaign.Status.RUNNING
        self.campaign.save(update_fields=('status', 'updated_at'))
        for message in queryset:
            message.status = CampaignMessage.Status.SENDING
            message.attempts += 1
            message.save(update_fields=('status', 'attempts', 'updated_at'))
            try:
                result = self.messenger.dispatch_message(message)
            except Exception as exc:  # pragma: no cover - network
                counts['failed'] += 1
                self._handle_failure(message, str(exc))
                continue
            self._handle_success(message, result)
            counts['sent'] += 1
        self.refresh_metrics()
        remaining = self.campaign.messages.filter(status__in=pending_statuses).count()
        if remaining == 0:
            status = Campaign.Status.FAILED if counts['failed'] else Campaign.Status.COMPLETED
            self._finalize(status=status)
        return counts

    def refresh_metrics(self):
        stats = self.campaign.messages.aggregate(
            sent=Count('id', filter=Q(status=CampaignMessage.Status.SENT)),
            opened=Count('id', filter=Q(status=CampaignMessage.Status.OPENED)),
            clicked=Count('id', filter=Q(status=CampaignMessage.Status.CLICKED)),
        )
        metrics = self.campaign.metrics or {}
        metrics.update({k: stats.get(k, 0) for k in ('sent', 'opened', 'clicked')})
        Campaign.objects.filter(id=self.campaign.id).update(metrics=metrics, last_run_at=timezone.now())

    def _template_key(self, channel: str) -> str:
        mapping = {
            CampaignMessage.Channel.EMAIL: 'email_body',
            CampaignMessage.Channel.WHATSAPP: 'whatsapp_message',
            CampaignMessage.Channel.SMS: 'sms_text',
            CampaignMessage.Channel.FACEBOOK: 'social_post',
            CampaignMessage.Channel.INSTAGRAM: 'social_post',
            CampaignMessage.Channel.TWITTER: 'social_post',
        }
        return mapping.get(channel, 'email_body')

    def _variant_content(self, content: dict[str, Any], template_key: str, variant: CampaignVariant | None):
        if variant:
            return variant.channel_payload.get(template_key) or content.get(template_key)
        return content.get(template_key)

    def _resolve_channels(self, customer: Customer) -> list[str]:
        preferred = customer.preferred_channels or []
        enabled = [channel for channel, active in self.campaign.channels.items() if active]
        ordered = preferred + [ch for ch in enabled if ch not in preferred]
        deduped = []
        for ch in ordered:
            if ch not in enabled:
                continue
            if ch == CampaignMessage.Channel.WHATSAPP and not customer.phone_number:
                continue
            if ch == CampaignMessage.Channel.SMS and not customer.phone_number:
                continue
            if ch not in deduped:
                deduped.append(ch)
        return deduped

    def _fallback_channels(self, primary_channel: str, customer: Customer) -> list[str]:
        candidates = self._resolve_channels(customer)
        return [ch for ch in candidates if ch != primary_channel]

    def _personalize(self, template: str, customer: Customer) -> str:
        product = self.campaign.product
        replacements = {
            'first_name': customer.first_name or '',
            'last_name': customer.last_name or '',
            'full_name': f"{customer.first_name or ''} {customer.last_name or ''}".strip(),
            'product_name': product.name if product else '',
            'customer_email': customer.email,
        }
        content = template
        for key, value in replacements.items():
            content = content.replace(f'{{{{{key}}}}}', value)
        return content

    def _handle_failure(self, message: CampaignMessage, error: str):
        message.last_error = error[:500]
        can_retry = message.attempts < message.max_attempts
        message.status = CampaignMessage.Status.PENDING if can_retry else CampaignMessage.Status.FAILED
        message.save(update_fields=('status', 'last_error', 'updated_at'))
        CampaignLog.objects.create(
            campaign=self.campaign,
            message=message,
            action='Message failed',
            details=error,
        )
        if not can_retry:
            self._queue_fallback(message)

    def _handle_success(self, message: CampaignMessage, result: BulkMessenger.DispatchResult):
        message.status = result.status
        message.sent_at = timezone.now()
        message.external_id = result.external_id or message.external_id
        message.last_error = ''
        message.metadata = {**(message.metadata or {}), **result.metadata}
        message.save(update_fields=('status', 'sent_at', 'external_id', 'metadata', 'last_error', 'updated_at'))
        CampaignLog.objects.create(
            campaign=self.campaign,
            message=message,
            action='Message sent',
            metadata=result.metadata,
        )

    def _finalize(self, *, status: str):
        self.campaign.status = status
        self.campaign.save(update_fields=('status', 'updated_at', 'last_run_at'))
        detail = f"Metrics: {self.campaign.metrics}"
        self.notifications.notify_campaign_status(campaign=self.campaign, status=status, details=detail)

    def _queue_fallback(self, message: CampaignMessage):
        fallback_channels = message.metadata.get('fallback_channels') if message.metadata else []
        if not fallback_channels:
            return
        next_channel = fallback_channels[0]
        CampaignMessage.objects.get_or_create(
            campaign=self.campaign,
            customer=message.customer,
            channel=next_channel,
            defaults={
                'content': message.content,
                'status': CampaignMessage.Status.PENDING,
                'metadata': {
                    **(message.metadata or {}),
                    'fallback_channels': fallback_channels[1:],
                    'fallback_of': str(message.id),
                },
                'variant': message.variant,
            },
        )
        CampaignLog.objects.create(
            campaign=self.campaign,
            message=message,
            action='Fallback scheduled',
            metadata={'next_channel': next_channel},
        )


class SegmentationService:
    """Compute interest scores and auto-update segments."""

    def __init__(self, *, user: User):
        self.user = user

    def refresh_customer_scores(self, customer: Customer):
        events = customer.events.all()[:200]
        engagement = sum(1 for event in events if event.event_type in {CustomerEvent.EventType.EMAIL_OPEN, CustomerEvent.EventType.CLICK})
        interest = sum(float(event.payload.get('value', 1)) for event in events if event.event_type == CustomerEvent.EventType.PURCHASE)
        customer.engagement_score = min(100.0, engagement * 5)
        customer.interest_score = min(100.0, interest * 10)
        customer.churn_risk_score = max(0.0, 100.0 - customer.engagement_score * 0.5)
        customer.churn_predicted_at = timezone.now()
        customer.save(
            update_fields=(
                'engagement_score',
                'interest_score',
                'churn_risk_score',
                'churn_predicted_at',
                'updated_at',
            )
        )

    def auto_update_segments(self):
        segments = self.user.customer_segments.prefetch_related('tags')
        for segment in segments:
            matching = segment.apply_filters()
            metadata = {
                'customer_count': matching.count(),
                'avg_interest': matching.aggregate(avg=Avg('interest_score'))['avg'] or 0,
            }
            segment.metadata.update(metadata)
            segment.save(update_fields=('metadata', 'updated_at'))


class ChurnPredictionService:
    """Lightweight churn scoring using behavioral heuristics."""

    def __init__(self, *, user: User):
        self.user = user

    def rank_high_risk(self, *, limit: int = 10) -> list[Customer]:
        customers = list(
            Customer.objects.filter(user=self.user)
            .prefetch_related('events')
            .order_by('-updated_at')
        )
        if not customers:
            return []
        now = timezone.now()
        ranked: list[Customer] = []
        for customer in customers:
            recency_days = 0
            if customer.last_purchase_at:
                recency_days = max(0, (now - customer.last_purchase_at).days)
            engagement = customer.engagement_score or 0
            interest = customer.interest_score or 0
            purchase_value = float(customer.average_order_value or Decimal('0'))
            event_count = customer.events.filter(occurred_at__gte=now - timedelta(days=90)).count()
            # Simple heuristic-driven score (bounded 0-100)
            score = min(
                100.0,
                recency_days * 0.6 + (100 - min(engagement, 100)) * 0.3 + (50 - min(interest, 50)) + (5 - min(event_count, 5)) * 4,
            )
            if purchase_value < 10:
                score *= 0.9
            customer.churn_risk_score = round(score, 2)
            customer.churn_predicted_at = now
            customer.save(update_fields=('churn_risk_score', 'churn_predicted_at', 'updated_at'))
            ranked.append(customer)
        ranked.sort(key=lambda item: item.churn_risk_score, reverse=True)
        return ranked[:limit]


class CampaignAnalyticsService:
    """Provide optimization insights from historical campaigns."""

    def __init__(self, *, user: User):
        self.user = user

    def recommend_send_time(self) -> Optional[timezone.datetime]:
        qs = (
            Campaign.objects.filter(user=self.user, status=Campaign.Status.COMPLETED, last_run_at__isnull=False)
            .values('last_run_at', 'metrics')
            .order_by('-last_run_at')[:200]
        )
        if not qs:
            return None
        df = pd.DataFrame([
            {
                'hour': item['last_run_at'].astimezone(timezone.utc).hour,
                'sent': item['metrics'].get('sent', 0),
                'opened': item['metrics'].get('opened', 0),
                'clicked': item['metrics'].get('clicked', 0),
            }
            for item in qs
        ])
        df['open_rate'] = df.apply(lambda row: (row['opened'] / row['sent']) if row['sent'] else 0, axis=1)
        X = df[['hour']].values
        y = df['open_rate'].values
        model = LinearRegression().fit(X, y)
        best_hour = int(np.clip(np.argmax(model.predict(np.arange(0, 24).reshape(-1, 1))), 0, 23))
        recommended = timezone.now().replace(hour=best_hour, minute=0, second=0, microsecond=0)
        return recommended

    def update_campaign_metrics(self, campaign: Campaign):
        stats = campaign.messages.values('variant_id').annotate(
            sent=Count('id', filter=Q(status=CampaignMessage.Status.SENT)),
            opened=Count('id', filter=Q(status=CampaignMessage.Status.OPENED)),
            clicked=Count('id', filter=Q(status=CampaignMessage.Status.CLICKED)),
        )
        for row in stats:
            if not row['variant_id']:
                continue
            metrics = {
                'sent': row['sent'],
                'opened': row['opened'],
                'clicked': row['clicked'],
                'delivered': row['sent'],
                'conversions': 0,
            }
            CampaignVariant.objects.filter(id=row['variant_id']).update(metrics=metrics)

        winner = campaign.variants.order_by('-metrics__clicked', '-metrics__opened').first()
        if winner and not winner.is_winner:
            CampaignVariant.objects.filter(campaign=campaign).update(is_winner=False)
            winner.is_winner = True
            winner.save(update_fields=('is_winner', 'updated_at'))
            campaign.optimization_metadata['winner'] = winner.label
            campaign.save(update_fields=('optimization_metadata',))


class CampaignOptimizationService:
    """Generate AI-driven variants and suggestions."""

    def __init__(self, *, campaign: Campaign):
        self.campaign = campaign

    def generate_variants(self, *, count: int = 3, language_code: str | None = None) -> list[CampaignVariant]:
        if not self.campaign.product:
            raise ValueError('Campaign requires product for variant generation')
        generator = AIContentGenerator()
        payloads = generator.generate_campaign_variants(
            product=self.campaign.product,
            variant_count=count,
            language_code=language_code or self.campaign.language_code,
            segment_profile=self.campaign.segment.description if self.campaign.segment else None,
        )
        created: list[CampaignVariant] = []
        for variant_payload in payloads:
            variant, _ = CampaignVariant.objects.update_or_create(
                campaign=self.campaign,
                label=variant_payload['label'],
                defaults={'channel_payload': variant_payload, 'status': CampaignVariant.Status.EXPERIMENTAL},
            )
            created.append(variant)
        return created

    def create_suggestion(self, *, user: User):
        top_product = Product.objects.filter(user=user).order_by('-created_at').first()
        if not top_product:
            return None
        suggestion = AISuggestion.objects.create(
            user=user,
            suggestion_type=AISuggestion.SuggestionType.PRODUCT,
            payload={'product_id': str(top_product.id), 'campaign_id': str(self.campaign.id)},
            score=0.92,
        )
        return suggestion


class AISuggestionService:
    """Derive next-best actions across products, segments, and channels."""

    def __init__(self, *, user: User):
        self.user = user

    def generate(self) -> list[AISuggestion]:
        suggestions: list[AISuggestion] = []
        product = (
            Product.objects.filter(user=self.user)
            .annotate(recent_campaigns=Count('campaigns'))
            .order_by('-recent_campaigns', '-created_at')
            .first()
        )
        if product:
            suggestions.append(
                self._upsert(
                    suggestion_type=AISuggestion.SuggestionType.PRODUCT,
                    payload={'product_id': str(product.id), 'product_name': product.name},
                    score=0.85,
                )
            )
        segment = self.user.customer_segments.order_by('-metadata__customer_count', 'name').first()
        if segment:
            suggestions.append(
                self._upsert(
                    suggestion_type=AISuggestion.SuggestionType.SEGMENT,
                    payload={'segment_id': str(segment.id), 'segment_name': segment.name},
                    score=0.78,
                )
            )
        channel_stats = (
            CampaignMessage.objects.filter(campaign__user=self.user)
            .values('channel')
            .annotate(clicks=Count('id', filter=Q(status=CampaignMessage.Status.CLICKED)))
            .order_by('-clicks')
        )
        if channel_stats:
            top_channel = channel_stats[0]
            suggestions.append(
                self._upsert(
                    suggestion_type=AISuggestion.SuggestionType.CHANNEL,
                    payload={'channel': top_channel['channel'], 'clicks': top_channel['clicks']},
                    score=0.72,
                )
            )
        analytics = CampaignAnalyticsService(user=self.user)
        recommended_time = analytics.recommend_send_time()
        if recommended_time:
            suggestions.append(
                self._upsert(
                    suggestion_type=AISuggestion.SuggestionType.SCHEDULE,
                    payload={'recommended_time': recommended_time.isoformat()},
                    score=0.8,
                )
            )
        return suggestions

    def _upsert(self, *, suggestion_type: str, payload: dict[str, Any], score: float) -> AISuggestion:
        suggestion, _ = AISuggestion.objects.update_or_create(
            user=self.user,
            suggestion_type=suggestion_type,
            defaults={'payload': payload, 'score': round(score, 2), 'status': 'pending'},
        )
        return suggestion


class CampaignExecutionService:
    """Reusable workflow for campaign dispatch."""

    def __init__(self, *, campaign: Campaign, user: User):
        self.campaign = campaign
        self.user = user

    def dispatch(self, *, language_code: str | None = None, force: bool = False) -> dict[str, Any]:
        if not self.campaign.product:
            raise CampaignExecutionError('Campaign requires a linked product')
        language = language_code or self.campaign.language_code
        generator = AIContentGenerator()
        try:
            payload = generator.generate_campaign_assets(
                product=self.campaign.product,
                language_code=language,
                audience_notes=self.campaign.segment.description if self.campaign.segment else None,
            )
        except AIContentGeneratorError as exc:
            raise CampaignExecutionError(str(exc)) from exc

        Campaign.objects.filter(id=self.campaign.id).update(
            language_code=language,
            summary=payload.get('summary', self.campaign.summary),
            subject_line=payload.get('subject_line', self.campaign.subject_line),
            title=payload.get('title', self.campaign.title),
            hashtags=payload.get('hashtags', self.campaign.hashtags),
        )
        self.campaign.refresh_from_db()

        segmentation = SegmentationService(user=self.user)
        segmentation.auto_update_segments()

        customers_qs = (
            self.campaign.segment.apply_filters()
            if self.campaign.segment
            else Customer.objects.filter(user=self.user)
        )
        if not customers_qs.exists():
            raise CampaignExecutionError('No customers match this campaign')
        customers = list(customers_qs)

        optimization = CampaignOptimizationService(campaign=self.campaign)
        try:
            variants = optimization.generate_variants(
                count=getattr(settings, 'A_B_TEST_VARIANTS', 3),
                language_code=language,
            )
        except (ValueError, AIContentGeneratorError) as exc:
            variants = []
            LOGGER.warning('Variant generation skipped: %s', exc)

        orchestrator = CampaignOrchestrator(campaign=self.campaign)
        created = 0
        if variants:
            bucket_count = len(variants)
            for idx, variant in enumerate(variants):
                targeted = customers[idx::bucket_count]
                if not targeted:
                    continue
                created += orchestrator.build_messages(
                    customers=targeted,
                    content=variant.channel_payload,
                    variant=variant,
                )
        else:
            created = orchestrator.build_messages(customers=customers, content=payload)

        try:
            send_result = orchestrator.send_pending_messages(force=force)
        except ValueError as exc:
            raise CampaignExecutionError(str(exc)) from exc

        analytics = CampaignAnalyticsService(user=self.user)
        analytics.update_campaign_metrics(self.campaign)
        optimization.create_suggestion(user=self.user)

        return {'messages_created': created, **send_result, 'language_code': language}


class AutomationService:
    """Execute AutomationRule instances for a user."""

    FREQUENCY_WINDOWS = {
        '@hourly': timedelta(hours=1),
        '@daily': timedelta(days=1),
        '@weekly': timedelta(weeks=1),
    }

    def __init__(self, *, user: User):
        self.user = user

    def run(self):
        for rule in self.user.automation_rules.filter(is_active=True):
            if not self._is_due(rule):
                continue
            self.execute_rule(rule)

    def execute_rule(self, rule: AutomationRule):
        handlers = {
            AutomationRule.RuleType.CREATE_CAMPAIGN: self._handle_create_campaign,
            AutomationRule.RuleType.SCHEDULE_CAMPAIGN: self._handle_schedule_campaign,
            AutomationRule.RuleType.SEND_CAMPAIGN: self._handle_send_campaign,
        }
        handler = handlers.get(rule.rule_type)
        if not handler:
            return
        handler(rule)
        rule.last_run_at = timezone.now()
        rule.save(update_fields=('last_run_at', 'updated_at'))

    def _is_due(self, rule: AutomationRule) -> bool:
        if not rule.last_run_at:
            return True
        window = self.FREQUENCY_WINDOWS.get(rule.schedule_expression, timedelta(hours=1))
        return timezone.now() - rule.last_run_at >= window

    def _handle_create_campaign(self, rule: AutomationRule):
        config = rule.config or {}
        product_id = config.get('product_id')
        product = None
        if product_id:
            product = Product.objects.filter(id=product_id, user=self.user).first()
        if not product:
            product = Product.objects.filter(user=self.user).order_by('-created_at').first()
        if not product:
            return
        segment_id = config.get('segment_id')
        segment = None
        if segment_id:
            segment = self.user.customer_segments.filter(id=segment_id).first()
        name = config.get('name') or f"Auto {product.name} {timezone.now():%Y%m%d%H%M}"
        defaults = {
            'product': product,
            'segment': segment,
            'channels': config.get('channels') or {'email': True, 'whatsapp': True},
            'language_code': config.get('language_code', getattr(settings, 'DEFAULT_CAMPAIGN_LANGUAGE', 'en')),
            'summary': config.get('summary', '') or product.description[:240],
        }
        campaign, created = Campaign.objects.get_or_create(
            user=self.user,
            name=name,
            defaults=defaults,
        )
        if created:
            log_activity(user=self.user, action='Automation created campaign', metadata={'campaign_id': str(campaign.id)})

    def _handle_schedule_campaign(self, rule: AutomationRule):
        limit = int((rule.config or {}).get('limit', 3))
        campaigns = (
            self.user.campaigns.filter(status=Campaign.Status.DRAFT, scheduled_at__isnull=True)
            .order_by('created_at')[:limit]
        )
        analytics = CampaignAnalyticsService(user=self.user)
        recommended_time = analytics.recommend_send_time() or timezone.now() + timedelta(hours=1)
        for campaign in campaigns:
            campaign.scheduled_at = recommended_time
            campaign.timezone = self.user.customers.first().timezone if self.user.customers.exists() else 'UTC'
            campaign.status = Campaign.Status.SCHEDULED
            campaign.save(update_fields=('scheduled_at', 'timezone', 'status', 'updated_at'))
            log_activity(
                user=self.user,
                action='Automation scheduled campaign',
                metadata={'campaign_id': str(campaign.id)},
            )

    def _handle_send_campaign(self, rule: AutomationRule):
        limit = int((rule.config or {}).get('limit', 2))
        force = bool((rule.config or {}).get('force', False))
        campaigns = (
            self.user.campaigns.filter(
                status__in=[Campaign.Status.SCHEDULED, Campaign.Status.RUNNING],
                scheduled_at__lte=timezone.now(),
            )
            .order_by('scheduled_at')[:limit]
        )
        for campaign in campaigns:
            executor = CampaignExecutionService(campaign=campaign, user=self.user)
            try:
                result = executor.dispatch(force=force)
            except CampaignExecutionError as exc:
                LOGGER.warning('Automated send failed: %s', exc)
                continue
            log_activity(
                user=self.user,
                action='Automation dispatched campaign',
                metadata={'campaign_id': str(campaign.id), **result},
            )


class PaymentGatewayService:
    """Basic wrapper simulating payment intent creation."""

    def __init__(self, *, user: User):
        self.user = user

    def create_payment(
        self,
        *,
        campaign: Campaign,
        amount: Decimal,
        currency: str = 'USD',
        provider: str = 'stripe',
    ) -> CampaignPayment:
        payment = CampaignPayment.objects.create(
            campaign=campaign,
            provider=provider,
            amount=amount,
            currency=currency,
            metadata={'initiated_by': str(self.user.id)},
        )
        # Placeholder for real payment integration
        payment.transaction_id = f"{provider}-{payment.id}"
        payment.status = CampaignPayment.Status.AUTHORIZED
        payment.processed_at = timezone.now()
        payment.save(update_fields=('transaction_id', 'status', 'processed_at'))
        return payment

