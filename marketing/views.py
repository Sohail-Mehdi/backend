"""API views for the marketing backend."""
from __future__ import annotations

import csv
import io
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .ai_engine import AIContentGenerator, AIContentGeneratorError
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
    Notification,
    Product,
    User,
)
from .serializers import (
    ActivityLogSerializer,
    AIContentSerializer,
    AIContentUpdateSerializer,
    AutomationRuleSerializer,
    CampaignDetailSerializer,
    CampaignLogSerializer,
    CampaignMessageSerializer,
    CampaignPaymentSerializer,
    CampaignVariantSerializer,
    CampaignScheduleSerializer,
    CampaignSendSerializer,
    CampaignSerializer,
    CampaignSuggestionSerializer,
    CustomerEventSerializer,
    CustomerSegmentSerializer,
    CustomerSerializer,
    DashboardProductSerializer,
    EmailTokenObtainPairSerializer,
    AISuggestionSerializer,
    NotificationSerializer,
    ProductSerializer,
    SignupSerializer,
)
from .services import (
    AISuggestionService,
    AutomationService,
    CampaignAnalyticsService,
    CampaignExecutionError,
    CampaignExecutionService,
    CampaignOptimizationService,
    CampaignOrchestrator,
    ChurnPredictionService,
    CustomerImportService,
    PaymentGatewayService,
    SegmentationService,
    log_activity,
)


LOGGER = logging.getLogger(__name__)


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'user': serializer.data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainPairSerializer


class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Product.objects.filter(user=self.request.user)
            .prefetch_related('ai_contents')
            .order_by('-created_at')
        )
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(category__icontains=search)
            )
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__iexact=category)
        return queryset

    def perform_create(self, serializer):
        product = serializer.save(user=self.request.user)
        log_activity(
            user=self.request.user,
            action='Product uploaded',
            product=product,
        )


class GenerateProductContentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id, user=request.user)
        generator = AIContentGenerator()
        try:
            language_code = (
                request.data.get('language_code')
                or request.query_params.get('language_code')
                or getattr(settings, 'DEFAULT_CAMPAIGN_LANGUAGE', 'en')
            )
            channel_payload = generator.generate_product_content(
                product=product,
                language_code=language_code,
            )
        except AIContentGeneratorError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        saved_contents: list[AIContent] = []
        with transaction.atomic():
            for channel, content_text in channel_payload.items():
                content_obj, _ = AIContent.objects.update_or_create(
                    product=product,
                    channel=channel,
                    defaults={
                        'content_text': content_text,
                        'status': AIContent.Status.GENERATED,
                        'language_code': language_code,
                    },
                )
                saved_contents.append(content_obj)

        log_activity(
            user=request.user,
            action='AI content generated',
            product=product,
            metadata={'channels': list(channel_payload.keys()), 'language_code': language_code},
        )
        serializer = AIContentSerializer(saved_contents, many=True)
        return Response(
            {
                'product_id': str(product.id),
                'contents': serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class ProductContentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, product_id):
        product = get_object_or_404(Product, id=product_id, user=request.user)
        serializer = AIContentSerializer(product.ai_contents.all(), many=True)
        return Response(
            {
                'product_id': str(product.id),
                'contents': serializer.data,
            }
        )


class ContentUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, product_id, content_id):
        product = get_object_or_404(Product, id=product_id, user=request.user)
        content = get_object_or_404(AIContent, id=content_id, product=product)
        serializer = AIContentUpdateSerializer(content, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data.get('status') or AIContent.Status.EDITED
        serializer.save(status=new_status)
        log_activity(
            user=request.user,
            action='AI content updated',
            product=product,
            metadata={'content_id': str(content.id), 'status': new_status},
        )
        refreshed = AIContentSerializer(content)
        return Response(refreshed.data)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def get(self, request):
        products = (
            Product.objects.filter(user=request.user)
            .prefetch_related('ai_contents')
            .order_by('-created_at')
        )
        serializer = DashboardProductSerializer(products, many=True)
        status_breakdown = (
            AIContent.objects.filter(product__user=request.user)
            .values('status')
            .annotate(total=Count('id'))
        )
        summary = {item['status']: item['total'] for item in status_breakdown}
        campaigns = Campaign.objects.filter(user=request.user)
        campaign_breakdown = campaigns.values('status').annotate(total=Count('id'))
        message_metrics = (
            CampaignMessage.objects.filter(campaign__user=request.user)
            .aggregate(
                sent=Count('id', filter=Q(status=CampaignMessage.Status.SENT)),
                opened=Count('id', filter=Q(status=CampaignMessage.Status.OPENED)),
                clicked=Count('id', filter=Q(status=CampaignMessage.Status.CLICKED)),
                failed=Count('id', filter=Q(status=CampaignMessage.Status.FAILED)),
            )
        )
        revenue_total = sum((campaign.metrics or {}).get('revenue', 0) for campaign in campaigns)
        top_campaigns = campaigns.order_by('-metrics__clicked')[:5].values(
            'id', 'name', 'status', 'metrics'
        )
        notification_slice = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notifications = NotificationSerializer(notification_slice, many=True).data
        AISuggestionService(user=request.user).generate()
        suggestion_qs = AISuggestion.objects.filter(user=request.user).order_by('-score')[:5]
        suggestions = AISuggestionSerializer(suggestion_qs, many=True).data
        churn_candidates = ChurnPredictionService(user=request.user).rank_high_risk(limit=3)
        churn_data = CustomerSerializer(churn_candidates, many=True, context={'request': request}).data
        automation_count = request.user.automation_rules.filter(is_active=True).count()
        return Response(
            {
                'summary': {
                    'products': products.count(),
                    'content_generated': summary.get(AIContent.Status.GENERATED, 0),
                    'content_edited': summary.get(AIContent.Status.EDITED, 0),
                    'content_ready': summary.get(AIContent.Status.READY, 0),
                },
                'campaign_summary': {
                    'total': campaigns.count(),
                    'status': {item['status']: item['total'] for item in campaign_breakdown},
                    'messages': message_metrics,
                    'revenue': revenue_total,
                    'top_campaigns': list(top_campaigns),
                },
                'notifications': notifications,
                'ai_suggestions': suggestions,
                'churn_risk': churn_data,
                'automation_rules_active': automation_count,
                'products': serializer.data,
            }
        )


class ActivityLogListView(generics.ListAPIView):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            ActivityLog.objects.filter(user=self.request.user)
            .select_related('product')
            .order_by('-timestamp')
        )


class CustomerListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = {
        'get': (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST),
        'post': (User.Role.ADMIN, User.Role.MANAGER),
    }

    def get_queryset(self):
        queryset = Customer.objects.filter(user=self.request.user).prefetch_related('tags')
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        tag = self.request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(tags__slug=tag)
        return queryset.order_by('-created_at')


class CustomerDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = {
        'get': (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST),
        'put': (User.Role.ADMIN, User.Role.MANAGER),
        'patch': (User.Role.ADMIN, User.Role.MANAGER),
        'delete': (User.Role.ADMIN,),
    }

    def get_queryset(self):
        return Customer.objects.filter(user=self.request.user).prefetch_related('tags')


class CustomerUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER)

    def post(self, request):
        file_obj = request.data.get('file')
        if not file_obj:
            return Response({'detail': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)
        service = CustomerImportService(user=request.user)
        try:
            parsed = service.parse(file_obj)
            result = service.upsert_customers(parsed)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_activity(
            user=request.user,
            action='Customer upload processed',
            metadata=result,
        )
        return Response({'detail': 'Upload processed', **result}, status=status.HTTP_201_CREATED)


class CustomerSegmentListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomerSegmentSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = {
        'get': (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST),
        'post': (User.Role.ADMIN, User.Role.MANAGER),
    }

    def get_queryset(self):
        queryset = CustomerSegment.objects.filter(user=self.request.user).prefetch_related('tags')
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by('name')


class CustomerSegmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerSegmentSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = {
        'get': (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST),
        'put': (User.Role.ADMIN, User.Role.MANAGER),
        'patch': (User.Role.ADMIN, User.Role.MANAGER),
        'delete': (User.Role.ADMIN,),
    }

    def get_queryset(self):
        return CustomerSegment.objects.filter(user=self.request.user).prefetch_related('tags')


class AutomationRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = AutomationRuleSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = {
        'get': (User.Role.ADMIN, User.Role.MANAGER),
        'post': (User.Role.ADMIN, User.Role.MANAGER),
    }

    def get_queryset(self):
        return AutomationRule.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AutomationRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AutomationRuleSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = {
        'get': (User.Role.ADMIN, User.Role.MANAGER),
        'put': (User.Role.ADMIN, User.Role.MANAGER),
        'patch': (User.Role.ADMIN, User.Role.MANAGER),
        'delete': (User.Role.ADMIN,),
    }

    def get_queryset(self):
        return AutomationRule.objects.filter(user=self.request.user)


class AutomationRunView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER)

    def post(self, request):
        AutomationService(user=request.user).run()
        return Response({'detail': 'Automation rules executed'})


class CampaignListCreateView(generics.ListCreateAPIView):
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = {
        'get': (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST),
        'post': (User.Role.ADMIN, User.Role.MANAGER),
    }

    def get_queryset(self):
        queryset = Campaign.objects.filter(user=self.request.user).select_related('product', 'segment')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(title__icontains=search))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        self._validate_relationships(serializer)
        campaign = serializer.save()
        analytics = CampaignAnalyticsService(user=self.request.user)
        recommended = analytics.recommend_send_time()
        if recommended:
            campaign.recommended_send_time = recommended.astimezone(timezone.get_current_timezone())
            campaign.save(update_fields=('recommended_send_time', 'updated_at'))
        log_activity(
            user=self.request.user,
            action='Campaign created',
            metadata={'campaign_id': str(campaign.id)},
        )

    def _validate_relationships(self, serializer):
        product = serializer.validated_data.get('product')
        if product and product.user != self.request.user:
            raise PermissionDenied('Cannot attach product from another account')
        segment = serializer.validated_data.get('segment')
        if segment and segment.user != self.request.user:
            raise PermissionDenied('Cannot attach segment from another account')


class CampaignDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CampaignDetailSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = {
        'get': (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST),
        'put': (User.Role.ADMIN, User.Role.MANAGER),
        'patch': (User.Role.ADMIN, User.Role.MANAGER),
        'delete': (User.Role.ADMIN,),
    }

    def get_queryset(self):
        return Campaign.objects.filter(user=self.request.user).select_related('product', 'segment')

    def perform_update(self, serializer):
        product = serializer.validated_data.get('product')
        if product and product.user != self.request.user:
            raise PermissionDenied('Cannot attach product from another account')
        segment = serializer.validated_data.get('segment')
        if segment and segment.user != self.request.user:
            raise PermissionDenied('Cannot attach segment from another account')
        serializer.save()


class CampaignSuggestionGenerateView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER)

    def post(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
        if not campaign.product:
            return Response({'detail': 'Campaign must be linked to a product'}, status=status.HTTP_400_BAD_REQUEST)
        generator = AIContentGenerator()
        try:
            payload = generator.generate_campaign_assets(
                product=campaign.product,
                language_code=request.data.get('language_code', campaign.language_code),
                audience_notes=campaign.segment.description if campaign.segment else None,
            )
        except AIContentGeneratorError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        suggestion = CampaignSuggestion.objects.create(campaign=campaign, payload=payload)
        serializer = CampaignSuggestionSerializer(suggestion)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CampaignSuggestionDecisionView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER)

    def post(self, request, campaign_id, suggestion_id):
        action = request.data.get('action')
        if action not in {'approve', 'reject'}:
            return Response({'detail': 'action must be approve or reject'}, status=status.HTTP_400_BAD_REQUEST)
        campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
        suggestion = get_object_or_404(CampaignSuggestion, id=suggestion_id, campaign=campaign)
        suggestion.status = (
            CampaignSuggestion.Status.APPROVED if action == 'approve' else CampaignSuggestion.Status.REJECTED
        )
        suggestion.save(update_fields=('status', 'updated_at'))
        if action == 'approve':
            payload = suggestion.payload
            Campaign.objects.filter(id=campaign.id).update(
                title=payload.get('title', campaign.title),
                subject_line=payload.get('subject_line', campaign.subject_line),
                summary=payload.get('summary', campaign.summary),
                hashtags=payload.get('hashtags', campaign.hashtags),
            )
        log_activity(
            user=request.user,
            action='Campaign suggestion decided',
            metadata={'campaign_id': str(campaign.id), 'suggestion_id': str(suggestion.id), 'action': action},
        )
        return Response({'status': suggestion.status})


class CampaignScheduleView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER)

    def post(self, request, campaign_id):
        serializer = CampaignScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
        campaign.scheduled_at = serializer.validated_data['scheduled_at']
        campaign.timezone = serializer.validated_data['timezone']
        campaign.status = Campaign.Status.SCHEDULED
        analytics = CampaignAnalyticsService(user=request.user)
        recommended = analytics.recommend_send_time()
        if recommended:
            campaign.recommended_send_time = recommended.astimezone(timezone.get_current_timezone())
        update_fields = ['scheduled_at', 'timezone', 'status', 'updated_at']
        if recommended:
            update_fields.append('recommended_send_time')
        campaign.save(update_fields=tuple(update_fields))
        return Response({'detail': 'Campaign scheduled'})


class CampaignSendView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER)

    def post(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
        serializer = CampaignSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        language = serializer.validated_data.get('language_code') or campaign.language_code
        executor = CampaignExecutionService(campaign=campaign, user=request.user)
        try:
            result = executor.dispatch(
                language_code=language,
                force=serializer.validated_data.get('force', False),
            )
        except CampaignExecutionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_activity(
            user=request.user,
            action='Campaign dispatched',
            metadata={'campaign_id': str(campaign.id), **result},
        )
        return Response(result)


class CampaignPaymentCreateView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER)

    def post(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
        serializer = CampaignPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment_service = PaymentGatewayService(user=request.user)
        payment = payment_service.create_payment(
            campaign=campaign,
            amount=serializer.validated_data['amount'],
            currency=serializer.validated_data.get('currency', 'USD'),
            provider=serializer.validated_data.get('provider', 'stripe'),
        )
        response = CampaignPaymentSerializer(payment)
        log_activity(
            user=request.user,
            action='Campaign payment initiated',
            metadata={'campaign_id': str(campaign.id), 'payment_id': str(payment.id)},
        )
        return Response(response.data, status=status.HTTP_201_CREATED)


class CampaignMessageListView(generics.ListAPIView):
    serializer_class = CampaignMessageSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def get_queryset(self):
        campaign = get_object_or_404(Campaign, id=self.kwargs['campaign_id'], user=self.request.user)
        queryset = campaign.messages.select_related('customer')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by('-created_at')


class CampaignLogListView(generics.ListAPIView):
    serializer_class = CampaignLogSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def get_queryset(self):
        campaign = get_object_or_404(Campaign, id=self.kwargs['campaign_id'], user=self.request.user)
        return campaign.logs.select_related('message').order_by('-created_at')


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user)
        level = self.request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)
        return queryset.order_by('-created_at')


class NotificationUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_read()
        serializer = NotificationSerializer(notification)
        return Response(serializer.data)


class CampaignExportView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def get(self, request):
        export_format = request.query_params.get('format', 'csv')
        campaigns = Campaign.objects.filter(user=request.user).order_by('-created_at')
        if export_format == 'pdf':
            buffer = io.BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            y = height - 50
            for campaign in campaigns:
                pdf.drawString(40, y, f"{campaign.name} | Status: {campaign.status} | Sent: {campaign.metrics.get('sent', 0)}")
                y -= 20
                if y < 50:
                    pdf.showPage()
                    y = height - 50
            pdf.save()
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename=campaigns.pdf'
            return response
        if export_format == 'json':
            payload = [
                {
                    'id': str(campaign.id),
                    'name': campaign.name,
                    'status': campaign.status,
                    'metrics': campaign.metrics,
                    'scheduled_at': campaign.scheduled_at,
                }
                for campaign in campaigns
            ]
            return Response(payload)
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(['Name', 'Status', 'Scheduled At', 'Sent', 'Opened', 'Clicked'])
        for campaign in campaigns:
            metrics = campaign.metrics or {}
            writer.writerow([
                campaign.name,
                campaign.status,
                campaign.scheduled_at.isoformat() if campaign.scheduled_at else '',
                metrics.get('sent', 0),
                metrics.get('opened', 0),
                metrics.get('clicked', 0),
            ])
        response = HttpResponse(stream.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=campaigns.csv'
        return response


class CampaignVariantListView(generics.ListAPIView):
    serializer_class = CampaignVariantSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def get_queryset(self):
        campaign = get_object_or_404(Campaign, id=self.kwargs['campaign_id'], user=self.request.user)
        return campaign.variants.order_by('-created_at')


class RealtimeAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def get(self, request):
        window_days = getattr(settings, 'DEFAULT_ANALYTICS_WINDOW_DAYS', 30)
        since = timezone.now() - timedelta(days=window_days)
        messages = CampaignMessage.objects.filter(campaign__user=request.user, created_at__gte=since)
        metrics = messages.aggregate(
            sent=Count('id', filter=Q(status=CampaignMessage.Status.SENT)),
            delivered=Count('id', filter=Q(status__in=[CampaignMessage.Status.SENT, CampaignMessage.Status.OPENED])),
            opened=Count('id', filter=Q(status=CampaignMessage.Status.OPENED)),
            clicked=Count('id', filter=Q(status=CampaignMessage.Status.CLICKED)),
            failed=Count('id', filter=Q(status=CampaignMessage.Status.FAILED)),
        )
        variant_perf = list(
            CampaignVariant.objects.filter(campaign__user=request.user)
            .values('campaign_id', 'label', 'metrics', 'is_winner')
        )
        return Response({'window_days': window_days, 'metrics': metrics, 'variants': variant_perf})


class ChurnRiskView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def get(self, request):
        limit = int(request.query_params.get('limit', 10))
        customers = ChurnPredictionService(user=request.user).rank_high_risk(limit=limit)
        serializer = CustomerSerializer(customers, many=True, context={'request': request})
        return Response(serializer.data)


class AISuggestionListView(generics.ListAPIView):
    serializer_class = AISuggestionSerializer
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER, User.Role.ANALYST)

    def get_queryset(self):
        AISuggestionService(user=self.request.user).generate()
        return AISuggestion.objects.filter(user=self.request.user).order_by('-score')


class AISuggestionActionView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER)

    def post(self, request, suggestion_id):
        suggestion = get_object_or_404(AISuggestion, id=suggestion_id, user=request.user)
        action = request.data.get('action')
        if action not in {'accept', 'dismiss'}:
            return Response({'detail': 'action must be accept or dismiss'}, status=status.HTTP_400_BAD_REQUEST)
        suggestion.status = 'accepted' if action == 'accept' else 'dismissed'
        suggestion.acted_at = timezone.now()
        suggestion.save(update_fields=('status', 'acted_at'))
        serializer = AISuggestionSerializer(suggestion)
        return Response(serializer.data)


class CustomerEventIngestView(APIView):
    permission_classes = [IsAuthenticated]
    allowed_roles = (User.Role.ADMIN, User.Role.MANAGER)

    def post(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id, user=request.user)
        serializer = CustomerEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = CustomerEvent.objects.create(customer=customer, **serializer.validated_data)
        SegmentationService(user=request.user).refresh_customer_scores(customer)
        log_activity(
            user=request.user,
            action='Customer event ingested',
            metadata={'customer_id': str(customer.id), 'event_type': event.event_type},
        )
        return Response({'id': str(event.id), 'detail': 'Event recorded'}, status=status.HTTP_201_CREATED)
