from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from fastapi.security import OAuth2PasswordBearer
import datetime

from .. import models, database

# JWT config - must match the one in auth.py and other routes
from jose import jwt, JWTError

SECRET_KEY = "CHANGE_THIS_SECRET_IN_PRODUCTION"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

router = APIRouter(
    prefix="/applications",
    tags=["Applications"],
)

# Utility to get current user from token
def get_current_user(db: Session = Depends(database.get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub") or 0)
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise credentials_exception
    return user

# ---------- Schemas ----------
class ApplicationBase(BaseModel):
    cover_letter: Optional[str] = Field(None, description="Candidate cover letter for this application")

class ApplicationCreate(ApplicationBase):
    job_id: int = Field(..., description="ID of the job to apply")

class ApplicationRead(ApplicationBase):
    id: int
    status: str
    created_at: datetime.datetime
    job_id: int
    candidate_id: int

    class Config:
        orm_mode = True

class ApplicationStatusUpdate(BaseModel):
    status: str = Field(..., description="New application status (applied, reviewed, rejected, accepted)")

class CandidateBrief(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    resume_url: Optional[str]
    skills: Optional[str]
    class Config:
        orm_mode = True

class ApplicationWithCandidate(ApplicationRead):
    candidate: Optional[CandidateBrief]

# ---------- Candidate APIs ----------

# PUBLIC_INTERFACE
@router.post("/", response_model=ApplicationRead, summary="Apply for a job", tags=["Applications"])
def apply_for_job(
    application: ApplicationCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Candidate applies for a job posting. Must be authenticated as candidate.
    """
    if current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only candidates can apply for jobs.")

    # Cannot apply to the same job more than once
    existing = db.query(models.Application).filter(
        models.Application.job_id == application.job_id,
        models.Application.candidate_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Application already exists for this job.")

    # Ensure job exists and is active
    job = db.query(models.Job).filter(models.Job.id == application.job_id, models.Job.is_active == True).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or not active.")

    db_app = models.Application(
        job_id=application.job_id,
        candidate_id=current_user.id,
        cover_letter=application.cover_letter,
        status="applied"
    )
    db.add(db_app)
    db.commit()
    db.refresh(db_app)
    return db_app

# PUBLIC_INTERFACE
@router.get("/my", response_model=List[ApplicationRead], summary="List my applications", tags=["Applications"])
def list_my_applications(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Current user (candidate) views all their job applications.
    """
    if current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only candidates can view their applications.")
    apps = db.query(models.Application).filter(models.Application.candidate_id == current_user.id).order_by(
        models.Application.created_at.desc()
    ).all()
    return apps

# PUBLIC_INTERFACE
@router.get("/my/{application_id}", response_model=ApplicationRead, summary="Get my application status", tags=["Applications"])
def get_my_application(
    application_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get details and status for your own application.
    """
    if current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only candidates can view their application status.")
    app = db.query(models.Application).filter(
        models.Application.id == application_id,
        models.Application.candidate_id == current_user.id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")
    return app

# ---------- Employer APIs ----------

# PUBLIC_INTERFACE
@router.get("/job/{job_id}/applicants", response_model=List[ApplicationWithCandidate],
            summary="View applicants for a job posting", tags=["Applications"])
def list_applicants_for_job(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Employer can view all applicants for a specific job posting they own.
    """
    if not current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only employers can view applicants.")
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.employer_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or not owned by employer.")
    apps = db.query(models.Application).filter(models.Application.job_id == job_id).all()

    # Attach brief candidate profile
    result = []
    for app in apps:
        user = db.query(models.User).filter(models.User.id == app.candidate_id).first()
        candidate_prof = db.query(models.CandidateProfile).filter(models.CandidateProfile.user_id == app.candidate_id).first()
        result.append(ApplicationWithCandidate(
            **app.__dict__,
            candidate=CandidateBrief(
                id=user.id,
                email=user.email,
                full_name=candidate_prof.full_name if candidate_prof else None,
                resume_url=candidate_prof.resume_url if candidate_prof else None,
                skills=candidate_prof.skills if candidate_prof else None,
            ) if user else None
        ))
    return result

# PUBLIC_INTERFACE
@router.put("/{application_id}/status", response_model=ApplicationRead,
            summary="Update application status", tags=["Applications"])
def update_application_status(
    application_id: int,
    status_update: ApplicationStatusUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Employer updates the status of an application (applied/reviewed/rejected/accepted).
    """
    if not current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only employers can update application statuses.")

    app = db.query(models.Application).join(models.Job).filter(
        models.Application.id == application_id,
        models.Job.employer_id == current_user.id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not owned by employer.")
    valid_statuses = {"applied", "reviewed", "rejected", "accepted"}
    if status_update.status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Invalid status value.")
    app.status = status_update.status
    db.commit()
    db.refresh(app)
    return app
