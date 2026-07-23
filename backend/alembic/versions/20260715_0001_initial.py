"""initial schema

Revision ID: 20260715_0001
Revises:
Create Date: 2026-07-15 00:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260715_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role = postgresql.ENUM("admin", "viewer", name="user_role", create_type=False)
deploy_strategy = postgresql.ENUM("canary", "blue_green", name="deploy_strategy", create_type=False)
deploy_status = postgresql.ENUM("pending", "running", "shifted", "failed", name="deploy_status", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    deploy_strategy.create(bind, checkfirst=True)
    deploy_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    op.create_table(
        "models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_team", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_models_id"), "models", ["id"], unique=False)
    op.create_index(op.f("ix_models_name"), "models", ["name"], unique=False)

    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("artifact_uri", sa.String(length=1024), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_versions_id"), "model_versions", ["id"], unique=False)
    op.create_index(op.f("ix_model_versions_model_id"), "model_versions", ["model_id"], unique=False)

    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=False),
        sa.Column("run_name", sa.String(length=255), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("artifact_uri", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_experiments_id"), "experiments", ["id"], unique=False)

    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False, server_default="staging"),
        sa.Column("strategy", deploy_strategy, nullable=False),
        sa.Column("status", deploy_status, nullable=False),
        sa.Column("traffic_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deployments_id"), "deployments", ["id"], unique=False)

    op.create_table(
        "inference_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_version_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inference_logs_created_at"), "inference_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_inference_logs_id"), "inference_logs", ["id"], unique=False)
    op.create_index(op.f("ix_inference_logs_model_version_id"), "inference_logs", ["model_version_id"], unique=False)
    op.create_index(op.f("ix_inference_logs_request_id"), "inference_logs", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_inference_logs_request_id"), table_name="inference_logs")
    op.drop_index(op.f("ix_inference_logs_model_version_id"), table_name="inference_logs")
    op.drop_index(op.f("ix_inference_logs_id"), table_name="inference_logs")
    op.drop_index(op.f("ix_inference_logs_created_at"), table_name="inference_logs")
    op.drop_table("inference_logs")

    op.drop_index(op.f("ix_deployments_id"), table_name="deployments")
    op.drop_table("deployments")

    op.drop_index(op.f("ix_experiments_id"), table_name="experiments")
    op.drop_table("experiments")

    op.drop_index(op.f("ix_model_versions_model_id"), table_name="model_versions")
    op.drop_index(op.f("ix_model_versions_id"), table_name="model_versions")
    op.drop_table("model_versions")

    op.drop_index(op.f("ix_models_name"), table_name="models")
    op.drop_index(op.f("ix_models_id"), table_name="models")
    op.drop_table("models")

    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    deploy_status.drop(bind, checkfirst=True)
    deploy_strategy.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
