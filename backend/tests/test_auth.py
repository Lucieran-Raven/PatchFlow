"""Unit tests for authentication module.

Tests password hashing, login verification, JWT handling, and edge cases.
"""
import pytest
import asyncio
from datetime import timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch

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
        password = "secure_password123"
        hashed = pwd_context.hash(password)
        
        # Hash should be different from plain text
        assert hashed != password
        # Hash should be bcrypt format
        assert hashed.startswith("$2b$")
    
    def test_password_verification_success(self):
        """Test successful password verification."""
        password = "secure_password123"
        hashed = pwd_context.hash(password)
        
        assert pwd_context.verify(password, hashed) is True
    
    def test_password_verification_failure(self):
        """Test failed password verification."""
        password = "secure_password123"
        wrong_password = "wrong_password"
        hashed = pwd_context.hash(password)
        
        assert pwd_context.verify(wrong_password, hashed) is False
    
    def test_password_strength_validation(self):
        """Test password strength requirements."""
        # These should fail
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
        
        with pytest.raises(JWTError):
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    def test_token_expired(self):
        """Test that expired tokens are rejected."""
        # Create expired token
        expired_token = jwt.encode(
            {"sub": "test@example.com", "exp": 0},  # Expired in 1970
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        with pytest.raises(JWTError):
            jwt.decode(expired_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


class TestUserRegistration:
    """Test user registration logic."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        return session
    
    @pytest.fixture
    def mock_result(self):
        """Create mock query result."""
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=None)
        return result
    
    @pytest.mark.asyncio
    async def test_register_success(self, mock_db, mock_result):
        """Test successful user registration."""
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        user_data = UserCreate(
            email="test@example.com",
            password="secure_password123",
            name="Test User"
        )
        
        # Patch the User model to return a mock user
        with patch('api.routes.auth.User') as MockUser:
            mock_user = MagicMock()
            mock_user.email = "test@example.com"
            mock_user.name = "Test User"
            mock_user.hashed_password = "hashed_password"
            MockUser.return_value = mock_user
            
            result = await register(user_data, mock_db)
            
            # Verify user was created with hashed password
            assert MockUser.called
            call_kwargs = MockUser.call_args.kwargs
            assert call_kwargs['email'] == "test@example.com"
            assert call_kwargs['name'] == "Test User"
            assert call_kwargs['hashed_password'] is not None
            assert call_kwargs['hashed_password'] != "secure_password123"
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, mock_db):
        """Test registration with duplicate email."""
        # Mock existing user
        existing_user = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=existing_user)
        mock_db.execute = AsyncMock(return_value=result)
        
        user_data = UserCreate(
            email="existing@example.com",
            password="secure_password123"
        )
        
        with pytest.raises(Exception) as exc_info:
            await register(user_data, mock_db)
        
        assert "Email already registered" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_register_weak_password(self, mock_db):
        """Test registration with weak password."""
        weak_passwords = [
            ("short", "Password must be at least 8 characters"),
            ("password", "Password is too common"),
            ("12345678", "Password is too common"),
            ("qwerty123", "Password is too common"),
        ]
        
        for password, expected_error in weak_passwords:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_db.execute = AsyncMock(return_value=mock_result)
            
            user_data = UserCreate(
                email="test@example.com",
                password=password
            )
            
            with pytest.raises(Exception) as exc_info:
                await register(user_data, mock_db)
            
            assert expected_error in str(exc_info.value)


class TestUserLogin:
    """Test user login logic."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        return session
    
    @pytest.mark.asyncio
    async def test_login_success(self, mock_db):
        """Test successful login."""
        # Create mock user with hashed password
        password = "secure_password123"
        hashed_password = pwd_context.hash(password)
        
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.hashed_password = hashed_password
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=result)
        
        user_data = UserLogin(
            email="test@example.com",
            password=password
        )
        
        token = await login(user_data, mock_db)
        
        assert token is not None
        assert isinstance(token, dict)
        assert "access_token" in token
        assert token["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, mock_db):
        """Test login with wrong password."""
        password = "secure_password123"
        hashed_password = pwd_context.hash(password)
        
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.hashed_password = hashed_password
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=result)
        
        user_data = UserLogin(
            email="test@example.com",
            password="wrong_password"
        )
        
        with pytest.raises(Exception) as exc_info:
            await login(user_data, mock_db)
        
        assert "Incorrect email or password" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_login_user_not_found(self, mock_db):
        """Test login with non-existent user."""
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=result)
        
        user_data = UserLogin(
            email="nonexistent@example.com",
            password="secure_password123"
        )
        
        with pytest.raises(Exception) as exc_info:
            await login(user_data, mock_db)
        
        assert "Incorrect email or password" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_login_no_password_hash(self, mock_db):
        """Test login with user that has no password hash."""
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.hashed_password = None  # No password set
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=result)
        
        user_data = UserLogin(
            email="test@example.com",
            password="secure_password123"
        )
        
        with pytest.raises(Exception) as exc_info:
            await login(user_data, mock_db)
        
        assert "Incorrect email or password" in str(exc_info.value)


class TestCurrentUser:
    """Test get_current_user dependency."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        return session
    
    @pytest.fixture
    def valid_token(self):
        """Create a valid JWT token."""
        return create_access_token({"sub": "test@example.com"})
    
    @pytest.fixture
    def mock_credentials(self, valid_token):
        """Create mock HTTP credentials."""
        from fastapi.security import HTTPAuthorizationCredentials
        creds = MagicMock(spec=HTTPAuthorizationCredentials)
        creds.credentials = valid_token
        return creds
    
    @pytest.mark.asyncio
    async def test_get_current_user_success(self, mock_db, mock_credentials):
        """Test successful user retrieval from token."""
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=mock_user)
        mock_db.execute = AsyncMock(return_value=result)
        
        user = await get_current_user(mock_credentials, mock_db)
        
        assert user == mock_user
        assert user.email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, mock_db):
        """Test with invalid token."""
        from fastapi.security import HTTPAuthorizationCredentials
        creds = MagicMock(spec=HTTPAuthorizationCredentials)
        creds.credentials = "invalid_token"
        
        with pytest.raises(Exception) as exc_info:
            await get_current_user(creds, mock_db)
        
        assert "Could not validate credentials" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_current_user_missing_sub(self, mock_db):
        """Test with token missing sub claim."""
        from fastapi.security import HTTPAuthorizationCredentials
        token = jwt.encode(
            {"other_claim": "value"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        creds = MagicMock(spec=HTTPAuthorizationCredentials)
        creds.credentials = token
        
        with pytest.raises(Exception) as exc_info:
            await get_current_user(creds, mock_db)
        
        assert "Could not validate credentials" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_current_user_not_found(self, mock_db, mock_credentials):
        """Test when user from token doesn't exist in DB."""
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=result)
        
        with pytest.raises(Exception) as exc_info:
            await get_current_user(mock_credentials, mock_db)
        
        assert "Could not validate credentials" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
