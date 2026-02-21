import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Boolean, Integer, Text,
    DateTime, ForeignKey, UniqueConstraint, CheckConstraint,
)
from sqlalchemy.types import JSON
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def gen_uuid():
    return str(uuid.uuid4())


# Use JSON (works on both SQLite and PostgreSQL; use JSONB on Postgres for production)
class Institution(Base):
    __tablename__ = "institutions"
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    domain = Column(String, unique=True)
    module_config = Column(JSON, default=dict)
    weight_config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="institution")
    submissions = relationship("Submission", back_populates="institution")
    module_configs = relationship("ModuleConfig", back_populates="institution")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    institution_id = Column(String, ForeignKey("institutions.id"), nullable=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="student")
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    institution = relationship("Institution", back_populates="users")
    submissions = relationship("Submission", back_populates="user")
    writing_profile = relationship("WritingProfile", back_populates="user", uselist=False)


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    institution_id = Column(String, ForeignKey("institutions.id"), nullable=True)
    file_path = Column(String, nullable=False)
    file_hash = Column(String, nullable=False)
    text_hash = Column(String)
    original_filename = Column(String)
    file_size_bytes = Column(Integer)
    word_count = Column(Integer)
    status = Column(String, default="pending")
    modules_requested = Column(JSON)
    assignment_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="submissions")
    institution = relationship("Institution", back_populates="submissions")
    report = relationship("IntegrityReport", back_populates="submission", uselist=False)


class IntegrityReport(Base):
    __tablename__ = "integrity_reports"
    id = Column(String, primary_key=True, default=gen_uuid)
    submission_id = Column(String, ForeignKey("submissions.id"), unique=True)
    integrity_score = Column(Float, nullable=False)
    risk_level = Column(String)
    confidence = Column(Float)
    module_results = Column(JSON, nullable=False)
    weights_used = Column(JSON)
    recommendation = Column(Text)
    flags = Column(JSON)
    pdf_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    submission = relationship("Submission", back_populates="report")


class WritingProfile(Base):
    __tablename__ = "writing_profiles"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True)
    feature_vector = Column(JSON, nullable=False)  # stored as list
    sample_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="writing_profile")


class ModuleConfig(Base):
    __tablename__ = "module_configs"
    id = Column(String, primary_key=True, default=gen_uuid)
    institution_id = Column(String, ForeignKey("institutions.id"))
    module_id = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    weight = Column(Float, default=1.0)
    config = Column(JSON, default=dict)

    institution = relationship("Institution", back_populates="module_configs")
    __table_args__ = (UniqueConstraint("institution_id", "module_id"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=gen_uuid)
    actor_id = Column(String)
    action = Column(String, nullable=False)
    resource_type = Column(String)
    resource_id = Column(String)
    details = Column(JSON)
    ip_address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
