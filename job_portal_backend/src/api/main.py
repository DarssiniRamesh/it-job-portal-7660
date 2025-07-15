from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import auth
from .routes import profile
from .routes import jobs

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register authentication routes
app.include_router(auth.router)
# Register profile management routes
app.include_router(profile.router)
# Register job (employer/candidate) routes
app.include_router(jobs.router)

@app.get("/")
def health_check():
    return {"message": "Healthy"}
