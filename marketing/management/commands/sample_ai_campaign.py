"""Generate sample AI campaign assets for a product."""
from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from marketing.ai_engine import AIContentGenerator, AIContentGeneratorError
from marketing.models import Product


class Command(BaseCommand):
    help = 'Generates AI campaign content for a product and prints the JSON payload.'

    def add_arguments(self, parser):
        parser.add_argument('--product-id', required=True, help='Product UUID to seed the AI prompt')
        parser.add_argument('--language', default='en', help='Language code for generation (en/es/etc.)')

    def handle(self, *args, **options):
        product_id = options['product_id']
        language = options['language']
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist as exc:  # pragma: no cover
            raise CommandError(f'Product {product_id} not found') from exc
        generator = AIContentGenerator()
        try:
            payload: dict[str, Any] = generator.generate_campaign_assets(
                product=product,
                language_code=language,
            )
        except AIContentGeneratorError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
