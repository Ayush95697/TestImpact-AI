from sqlalchemy import Column, ForeignKey, Integer, Table

from app.database import Base

test_case_modules = Table(
    "test_case_modules",
    Base.metadata,
    Column(
        "test_case_id",
        Integer,
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "module_id",
        Integer,
        ForeignKey("modules.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)

