from typing import List, TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.module import Module
    from app.models.project import Project
    from app.models.test_execution import TestExecution


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    steps: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    project: Mapped["Project"] = relationship("Project", back_populates="test_cases")
    modules: Mapped[List["Module"]] = relationship(
        "Module",
        secondary="test_case_modules",
        back_populates="test_cases",
    )
    executions: Mapped[List["TestExecution"]] = relationship(
        "TestExecution",
        back_populates="test_case",
    )

    @property
    def module_ids(self) -> List[int]:
        """Returns the list of associated module IDs."""
        return [m.id for m in self.modules]
