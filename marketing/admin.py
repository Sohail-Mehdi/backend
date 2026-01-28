"""Admin registrations for marketing app."""
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    AIContent,
    AISuggestion,
    ActivityLog,
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
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ('-created_at',)
    list_display = ('email', 'name', 'role', 'is_active', 'created_at')
    search_fields = ('email', 'name')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile', {'fields': ('name', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password1', 'password2'),
        }),
    )
    readonly_fields = ('created_at',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'user', 'created_at')
    search_fields = ('name', 'category', 'user__email')
    list_filter = ('category',)


@admin.register(AIContent)
class AIContentAdmin(admin.ModelAdmin):
    list_display = ('product', 'channel', 'status', 'language_code', 'updated_at')
    list_filter = ('channel', 'status', 'language_code')
    search_fields = ('product__name',)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'product', 'timestamp')
    search_fields = ('action', 'user__email')
    list_filter = ('action',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('email', 'user', 'preferred_language', 'timezone', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('preferred_language',)
    filter_horizontal = ('tags',)


@admin.register(CustomerSegment)
class CustomerSegmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('tags',)


@admin.register(CustomerTag)
class CustomerTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'user')
    search_fields = ('name', 'slug')


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'scheduled_at', 'recommended_send_time', 'user', 'updated_at')
    list_filter = ('status', 'language_code')
    search_fields = ('name', 'title')


@admin.register(CampaignMessage)
class CampaignMessageAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'customer', 'channel', 'status', 'attempts', 'created_at')
    list_filter = ('channel', 'status')
    search_fields = ('campaign__name', 'customer__email')


@admin.register(CampaignSuggestion)
class CampaignSuggestionAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(CampaignVariant)
class CampaignVariantAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'label', 'status', 'is_winner', 'created_at')
    list_filter = ('status', 'is_winner')
    search_fields = ('campaign__name', 'label')


@admin.register(CampaignPayment)
class CampaignPaymentAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'provider', 'amount', 'currency', 'status', 'processed_at')
    list_filter = ('provider', 'status')
    search_fields = ('campaign__name', 'transaction_id')


@admin.register(CampaignLog)
class CampaignLogAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'action', 'created_at')
    search_fields = ('campaign__name', 'action')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'level', 'status', 'created_at')
    list_filter = ('level', 'status')
    search_fields = ('title', 'user__email')


@admin.register(CustomerEvent)
class CustomerEventAdmin(admin.ModelAdmin):
    list_display = ('customer', 'event_type', 'occurred_at')
    list_filter = ('event_type',)
    search_fields = ('customer__email',)


@admin.register(AISuggestion)
class AISuggestionAdmin(admin.ModelAdmin):
    list_display = ('user', 'suggestion_type', 'score', 'status', 'created_at')
    list_filter = ('suggestion_type', 'status')
    search_fields = ('user__email',)


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'rule_type', 'is_active', 'schedule_expression', 'user', 'last_run_at')
    list_filter = ('rule_type', 'is_active')
    search_fields = ('name', 'user__email')
