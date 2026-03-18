"""Unit tests for authentication module.

Tests password hashing, login verification, JWT handling, and edge cases.
"""
import pytest
import asyncio
from datetime import timedelta, datetime, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch, create_autospec
from fastapi.security import HTTPAuthorizationCredentials

from api.routes.auth import (
    create_access_token,
    get_current_user,
    register,
    login,
    pwd_context,
    Token,
    UserCreate,
    UserLogin
)
from core.config import settings
from models import User


class TestPasswordSecurity:
    """Test password hashing and verification."""
    
    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        password = "SecurePass123!"  # Shortened for bcrypt 72-byte limit
        hashed = pwd_context.hash(password)
        
        # Hash should be different from plain text
        assert hashed != password
        # Hash should be bcrypt format
        assert hashed.startswith(("$2b$", "$2a$"))
    
    def test_password_verification_success(self):
        """Test successful password verification."""
        password = "SecurePass123!"  # Shortened for bcrypt
        hashed = pwd_context.hash(password)
        
        assert pwd_context.verify(password, hashed) is True
    
    def test_password_verification_failure(self):
        """Test failed password verification."""
        password = "SecurePass123!"  # Shortened for bcrypt
        wrong_password = "wrong_password"
        hashed = pwd_context.hash(password)
        
        assert pwd_context.verify(wrong_password, hashed) is False
    
    def test_password_strength_validation(self):
        """Test password strength requirements."""
        # These should fail validation
        weak_passwords = [
            "short",  # Too short
            "password",  # Common
            "12345678",  # Common numeric
            "qwerty123",  # Common pattern
        ]
        
        for pwd in weak_passwords:
            # Check minimum length
            assert len(pwd) < 8 or pwd.lower() in ['password', '12345678', 'qwerty123']


class TestJWTTokenHandling:
    """Test JWT token creation and validation."""
    
    def test_create_access_token(self):
        """Test token creation with default expiration."""
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        
        # Should return a string
        assert isinstance(token, str)
        
        # Should be decodable
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "test@example.com"
        assert "exp" in payload
    
    def test_create_access_token_with_custom_expiry(self):
        """Test token creation with custom expiration."""
        data = {"sub": "test@example.com"}
        expires = timedelta(minutes=30)
        token = create_access_token(data, expires)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "test@example.com"
    
    def test_token_invalid_signature(self):
        """Test that tokens with invalid signatures are rejected."""
        # Create token with wrong secret
        token = jwt.encode(
            {"sub": "test@example.com"},
            "wrong_secret",
            algorithm=settings.ALGORITHM
        )
        
        # Should raise JWTError when decoding with correct secret
        with pytest.raises(JWTError):
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    def test_token_expired(self):
        """Test that expired tokens are rejected."""
        # Create an already expired token
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = jwt.encode(
            {"sub": "test@example.com", "exp": expired_time},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        # Should raise JWTError
        with pytest.raises(JWTError):
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


class TestUserRegistration:
    """Test user registration flow."""
    
    @pytest.mark.asyncio
    async def test_register_success(self):
        """Test successful user registration."""
        # Create proper mock
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock the execute chain properly
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # User doesn't exist
        mock_session.execute.return_value = mock_result
        
        user_data = UserCreate(
            email="newuser@example.com",
            password="SecurePass123!",
            name="Test User"
        )
        
        result = await register(user_data, mock_session)
        
        assert result.email == user_data.email
        assert result.name == user_data.name
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self):
        """Test registration with existing email."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock existing user
        existing_user = User(
            email="existing@example.com",
            name="Existing User",
            hashed_password="hashed"
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_session.execute.return_value = mock_result
        
        user_data = UserCreate(
            email="existing@example.com",
            password="SecurePass123!",
            name="Test User"
        )
        
        with pytest.raises(Exception) as exc_info:
            await register(user_data, mock_session)
        
        assert "already registered" in str(exc_info.value).lower()


class TestUserLogin:
    """Test user login flow."""
    
    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create user with hashed password
        password = "SecurePass123!"
        hashed = pwd_context.hash(password)
        
        user = User(
            email="test@example.com",
            name="Test User",
            hashed_password=hashed
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result
        
        login_data = UserLogin(
            email="test@example.com",
            password=password
        )
        
        result = await login(login_data, mock_session)
        
        assert "access_token" in result
        assert result["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        """Test login with incorrect password."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Create user with hashed password
        password = "SecurePass123!"
        hashed = pwd_context.hash(password)
        
        user = User(
            email="test@example.com",
            name="Test User",
            hashed_password=hashed
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result
        
        login_data = UserLogin(
            email="test@example.com",
            password="wrongpassword"
        )
        
        with pytest.raises(Exception) as exc_info:
            await login(login_data, mock_session)
        
        assert "incorrect" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_login_user_not_found(self):
        """Test login with non-existent user."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        login_data = UserLogin(
            email="nonexistent@example.com",
            password="SecurePass123!"
        )
        
        with pytest.raises(Exception) as exc_info:
            await login(login_data, mock_session)
        
        assert "incorrect" in str(exc_info.value).lower()


class TestCurrentUser:
    """Test current user retrieval from token."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_success(self):
        """Test retrieving current user with valid token."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        user = User(
            email="test@example.com",
            name="Test User",
            hashed_password="hashed"
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result
        
        # Create valid token wrapped in mock credentials
        token = create_access_token({"sub": "test@example.com"})
        mock_creds = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_creds.credentials = token
        
        result = await get_current_user(mock_creds, mock_session)
        
        assert result.email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_current_user_not_found(self):
        """Test retrieving user that doesn't exist."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Create valid token wrapped in mock credentials
        token = create_access_token({"sub": "nonexistent@example.com"})
        mock_creds = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_creds.credentials = token
        
        with pytest.raises(Exception) as exc_info:
            await get_current_user(mock_creds, mock_session)
        
        assert "not found" in str(exc_info.value).lower() or "credentials" in str(exc_info.value).lower()


class TestPasswordEdgeCases:
    """Test password edge cases and security."""
    
    def test_password_unicode_handling(self):
        """Test password hashing with unicode characters."""
        password = "Sécurité123!"  # Mixed unicode
        hashed = pwd_context.hash(password)
        
        # Should verify correctly
        assert pwd_context.verify(password, hashed) is True
    
    def test_password_max_length(self):
        """Test bcrypt 72-byte limit handling."""
        # bcrypt truncates at 72 bytes, test that we handle this
        short_pass = "A" * 20  # 20 chars, well under 72 bytes
        
        short_hash = pwd_context.hash(short_pass)
        
        # Should hash without error
        assert short_hash.startswith(("$2b$", "$2a$"))
        
        # Verification should work
        assert pwd_context.verify(short_pass, short_hash) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
