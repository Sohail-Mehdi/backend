from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..models.models import (
    AIContentChannel,
    AIContentStatus,
    CampaignStatus,
    CampaignSuggestionStatus,
    CampaignVariantStatus,
    CampaignMessageChannel,
    CampaignMessageStatus,
    NotificationLevel,
    NotificationStatus,
    UserRole,
    AISuggestionType,
    AutomationRuleType,
    CampaignPaymentStatus,
)

# User Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: UserRole = UserRole.MANAGER

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class User(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: Dict[str, Any]

# AI Content Schemas
class AIContentBase(BaseModel):
    channel: AIContentChannel
    content_text: str
    status: AIContentStatus = AIContentStatus.GENERATED
    language_code: str = "en"

class AIContentCreate(AIContentBase):
    product_id: UUID

class AIContentUpdate(BaseModel):
    content_text: Optional[str] = None
    status: Optional[AIContentStatus] = None
    language_code: Optional[str] = None

class AIContent(AIContentBase):
    id: UUID
    product_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Product Schemas
class ProductBase(BaseModel):
    name: str
    description: str
    category: str
    price: Optional[Decimal] = None
    sku: Optional[str] = ""
    image_url: Optional[str] = ""
    attributes: Dict[str, Any] = {}

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    ai_contents: List[AIContent] = []

    model_config = ConfigDict(from_attributes=True)

# Customer Tag Schemas
class CustomerTagBase(BaseModel):
    name: str
    slug: str

class CustomerTagCreate(CustomerTagBase):
    pass

class CustomerTag(CustomerTagBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Customer Schemas
class CustomerBase(BaseModel):
    email: EmailStr
    phone_number: Optional[str] = ""
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    timezone: str = "UTC"
    preferred_language: str = "en"
    categories_of_interest: List[str] = []
    purchase_metadata: Dict[str, Any] = {}
    average_order_value: Decimal = Decimal("0.00")
    last_purchase_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    preferred_channels: List[str] = []
    recommended_products: List[str] = []
    interest_score: float = 0.0
    engagement_score: float = 0.0
    churn_risk_score: float = 0.0
    churn_predicted_at: Optional[datetime] = None

class CustomerCreate(CustomerBase):
    tag_ids: List[UUID] = []

class Customer(CustomerBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    tags: List[CustomerTag] = []

    model_config = ConfigDict(from_attributes=True)

# Segment Schemas
class CustomerSegmentBase(BaseModel):
    name: str
    description: Optional[str] = ""
    category_filters: List[str] = []
    behavior_filters: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}

class CustomerSegmentCreate(CustomerSegmentBase):
    tag_ids: List[UUID] = []

class CustomerSegment(CustomerSegmentBase):
    id: UUID
    user_id: UUID
    customer_count: int = 0
    created_at: datetime
    updated_at: datetime
    tags: List[CustomerTag] = []

    model_config = ConfigDict(from_attributes=True)

# Campaign Schemas
class CampaignBase(BaseModel):
    name: str
    title: Optional[str] = ""
    subject_line: Optional[str] = ""
    hashtags: List[str] = []
    summary: Optional[str] = ""
    language_code: str = "en"
    timezone: str = "UTC"
    scheduled_at: Optional[datetime] = None
    channels: Dict[str, bool]
    personalization: Dict[str, Any] = {}
    status: CampaignStatus = CampaignStatus.DRAFT
    metrics: Dict[str, Any] = {'sent': 0, 'opened': 0, 'clicked': 0, 'revenue': 0.0}
    product_id: Optional[UUID] = None
    segment_id: Optional[UUID] = None

class CampaignCreate(CampaignBase):
    pass

class Campaign(CampaignBase):
    id: UUID
    user_id: UUID
    product_name: Optional[str] = None
    segment_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CampaignScheduleSerializer(BaseModel):
    scheduled_at: datetime
    timezone: str = "UTC"

class CampaignSendSerializer(BaseModel):
    language_code: Optional[str] = None
    force: bool = False

# AI Suggestion Schemas
class AISuggestionBase(BaseModel):
    suggestion_type: AISuggestionType
    payload: Dict[str, Any]
    score: float = 0.0
    status: str = "pending"

class AISuggestion(AISuggestionBase):
    id: UUID
    created_at: datetime
    acted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# Notification Schemas
class NotificationBase(BaseModel):
    title: str
    body: str
    level: NotificationLevel = NotificationLevel.INFO
    status: NotificationStatus = NotificationStatus.PENDING

class Notification(NotificationBase):
    id: UUID
    created_at: datetime
    read_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# Automation Rule Schemas
class AutomationRuleBase(BaseModel):
    name: str
    description: Optional[str] = ""
    rule_type: AutomationRuleType
    config: Dict[str, Any] = {}
    schedule_expression: str = "@daily"
    is_active: bool = True

class AutomationRuleCreate(AutomationRuleBase):
    pass

class AutomationRule(AutomationRuleBase):
    id: UUID
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Payment Schemas
class CampaignPaymentBase(BaseModel):
    provider: str = "stripe"
    amount: Decimal
    currency: str = "USD"
    metadata: Dict[str, Any] = {}

class CampaignPaymentCreate(CampaignPaymentBase):
    campaign_id: UUID

class CampaignPayment(CampaignPaymentBase):
    id: UUID
    transaction_id: Optional[str] = None
    status: CampaignPaymentStatus
    processed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Dashboard Schemas
class DashboardSummary(BaseModel):
    products: int
    content_generated: int
    content_edited: int
    content_ready: int

class CampaignSummary(BaseModel):
    total: int
    status: Dict[str, int]
    messages: Dict[str, int]
    revenue: float
    top_campaigns: List[Dict[str, Any]]

class DashboardResponse(BaseModel):
    summary: DashboardSummary
    campaign_summary: CampaignSummary
    notifications: List[Notification]
    ai_suggestions: List[AISuggestion]
    churn_risk: List[Customer]
    automation_rules_active: int
    products: List[Product]
