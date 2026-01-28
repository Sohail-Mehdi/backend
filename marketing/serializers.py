"""DRF serializers for the marketing backend."""
from __future__ import annotations

from typing import Any, Optional

import phonenumbers
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
    ActivityLog,
    AIContent,
    AISuggestion,
    AutomationRule,
    Campaign,
    CampaignLog,
    CampaignMessage,
    CampaignPayment,
    CampaignSuggestion,
    CampaignVariant,
    Customer,
    CustomerEvent,
    CustomerSegment,
    CustomerTag,
    Notification,
    Product,
)

User = get_user_model()


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('id', 'name', 'email', 'password', 'role', 'created_at')
        read_only_fields = ('id', 'created_at')

    def create(self, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop('password')
        return User.objects.create_user(password=password, **validated_data)


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Customize token payload to include role and name."""

    @classmethod
    def get_token(cls, user):  # type: ignore[override]
        token = super().get_token(user)
        token['role'] = user.role
        token['name'] = user.name
        return token

    def validate(self, attrs):  # type: ignore[override]
        data = super().validate(attrs)
        data['user'] = {
            'id': str(self.user.id),
            'name': self.user.name,
            'email': self.user.email,
            'role': self.user.role,
        }
        return data


class AIContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIContent
        fields = (
            'id',
            'channel',
            'content_text',
            'status',
            'language_code',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class ProductSerializer(serializers.ModelSerializer):
    ai_contents = AIContentSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'description',
            'category',
            'price',
            'sku',
            'image_url',
            'attributes',
            'created_at',
            'ai_contents',
        )
        read_only_fields = ('id', 'created_at', 'ai_contents')


class AIContentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIContent
        fields = ('content_text', 'status', 'language_code')
        extra_kwargs = {
            'status': {'required': False},
            'content_text': {'required': False},
            'language_code': {'required': False},
        }


class DashboardProductSerializer(serializers.ModelSerializer):
    ai_contents = AIContentSerializer(many=True, read_only=True)
    latest_status = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'category',
            'created_at',
            'latest_status',
            'ai_contents',
        )

    def get_latest_status(self, obj: Product) -> str:
        latest_content = obj.ai_contents.order_by('-updated_at').first()
        return latest_content.status if latest_content else 'pending'


class ActivityLogSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = ('id', 'action', 'product_name', 'metadata', 'timestamp')

    def get_product_name(self, obj: ActivityLog) -> Optional[str]:
        return obj.product.name if obj.product else None


class CustomerTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerTag
        fields = ('id', 'name', 'slug', 'created_at')
        read_only_fields = ('id', 'created_at')


class CustomerSerializer(serializers.ModelSerializer):
    tags = CustomerTagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=CustomerTag.objects.none(),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Customer
        fields = (
            'id',
            'email',
            'phone_number',
            'first_name',
            'last_name',
            'timezone',
            'preferred_language',
            'categories_of_interest',
            'purchase_metadata',
            'average_order_value',
            'last_purchase_at',
            'metadata',
            'preferred_channels',
            'recommended_products',
            'interest_score',
            'engagement_score',
            'churn_risk_score',
            'churn_predicted_at',
            'tags',
            'tag_ids',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'tags', 'created_at', 'updated_at', 'churn_predicted_at')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context['request'].user if 'request' in self.context else None
        if user and hasattr(user, 'customer_tags'):
            self.fields['tag_ids'].queryset = CustomerTag.objects.filter(user=user)

    def validate_phone_number(self, value: str) -> str:
        if not value:
            return value
        try:
            parsed = phonenumbers.parse(value, None)
        except phonenumbers.NumberParseException as exc:
            raise serializers.ValidationError('Invalid phone number') from exc
        if not phonenumbers.is_valid_number(parsed):
            raise serializers.ValidationError('Invalid phone number')
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    def validate_preferred_language(self, value: str) -> str:
        allowed = getattr(settings, 'ALLOWED_CAMPAIGN_LANGUAGES', ['en'])
        if value not in allowed:
            raise serializers.ValidationError('Unsupported language code')
        return value

    def create(self, validated_data: dict[str, Any]) -> Customer:
        tag_ids = validated_data.pop('tag_ids', [])
        customer = Customer.objects.create(user=self.context['request'].user, **validated_data)
        if tag_ids:
            customer.tags.set(tag_ids)
        return customer

    def update(self, instance: Customer, validated_data: dict[str, Any]) -> Customer:
        tag_ids = validated_data.pop('tag_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        return instance


class CustomerSegmentSerializer(serializers.ModelSerializer):
    tags = CustomerTagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=CustomerTag.objects.none(),
        many=True,
        required=False,
        write_only=True,
    )
    customer_count = serializers.SerializerMethodField()

    class Meta:
        model = CustomerSegment
        fields = (
            'id',
            'name',
            'description',
            'category_filters',
            'behavior_filters',
            'metadata',
            'tags',
            'tag_ids',
            'customer_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'tags', 'customer_count', 'created_at', 'updated_at')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.context['request'].user if 'request' in self.context else None
        if user and hasattr(user, 'customer_tags'):
            self.fields['tag_ids'].queryset = CustomerTag.objects.filter(user=user)

    def get_customer_count(self, obj: CustomerSegment) -> int:
        return obj.apply_filters().count()

    def create(self, validated_data: dict[str, Any]) -> CustomerSegment:
        tag_ids = validated_data.pop('tag_ids', [])
        segment = CustomerSegment.objects.create(user=self.context['request'].user, **validated_data)
        if tag_ids:
            segment.tags.set(tag_ids)
        return segment

    def update(self, instance: CustomerSegment, validated_data: dict[str, Any]) -> CustomerSegment:
        tag_ids = validated_data.pop('tag_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        return instance


class CampaignSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSuggestion
        fields = ('id', 'payload', 'status', 'created_at', 'updated_at')
        read_only_fields = ('id', 'payload', 'created_at', 'updated_at')


class CampaignVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignVariant
        fields = (
            'id',
            'label',
            'channel_payload',
            'status',
            'metrics',
            'is_winner',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'metrics', 'is_winner', 'created_at', 'updated_at')


class CampaignSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    segment_name = serializers.CharField(source='segment.name', read_only=True)

    class Meta:
        model = Campaign
        fields = (
            'id',
            'name',
            'title',
            'subject_line',
            'hashtags',
            'summary',
            'language_code',
            'timezone',
            'scheduled_at',
            'channels',
            'personalization',
            'status',
            'metrics',
            'product',
            'product_name',
            'segment',
            'segment_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'status',
            'metrics',
            'created_at',
            'updated_at',
            'product_name',
            'segment_name',
        )

    def validate_channels(self, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise serializers.ValidationError('At least one channel is required')
        allowed = {'email', 'whatsapp', 'social'}
        unknown = set(value.keys()) - allowed
        if unknown:
            raise serializers.ValidationError(f'Unsupported channels: {", ".join(sorted(unknown))}')
        enabled = [channel for channel, enabled in value.items() if enabled]
        if not enabled:
            raise serializers.ValidationError('Please enable at least one channel')
        return {channel: bool(enabled) for channel, enabled in value.items()}

    def validate_language_code(self, value: str) -> str:
        allowed = getattr(settings, 'ALLOWED_CAMPAIGN_LANGUAGES', ['en'])
        if value not in allowed:
            raise serializers.ValidationError('Unsupported language code')
        return value

    def create(self, validated_data: dict[str, Any]) -> Campaign:
        return Campaign.objects.create(user=self.context['request'].user, **validated_data)


class CampaignDetailSerializer(CampaignSerializer):
    suggestions = CampaignSuggestionSerializer(many=True, read_only=True)
    variants = CampaignVariantSerializer(many=True, read_only=True)

    class Meta(CampaignSerializer.Meta):
        fields = CampaignSerializer.Meta.fields + ('suggestions', 'variants')


class CampaignScheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()
    timezone = serializers.CharField(max_length=64)


class CampaignSendSerializer(serializers.Serializer):
    language_code = serializers.CharField(max_length=8, required=False)
    force = serializers.BooleanField(required=False, default=False)

    def validate_language_code(self, value: str) -> str:
        if not value:
            return value
        allowed = getattr(settings, 'ALLOWED_CAMPAIGN_LANGUAGES', ['en'])
        if value not in allowed:
            raise serializers.ValidationError('Unsupported language code')
        return value


class CampaignMessageSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    variant_label = serializers.CharField(source='variant.label', read_only=True)

    class Meta:
        model = CampaignMessage
        fields = (
            'id',
            'customer_email',
            'channel',
            'content',
            'status',
            'attempts',
            'max_attempts',
            'last_error',
            'sent_at',
            'opened_at',
            'clicked_at',
            'metadata',
            'variant_label',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class CampaignLogSerializer(serializers.ModelSerializer):
    message_id = serializers.CharField(source='message.id', read_only=True)

    class Meta:
        model = CampaignLog
        fields = ('id', 'action', 'details', 'metadata', 'message_id', 'created_at')
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'title', 'body', 'level', 'status', 'created_at', 'read_at')
        read_only_fields = fields


class CustomerEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerEvent
        fields = ('id', 'event_type', 'payload', 'occurred_at')
        read_only_fields = ('id', 'occurred_at')


class AISuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISuggestion
        fields = (
            'id',
            'suggestion_type',
            'payload',
            'score',
            'status',
            'created_at',
            'acted_at',
        )
        read_only_fields = ('id', 'score', 'created_at', 'acted_at')


class AutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRule
        fields = (
            'id',
            'name',
            'description',
            'rule_type',
            'config',
            'schedule_expression',
            'is_active',
            'last_run_at',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'last_run_at', 'created_at', 'updated_at')


class CampaignPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignPayment
        fields = (
            'id',
            'campaign',
            'provider',
            'amount',
            'currency',
            'transaction_id',
            'status',
            'metadata',
            'processed_at',
            'created_at',
        )
        read_only_fields = ('id', 'transaction_id', 'status', 'processed_at', 'created_at', 'campaign')
