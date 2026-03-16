from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
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
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    github_org_id = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    members = relationship("OrganizationMember", back_populates="organization", lazy="dynamic")
    repositories = relationship("Repository", back_populates="organization", lazy="dynamic")

class OrganizationMember(Base):
    __tablename__ = "organization_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(String(50), default="member")  # owner, admin, member
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="organizations")

class Repository(Base):
    __tablename__ = "repositories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    full_name = Column(String(500), nullable=False, index=True)
    github_id = Column(String(255), unique=True, nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)
    is_private = Column(Boolean, default=False)
    default_branch = Column(String(100), default="main")
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    last_scan_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner = relationship("User", back_populates="repositories")
    organization = relationship("Organization", back_populates="repositories")
    vulnerabilities = relationship("Vulnerability", back_populates="repository", lazy="dynamic")

class Vulnerability(Base):
    __tablename__ = "vulnerabilities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False, index=True)
    
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
