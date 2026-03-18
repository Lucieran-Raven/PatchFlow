# =============================================================================
# Clerk Authentication Integration
# =============================================================================
# Modern authentication for PatchFlow - replaces custom JWT with Clerk
# =============================================================================

from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import httpx
import jwt
from jwt import PyJWKClient
import structlog

from core.config import settings

logger = structlog.get_logger()

# Clerk configuration
CLERK_JWKS_URL = f"https://{settings.CLERK_DOMAIN}/.well-known/jwks.json"
CLERK_ISSUER = f"https://{settings.CLERK_DOMAIN}"
CLERK_API_URL = "https://api.clerk.dev/v1"

# Initialize JWKS client for token validation
jwks_client = PyJWKClient(CLERK_JWKS_URL)

class ClerkUser(BaseModel):
    """Authenticated user from Clerk."""
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    image_url: Optional[str] = None
    org_id: Optional[str] = None
    org_role: Optional[str] = None
    
    @property
    def name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.email.split('@')[0]

async def verify_clerk_token(token: str) -> dict:
    """Verify a Clerk JWT token and return the decoded payload."""
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
            audience=settings.CLERK_AUDIENCE,
            options={"verify_exp": True}
        )
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    except Exception as e:
        logger.error("Token verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_current_user_clerk(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> ClerkUser:
    """Get current authenticated user from Clerk token."""
    token = credentials.credentials
    
    # Verify the token
    payload = await verify_clerk_token(token)
    
    # Extract user info from token claims
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: no user ID"
        )
    
    # Get email from claims (Clerk puts it in different places)
    email = payload.get("email") or payload.get("user", {}).get("email_address")
    if not email:
        # Fetch from Clerk API if not in token
        email = await fetch_user_email_from_clerk(user_id)
    
    # Extract organization info (if user is in an org)
    org_id = payload.get("org_id")
    org_role = payload.get("org_role")
    
    return ClerkUser(
        id=user_id,
        email=email,
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
        image_url=payload.get("image_url"),
        org_id=org_id,
        org_role=org_role
    )

async def fetch_user_email_from_clerk(user_id: str) -> str:
    """Fetch user email from Clerk API if not in token."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{CLERK_API_URL}/users/{user_id}",
            headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"}
        )
        if response.status_code != 200:
            logger.error("Failed to fetch user from Clerk", 
                        user_id=user_id, 
                        status=response.status_code)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not fetch user details"
            )
        
        user_data = response.json()
        email_addresses = user_data.get("email_addresses", [])
        if email_addresses:
            return email_addresses[0]["email_address"]
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User has no email address"
        )

async def get_or_create_user_from_clerk(
    clerk_user: ClerkUser,
    db: AsyncSession
) -> User:
    """Get existing user or create new one from Clerk data."""
    from models import User
    from sqlalchemy import select
    
    # Try to find user by Clerk ID first
    result = await db.execute(
        select(User).where(User.clerk_id == clerk_user.id)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Update user info if changed
        user.email = clerk_user.email
        user.name = clerk_user.name
        if clerk_user.image_url:
            user.avatar_url = clerk_user.image_url
        await db.commit()
        return user
    
    # Try to find by email (migration case)
    result = await db.execute(
        select(User).where(User.email == clerk_user.email)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Link existing user to Clerk
        user.clerk_id = clerk_user.id
        if clerk_user.image_url:
            user.avatar_url = clerk_user.image_url
        await db.commit()
        return user
    
    # Create new user
    new_user = User(
        clerk_id=clerk_user.id,
        email=clerk_user.email,
        name=clerk_user.name,
        avatar_url=clerk_user.image_url,
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info("Created new user from Clerk", 
                user_id=new_user.id, 
                email=clerk_user.email)
    
    return new_user

# Backward compatibility - allow both auth methods
async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
) -> User:
    """Get current user - supports both Clerk and legacy JWT."""
    from core.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession
    
    # Get DB session
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required"
            )
        
        token = credentials.credentials
        
        # Check if it's a Clerk token (starts with ey and has Clerk structure)
        try:
            # Try Clerk first
            clerk_user = await get_current_user_clerk(credentials)
            user = await get_or_create_user_from_clerk(clerk_user, db)
            return user
        except HTTPException:
            # Fall back to legacy JWT
            pass
        
        # Legacy JWT auth
        from api.routes.auth import get_current_user as legacy_get_user
        return await legacy_get_user(credentials, db)
        
    finally:
        await db_gen.aclose()

from fastapi import Depends
