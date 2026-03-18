from pydantic_settings import BaseSettings
from typing import List
import json

class Settings(BaseSettings):
    """Application configuration."""
    
    # App
    APP_NAME: str = "PatchFlow"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    DOCKER_ENV: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/patchflow"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS - stored as comma-separated string, parsed to list
    CORS_ORIGINS: str = "http://localhost:3000,https://patchflow.ai"
    FRONTEND_URL: str = "http://localhost:3000"
    
    # GitHub
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Clerk Authentication
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_SECRET_KEY: str = ""
    CLERK_DOMAIN: str = "clerk.patchflow.ai"  # e.g., your-domain.clerk.accounts.dev
    CLERK_AUDIENCE: str = ""  # JWT audience, usually your frontend URL
    CLERK_WEBHOOK_SECRET: str = ""  # For verifying webhook signatures
    
    class Config:
        env_file = ".env"

    def get_cors_origins(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
