import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Float,
    Integer,
    JSON,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db.session import Base

# Many-to-Many association tables
customer_tags = Table(
    'marketing_customer_tags',
    Base.metadata,
    Column('customer_id', CHAR(36), ForeignKey('marketing_customer.id'), primary_key=True),
    Column('customertag_id', CHAR(36), ForeignKey('marketing_customertag.id'), primary_key=True)
)

segment_tags = Table(
    'marketing_customersegment_tags',
    Base.metadata,
    Column('customersegment_id', CHAR(36), ForeignKey('marketing_customersegment.id'), primary_key=True),
    Column('customertag_id', CHAR(36), ForeignKey('marketing_customertag.id'), primary_key=True)
)

class UserRole(str, Enum):
    ADMIN = 'admin'
    MANAGER = 'manager'
    ANALYST = 'analyst'
    STORE_OWNER = 'store'
    AGENCY = 'agency'

class User(Base):
    __tablename__ = "marketing_user"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(120), nullable=False)
    email = Column(String(191), unique=True, index=True, nullable=False)
    password = Column(String(128), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.MANAGER)
    is_active = Column(Boolean, default=True)
    is_staff = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="user")
    campaigns = relationship("Campaign", back_populates="user")
    activity_logs = relationship("ActivityLog", back_populates="user")
    customer_tags = relationship("CustomerTag", back_populates="user")
    customer_segments = relationship("CustomerSegment", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    ai_suggestions = relationship("AISuggestion", back_populates="user")
    automation_rules = relationship("AutomationRule", back_populates="user")

class Product(Base):
    __tablename__ = "marketing_product"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("marketing_user.id"), nullable=False)
    name = Column(String(180), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(120), nullable=False)
    price = Column(Numeric(10, 2), nullable=True)
    sku = Column(String(64), nullable=True)
    image_url = Column(String(255), nullable=True)
    attributes = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="products")
    ai_contents = relationship("AIContent", back_populates="product", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="campaigns") # Wait, this should match User relationship or be separate?
    # Actually Campaign model has product_id and product relationship. Let's fix.
    campaigns_rel = relationship("Campaign", back_populates="product")
    activity_logs = relationship("ActivityLog", back_populates="product")

class AIContentChannel(str, Enum):
    SOCIAL = 'social'
    EMAIL = 'email'
    WHATSAPP = 'whatsapp'

class AIContentStatus(str, Enum):
    GENERATED = 'generated'
    EDITED = 'edited'
    READY = 'ready'

class AIContent(Base):
    __tablename__ = "marketing_aicontent"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(CHAR(36), ForeignKey("marketing_product.id"), nullable=False)
    channel = Column(SQLEnum(AIContentChannel), nullable=False)
    content_text = Column(Text, nullable=False)
    status = Column(SQLEnum(AIContentStatus), default=AIContentStatus.GENERATED)
    language_code = Column(String(8), default='en')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="ai_contents")

class ActivityLog(Base):
    __tablename__ = "marketing_activitylog"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("marketing_user.id"), nullable=False)
    action = Column(String(255), nullable=False)
    product_id = Column(CHAR(36), ForeignKey("marketing_product.id"), nullable=True)
    metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="activity_logs")
    product = relationship("Product", back_populates="activity_logs")

class CustomerTag(Base):
    __tablename__ = "marketing_customertag"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("marketing_user.id"), nullable=False)
    name = Column(String(80), nullable=False)
    slug = Column(String(80), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="customer_tags")

class Customer(Base):
    __tablename__ = "marketing_customer"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("marketing_user.id"), nullable=False)
    email = Column(String(191), nullable=False)
    phone_number = Column(String(32), nullable=True)
    first_name = Column(String(80), nullable=True)
    last_name = Column(String(80), nullable=True)
    timezone = Column(String(64), default='UTC')
    preferred_language = Column(String(8), default='en')
    categories_of_interest = Column(JSON, default=list)
    purchase_metadata = Column(JSON, default=dict)
    average_order_value = Column(Numeric(10, 2), default=0.00)
    last_purchase_at = Column(DateTime, nullable=True)
    metadata = Column(JSON, default=dict)
    preferred_channels = Column(JSON, default=list)
    recommended_products = Column(JSON, default=list)
    interest_score = Column(Float, default=0.0)
    engagement_score = Column(Float, default=0.0)
    churn_risk_score = Column(Float, default=0.0)
    churn_predicted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="customers")
    tags = relationship("CustomerTag", secondary=customer_tags, backref="customers")
    messages = relationship("CampaignMessage", back_populates="customer")
    events = relationship("CustomerEvent", back_populates="customer")

class CustomerSegment(Base):
    __tablename__ = "marketing_customersegment"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("marketing_user.id"), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    category_filters = Column(JSON, default=list)
    behavior_filters = Column(JSON, default=dict)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="customer_segments")
    tags = relationship("CustomerTag", secondary=segment_tags, backref="segments")
    campaigns = relationship("Campaign", back_populates="segment")

class CustomerEventType(str, Enum):
    PURCHASE = 'purchase'
    BROWSE = 'browse'
    CART = 'cart'
    EMAIL_OPEN = 'email_open'
    CLICK = 'click'
    WHATSAPP_REPLY = 'whatsapp_reply'

class CustomerEvent(Base):
    __tablename__ = "marketing_customerevent"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(CHAR(36), ForeignKey("marketing_customer.id"), nullable=False)
    event_type = Column(String(32), nullable=False)
    payload = Column(JSON, default=dict)
    occurred_at = Column(DateTime, server_default=func.now())

    customer = relationship("Customer", back_populates="events")

class CampaignStatus(str, Enum):
    DRAFT = 'draft'
    SCHEDULED = 'scheduled'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'

class Campaign(Base):
    __tablename__ = "marketing_campaign"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("marketing_user.id"), nullable=False)
    product_id = Column(CHAR(36), ForeignKey("marketing_product.id"), nullable=True)
    segment_id = Column(CHAR(36), ForeignKey("marketing_customersegment.id"), nullable=True)
    name = Column(String(160), nullable=False)
    title = Column(String(180), nullable=True)
    subject_line = Column(String(180), nullable=True)
    hashtags = Column(JSON, default=list)
    summary = Column(Text, nullable=True)
    language_code = Column(String(8), default='en')
    timezone = Column(String(64), default='UTC')
    scheduled_at = Column(DateTime, nullable=True)
    channels = Column(JSON, nullable=False)
    personalization = Column(JSON, default=dict)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT)
    metrics = Column(JSON, default=lambda: {'sent': 0, 'opened': 0, 'clicked': 0, 'revenue': 0.0})
    recommended_send_time = Column(DateTime, nullable=True)
    optimization_metadata = Column(JSON, default=dict)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="campaigns")
    product = relationship("Product", back_populates="campaigns_rel")
    segment = relationship("CustomerSegment", back_populates="campaigns")
    suggestions = relationship("CampaignSuggestion", back_populates="campaign")
    variants = relationship("CampaignVariant", back_populates="campaign")
    messages = relationship("CampaignMessage", back_populates="campaign")
    logs = relationship("CampaignLog", back_populates="campaign")

class CampaignSuggestionStatus(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class CampaignSuggestion(Base):
    __tablename__ = "marketing_campaignsuggestion"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(CHAR(36), ForeignKey("marketing_campaign.id"), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(SQLEnum(CampaignSuggestionStatus), default=CampaignSuggestionStatus.PENDING)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    campaign = relationship("Campaign", back_populates="suggestions")

class CampaignVariantStatus(str, Enum):
    EXPERIMENTAL = 'experimental'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'

class CampaignVariant(Base):
    __tablename__ = "marketing_campaignvariant"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(CHAR(36), ForeignKey("marketing_campaign.id"), nullable=False)
    label = Column(String(80), nullable=False)
    channel_payload = Column(JSON, nullable=False)
    status = Column(SQLEnum(CampaignVariantStatus), default=CampaignVariantStatus.EXPERIMENTAL)
    metrics = Column(JSON, default=lambda: {'sent': 0, 'delivered': 0, 'opened': 0, 'clicked': 0, 'conversions': 0})
    is_winner = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    campaign = relationship("Campaign", back_populates="variants")

class CampaignMessageChannel(str, Enum):
    EMAIL = 'email'
    WHATSAPP = 'whatsapp'
    SMS = 'sms'
    FACEBOOK = 'facebook'
    INSTAGRAM = 'instagram'
    TWITTER = 'twitter'

class CampaignMessageStatus(str, Enum):
    PENDING = 'pending'
    SCHEDULED = 'scheduled'
    SENDING = 'sending'
    SENT = 'sent'
    FAILED = 'failed'
    OPENED = 'opened'
    CLICKED = 'clicked'

class CampaignMessage(Base):
    __tablename__ = "marketing_campaignmessage"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(CHAR(36), ForeignKey("marketing_campaign.id"), nullable=False)
    customer_id = Column(CHAR(36), ForeignKey("marketing_customer.id"), nullable=False)
    channel = Column(SQLEnum(CampaignMessageChannel), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(SQLEnum(CampaignMessageStatus), default=CampaignMessageStatus.PENDING)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    last_error = Column(Text, nullable=True)
    external_id = Column(String(120), nullable=True)
    metadata = Column(JSON, default=dict)
    variant_id = Column(CHAR(36), ForeignKey("marketing_campaignvariant.id"), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    campaign = relationship("Campaign", back_populates="messages")
    customer = relationship("Customer", back_populates="messages")

class CampaignLog(Base):
    __tablename__ = "marketing_campaignlog"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(CHAR(36), ForeignKey("marketing_campaign.id"), nullable=False)
    message_id = Column(CHAR(36), ForeignKey("marketing_campaignmessage.id"), nullable=True)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())

    campaign = relationship("Campaign", back_populates="logs")

class NotificationLevel(str, Enum):
    INFO = 'info'
    SUCCESS = 'success'
    WARNING = 'warning'
    ERROR = 'error'

class NotificationStatus(str, Enum):
    PENDING = 'pending'
    SENT = 'sent'
    READ = 'read'

class Notification(Base):
    __tablename__ = "marketing_notification"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("marketing_user.id"), nullable=False)
    title = Column(String(160), nullable=False)
    body = Column(Text, nullable=False)
    level = Column(SQLEnum(NotificationLevel), default=NotificationLevel.INFO)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    created_at = Column(DateTime, server_default=func.now())
    read_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="notifications")

class AISuggestionType(str, Enum):
    PRODUCT = 'product'
    SEGMENT = 'segment'
    SCHEDULE = 'schedule'
    CHANNEL = 'channel'

class AISuggestion(Base):
    __tablename__ = "marketing_aisuggestion"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("marketing_user.id"), nullable=False)
    suggestion_type = Column(SQLEnum(AISuggestionType), nullable=False)
    payload = Column(JSON, nullable=False)
    score = Column(Float, default=0.0)
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, server_default=func.now())
    acted_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="ai_suggestions")

class AutomationRuleType(str, Enum):
    CREATE_CAMPAIGN = 'create_campaign'
    SCHEDULE_CAMPAIGN = 'schedule_campaign'
    SEND_CAMPAIGN = 'send_campaign'

class AutomationRule(Base):
    __tablename__ = "marketing_automationrule"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey("marketing_user.id"), nullable=False)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    rule_type = Column(SQLEnum(AutomationRuleType), nullable=False)
    config = Column(JSON, default=dict)
    schedule_expression = Column(String(120), default='@daily')
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="automation_rules")

class CampaignPaymentStatus(str, Enum):
    PENDING = 'pending'
    AUTHORIZED = 'authorized'
    SETTLED = 'settled'
    FAILED = 'failed'
    REFUNDED = 'refunded'

class CampaignPayment(Base):
    __tablename__ = "marketing_campaignpayment"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(CHAR(36), ForeignKey("marketing_campaign.id"), nullable=False)
    provider = Column(String(80), default='stripe')
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), default='USD')
    transaction_id = Column(String(120), nullable=True)
    status = Column(SQLEnum(CampaignPaymentStatus), default=CampaignPaymentStatus.PENDING)
    metadata = Column(JSON, default=dict)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    campaign = relationship("Campaign", back_populates="payments")

def init_models():
    # This can be used to ensure all models are registered
    pass
