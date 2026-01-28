"""Database models for the AI Marketing Tool backend."""
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def empty_dict():
    return {}


def empty_list():
    return []


def default_metrics():
    return {'sent': 0, 'opened': 0, 'clicked': 0, 'revenue': 0.0}


def default_max_attempts():
    return getattr(settings, 'CAMPAIGN_MAX_RETRIES', 3)


def default_variant_metrics():
    return {
        'sent': 0,
        'delivered': 0,
        'opened': 0,
        'clicked': 0,
        'conversions': 0,
    }


class UserManager(BaseUserManager):
    """Manager for custom user model that authenticates with email."""

    def create_user(self, email: str, password: Optional[str] = None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        extra_fields.setdefault('role', User.Role.MANAGER)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Primary user record supporting role-based access."""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        MANAGER = 'manager', 'Marketing Manager'
        ANALYST = 'analyst', 'Analyst'
        STORE_OWNER = 'store', 'Store Owner'
        AGENCY = 'agency', 'Agency'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MANAGER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'role']

    objects = UserManager()

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"{self.email} ({self.get_role_display()})"


class Product(models.Model):
    """Store products for which marketing content will be generated."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=180)
    description = models.TextField()
    category = models.CharField(max_length=120)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    sku = models.CharField(max_length=64, blank=True)
    image_url = models.URLField(blank=True)
    attributes = models.JSONField(default=empty_dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"{self.name} ({self.user.email})"


class AIContent(models.Model):
    """AI-generated marketing content for each digital channel."""

    class Channel(models.TextChoices):
        SOCIAL = 'social', 'Social Media'
        EMAIL = 'email', 'Email'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    class Status(models.TextChoices):
        GENERATED = 'generated', 'Generated'
        EDITED = 'edited', 'Edited'
        READY = 'ready', 'Ready'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        related_name='ai_contents',
        on_delete=models.CASCADE,
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    content_text = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.GENERATED,
    )
    language_code = models.CharField(max_length=8, default='en')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        unique_together = ('product', 'channel')

    def __str__(self) -> str:
        return f"{self.product.name} [{self.channel}]"


class ActivityLog(models.Model):
    """Audit log for user-triggered actions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='activity_logs', on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    product = models.ForeignKey(
        Product,
        related_name='activity_logs',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    metadata = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-timestamp',)

    def __str__(self) -> str:
        return f"{self.action} by {self.user.email}"


class CustomerTag(models.Model):
    """Lightweight tagging for customer segmentation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='customer_tags', on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'slug')
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name


class Customer(models.Model):
    """End customers receiving marketing campaigns."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='customers', on_delete=models.CASCADE)
    email = models.EmailField()
    phone_number = models.CharField(max_length=32, blank=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    timezone = models.CharField(max_length=64, default='UTC')
    preferred_language = models.CharField(max_length=8, default='en')
    categories_of_interest = models.JSONField(default=empty_list, blank=True)
    purchase_metadata = models.JSONField(default=empty_dict, blank=True)
    average_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    last_purchase_at = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField(CustomerTag, related_name='customers', blank=True)
    metadata = models.JSONField(default=empty_dict, blank=True)
    preferred_channels = models.JSONField(default=empty_list, blank=True)
    recommended_products = models.JSONField(default=empty_list, blank=True)
    interest_score = models.FloatField(default=0.0)
    engagement_score = models.FloatField(default=0.0)
    churn_risk_score = models.FloatField(default=0.0)
    churn_predicted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        unique_together = ('user', 'email')

    def __str__(self) -> str:
        return self.email


class CustomerSegment(models.Model):
    """Dynamic segment definitions for targeting."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='customer_segments', on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    category_filters = models.JSONField(default=empty_list, blank=True)
    behavior_filters = models.JSONField(default=empty_dict, blank=True)
    metadata = models.JSONField(default=empty_dict, blank=True)
    tags = models.ManyToManyField(CustomerTag, related_name='segments', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        unique_together = ('user', 'name')

    def __str__(self) -> str:
        return self.name

    def apply_filters(self, queryset=None):
        queryset = queryset or Customer.objects.filter(user=self.user)
        categories = self.category_filters or []
        if categories:
            for category in categories:
                queryset = queryset.filter(categories_of_interest__contains=[category])

        behavior = self.behavior_filters or {}
        min_value = behavior.get('min_average_order_value')
        if min_value is not None:
            queryset = queryset.filter(average_order_value__gte=min_value)
        recent_days = behavior.get('purchased_within_days')
        if recent_days:
            cutoff = timezone.now() - timedelta(days=recent_days)
            queryset = queryset.filter(last_purchase_at__gte=cutoff)

        tag_ids = list(self.tags.values_list('id', flat=True))
        if tag_ids:
            queryset = queryset.filter(tags__in=tag_ids).distinct()

        return queryset.distinct()


class CustomerEvent(models.Model):
    """Behavioral events driving AI-powered segmentation."""

    class EventType(models.TextChoices):
        PURCHASE = 'purchase', 'Purchase'
        BROWSE = 'browse', 'Browsing Session'
        CART = 'cart', 'Cart Event'
        EMAIL_OPEN = 'email_open', 'Email Open'
        CLICK = 'click', 'Click-through'
        WHATSAPP_REPLY = 'whatsapp_reply', 'WhatsApp Reply'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, related_name='events', on_delete=models.CASCADE)
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    payload = models.JSONField(default=empty_dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('-occurred_at',)

    def __str__(self) -> str:
        return f"{self.customer.email} - {self.event_type}"


class Campaign(models.Model):
    """Marketing campaigns with scheduling + AI metadata."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='campaigns', on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product,
        related_name='campaigns',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    segment = models.ForeignKey(
        CustomerSegment,
        related_name='campaigns',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=160)
    title = models.CharField(max_length=180, blank=True)
    subject_line = models.CharField(max_length=180, blank=True)
    hashtags = models.JSONField(default=empty_list, blank=True)
    summary = models.TextField(blank=True)
    language_code = models.CharField(max_length=8, default='en')
    timezone = models.CharField(max_length=64, default='UTC')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    channels = models.JSONField(default=empty_dict)
    personalization = models.JSONField(default=empty_dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    metrics = models.JSONField(default=default_metrics)
    recommended_send_time = models.DateTimeField(null=True, blank=True)
    optimization_metadata = models.JSONField(default=empty_dict, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return self.name


class CampaignSuggestion(models.Model):
    """AI-generated campaign suggestions awaiting approval."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, related_name='suggestions', on_delete=models.CASCADE)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"Suggestion for {self.campaign.name}"


class CampaignVariant(models.Model):
    """AI-generated content variations for A/B tests."""

    class Status(models.TextChoices):
        EXPERIMENTAL = 'experimental', 'Experimental'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, related_name='variants', on_delete=models.CASCADE)
    label = models.CharField(max_length=80)
    channel_payload = models.JSONField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.EXPERIMENTAL)
    metrics = models.JSONField(default=default_variant_metrics)
    is_winner = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        unique_together = ('campaign', 'label')

    def __str__(self) -> str:
        return f"{self.campaign.name}::{self.label}"


class CampaignMessage(models.Model):
    """Per-recipient message delivery records."""

    class Channel(models.TextChoices):
        EMAIL = 'email', 'Email'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        SMS = 'sms', 'SMS'
        FACEBOOK = 'facebook', 'Facebook'
        INSTAGRAM = 'instagram', 'Instagram'
        TWITTER = 'twitter', 'Twitter'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SCHEDULED = 'scheduled', 'Scheduled'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        OPENED = 'opened', 'Opened'
        CLICKED = 'clicked', 'Clicked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, related_name='messages', on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, related_name='messages', on_delete=models.CASCADE)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    content = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=default_max_attempts)
    last_error = models.TextField(blank=True)
    external_id = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=empty_dict, blank=True)
    variant = models.ForeignKey(
        'CampaignVariant',
        related_name='messages',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('campaign', 'status')),
        ]

    def __str__(self) -> str:
        return f"{self.campaign.name} -> {self.customer.email} ({self.channel})"


class CampaignLog(models.Model):
    """Trace campaign lifecycle events and retries."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, related_name='logs', on_delete=models.CASCADE)
    message = models.ForeignKey(
        CampaignMessage,
        related_name='logs',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    metadata = models.JSONField(default=empty_dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"{self.action} ({self.campaign.name})"


class Notification(models.Model):
    """Dashboard + email notifications."""

    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        SUCCESS = 'success', 'Success'
        WARNING = 'warning', 'Warning'
        ERROR = 'error', 'Error'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        READ = 'read', 'Read'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    body = models.TextField()
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def mark_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            self.status = Notification.Status.READ
            self.save(update_fields=('read_at', 'status'))

    def __str__(self) -> str:
        return f"{self.title} ({self.level})"


class AISuggestion(models.Model):
    """AI-driven recommendations for next-best actions."""

    class SuggestionType(models.TextChoices):
        PRODUCT = 'product', 'Product Promotion'
        SEGMENT = 'segment', 'Segment Targeting'
        SCHEDULE = 'schedule', 'Scheduling'
        CHANNEL = 'channel', 'Channel Optimization'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='ai_suggestions', on_delete=models.CASCADE)
    suggestion_type = models.CharField(max_length=20, choices=SuggestionType.choices)
    payload = models.JSONField()
    score = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    acted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"{self.get_suggestion_type_display()} ({self.score:.2f})"


class AutomationRule(models.Model):
    """Declarative automation rules for campaign workflows."""

    class RuleType(models.TextChoices):
        CREATE_CAMPAIGN = 'create_campaign', 'Create Campaign'
        SCHEDULE_CAMPAIGN = 'schedule_campaign', 'Schedule Campaign'
        SEND_CAMPAIGN = 'send_campaign', 'Send Campaign'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='automation_rules', on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    rule_type = models.CharField(max_length=40, choices=RuleType.choices)
    config = models.JSONField(default=empty_dict, blank=True)
    schedule_expression = models.CharField(max_length=120, default='@daily')
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        unique_together = ('user', 'name')

    def __str__(self) -> str:
        return f"{self.name} ({self.rule_type})"


class CampaignPayment(models.Model):
    """Record payment intents for paid marketing campaigns."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        AUTHORIZED = 'authorized', 'Authorized'
        SETTLED = 'settled', 'Settled'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, related_name='payments', on_delete=models.CASCADE)
    provider = models.CharField(max_length=80, default='stripe')
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    currency = models.CharField(max_length=8, default='USD')
    transaction_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    metadata = models.JSONField(default=empty_dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"{self.campaign.name} [{self.status}]"
