from datetime import datetime, timezone
from typing import Any, Dict, List, TYPE_CHECKING
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.analysis_run import AnalysisRun
    from app.models.test_case import TestCase


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "test_case_id", name="uq_run_test_case"),
        UniqueConstraint("analysis_run_id", "rank", name="uq_run_rank"),
        CheckConstraint("score >= 0.0 AND score <= 100.0", name="chk_recommendation_score_range"),
        CheckConstraint(
            "review_status IN ('pending', 'accepted', 'rejected')",
            name="chk_recommendation_review_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    analysis_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("test_cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    impact_level: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    score_breakdown: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    supporting_evidence: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    analysis_run: Mapped["AnalysisRun"] = relationship(
        "AnalysisRun",
        back_populates="recommendations",
    )
    test_case: Mapped["TestCase"] = relationship("TestCase")

