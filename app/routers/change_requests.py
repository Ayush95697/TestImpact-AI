from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.change_request import ChangeRequest
from app.models.module import Module
from app.models.project import Project
from app.schemas.change_request import (
    ChangeRequestCreate,
    ChangeRequestResponse,
    ChangeRequestUpdate,
)

router = APIRouter(
    prefix="/change-requests",
    tags=["Change Requests"],
)


@router.post(
    "",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new change request",
)
def create_change_request(
    cr_in: ChangeRequestCreate,
    db: Session = Depends(get_db),
) -> ChangeRequestResponse:
    # 1. Validate project existence
    project = db.query(Project).filter(Project.id == cr_in.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {cr_in.project_id} not found",
        )

    # 2. Validate all supplied modules exist
    modules = db.query(Module).filter(Module.id.in_(cr_in.module_ids)).all()
    found_ids = {m.id for m in modules}
    missing_ids = set(cr_in.module_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module(s) with ID(s) {sorted(list(missing_ids))} not found",
        )

    # 3. Verify all modules belong to the specified project
    mismatched = [m.id for m in modules if m.project_id != cr_in.project_id]
    if mismatched:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Module(s) with ID(s) {mismatched} do not belong to project "
                f"{cr_in.project_id}. Cross-project association is not allowed."
            ),
        )

    db_cr = ChangeRequest(
        project_id=cr_in.project_id,
        title=cr_in.title,
        description=cr_in.description,
        status=cr_in.status,
        modules=modules,
    )
    db.add(db_cr)
    db.commit()
    db.refresh(db_cr)
    return db_cr


@router.get(
    "",
    response_model=List[ChangeRequestResponse],
    summary="Get change requests with optional project_id and module_id filters",
)
def get_change_requests(
    project_id: Optional[int] = Query(None, description="Filter change requests by project ID"),
    module_id: Optional[int] = Query(None, description="Filter change requests by module ID"),
    db: Session = Depends(get_db),
) -> List[ChangeRequestResponse]:
    query = db.query(ChangeRequest)

    if project_id is not None:
        query = query.filter(ChangeRequest.project_id == project_id)

    if module_id is not None:
        query = query.join(ChangeRequest.modules).filter(Module.id == module_id)

    return query.order_by(ChangeRequest.id.asc()).all()


@router.get(
    "/{change_request_id}",
    response_model=ChangeRequestResponse,
    summary="Get a change request by ID",
)
def get_change_request_by_id(
    change_request_id: int,
    db: Session = Depends(get_db),
) -> ChangeRequestResponse:
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == change_request_id).first()
    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request with ID {change_request_id} not found",
        )
    return cr


@router.patch(
    "/{change_request_id}",
    response_model=ChangeRequestResponse,
    summary="Update a change request partially",
)
def update_change_request(
    change_request_id: int,
    cr_in: ChangeRequestUpdate,
    db: Session = Depends(get_db),
) -> ChangeRequestResponse:
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == change_request_id).first()
    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request with ID {change_request_id} not found",
        )

    update_data = cr_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided to update",
        )

    # Handle module_ids update if provided
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
        mismatched = [m.id for m in modules if m.project_id != cr.project_id]
        if mismatched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Module(s) with ID(s) {mismatched} do not belong to project "
                    f"{cr.project_id}. Cross-project association is not allowed."
                ),
            )

        cr.modules = modules

    for field, value in update_data.items():
        setattr(cr, field, value)

    db.commit()
    db.refresh(cr)
    return cr


@router.delete(
    "/{change_request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a change request",
)
def delete_change_request(
    change_request_id: int,
    db: Session = Depends(get_db),
) -> None:
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == change_request_id).first()
    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request with ID {change_request_id} not found",
        )

    db.delete(cr)
    db.commit()
    return None

