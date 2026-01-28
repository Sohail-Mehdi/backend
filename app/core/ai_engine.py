"""Wrapper around OpenAI for generating marketing content."""
import json
import logging
import os
from typing import Dict, List, Any, Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

LOGGER = logging.getLogger(__name__)

CHANNEL_KEY_MAP = {
    'social_media_caption': 'social',
    'email_newsletter_text': 'email',
    'whatsapp_message_text': 'whatsapp',
}

CAMPAIGN_KEY_MAP = {
    'email_body': 'email_body',
    'whatsapp_message': 'whatsapp_message',
    'social_post': 'social_post',
    'product_summary': 'summary',
    'campaign_title': 'title',
    'email_subject_line': 'subject_line',
    'recommended_hashtags': 'hashtags',
}

class AIContentGeneratorError(RuntimeError):
    """Raised when AI content generation fails."""

class AIContentGenerator:
    """Lightweight orchestrator for OpenAI-powered content generation."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise AIContentGeneratorError('OPENAI_API_KEY is not configured')
        self.model = model or os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.client = OpenAI(api_key=self.api_key)

    def _build_prompt(self, product_data: Dict[str, Any], language_code: str = 'en') -> str:
        image_url = product_data.get('image_url')
        price = product_data.get('price')
        sku = product_data.get('sku')
        
        image_line = f"Image reference: {image_url}\n" if image_url else ''
        price_line = f"Price: {price}\n" if price else ''
        sku_line = f"SKU: {sku}\n" if sku else ''
        
        return (
            "Create compelling marketing copy for the following product.\n"
            "Provide concise, channel-ready text for:\n"
            "1. Social media caption\n"
            "2. Email newsletter snippet\n"
            "3. WhatsApp promotional message\n"
            "Return strictly formatted JSON with keys 'social_media_caption',\n"
            "'email_newsletter_text', and 'whatsapp_message_text'.\n"
            f"Respond in the {language_code} language.\n\n"
            f"Product Name: {product_data.get('name')}\n"
            f"Category: {product_data.get('category')}\n"
            f"Description: {product_data.get('description')}\n"
            f"{price_line}{sku_line}{image_line}"
        )

    def _parse_payload(self, payload: str, mapping: Dict[str, str]) -> Dict[str, str]:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            LOGGER.error('Failed to parse OpenAI response: %s', exc)
            raise AIContentGeneratorError('Invalid response from AI model') from exc
        return {
            mapping[key]: value.strip()
            for key, value in data.items()
            if key in mapping and isinstance(value, str)
        }

    def generate_product_content(self, product_data: Dict[str, Any], language_code: str = 'en') -> Dict[str, str]:
        prompt = self._build_prompt(product_data, language_code=language_code)
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0.7,
                response_format={'type': 'json_object'},
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are an expert marketing copywriter.',
                    },
                    {
                        'role': 'user',
                        'content': prompt,
                    },
                ],
            )
        except Exception as exc:
            LOGGER.exception('OpenAI API call failed')
            raise AIContentGeneratorError('Unable to reach OpenAI API') from exc

        content = completion.choices[0].message.content.strip()
        parsed = self._parse_payload(content, CHANNEL_KEY_MAP)
        if not parsed:
            raise AIContentGeneratorError('AI model returned empty content payload')
        return parsed

    def generate_campaign_assets(
        self,
        product_data: Dict[str, Any],
        language_code: str = 'en',
        audience_notes: Optional[str] = None,
    ) -> Dict[str, str]:
        audience_line = f"Primary audience details: {audience_notes}\n" if audience_notes else ''
        prompt = (
            "You are an elite marketing campaign strategist.\n"
            "Produce persuasive, channel-tailored messaging for email, WhatsApp, and social media.\n"
            "Also craft a two-sentence product summary, a punchy campaign title, an email subject line,"
            " and 3-5 relevant hashtags. Respond strictly in JSON with keys:\n"
            "'email_body', 'whatsapp_message', 'social_post', 'product_summary', 'campaign_title',"
            " 'email_subject_line', 'recommended_hashtags'.\n"
            f"All content must be localized in {language_code}.\n\n"
            f"Product Name: {product_data.get('name')}\n"
            f"Category: {product_data.get('category')}\n"
            f"Description: {product_data.get('description')}\n"
            f"Attributes: {json.dumps(product_data.get('attributes', {}), default=str)}\n"
            f"{audience_line}"
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0.65,
                response_format={'type': 'json_object'},
                messages=[
                    {
                        'role': 'system',
                        'content': 'You specialize in omnichannel ecommerce campaigns.',
                    },
                    {
                        'role': 'user',
                        'content': prompt,
                    },
                ],
            )
        except Exception as exc:
            LOGGER.exception('OpenAI campaign generation failed')
            raise AIContentGeneratorError('Unable to reach OpenAI API') from exc

        content = completion.choices[0].message.content.strip()
        parsed = self._parse_payload(content, CAMPAIGN_KEY_MAP)
        if not parsed:
            raise AIContentGeneratorError('AI model returned empty campaign payload')
        if 'hashtags' in parsed and parsed['hashtags']:
            parsed['hashtags'] = [tag.strip() for tag in parsed['hashtags'].split()] if isinstance(parsed['hashtags'], str) else parsed['hashtags']
        return parsed

    def generate_campaign_variants(
        self,
        product_data: Dict[str, Any],
        variant_count: int = 3,
        language_code: str = 'en',
        segment_profile: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        prompt = (
            "Create multiple marketing message variations for a sophisticated A/B test."
            " Each variation must include JSON keys 'email_body', 'sms_text', 'whatsapp_message',"
            " 'social_post', 'subject_line', and 'call_to_action'."
            f" Respond in {language_code} with an array called 'variants'."
            f" Product: {product_data.get('name')} ({product_data.get('category')}).\nDescription: {product_data.get('description')}.\n"
            f"Attributes: {json.dumps(product_data.get('attributes', {}), default=str)}.\n"
            f"Segment profile: {segment_profile or 'general audience'}"
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                temperature=0.75,
                response_format={'type': 'json_object'},
                messages=[
                    {'role': 'system', 'content': 'You craft high-performing marketing experiments.'},
                    {'role': 'user', 'content': prompt},
                ],
            )
        except Exception as exc:
            LOGGER.exception('OpenAI variant generation failed')
            raise AIContentGeneratorError('Unable to reach OpenAI API') from exc

        content = completion.choices[0].message.content.strip()
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            LOGGER.error('Variant payload parse error: %s', exc)
            raise AIContentGeneratorError('Variant response parsing failed') from exc
        variants = payload.get('variants') if isinstance(payload, dict) else None
        if not variants or not isinstance(variants, list):
            raise AIContentGeneratorError('AI did not return variants list')
        normalized: List[Dict[str, str]] = []
        for idx, variant in enumerate(variants[:variant_count], start=1):
            if not isinstance(variant, dict):
                continue
            normalized.append(
                {
                    'label': f'V{idx}',
                    'email_body': variant.get('email_body', '').strip(),
                    'sms_text': variant.get('sms_text', '').strip(),
                    'whatsapp_message': variant.get('whatsapp_message', '').strip(),
                    'social_post': variant.get('social_post', '').strip(),
                    'subject_line': variant.get('subject_line', '').strip(),
                    'call_to_action': variant.get('call_to_action', '').strip(),
                }
            )
        if not normalized:
            raise AIContentGeneratorError('No usable variants returned')
        return normalized
