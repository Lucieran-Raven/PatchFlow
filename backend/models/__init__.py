from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)  # For email/password auth
    github_id = Column(String(255), unique=True, nullable=True)
    github_username = Column(String(255), nullable=True)
    github_token = Column(Text, nullable=True)  # Encrypted in production
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    repositories = relationship("Repository", back_populates="owner", lazy="dynamic")
    organizations = relationship("OrganizationMember", back_populates="user", lazy="dynamic")

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    github_org_id = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    members = relationship("OrganizationMember", back_populates="organization", lazy="dynamic")
    repositories = relationship("Repository", back_populates="organization", lazy="dynamic")

class OrganizationMember(Base):
    __tablename__ = "organization_members"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(String(50), default="member")  # owner, admin, member
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="organizations")

class Repository(Base):
    __tablename__ = "repositories"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    full_name = Column(String(500), nullable=False, index=True)
    github_id = Column(String(255), unique=True, nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)
    clone_url = Column(String(500), nullable=True)
    language = Column(String(100), nullable=True)
    is_private = Column(Boolean, default=False)
    default_branch = Column(String(100), default="main")
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    last_scan_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Webhook fields
    webhook_id = Column(String(255), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    webhook_url = Column(String(500), nullable=True)
    webhook_events = Column(JSON, default=list)
    
    owner = relationship("User", back_populates="repositories")
    organization = relationship("Organization", back_populates="repositories")
    vulnerabilities = relationship("Vulnerability", back_populates="repository", lazy="dynamic")
    webhook_events_received = relationship("WebhookEvent", back_populates="repository", lazy="dynamic")
    scan_jobs = relationship("ScanJob", back_populates="repository", lazy="dynamic")

class Vulnerability(Base):
    __tablename__ = "vulnerabilities"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id"), nullable=False, index=True)
    scan_job_id = Column(String(36), ForeignKey("scan_jobs.id"), nullable=True, index=True)
    
    # Vulnerability details
    cve_id = Column(String(50), nullable=True, index=True)
    cwe_id = Column(String(50), nullable=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, index=True)  # critical, high, medium, low
    confidence_score = Column(Integer, nullable=True)  # 0-100
    
    # Location
    file_path = Column(String(500), nullable=True)
    line_start = Column(Integer, nullable=True)
    line_end = Column(Integer, nullable=True)
    package_name = Column(String(255), nullable=True)
    current_version = Column(String(100), nullable=True)
    fixed_version = Column(String(100), nullable=True)
    
    # Status
    status = Column(String(50), default="open", index=True)  # open, investigating, fixing, pr_created, merged, closed, false_positive
    
    # AI Analysis
    root_cause = Column(Text, nullable=True)
    exploitation_vector = Column(Text, nullable=True)
    risk_factors = Column(JSON, default=list)
    
    # Remediation
    fix_generated = Column(Boolean, default=False)
    fix_code = Column(Text, nullable=True)
    test_cases = Column(Text, nullable=True)
    pr_url = Column(String(500), nullable=True)
    pr_number = Column(Integer, nullable=True)
    
    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow)
    triaged_at = Column(DateTime, nullable=True)
    fixed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    repository = relationship("Repository", back_populates="vulnerabilities")
    scan_job = relationship("ScanJob", back_populates="vulnerabilities")

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id"), nullable=False, index=True)
    
    # GitHub webhook data
    event_type = Column(String(100), nullable=False, index=True)  # push, pull_request, etc.
    delivery_id = Column(String(255), unique=True, nullable=True)  # X-GitHub-Delivery header
    payload = Column(JSON, default=dict)  # Full webhook payload
    
    # Event details
    action = Column(String(100), nullable=True)  # e.g., "opened", "synchronize", "closed"
    ref = Column(String(255), nullable=True)  # Git ref (e.g., refs/heads/main)
    before_commit = Column(String(100), nullable=True)  # Previous commit SHA
    after_commit = Column(String(100), nullable=True)  # New commit SHA
    pusher_name = Column(String(255), nullable=True)
    pusher_email = Column(String(255), nullable=True)
    commit_message = Column(Text, nullable=True)
    
    # Processing status
    status = Column(String(50), default="pending", index=True)  # pending, processing, completed, failed
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    scan_triggered = Column(Boolean, default=False)
    
    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    repository = relationship("Repository", back_populates="webhook_events_received")

class ScanJob(Base):
    __tablename__ = "scan_jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id = Column(String(36), ForeignKey("repositories.id"), nullable=False, index=True)
    
    # Scan configuration
    trigger_type = Column(String(50), nullable=False)  # webhook, manual, scheduled
    branch = Column(String(100), default="main")
    scanners_used = Column(JSON, default=list)  # ['trivy', 'github_advisory']
    
    # Scan status
    status = Column(String(50), default="queued", index=True)  # queued, running, completed, failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Scan results summary
    total_findings = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    
    # Raw scan data
    scan_results = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    repository = relationship("Repository", back_populates="scan_jobs")
    vulnerabilities = relationship("Vulnerability", back_populates="scan_job", lazy="dynamic")
