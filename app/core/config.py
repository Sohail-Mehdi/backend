import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Marketing Tool API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-me")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "mysql+pymysql://user:password@localhost/dbname")
    
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Provider limits
    BULK_EMAIL_RATE_LIMIT_PER_MIN: int = int(os.getenv("BULK_EMAIL_RATE_LIMIT_PER_MIN", "60"))
    BULK_WHATSAPP_RATE_LIMIT_PER_MIN: int = int(os.getenv("BULK_WHATSAPP_RATE_LIMIT_PER_MIN", "30"))
    BULK_SMS_RATE_LIMIT_PER_MIN: int = int(os.getenv("BULK_SMS_RATE_LIMIT_PER_MIN", "30"))
    
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM: str = os.getenv("TWILIO_WHATSAPP_FROM", "")
    
    SMS_PROVIDER_API_KEY: str = os.getenv("SMS_PROVIDER_API_KEY", "")
    SMS_PROVIDER_SENDER_ID: str = os.getenv("SMS_PROVIDER_SENDER_ID", "AI-MKT")
    
    ADMIN_ALERT_EMAIL: str = os.getenv("ADMIN_ALERT_EMAIL", "")
    ADMIN_ALERT_PHONE: str = os.getenv("ADMIN_ALERT_PHONE", "")
    ADMIN_NOTIFICATION_CHANNELS: str = os.getenv("ADMIN_NOTIFICATION_CHANNELS", "email")
    
    DEFAULT_FROM_EMAIL: str = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")
    FRONTEND_DASHBOARD_URL: str = os.getenv("FRONTEND_DASHBOARD_URL", "http://localhost:5173")
    
    A_B_TEST_VARIANTS: int = int(os.getenv("A_B_TEST_VARIANTS", "3"))

settings = Settings()
