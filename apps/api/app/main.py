from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.config import settings
from app.database import Base, engine, get_db
from app.models import Project, TrainingWebsite, TrainingSession, AuditEvent
from app.schemas import WebsiteCreate, WebsiteRead, SessionCreate, SessionRead, HealthRead
from app.security import validate_target_url, UnsafeTarget
from app.tasks import explore_training_session

Base.metadata.create_all(bind=engine)
app = FastAPI(title="AI78QA API", version="0.1.0", description="Autonomous QA and Training Lab API")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health", response_model=HealthRead)
def health():
    return {"status":"ok","service":"ai78qa-api","version":"0.1.0"}

@app.get("/api/v1/projects")
def list_projects(db: Session = Depends(get_db)):
    return [{"id":p.id,"name":p.name,"description":p.description,"created_at":p.created_at} for p in db.scalars(select(Project).order_by(Project.created_at.desc())).all()]

@app.post("/api/v1/projects")
def create_project(payload: dict, db: Session = Depends(get_db)):
    name = str(payload.get("name","")).strip()
    if not name or len(name)>160:
        raise HTTPException(422,"Project name is required (maximum 160 characters).")
    project = Project(name=name, description=str(payload.get("description",""))[:2000])
    db.add(project); db.flush()
    db.add(AuditEvent(action="project.created",resource_type="project",resource_id=project.id,details={"name":name}))
    db.commit(); db.refresh(project)
    return {"id":project.id,"name":project.name,"description":project.description}

@app.get("/api/v1/training/websites", response_model=list[WebsiteRead])
def list_websites(db: Session = Depends(get_db)):
    return db.scalars(select(TrainingWebsite).order_by(TrainingWebsite.created_at.desc())).all()

@app.post("/api/v1/training/websites", response_model=WebsiteRead, status_code=201)
def create_website(payload: WebsiteCreate, db: Session = Depends(get_db)):
    try:
        host = validate_target_url(str(payload.base_url))
    except UnsafeTarget as exc:
        raise HTTPException(400,str(exc)) from exc
    website = TrainingWebsite(name=payload.name,base_url=str(payload.base_url),environment_type=payload.environment_type,allowed_domains=[host],policy={"mode":"observe","max_pages":100,"max_depth":5,"external_navigation":False,"form_submission":False})
    db.add(website); db.flush()
    db.add(AuditEvent(action="training.website.created",resource_type="training_website",resource_id=website.id,details={"host":host}))
    db.commit(); db.refresh(website)
    return website

@app.get("/api/v1/training/sessions", response_model=list[SessionRead])
def list_sessions(db: Session = Depends(get_db)):
    return db.scalars(select(TrainingSession).order_by(TrainingSession.created_at.desc())).all()

@app.post("/api/v1/training/sessions", response_model=SessionRead, status_code=202)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    website = db.get(TrainingWebsite,payload.website_id)
    if not website:
        raise HTTPException(404,"Training website not found.")
    try:
        host = validate_target_url(website.base_url)
    except UnsafeTarget as exc:
        raise HTTPException(400,str(exc)) from exc
    if host not in (website.allowed_domains or []):
        raise HTTPException(403,"Website host is not in the approved domain list.")
    session = TrainingSession(website_id=website.id,max_pages=payload.max_pages,max_depth=payload.max_depth,mode="observe",status="queued")
    db.add(session); db.flush()
    db.add(AuditEvent(action="training.session.queued",resource_type="training_session",resource_id=session.id,details={"host":host,"max_pages":payload.max_pages}))
    db.commit(); db.refresh(session)
    try:
        explore_training_session.delay(session.id)
    except Exception:
        pass
    return session

@app.get("/api/v1/training/sessions/{session_id}", response_model=SessionRead)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.get(TrainingSession,session_id)
    if not session:
        raise HTTPException(404,"Session not found.")
    return session

@app.get("/api/v1/intelligence/summary")
def intelligence_summary(db: Session = Depends(get_db)):
    return {"websites":len(db.scalars(select(TrainingWebsite)).all()),"sessions":len(db.scalars(select(TrainingSession)).all()),"observations":0,"models":0,"learning_mode":"hybrid","model_promotion":"held-out evaluation required"}
