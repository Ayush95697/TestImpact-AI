from datetime import datetime, timezone
from typing import Any, Dict, List, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.analysis_run import AnalysisRun


class AnalysisExplanation(Base):
    __tablename__ = "analysis_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    analysis_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    overall_summary: Mapped[str] = mapped_column(Text, nullable=False)
    risk_observations: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    recommendation_explanations: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )
    limitations: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    analysis_run: Mapped["AnalysisRun"] = relationship(
        "AnalysisRun",
        back_populates="explanation",
    )

