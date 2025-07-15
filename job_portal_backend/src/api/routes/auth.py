from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext

from .. import models, database

# JWT configuration
SECRET_KEY = "CHANGE_THIS_SECRET_IN_PRODUCTION"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# Pydantic schemas
class UserRegister(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="Password")
    is_employer: Optional[bool] = Field(False, description="Register as employer")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

# PUBLIC_INTERFACE
@router.post("/register", response_model=Token, summary="Register user")
async def register_user(user: UserRegister, db: Session = Depends(database.get_db)):
    """
    Registers a new user (either candidate or employer).
    Ensures unique email and securely hashes passwords.
    """
    existing_user = get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered.")

    hashed_password = get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        is_employer=bool(user.is_employer)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    payload = {"sub": str(new_user.id), "email": new_user.email, "is_employer": new_user.is_employer}
    token = create_access_token(data=payload)
    return {"access_token": token, "token_type": "bearer"}

# PUBLIC_INTERFACE
@router.post("/login", response_model=Token, summary="User login with email & password")
async def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """
    Authenticates user and returns a JWT on successful login.

    - **username (email)**: Email of the user.
    - **password**: Password of the user.
    """
    user = get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    payload = {"sub": str(user.id), "email": user.email, "is_employer": user.is_employer}
    token = create_access_token(data=payload)
    return {"access_token": token, "token_type": "bearer"}
