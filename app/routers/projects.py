from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    # Check for existing project name to provide immediate 409
    existing = db.query(Project).filter(Project.name == project_in.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{project_in.name}' already exists",
        )

    db_project = Project(
        name=project_in.name,
        description=project_in.description,
    )
    try:
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{project_in.name}' already exists",
        )

    return db_project


@router.get(
    "",
    response_model=List[ProjectResponse],
    summary="Get all projects",
)
def get_all_projects(
    db: Session = Depends(get_db),
) -> List[ProjectResponse]:
    return db.query(Project).order_by(Project.id.asc()).all()


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project by ID",
)
def get_project_by_id(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )
    return project


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project partially",
)
def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    update_data = project_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided to update",
        )

    # Check for name conflict if name is being changed
    if "name" in update_data and update_data["name"] != project.name:
        existing = (
            db.query(Project)
            .filter(Project.name == update_data["name"], Project.id != project_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with name '{update_data['name']}' already exists",
            )

    for field, value in update_data.items():
        setattr(project, field, value)

    try:
        db.commit()
        db.refresh(project)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{update_data.get('name')}' already exists",
        )

    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    db.delete(project)
    db.commit()
    return None
