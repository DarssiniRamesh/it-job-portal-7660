from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_
import datetime

from .. import models, database

# JWT config - must match the one in auth.py and profile.py
from jose import jwt, JWTError

SECRET_KEY = "CHANGE_THIS_SECRET_IN_PRODUCTION"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)

# ----------- UTILS: Auth & Get current user ------------
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

# ------------- Pydantic Schemas -------------
class JobBase(BaseModel):
    title: str = Field(..., description="Job title")
    description: str = Field(..., description="Job description")
    location: Optional[str] = Field(None, description="Job location")
    salary: Optional[str] = Field(None, description="Salary range")
    is_active: Optional[bool] = Field(True, description="Is the job posting active?")

class JobCreate(JobBase):
    pass

class JobUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    location: Optional[str]
    salary: Optional[str]
    is_active: Optional[bool]

class JobRead(JobBase):
    id: int
    posted_at: datetime.datetime
    employer_id: int

    class Config:
        orm_mode = True

# ---------- Employer APIs: CRUD --------------
# PUBLIC_INTERFACE
@router.post("/", response_model=JobRead, summary="Create a Job Posting", tags=["Jobs"])
def create_job(
    job: JobCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Employer creates a job posting. User must be authenticated employer.
    """
    if not current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only employers can create job postings.")
    db_job = models.Job(
        title=job.title,
        description=job.description,
        location=job.location,
        salary=job.salary,
        is_active=job.is_active,
        employer_id=current_user.id
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

# PUBLIC_INTERFACE
@router.get("/my", response_model=List[JobRead], summary="List My Posted Jobs", tags=["Jobs"])
def list_my_jobs(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Employer lists all jobs they've posted.
    """
    if not current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only employers can view their jobs.")
    jobs = db.query(models.Job).filter(models.Job.employer_id == current_user.id).all()
    return jobs

# PUBLIC_INTERFACE
@router.get("/{job_id}", response_model=JobRead, summary="Get Job Details", tags=["Jobs"])
def get_job(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get details for a specific job posting (employer only).
    """
    job = db.query(models.Job).filter(models.Job.id == job_id, models.Job.employer_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only employers can access individual job details.")
    return job

# PUBLIC_INTERFACE
@router.put("/{job_id}", response_model=JobRead, summary="Update a Job Posting", tags=["Jobs"])
def update_job(
    job_id: int,
    job_update: JobUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update a job posting (employer only).
    """
    job = db.query(models.Job).filter(models.Job.id == job_id, models.Job.employer_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only employers can update jobs.")
    for field, value in job_update.dict(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job

# PUBLIC_INTERFACE
@router.delete("/{job_id}", summary="Delete a Job Posting", tags=["Jobs"])
def delete_job(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Delete a job posting (employer only).
    """
    job = db.query(models.Job).filter(models.Job.id == job_id, models.Job.employer_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only employers can delete jobs.")
    db.delete(job)
    db.commit()
    return {"detail": "Job deleted successfully."}

# ----------- Candidate APIs: LIST/SEARCH/FILTER -----------
# PUBLIC_INTERFACE
@router.get("/", response_model=List[JobRead], summary="List/Search/Filter IT Jobs", tags=["Jobs"])
def list_jobs(
    db: Session = Depends(database.get_db),
    search: Optional[str] = Query(None, description="Search in title/description/location"),
    location: Optional[str] = Query(None, description="Location filter"),
    min_salary: Optional[int] = Query(None, description="Minimum salary (as integer, if possible)"),
    only_active: bool = Query(True, description="Only active jobs")
):
    """
    List/search/filter IT jobs (for candidates & public). Supports:
    - Keyword search by title/description/location
    - Filter by location
    - Filter by min salary (if salary is convertible to an integer)
    - Only active jobs by default
    """
    query = db.query(models.Job)
    if only_active:
        query = query.filter(models.Job.is_active == True)
    if search:
        ilike = f"%{search.lower()}%"
        query = query.filter(
            or_(
                models.Job.title.ilike(ilike),
                models.Job.description.ilike(ilike),
                models.Job.location.ilike(ilike)
            )
        )
    if location:
        query = query.filter(models.Job.location.ilike(f"%{location.lower()}%"))
    jobs = query.order_by(models.Job.posted_at.desc()).all()

    # Apply min_salary filter if possible
    if min_salary is not None:
        def parse_salary(s):
            if not s:
                return 0
            if isinstance(s, int):
                return s
            try:
                # Common patterns: "10000", "$10000", "10,000 USD", "10k"
                s_clean = s.replace('$', '').replace(',', '').lower()
                if 'k' in s_clean:
                    s_clean = s_clean.replace('k', '')
                    return int(float(s_clean) * 1000)
                # Grab first sequence of digits
                import re
                digits = re.findall(r"\d+", s_clean)
                if digits:
                    return int(digits[0])
            except Exception:
                return 0
            return 0
        jobs = [job for job in jobs if parse_salary(job.salary) >= min_salary]

    return jobs
