from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Seeds the database with initial users: Admin, Seller, and Agent.'

    def handle(self, *args, **options):
        User = get_user_model()
        
        users_to_create = [
            {
                'email': 'admin@gmail.com',
                'password': '12345678',
                'role': User.Role.ADMIN,
                'name': 'Admin User',
                'is_superuser': True,
                'is_staff': True
            },
            {
                'email': 'seller@gmail.com',
                'password': '12345678',
                'role': User.Role.STORE_OWNER,
                'name': 'Seller User',
                'is_superuser': False,
                'is_staff': False
            },
            {
                'email': 'agent@gmail.com',
                'password': '12345678',
                'role': User.Role.MANAGER,
                'name': 'Agent User',
                'is_superuser': False,
                'is_staff': False
            }
        ]

        for user_data in users_to_create:
            email = user_data['email']
            if User.objects.filter(email=email).exists():
                self.stdout.write(self.style.WARNING(f'User {email} already exists.'))
                continue

            if user_data.get('is_superuser'):
                User.objects.create_superuser(
                    email=email,
                    password=user_data['password'],
                    name=user_data['name'],
                    role=user_data['role']
                )
            else:
                User.objects.create_user(
                    email=email,
                    password=user_data['password'],
                    name=user_data['name'],
                    role=user_data['role']
                )
            
            self.stdout.write(self.style.SUCCESS(f'Successfully created user: {email}'))
