from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.defect import Defect
from app.models.module import Module
from app.models.project import Project
from app.schemas.defect import DefectCreate, DefectResponse, DefectUpdate

router = APIRouter(
    prefix="/defects",
    tags=["Defects"],
)


@router.post(
    "",
    response_model=DefectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new defect",
)
def create_defect(
    defect_in: DefectCreate,
    db: Session = Depends(get_db),
) -> DefectResponse:
    # 1. Validate project existence
    project = db.query(Project).filter(Project.id == defect_in.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {defect_in.project_id} not found",
        )

    # 2. Validate module existence
    module = db.query(Module).filter(Module.id == defect_in.module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module with ID {defect_in.module_id} not found",
        )

    # 3. Verify module belongs to the specified project
    if module.project_id != defect_in.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Module with ID {defect_in.module_id} belongs to project {module.project_id}, "
                f"not project {defect_in.project_id}. Cross-project association is not allowed."
            ),
        )

    db_defect = Defect(
        project_id=defect_in.project_id,
        module_id=defect_in.module_id,
        title=defect_in.title,
        description=defect_in.description,
        resolution_notes=defect_in.resolution_notes,
        severity=defect_in.severity,
    )
    db.add(db_defect)
    db.commit()
    db.refresh(db_defect)
    return db_defect


@router.get(
    "",
    response_model=List[DefectResponse],
    summary="Get defects with optional project_id and module_id filters",
)
def get_defects(
    project_id: Optional[int] = Query(None, description="Filter defects by project ID"),
    module_id: Optional[int] = Query(None, description="Filter defects by module ID"),
    db: Session = Depends(get_db),
) -> List[DefectResponse]:
    query = db.query(Defect)

    if project_id is not None:
        query = query.filter(Defect.project_id == project_id)

    if module_id is not None:
        query = query.filter(Defect.module_id == module_id)

    return query.order_by(Defect.id.asc()).all()


@router.get(
    "/{defect_id}",
    response_model=DefectResponse,
    summary="Get a defect by ID",
)
def get_defect_by_id(
    defect_id: int,
    db: Session = Depends(get_db),
) -> DefectResponse:
    defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not defect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Defect with ID {defect_id} not found",
        )
    return defect


@router.patch(
    "/{defect_id}",
    response_model=DefectResponse,
    summary="Update a defect partially",
)
def update_defect(
    defect_id: int,
    defect_in: DefectUpdate,
    db: Session = Depends(get_db),
) -> DefectResponse:
    defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not defect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Defect with ID {defect_id} not found",
        )

    update_data = defect_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided to update",
        )

    for field, value in update_data.items():
        setattr(defect, field, value)

    db.commit()
    db.refresh(defect)
    return defect


@router.delete(
    "/{defect_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a defect",
)
def delete_defect(
    defect_id: int,
    db: Session = Depends(get_db),
) -> None:
    defect = db.query(Defect).filter(Defect.id == defect_id).first()
    if not defect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Defect with ID {defect_id} not found",
        )

    db.delete(defect)
    db.commit()
    return None

