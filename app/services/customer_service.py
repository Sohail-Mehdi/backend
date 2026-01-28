import csv
import io
import openpyxl
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from pydantic import EmailStr, validate_call

from ..models import models
from ..core.config import settings

class CustomerService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def refresh_customer_scores(self, customer: models.Customer):
        # Top 200 events
        events = self.db.query(models.CustomerEvent).filter(
            models.CustomerEvent.customer_id == customer.id
        ).order_by(models.CustomerEvent.occurred_at.desc()).limit(200).all()
        
        engagement = sum(1 for event in events if event.event_type in ["email_open", "click"])
        interest = sum(float(event.payload.get("value", 1)) for event in events if event.event_type == "purchase")
        
        customer.engagement_score = min(100.0, engagement * 5.0)
        customer.interest_score = min(100.0, interest * 10.0)
        customer.churn_risk_score = max(0.0, 100.0 - customer.engagement_score * 0.5)
        customer.churn_predicted_at = datetime.utcnow()
        
        self.db.commit()

    def rank_high_risk_customers(self, limit: int = 10) -> List[models.Customer]:
        customers = self.db.query(models.Customer).filter(
            models.Customer.user_id == self.user_id
        ).all()
        
        if not customers:
            return []
            
        now = datetime.utcnow()
        for customer in customers:
            recency_days = 0
            if customer.last_purchase_at:
                recency_days = max(0, (now - customer.last_purchase_at).days)
                
            engagement = customer.engagement_score or 0
            interest = customer.interest_score or 0
            
            # Count recent events (last 90 days)
            event_count = self.db.query(models.CustomerEvent).filter(
                models.CustomerEvent.customer_id == customer.id,
                models.CustomerEvent.occurred_at >= now - timedelta(days=90)
            ).count()
            
            # Heuristic-driven score
            score = min(
                100.0,
                recency_days * 0.6 + (100 - min(engagement, 100)) * 0.3 + (50 - min(interest, 50)) + (5 - min(event_count, 5)) * 4,
            )
            purchase_value = float(customer.average_order_value or 0)
            if purchase_value < 10:
                score *= 0.9
                
            customer.churn_risk_score = round(float(score), 2)
            customer.churn_predicted_at = now
            
        self.db.commit()
        
        # Sort and return top candidates
        customers.sort(key=lambda x: x.churn_risk_score, reverse=True)
        return customers[:limit]

class CustomerImportService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    async def parse_and_upsert(self, file_content: bytes, filename: str) -> Dict[str, int]:
        filename = filename.lower()
        if filename.endswith('.csv'):
            text = file_content.decode('utf-8')
            parsed = self._parse_csv(text)
        elif filename.endswith(('.xlsx', '.xlsm')):
            parsed = self._parse_excel(file_content)
        else:
            raise ValueError('Only CSV or Excel uploads are supported')
            
        return self.upsert_customers(parsed)

    def _parse_csv(self, text: str) -> List[Dict[str, Any]]:
        reader = csv.DictReader(io.StringIO(text))
        return [row for row in reader if row.get('email')]

    def _parse_excel(self, raw: bytes) -> List[Dict[str, Any]]:
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(value).strip().lower() for value in rows[0] if value is not None]
        customers = []
        for row in rows[1:]:
            data = {headers[idx]: (cell or '') for idx, cell in enumerate(row) if idx < len(headers)}
            if data.get('email'):
                customers.append(data)
        return customers

    def upsert_customers(self, customers: List[Dict[str, Any]]) -> Dict[str, int]:
        created_count = 0
        updated_count = 0
        for data in customers:
            email = data.get('email', '').strip().lower()
            if not email:
                continue
            
            customer = self.db.query(models.Customer).filter(
                models.Customer.user_id == self.user_id,
                models.Customer.email == email
            ).first()
            
            if not customer:
                customer = models.Customer(
                    user_id=self.user_id,
                    email=email,
                    first_name=data.get('first_name', '').strip(),
                    last_name=data.get('last_name', '').strip(),
                    phone_number=data.get('phone', data.get('phone_number', '')).strip(),
                )
                self.db.add(customer)
                created_count += 1
            else:
                customer.first_name = data.get('first_name', customer.first_name)
                customer.last_name = data.get('last_name', customer.last_name)
                customer.phone_number = data.get('phone', data.get('phone_number', customer.phone_number))
                updated_count += 1
            
            # Handle tags
            tags_raw = data.get('tags', '')
            if tags_raw:
                tag_names = [t.strip() for t in tags_raw.split(',') if t.strip()]
                for name in tag_names:
                    slug = name.lower().replace(' ', '-')
                    tag = self.db.query(models.CustomerTag).filter(
                        models.CustomerTag.user_id == self.user_id,
                        models.CustomerTag.slug == slug
                    ).first()
                    if not tag:
                        tag = models.CustomerTag(user_id=self.user_id, name=name, slug=slug)
                        self.db.add(tag)
                    if tag not in customer.tags:
                        customer.tags.append(tag)
                        
        self.db.commit()
        return {'created': created_count, 'updated': updated_count}
