"""GitHub OAuth integration for PatchFlow."""
import httpx
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.config import settings
from models import User, Repository
from api.routes.auth import create_access_token, get_current_user as get_current_user_from_token
import secrets

router = APIRouter(prefix="/github", tags=["GitHub Integration"])

# In-memory state storage (use Redis in production)
oauth_states = {}

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"


@router.get("/login")
async def github_login():
    """Initiate GitHub OAuth flow."""
    state = secrets.token_urlsafe(32)
    oauth_states[state] = True
    
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": f"{settings.FRONTEND_URL}/auth/github/callback",
        "scope": "repo read:user read:org",
        "state": state
    }
    
    auth_url = f"{GITHUB_AUTH_URL}?client_id={params['client_id']}&redirect_uri={params['redirect_uri']}&scope={params['scope']}&state={params['state']}"
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle GitHub OAuth callback."""
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    del oauth_states[state]
    
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{settings.FRONTEND_URL}/auth/github/callback"
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get access token")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received")
    
    # Get user info from GitHub
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            f"{GITHUB_API_URL}/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")
        
        github_user = user_response.json()
    
    # Create or update user in database
    from sqlalchemy import select
    
    result = await db.execute(
        select(User).where(User.email == github_user.get("email"))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user
        user = User(
            email=github_user.get("email") or f"{github_user['login']}@github.com",
            full_name=github_user.get("name") or github_user["login"],
            github_id=str(github_user["id"]),
            github_token=access_token,
            github_username=github_user["login"],
            is_active=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Update existing user
        user.github_id = str(github_user["id"])
        user.github_token = access_token
        user.github_username = github_user["login"]
        await db.commit()
    
    # Create JWT token
    jwt_token = create_access_token({"sub": str(user.id)})
    
    # Redirect to frontend with token
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}"
    )


@router.get("/repos")
async def list_github_repos(
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """List user's GitHub repositories."""
    if not current_user.github_token:
        raise HTTPException(status_code=401, detail="GitHub not connected")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/user/repos",
            headers={
                "Authorization": f"Bearer {current_user.github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={"sort": "updated", "per_page": 100}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch repositories")
        
        repos = response.json()
    
    # Store repos in database
    from sqlalchemy import select
    stored_repos = []
    
    for repo_data in repos:
        result = await db.execute(
            select(Repository).where(Repository.github_id == str(repo_data["id"]))
        )
        repo = result.scalar_one_or_none()
        
        if not repo:
            repo = Repository(
                github_id=str(repo_data["id"]),
                name=repo_data["name"],
                full_name=repo_data["full_name"],
                url=repo_data["html_url"],
                clone_url=repo_data["clone_url"],
                language=repo_data.get("language"),
                owner_id=current_user.id,
                is_active=True
            )
            db.add(repo)
        else:
            repo.name = repo_data["name"]
            repo.full_name = repo_data["full_name"]
            repo.url = repo_data["html_url"]
            repo.language = repo_data.get("language")
        
        stored_repos.append(repo)
    
    await db.commit()
    
    return {
        "repositories": [
            {
                "id": repo.id,
                "github_id": repo.github_id,
                "name": repo.name,
                "full_name": repo.full_name,
                "url": repo.url,
                "language": repo.language,
                "is_active": repo.is_active
            }
            for repo in stored_repos
        ]
    }
