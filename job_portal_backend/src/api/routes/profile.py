from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from jose import JWTError, jwt

from .. import models, database

# JWT config - should match the one in auth.py
SECRET_KEY = "CHANGE_THIS_SECRET_IN_PRODUCTION"
ALGORITHM = "HS256"

router = APIRouter(
    prefix="/profile",
    tags=["Profile"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# -----------------
# Utility functions
# -----------------
def get_current_user(db: Session = Depends(database.get_db), token: str = Depends(oauth2_scheme)):
    """Decode JWT and get user in DB."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub") or 0)
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

# -----------------
# Schemas
# -----------------
class EmployerProfileRead(BaseModel):
    id: int
    company_name: str
    website: Optional[str]
    description: Optional[str]

    class Config:
        orm_mode = True

class EmployerProfileUpdate(BaseModel):
    company_name: Optional[str] = Field(None, description="Company name")
    website: Optional[str] = Field(None, description="Website URL")
    description: Optional[str] = Field(None, description="Company description")

class CandidateProfileRead(BaseModel):
    id: int
    full_name: str
    resume_url: Optional[str]
    skills: Optional[str]

    class Config:
        orm_mode = True

class CandidateProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, description="Full name")
    resume_url: Optional[str] = Field(None, description="Resume file or URL")
    skills: Optional[str] = Field(None, description="Skills and tech stack")

class UserProfile(BaseModel):
    id: int
    email: EmailStr
    is_employer: bool
    employer_profile: Optional[EmployerProfileRead]
    candidate_profile: Optional[CandidateProfileRead]

    class Config:
        orm_mode = True

# -----------------
# Endpoints
# -----------------

# PUBLIC_INTERFACE
@router.get("", response_model=UserProfile, summary="Get current user's profile", tags=["Profile"])
async def get_my_profile(current_user: models.User = Depends(get_current_user)):
    """
    Returns the profile for the authenticated user.  
    - Employer: returns employer_profile.  
    - Candidate: returns candidate_profile.
    """
    return current_user

# PUBLIC_INTERFACE
@router.put("/employer", response_model=EmployerProfileRead, summary="Update employer profile", tags=["Profile"])
async def update_employer_profile(
    profile_update: EmployerProfileUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Updates the employer's profile.  
    Only for logged-in users who are employers.
    """
    if not current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only employers can update employer profiles.")
    profile = db.query(models.EmployerProfile).filter(models.EmployerProfile.user_id == current_user.id).first()
    if not profile:
        # If not exists, create new
        profile = models.EmployerProfile(user_id=current_user.id, company_name=profile_update.company_name or "")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    for field, value in profile_update.dict(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile

# PUBLIC_INTERFACE
@router.put("/candidate", response_model=CandidateProfileRead, summary="Update candidate profile", tags=["Profile"])
async def update_candidate_profile(
    profile_update: CandidateProfileUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Updates the candidate's profile.  
    Only for logged-in users who are candidates.
    """
    if current_user.is_employer:
        raise HTTPException(status_code=403, detail="Only candidates can update candidate profiles.")
    profile = db.query(models.CandidateProfile).filter(models.CandidateProfile.user_id == current_user.id).first()
    if not profile:
        # If not exists, create new
        profile = models.CandidateProfile(user_id=current_user.id, full_name=profile_update.full_name or "")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    for field, value in profile_update.dict(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
