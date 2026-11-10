from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.module import Module
from app.models.project import Project
from app.schemas.module import ModuleCreate, ModuleResponse, ModuleUpdate

router = APIRouter(tags=["Modules"])


@router.post(
    "/projects/{project_id}/modules",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a module inside a project",
)
def create_module_in_project(
    project_id: int,
    module_in: ModuleCreate,
    db: Session = Depends(get_db),
) -> ModuleResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    existing = (
        db.query(Module)
        .filter(Module.project_id == project_id, Module.name == module_in.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Module with name '{module_in.name}' already exists in project {project_id}",
        )

    db_module = Module(
        project_id=project_id,
        name=module_in.name,
        description=module_in.description,
    )
    try:
        db.add(db_module)
        db.commit()
        db.refresh(db_module)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Module with name '{module_in.name}' already exists in project {project_id}",
        )

    return db_module


@router.get(
    "/projects/{project_id}/modules",
    response_model=List[ModuleResponse],
    summary="Get all modules in a project",
)
def get_modules_in_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> List[ModuleResponse]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found",
        )

    return (
        db.query(Module)
        .filter(Module.project_id == project_id)
        .order_by(Module.id.asc())
        .all()
    )


@router.get(
    "/modules/{module_id}",
    response_model=ModuleResponse,
    summary="Get a module by ID",
)
def get_module_by_id(
    module_id: int,
    db: Session = Depends(get_db),
) -> ModuleResponse:
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module with ID {module_id} not found",
        )
    return module


@router.patch(
    "/modules/{module_id}",
    response_model=ModuleResponse,
    summary="Update a module partially",
)
def update_module(
    module_id: int,
    module_in: ModuleUpdate,
    db: Session = Depends(get_db),
) -> ModuleResponse:
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module with ID {module_id} not found",
        )

    update_data = module_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided to update",
        )

    if "name" in update_data and update_data["name"] != module.name:
        existing = (
            db.query(Module)
            .filter(
                Module.project_id == module.project_id,
                Module.name == update_data["name"],
                Module.id != module_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Module with name '{update_data['name']}' already exists in project {module.project_id}",
            )

    for field, value in update_data.items():
        setattr(module, field, value)

    try:
        db.commit()
        db.refresh(module)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Module with name '{update_data.get('name')}' already exists in project {module.project_id}",
        )

    return module


@router.delete(
    "/modules/{module_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a module",
)
def delete_module(
    module_id: int,
    db: Session = Depends(get_db),
) -> None:
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module with ID {module_id} not found",
        )

    # Check if module is associated with test cases
    if module.test_cases:
        tc_count = len(module.test_cases)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete module with ID {module_id} because it is associated with "
                f"{tc_count} test case(s). Unlink or reassign them first."
            ),
        )

    # Check if module is associated with defects
    if module.defects:
        defect_count = len(module.defects)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete module with ID {module_id} because it is associated with "
                f"{defect_count} defect(s). Unlink or reassign them first."
            ),
        )

    # Check if module is associated with change requests
    if module.change_requests:
        cr_count = len(module.change_requests)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete module with ID {module_id} because it is associated with "
                f"{cr_count} change request(s). Unlink or reassign them first."
            ),
        )

    db.delete(module)
    db.commit()
    return None
