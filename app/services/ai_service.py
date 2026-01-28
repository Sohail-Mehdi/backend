from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..models import models
from ..ai_engine import AIContentGenerator

class AISuggestionService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def generate(self) -> List[models.AISuggestion]:
        # Logic from ported Django AISuggestionService.generate
        suggestions: List[models.AISuggestion] = []
        
        # Product suggestion
        product = self.db.query(models.Product).filter(
            models.Product.user_id == self.user_id
        ).order_by(models.Product.created_at.desc()).first()
        
        if product:
            suggestions.append(self._upsert(
                suggestion_type=models.AISuggestionType.PRODUCT,
                payload={'product_id': str(product.id), 'product_name': product.name},
                score=0.85
            ))
            
        # Segment suggestion
        segment = self.db.query(models.CustomerSegment).filter(
            models.CustomerSegment.user_id == self.user_id
        ).first() # Simplified
        
        if segment:
            suggestions.append(self._upsert(
                suggestion_type=models.AISuggestionType.SEGMENT,
                payload={'segment_id': str(segment.id), 'segment_name': segment.name},
                score=0.78
            ))
            
        return suggestions

    def _upsert(self, suggestion_type: models.AISuggestionType, payload: Dict[str, Any], score: float) -> models.AISuggestion:
        suggestion = self.db.query(models.AISuggestion).filter(
            models.AISuggestion.user_id == self.user_id,
            models.AISuggestion.suggestion_type == suggestion_type
        ).first()
        
        if not suggestion:
            suggestion = models.AISuggestion(
                user_id=self.user_id,
                suggestion_type=suggestion_type,
                payload=payload,
                score=round(score, 2),
                status='pending'
            )
            self.db.add(suggestion)
        else:
            suggestion.payload = payload
            suggestion.score = round(score, 2)
            
        self.db.commit()
        return suggestion
