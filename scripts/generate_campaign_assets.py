"""Sample script to generate campaign assets via OpenAI."""
from __future__ import annotations

import os
import sys

import django


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_project.settings')

django.setup()

from marketing.ai_engine import AIContentGenerator  # noqa: E402
from marketing.models import Product  # noqa: E402


def main():
    product = Product.objects.order_by('-created_at').first()
    if not product:
        print('No products found. Please create one via the API first.')
        return
    generator = AIContentGenerator()
    payload = generator.generate_campaign_assets(product=product)
    print('Generated payload:')
    for key, value in payload.items():
        print(f"- {key}: {value}\n")


if __name__ == '__main__':
    main()
