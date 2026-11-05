from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from pathlib import Path
import os
import re
import hmac
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.config import settings
from app.database import get_db
from app.models import Project, TrainingWebsite, TrainingSession, AuditEvent, Observation, EvidenceArtifact
from app.schemas import WebsiteCreate, WebsiteRead, SessionCreate, SessionRead, HealthRead
from app.security import validate_target_url, UnsafeTarget
from celery import Celery
from app.seed import seed_demo_website

seed_demo_website()
queue = Celery("ai78qa-api", broker=settings.redis_url, backend=settings.redis_url)
app = FastAPI(title="AI78QA API", version="0.1.0", description="Autonomous QA and Training Lab API")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def require_api_access_key(request, call_next):
    # Local Docker development remains frictionless. Production API traffic must carry
    # the server-managed key injected by the same-origin Vercel proxy.
    if settings.app_env.lower() == "production" and request.url.path != "/health":
        expected = settings.api_access_key
        supplied = request.headers.get("x-api-key", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized API request."})
    return await call_next(request)

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
        queue.send_task("training.explore", args=[session.id])
    except Exception:
        session.status = "queue_unavailable"
        session.summary = {"warning": "Session persisted but the worker broker is unavailable."}
        db.commit()
    return session

@app.get("/api/v1/training/sessions/{session_id}", response_model=SessionRead)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.get(TrainingSession,session_id)
    if not session:
        raise HTTPException(404,"Session not found.")
    return session

@app.get("/api/v1/intelligence/summary")
def intelligence_summary(db: Session = Depends(get_db)):
    return {
        "websites": db.scalar(select(func.count()).select_from(TrainingWebsite)) or 0,
        "sessions": db.scalar(select(func.count()).select_from(TrainingSession)) or 0,
        "observations": db.scalar(select(func.count()).select_from(Observation)) or 0,
        "models": 0,
        "learning_mode": "hybrid",
        "model_promotion": "held-out evaluation required",
    }


@app.get("/api/v1/training/sessions/{session_id}/observations")
def list_observations(
    session_id: str,
    kind: str | None = Query(default=None, max_length=48),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    session = db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found.")
    query = select(Observation).where(Observation.session_id == session_id)
    if kind:
        query = query.where(Observation.features["kind"].as_string() == kind)
    rows = db.scalars(query.order_by(Observation.created_at.asc()).offset(offset).limit(limit)).all()
    return [{
        "id": row.id, "page_url": row.page_url, "page_title": row.page_title,
        "element_type": row.element_type, "semantic_name": row.semantic_name,
        "features": row.features, "label": row.label,
        "label_verified": row.label_verified, "source": row.source,
        "created_at": row.created_at,
    } for row in rows]


@app.get("/api/v1/training/sessions/{session_id}/discovery")
def get_discovery_graph(session_id: str, db: Session = Depends(get_db)):
    session = db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found.")
    rows = db.scalars(select(Observation).where(
        Observation.session_id == session_id,
        Observation.source.in_(["page_snapshot", "interaction_transition"])
    ).order_by(Observation.created_at.asc())).all()
    pages = {}
    transitions = []
    for row in rows:
        features = row.features or {}
        if features.get("kind") == "page_snapshot":
            pages[features.get("page_key") or row.page_url] = {
                "page_key": features.get("page_key"), "url": row.page_url,
                "title": row.page_title, "depth": features.get("depth", 0),
                "discovered_from": features.get("discovered_from"),
                "headings": features.get("headings", []),
                "forms": features.get("forms", []),
                "tables": features.get("tables", []),
                "landmarks": features.get("landmarks", []),
                "element_count": features.get("element_count", 0),
                "evidence_file": features.get("evidence_file"),
            }
        elif features.get("kind") == "interaction_transition":
            transitions.append({
                "id": row.id, "from": features.get("before_url"),
                "to": features.get("after_url"),
                "action": features.get("action"), "target": features.get("target"),
                "state_changed": features.get("state_changed", False),
                "before_state": features.get("before_state"),
                "after_state": features.get("after_state"),
                "evidence_file": features.get("evidence_file"),
            })
    page_items = list(pages.values())
    navigation_edges = [
        {"from": page["discovered_from"], "to": page["url"]}
        for page in page_items if page.get("discovered_from")
    ]
    return {
        "session_id": session_id, "status": session.status,
        "pages": page_items, "navigation_edges": navigation_edges, "transitions": transitions,
        "summary": session.summary or {},
        "counts": {
            "pages": len(pages), "transitions": len(transitions),
            "changed_states": sum(1 for item in transitions if item["state_changed"]),
        },
    }


@app.get("/api/v1/training/sessions/{session_id}/evidence/{filename}")
def get_evidence_file(session_id: str, filename: str, db: Session = Depends(get_db)):
    session = db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.(?:png|jpe?g)", filename, flags=re.I):
        raise HTTPException(400, "Invalid evidence filename.")
    artifact = db.scalar(select(EvidenceArtifact).where(
        EvidenceArtifact.session_id == session_id,
        EvidenceArtifact.filename == filename,
    ))
    if artifact:
        return Response(
            content=artifact.data,
            media_type=artifact.mime_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"', "X-Content-Type-Options": "nosniff"},
        )
    root = Path(os.getenv("EVIDENCE_DIR", "/data/evidence")).resolve()
    target = (root / session_id / filename).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(404, "Evidence file not found.")
    media_type = "image/jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return FileResponse(target, media_type=media_type, filename=filename)
