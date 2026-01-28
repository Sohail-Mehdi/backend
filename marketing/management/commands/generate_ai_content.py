"""Management command to bulk-generate AI content for products."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from marketing.ai_engine import AIContentGenerator, AIContentGeneratorError
from marketing.models import AIContent, Product
from marketing.services import log_activity

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate AI-ready content for all products belonging to a user.'

    def add_arguments(self, parser):
        parser.add_argument('--user-email', required=True, help='User email to target')
        parser.add_argument('--language', default='en', help='Language code for generation')

    def handle(self, *args, **options):
        email = options['user_email']
        language = options['language']
        user = User.objects.filter(email=email).first()
        if not user:
            raise CommandError(f'User {email} not found')
        generator = AIContentGenerator()
        products = Product.objects.filter(user=user)
        if not products.exists():
            self.stdout.write(self.style.WARNING('No products found for this user.'))
            return
        created = 0
        for product in products:
            try:
                payload = generator.generate_product_content(product=product, language_code=language)
            except AIContentGeneratorError as exc:
                raise CommandError(str(exc))
            for channel, content_text in payload.items():
                AIContent.objects.update_or_create(
                    product=product,
                    channel=channel,
                    defaults={'content_text': content_text, 'status': AIContent.Status.GENERATED, 'language_code': language},
                )
                created += 1
            log_activity(
                user=user,
                action='CLI generated content',
                product=product,
                metadata={'channels': list(payload.keys()), 'language': language},
            )
        self.stdout.write(self.style.SUCCESS(f'Generated content for {created} items.'))
