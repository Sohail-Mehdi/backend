"""Dispatch due campaigns across all messaging channels."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from marketing.models import Campaign
from marketing.services import CampaignExecutionError, CampaignExecutionService, log_activity

User = get_user_model()


class Command(BaseCommand):
    help = 'Send all campaigns that are scheduled and ready to dispatch.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=5, help='Max campaigns per user to send')
        parser.add_argument('--force', action='store_true', help='Override status checks')

    def handle(self, *args, **options):
        limit = options['limit']
        force = options['force']
        for user in User.objects.all():
            campaigns = (
                Campaign.objects.filter(
                    user=user,
                    status__in=[Campaign.Status.SCHEDULED, Campaign.Status.RUNNING],
                    scheduled_at__lte=timezone.now(),
                )
                .order_by('scheduled_at')[:limit]
            )
            for campaign in campaigns:
                executor = CampaignExecutionService(campaign=campaign, user=user)
                try:
                    result = executor.dispatch(force=force)
                except CampaignExecutionError as exc:
                    self.stderr.write(f"Failed to send {campaign.id}: {exc}")
                    continue
                log_activity(
                    user=user,
                    action='CLI dispatched campaign',
                    metadata={'campaign_id': str(campaign.id), **result},
                )
                self.stdout.write(self.style.SUCCESS(f"Sent campaign {campaign.id}"))
