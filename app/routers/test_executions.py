from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.test_case import TestCase
from app.models.test_execution import TestExecution
from app.schemas.test_execution import TestExecutionCreate, TestExecutionResponse

router = APIRouter(
    prefix="/test-executions",
    tags=["Test Executions"],
)


@router.post(
    "",
    response_model=TestExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a test execution",
)
def create_test_execution(
    execution_in: TestExecutionCreate,
    db: Session = Depends(get_db),
) -> TestExecutionResponse:
    # Validate test case existence
    test_case = db.query(TestCase).filter(TestCase.id == execution_in.test_case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case with ID {execution_in.test_case_id} not found",
        )

    db_execution = TestExecution(
        test_case_id=execution_in.test_case_id,
        status=execution_in.status,
        build_version=execution_in.build_version,
    )
    db.add(db_execution)
    db.commit()
    db.refresh(db_execution)
    return db_execution


@router.get(
    "",
    response_model=List[TestExecutionResponse],
    summary="Get test executions with optional test_case_id and project_id filters",
)
def get_test_executions(
    test_case_id: Optional[int] = Query(None, description="Filter executions by test case ID"),
    project_id: Optional[int] = Query(None, description="Filter executions by project ID"),
    db: Session = Depends(get_db),
) -> List[TestExecutionResponse]:
    query = db.query(TestExecution)

    if test_case_id is not None:
        query = query.filter(TestExecution.test_case_id == test_case_id)

    if project_id is not None:
        query = query.join(TestExecution.test_case).filter(TestCase.project_id == project_id)

    return query.order_by(TestExecution.id.asc()).all()


@router.get(
    "/{execution_id}",
    response_model=TestExecutionResponse,
    summary="Get a test execution by ID",
)
def get_test_execution_by_id(
    execution_id: int,
    db: Session = Depends(get_db),
) -> TestExecutionResponse:
    execution = db.query(TestExecution).filter(TestExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test execution with ID {execution_id} not found",
        )
    return execution

