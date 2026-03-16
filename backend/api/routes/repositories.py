from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID

from core.database import get_db
from models import Repository, User

router = APIRouter()

class RepositoryCreate(BaseModel):
    name: str
    full_name: str
    github_id: Optional[str] = None
    description: Optional[str] = None
    url: Optional[HttpUrl] = None
    is_private: bool = False
    default_branch: str = "main"

class RepositoryResponse(BaseModel):
    id: str
    name: str
    full_name: str
    description: Optional[str]
    url: Optional[str]
    is_private: bool
    default_branch: str
    is_active: bool
    last_scan_at: Optional[str]
    created_at: str
    vulnerability_count: int

    class Config:
        from_attributes = True

@router.get("/", response_model=List[RepositoryResponse])
async def list_repositories(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all repositories for the current user."""
    result = await db.execute(
        select(Repository)
        .where(Repository.is_active == True)
        .order_by(desc(Repository.created_at))
        .offset(skip)
        .limit(limit)
    )
    repositories = result.scalars().all()
    return repositories

@router.post("/", response_model=RepositoryResponse)
async def create_repository(
    repo_data: RepositoryCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new repository."""
    # Check if repository already exists
    result = await db.execute(
        select(Repository).where(Repository.full_name == repo_data.full_name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Repository already exists")
    
    repo = Repository(
        name=repo_data.name,
        full_name=repo_data.full_name,
        github_id=repo_data.github_id,
        description=repo_data.description,
        url=str(repo_data.url) if repo_data.url else None,
        is_private=repo_data.is_private,
        default_branch=repo_data.default_branch,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo

@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(repo_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific repository."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo

@router.post("/{repo_id}/scan")
async def trigger_scan(repo_id: UUID, db: AsyncSession = Depends(get_db)):
    """Trigger a security scan for a repository."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # TODO: Trigger scan via message queue
    return {
        "message": "Scan triggered",
        "repository_id": str(repo_id),
        "scan_id": "scan-123",  # TODO: Generate real scan ID
        "status": "queued"
    }

@router.delete("/{repo_id}")
async def delete_repository(repo_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete (soft delete) a repository."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    repo.is_active = False
    await db.commit()
    return {"message": "Repository deleted"}
