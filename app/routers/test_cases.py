from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.module import Module
from app.models.project import Project
from app.models.test_case import TestCase
from app.schemas.test_case import TestCaseCreate, TestCaseResponse, TestCaseUpdate

router = APIRouter(
    prefix="/test-cases",
    tags=["Test Cases"],
)


@router.post(
    "",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new test case",
)
def create_test_case(
    test_case_in: TestCaseCreate,
    db: Session = Depends(get_db),
) -> TestCaseResponse:
    # 1. Validate that project exists
    project = db.query(Project).filter(Project.id == test_case_in.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {test_case_in.project_id} not found",
        )

    # 2. Validate that all module IDs exist
    modules = db.query(Module).filter(Module.id.in_(test_case_in.module_ids)).all()
    found_ids = {m.id for m in modules}
    missing_ids = set(test_case_in.module_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module(s) with ID(s) {sorted(list(missing_ids))} not found",
        )

    # 3. Verify that all associated modules belong to the same project
    mismatched = [m.id for m in modules if m.project_id != test_case_in.project_id]
    if mismatched:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Module(s) with ID(s) {mismatched} do not belong to project "
                f"{test_case_in.project_id}. Cross-project associations are not allowed."
            ),
        )

    # 4. Create the test case and associate modules
    db_test_case = TestCase(
        project_id=test_case_in.project_id,
        title=test_case_in.title,
        steps=test_case_in.steps,
        expected_result=test_case_in.expected_result,
        priority=test_case_in.priority,
        modules=modules,
    )
    db.add(db_test_case)
    db.commit()
    db.refresh(db_test_case)
    return db_test_case


@router.get(
    "",
    response_model=List[TestCaseResponse],
    summary="Get test cases with optional project_id and module_id filters",
)
def get_test_cases(
    project_id: Optional[int] = Query(None, description="Filter test cases by project ID"),
    module_id: Optional[int] = Query(None, description="Filter test cases by module ID"),
    db: Session = Depends(get_db),
) -> List[TestCaseResponse]:
    query = db.query(TestCase)

    if project_id is not None:
        query = query.filter(TestCase.project_id == project_id)

    if module_id is not None:
        query = query.join(TestCase.modules).filter(Module.id == module_id)

    return query.order_by(TestCase.id.asc()).all()


@router.get(
    "/{test_case_id}",
    response_model=TestCaseResponse,
    summary="Get a test case by ID",
)
def get_test_case_by_id(
    test_case_id: int,
    db: Session = Depends(get_db),
) -> TestCaseResponse:
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case with ID {test_case_id} not found",
        )
    return test_case


@router.patch(
    "/{test_case_id}",
    response_model=TestCaseResponse,
    summary="Update a test case partially",
)
def update_test_case(
    test_case_id: int,
    test_case_in: TestCaseUpdate,
    db: Session = Depends(get_db),
) -> TestCaseResponse:
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case with ID {test_case_id} not found",
        )

    update_data = test_case_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided to update",
        )

    # If module_ids are supplied, validate and replace associations
    if "module_ids" in update_data:
        new_module_ids = update_data.pop("module_ids")
        modules = db.query(Module).filter(Module.id.in_(new_module_ids)).all()
        found_ids = {m.id for m in modules}
        missing_ids = set(new_module_ids) - found_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module(s) with ID(s) {sorted(list(missing_ids))} not found",
            )

        # Check cross-project associations
        mismatched = [m.id for m in modules if m.project_id != test_case.project_id]
        if mismatched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Module(s) with ID(s) {mismatched} do not belong to project "
                    f"{test_case.project_id}. Cross-project associations are not allowed."
                ),
            )

        test_case.modules = modules

    # Update scalar fields
    for field, value in update_data.items():
        setattr(test_case, field, value)

    db.commit()
    db.refresh(test_case)
    return test_case


@router.delete(
    "/{test_case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a test case",
)
def delete_test_case(
    test_case_id: int,
    db: Session = Depends(get_db),
) -> None:
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case with ID {test_case_id} not found",
        )

    db.delete(test_case)
    db.commit()
    return None

