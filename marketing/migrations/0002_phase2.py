# Generated manually for Phase 2 expansion
import uuid
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models

import marketing.models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='aicontent',
            name='language_code',
            field=models.CharField(default='en', max_length=8),
        ),
        migrations.AddField(
            model_name='product',
            name='attributes',
            field=models.JSONField(blank=True, default=marketing.models.empty_dict),
        ),
        migrations.CreateModel(
            name='CustomerTag',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=80)),
                ('slug', models.SlugField(max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customer_tags', to='marketing.user')),
            ],
            options={'ordering': ('name',)},
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=160)),
                ('body', models.TextField()),
                ('level', models.CharField(choices=[('info', 'Info'), ('success', 'Success'), ('warning', 'Warning'), ('error', 'Error')], default='info', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('read', 'Read')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='marketing.user')),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254)),
                ('phone_number', models.CharField(blank=True, max_length=32)),
                ('first_name', models.CharField(blank=True, max_length=80)),
                ('last_name', models.CharField(blank=True, max_length=80)),
                ('timezone', models.CharField(default='UTC', max_length=64)),
                ('preferred_language', models.CharField(default='en', max_length=8)),
                ('categories_of_interest', models.JSONField(blank=True, default=marketing.models.empty_list)),
                ('purchase_metadata', models.JSONField(blank=True, default=marketing.models.empty_dict)),
                ('average_order_value', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('last_purchase_at', models.DateTimeField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=marketing.models.empty_dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customers', to='marketing.user')),
                ('tags', models.ManyToManyField(blank=True, related_name='customers', to='marketing.customertag')),
            ],
            options={'ordering': ('-created_at',), 'unique_together': {('user', 'email')}},
        ),
        migrations.CreateModel(
            name='CustomerSegment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('category_filters', models.JSONField(blank=True, default=marketing.models.empty_list)),
                ('behavior_filters', models.JSONField(blank=True, default=marketing.models.empty_dict)),
                ('metadata', models.JSONField(blank=True, default=marketing.models.empty_dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tags', models.ManyToManyField(blank=True, related_name='segments', to='marketing.customertag')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customer_segments', to='marketing.user')),
            ],
            options={'ordering': ('name',), 'unique_together': {('user', 'name')}},
        ),
        migrations.CreateModel(
            name='Campaign',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=160)),
                ('title', models.CharField(blank=True, max_length=180)),
                ('subject_line', models.CharField(blank=True, max_length=180)),
                ('hashtags', models.JSONField(blank=True, default=marketing.models.empty_list)),
                ('summary', models.TextField(blank=True)),
                ('language_code', models.CharField(default='en', max_length=8)),
                ('timezone', models.CharField(default='UTC', max_length=64)),
                ('scheduled_at', models.DateTimeField(blank=True, null=True)),
                ('channels', models.JSONField(default=marketing.models.empty_dict)),
                ('personalization', models.JSONField(blank=True, default=marketing.models.empty_dict)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('scheduled', 'Scheduled'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed')], default='draft', max_length=20)),
                ('metrics', models.JSONField(default=marketing.models.default_metrics)),
                ('last_run_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campaigns', to='marketing.product')),
                ('segment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campaigns', to='marketing.customersegment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='campaigns', to='marketing.user')),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.CreateModel(
            name='CampaignSuggestion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('payload', models.JSONField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='suggestions', to='marketing.campaign')),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.CreateModel(
            name='CampaignMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('channel', models.CharField(choices=[('email', 'Email'), ('whatsapp', 'WhatsApp'), ('social', 'Social')], max_length=20)),
                ('content', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('scheduled', 'Scheduled'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed'), ('opened', 'Opened'), ('clicked', 'Clicked')], default='pending', max_length=20)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('max_attempts', models.PositiveIntegerField(default=marketing.models.default_max_attempts)),
                ('last_error', models.TextField(blank=True)),
                ('external_id', models.CharField(blank=True, max_length=120)),
                ('metadata', models.JSONField(blank=True, default=marketing.models.empty_dict)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('opened_at', models.DateTimeField(blank=True, null=True)),
                ('clicked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='marketing.campaign')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='marketing.customer')),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.AddIndex(
            model_name='campaignmessage',
            index=models.Index(fields=('campaign', 'status'), name='marketing_campai_campaig_a6458f_idx'),
        ),
        migrations.CreateModel(
            name='CampaignLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(max_length=255)),
                ('details', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=marketing.models.empty_dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='marketing.campaign')),
                ('message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='logs', to='marketing.campaignmessage')),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.AlterUniqueTogether(
            name='customertag',
            unique_together={('user', 'slug')},
        ),
    ]
