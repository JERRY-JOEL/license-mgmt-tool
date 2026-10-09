from datetime import datetime, date

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Float,
    Text,
    UniqueConstraint,
)

from sqlalchemy.orm import relationship

from database.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    vendor = Column(String(255))
    category = Column(String(100))
    owner = Column(String(255))
    environment = Column(String(100))
    status = Column(String(50), default="Active")
    last_sync = Column(DateTime)

    licenses = relationship(
        "License",
        back_populates="application",
        cascade="all, delete-orphan"
    )


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False
    )

    product = Column(String(255))
    license_type = Column(String(100))

    purchased_qty = Column(Integer)
    assigned_qty = Column(Integer)
    available_qty = Column(Integer)
    used_qty = Column(Integer)

    cost = Column(Float)
    currency = Column(String(20))
    billing_cycle = Column(String(50))

    renewal_date = Column(Date)

    data_source = Column(String(255))
    last_updated = Column(DateTime, default=datetime.utcnow)

    application = relationship(
        "Application",
        back_populates="licenses"
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id")
    )

    external_user_id = Column(String(255))
    name = Column(String(255))
    email = Column(String(255))
    status = Column(String(50))
    role = Column(String(100))

    last_activity = Column(DateTime)


class LicenseAssignment(Base):
    __tablename__ = "license_assignments"

    id = Column(Integer, primary_key=True, index=True)

    license_id = Column(
        Integer,
        ForeignKey("licenses.id")
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    assigned_date = Column(DateTime)
    status = Column(String(50))


class LicenseAssignedUser(Base):
    __tablename__ = "license_assigned_users"

    __table_args__ = (
        UniqueConstraint(
            "license_id",
            "user_id",
            name="uq_license_assigned_users_license_user",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True,
    )
    license_id = Column(
        Integer,
        ForeignKey("licenses.id"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    sku_id = Column(String(255))
    display_name = Column(String(255))
    email = Column(String(255))
    external_user_id = Column(String(255))
    status = Column(String(50), default="assigned")
    assigned_at = Column(DateTime, default=datetime.utcnow)
    last_synced_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    application = relationship("Application")
    license = relationship("License")
    user = relationship("User")


class Microsoft365Data(Base):
    __tablename__ = "microsoft365_data"

    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "sku_id",
            name="uq_microsoft365_data_application_sku",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True,
    )
    sku_id = Column(String(255), nullable=False)
    product = Column(String(255))
    sku_part_number = Column(String(255))
    license_type = Column(String(255))
    purchased_quantity = Column(Integer)
    assigned_quantity = Column(Integer)
    available_quantity = Column(Integer)
    consumed_quantity = Column(Integer)
    synced_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    application = relationship("Application")


class SlackData(Base):
    __tablename__ = "slack_data"

    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "plan",
            "license_type",
            name="uq_slack_data_application_plan_type",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True,
    )
    plan = Column(String(255))
    license_type = Column(String(255))
    purchased_quantity = Column(Integer)
    entitled_quantity = Column(Integer)
    assigned_quantity = Column(Integer)
    available_quantity = Column(Integer)
    active_users = Column(Integer)
    inactive_users = Column(Integer)
    renewal_date = Column(Date)
    cost = Column(Float)
    currency = Column(String(20))
    billing_cycle = Column(String(50))
    data_source = Column(String(255))
    synced_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    application = relationship("Application")


class Usage(Base):
    __tablename__ = "usage"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id")
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    last_activity = Column(DateTime)
    usage_status = Column(String(50))
    usage_count = Column(Integer)

    last_updated = Column(
        DateTime,
        default=datetime.utcnow
    )


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id")
    )

    contract_id = Column(String(255))
    vendor = Column(String(255))

    purchased_qty = Column(Integer)

    cost = Column(Float)
    currency = Column(String(20))

    renewal_date = Column(Date)

    source_document = Column(Text)


class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id")
    )

    sync_time = Column(
        DateTime,
        default=datetime.utcnow
    )

    status = Column(String(50))

    records_processed = Column(Integer)

    records_created = Column(Integer)

    records_updated = Column(Integer)

    records_failed = Column(Integer)

    error_message = Column(Text)


class LicenseRequest(Base):
    """
    License request raised by the IT Team on behalf of a user.

    Approval pipeline (statuses):
        pending_tower_head  -> approval email sent to Tower Head
        pending_app_owner   -> approval email sent to Application Owner
        pending_it_review   -> IT Team final action in the portal
        approved / rejected / cancelled
    """

    __tablename__ = "license_requests"

    id = Column(Integer, primary_key=True, index=True)

    # Human-friendly id shown in portal + emails, e.g. REQ-20261009-0001
    request_id = Column(
        String(50), unique=True, nullable=False, index=True
    )

    # What is being requested
    application_name = Column(String(255), nullable=False)
    license_name = Column(String(255), nullable=False)
    license_type = Column(String(100))
    quantity = Column(Integer, default=1)
    request_type = Column(String(100), default="New License")
    priority = Column(String(50), default="Normal")
    justification = Column(Text)

    # End user the license is for (request raised by IT Team for them)
    requested_for = Column(String(255), nullable=False)
    requested_for_email = Column(String(255), nullable=False)

    # Who raised it (IT Team member)
    submitted_by = Column(String(255))
    submitted_by_email = Column(String(255))

    # Pipeline status
    status = Column(
        String(50), default="pending_tower_head", index=True
    )

    # ── Step 1: Tower Head (email approval) ────────────────────────────
    tower_head_name = Column(String(255))
    tower_head_email = Column(String(255))
    tower_head_token = Column(String(255), unique=True)
    tower_head_action = Column(String(50))   # approved | rejected
    tower_head_comment = Column(Text)
    tower_head_action_at = Column(DateTime)

    # ── Step 2: Application Owner (email approval) ─────────────────────
    app_owner_name = Column(String(255))
    app_owner_email = Column(String(255))
    app_owner_token = Column(String(255), unique=True)
    app_owner_action = Column(String(50))    # approved | rejected
    app_owner_comment = Column(Text)
    app_owner_action_at = Column(DateTime)

    # ── Step 3: IT Team final action (portal) ──────────────────────────
    final_comment = Column(Text)
    final_action_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
