"""Sample script to trigger campaign message dispatch."""
from __future__ import annotations

import os
import sys

import django


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_project.settings')

django.setup()

from marketing.models import Campaign  # noqa: E402
from marketing.services import CampaignOrchestrator  # noqa: E402


def main():
    campaign = Campaign.objects.filter(status__in=['scheduled', 'running']).order_by('-updated_at').first()
    if not campaign:
        print('No scheduled/running campaigns found.')
        return
    orchestrator = CampaignOrchestrator(campaign=campaign)
    customers = campaign.segment.apply_filters() if campaign.segment else campaign.user.customers.all()
    if not customers.exists():
        print('Campaign has no target customers.')
        return
    payload = {
        'email_body': 'Hello {{first_name}},\nCheck out our featured product today!',
        'whatsapp_message': 'Quick update: our latest offer is live!',
        'social_post': 'We just launched something new. Tap to explore! #launch',
    }
    created = orchestrator.build_messages(customers=customers, content=payload)
    result = orchestrator.send_pending_messages(force=True)
    print(f"Prepared {created} messages. Sent: {result['sent']}, Failed: {result['failed']}")


if __name__ == '__main__':
    main()
