"""Run AutomationRule workflows for one or all users."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from marketing.services import AutomationService

User = get_user_model()


class Command(BaseCommand):
    help = 'Execute automation rules for the provided user or every user.'

    def add_arguments(self, parser):
        parser.add_argument('--user-email', help='Optional user email to target')

    def handle(self, *args, **options):
        email = options.get('user_email')
        if email:
            user = User.objects.filter(email=email).first()
            if not user:
                raise CommandError(f'User {email} not found')
            AutomationService(user=user).run()
            self.stdout.write(self.style.SUCCESS(f'Processed automation rules for {email}'))
            return
        for user in User.objects.all():
            AutomationService(user=user).run()
            self.stdout.write(self.style.SUCCESS(f'Processed automation rules for {user.email}'))
