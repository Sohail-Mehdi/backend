"""Trigger bulk messaging for a campaign via the CLI."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from marketing.models import Campaign
from marketing.services import CampaignOrchestrator


class Command(BaseCommand):
    help = 'Dispatch pending messages for a campaign, respecting rate limits.'

    def add_arguments(self, parser):
        parser.add_argument('--campaign-id', required=True, help='Campaign UUID to process')
        parser.add_argument('--force', action='store_true', help='Override draft status checks')

    def handle(self, *args, **options):
        campaign_id = options['campaign_id']
        force = options['force']
        try:
            campaign = Campaign.objects.get(id=campaign_id)
        except Campaign.DoesNotExist as exc:  # pragma: no cover
            raise CommandError(f'Campaign {campaign_id} not found') from exc
        orchestrator = CampaignOrchestrator(campaign=campaign)
        result = orchestrator.send_pending_messages(force=force)
        self.stdout.write(self.style.SUCCESS(f"Sent: {result['sent']} | Failed: {result['failed']}"))
