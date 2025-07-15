from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, DateTime, Text
)
from sqlalchemy.orm import relationship
from .database import Base

import datetime

# PUBLIC_INTERFACE
class User(Base):
    """
    User model for authentication and account management.
    Can act as 'candidate' or 'employer'.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    is_employer = Column(Boolean, default=False)  # True for Employer, False for Candidate

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    employer_profile = relationship("EmployerProfile", back_populates="user", uselist=False)
    candidate_profile = relationship("CandidateProfile", back_populates="user", uselist=False)
    jobs = relationship("Job", back_populates="employer", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="candidate")

# PUBLIC_INTERFACE
class EmployerProfile(Base):
    """
    Profile for an employer, linked one-to-one with User.
    """
    __tablename__ = "employer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    website = Column(String(255))
    description = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    user = relationship("User", back_populates="employer_profile")

# PUBLIC_INTERFACE
class CandidateProfile(Base):
    """
    Profile for a candidate, linked one-to-one with User.
    """
    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    resume_url = Column(String(512))
    skills = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    user = relationship("User", back_populates="candidate_profile")

# PUBLIC_INTERFACE
class Job(Base):
    """
    Job posting, created by Employer.
    """
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(255))
    salary = Column(String(255))
    is_active = Column(Boolean, default=True)
    posted_at = Column(DateTime, default=datetime.datetime.utcnow)

    employer_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    employer = relationship("User", back_populates="jobs")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

# PUBLIC_INTERFACE
class Application(Base):
    """
    Job Application, created by Candidate for a Job.
    """
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(64), default="applied")  # e.g., applied, reviewed, rejected, accepted
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    cover_letter = Column(Text)

    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    job = relationship("Job", back_populates="applications")
    candidate = relationship("User", back_populates="applications")
