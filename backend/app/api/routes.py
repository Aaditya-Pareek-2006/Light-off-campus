from datetime import datetime, timezone
from pathlib import Path
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from app.db import get_db
from app.models import User, Building, Area, AreaAssignment, Report, ReportHistory, Notification, AwarenessTip, RoomChecklist, EnergyInspection, EnergyCampaign, CampaignPledge
from app.schemas import RegisterIn, LoginIn, UserOut, BuildingIn, AreaIn, ReportIn, StatusIn, StaffIn, AssignmentIn
from app.security import current_user, require_roles, hash_password, verify_password, make_token
from app.core.config import settings

router = APIRouter(prefix="/api")

def report_dict(r):
    return {"id":r.id,"student_id":r.student_id,"area_id":r.area_id,"description":r.description,"image_path":r.image_path,"status":r.status,"assigned_staff_id":r.assigned_staff_id,"created_at":r.created_at,"updated_at":r.updated_at,"area_name":r.area.name,"building_name":r.area.building.name,"area_type":r.area.area_type,"room_number":r.area.room_number}
def visible_report(db, report_id, user):
    q=db.query(Report).options(joinedload(Report.area).joinedload(Area.building)).filter(Report.id==report_id)
    r=q.first()
    if not r: raise HTTPException(404,"Report not found")
    if user.role=="student" and r.student_id!=user.id: raise HTTPException(403,"Not your report")
    if user.role=="staff" and r.assigned_staff_id!=user.id: raise HTTPException(403,"Report is not assigned to you")
    return r

@router.post("/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """Public registration always creates a student account.

    Staff accounts are created only by an authenticated administrator through
    /api/users/staff. The client cannot choose or override the account role.

    Optional deployment safeguard: set STUDENT_EMAIL_DOMAINS in the backend
    environment to a comma-separated allowlist, for example:
    STUDENT_EMAIL_DOMAINS=university.edu,students.university.edu
    Leave it unset during local demonstration if institutional email domains
    have not yet been confirmed.
    """
    email = str(data.email).strip().lower()
    name = data.name.strip()

    allowed_domains = {
        domain.strip().lower()
        for domain in os.getenv("STUDENT_EMAIL_DOMAINS", "").split(",")
        if domain.strip()
    }
    if allowed_domains:
        email_domain = email.rsplit("@", 1)[-1]
        if email_domain not in allowed_domains:
            raise HTTPException(
                status_code=403,
                detail="Please register using an approved university email address.",
            )

    existing_user = db.query(User).filter(func.lower(User.email) == email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Role is assigned exclusively on the server; never accept it from the client.
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(data.password),
        role="student",
    )
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create account. Check whether the email is already registered.")
    db.refresh(user)
    return {
        "access_token": make_token(user),
        "token_type": "bearer",
        "user": UserOut.model_validate(user),
    }
@router.post("/auth/login")
def login(data:LoginIn, db:Session=Depends(get_db)):
    u=db.query(User).filter(func.lower(User.email)==data.email.lower()).first()
    if not u or not verify_password(data.password,u.password_hash): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":make_token(u),"token_type":"bearer","user":UserOut.model_validate(u)}
@router.get("/auth/me",response_model=UserOut)
def me(user:User=Depends(current_user)): return user

@router.get("/buildings")
def buildings(db:Session=Depends(get_db), user:User=Depends(current_user)):
    return [{"id":b.id,"name":b.name,"building_type":b.building_type} for b in db.query(Building).order_by(Building.name).all()]
@router.post("/buildings")
def create_building(data:BuildingIn,db:Session=Depends(get_db),admin:User=Depends(require_roles("admin"))):
    b=Building(**data.model_dump()); db.add(b)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(409,"Building name already exists")
    db.refresh(b); return {"id":b.id,"name":b.name,"building_type":b.building_type}
@router.get("/areas")
def areas(db:Session=Depends(get_db),user:User=Depends(current_user)):
    query=db.query(Area).options(joinedload(Area.building))
    if user.role=="staff":
        assigned_ids=[x[0] for x in db.query(AreaAssignment.area_id).filter_by(staff_id=user.id,is_active=True).all()]
        query=query.filter(Area.id.in_(assigned_ids)) if assigned_ids else query.filter(Area.id==-1)
    rows=query.all()
    return [{"id":a.id,"building_id":a.building_id,"building_name":a.building.name,"name":a.name,"area_type":a.area_type,"room_number":a.room_number} for a in rows]
@router.post("/areas")
def create_area(data:AreaIn,db:Session=Depends(get_db),admin:User=Depends(require_roles("admin"))):
    if not db.get(Building,data.building_id): raise HTTPException(404,"Building not found")
    a=Area(**data.model_dump()); db.add(a); db.commit(); db.refresh(a)
    return {"id":a.id,"building_id":a.building_id,"name":a.name,"area_type":a.area_type,"room_number":a.room_number}

@router.post("/reports")
def create_report(data:ReportIn,db:Session=Depends(get_db),student:User=Depends(require_roles("student"))):
    area=db.query(Area).options(joinedload(Area.building)).filter(Area.id==data.area_id).first()
    if not area: raise HTTPException(404,"Area not found")
    assignment=db.query(AreaAssignment).filter_by(area_id=area.id,is_active=True).order_by(AreaAssignment.id.desc()).first()
    staff_id=assignment.staff_id if assignment else None
    r=Report(student_id=student.id,area_id=area.id,description=data.description.strip(),assigned_staff_id=staff_id,status="Assigned" if staff_id else "Submitted")
    db.add(r); db.flush(); db.add(ReportHistory(report_id=r.id,old_status=None,new_status=r.status,changed_by=student.id,remarks="Report submitted"))
    if staff_id: db.add(Notification(user_id=staff_id,report_id=r.id,message=f"New electricity-wastage report for {area.building.name} – {area.name}"))
    db.commit(); db.refresh(r)
    return report_dict(db.query(Report).options(joinedload(Report.area).joinedload(Area.building)).get(r.id))

@router.post("/reports/{report_id}/image")
async def upload_report_image(report_id:int, file:UploadFile=File(...), db:Session=Depends(get_db), user:User=Depends(current_user)):
    r=visible_report(db,report_id,user)
    if user.role not in ("student","admin") or (user.role=="student" and r.student_id!=user.id):
        raise HTTPException(403,"You cannot attach an image to this report")
    allowed={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}
    if file.content_type not in allowed: raise HTTPException(415,"Only JPG, PNG or WEBP images are allowed")
    content=await file.read()
    if len(content)>settings.max_upload_mb*1024*1024: raise HTTPException(413,f"Image must be smaller than {settings.max_upload_mb} MB")
    upload_dir=Path("uploads"); upload_dir.mkdir(exist_ok=True)
    filename=f"report-{report_id}-{uuid.uuid4().hex}{allowed[file.content_type]}"
    (upload_dir/filename).write_bytes(content)
    r.image_path=f"/uploads/{filename}"; db.commit()
    return {"image_path":r.image_path}

@router.get("/reports")
def list_reports(status:str|None=None, q:str|None=None, skip:int=0, limit:int=50,db:Session=Depends(get_db),user:User=Depends(current_user)):
    limit=max(1,min(limit,100)); query=db.query(Report).options(joinedload(Report.area).joinedload(Area.building))
    if user.role=="student": query=query.filter(Report.student_id==user.id)
    elif user.role=="staff": query=query.filter(Report.assigned_staff_id==user.id)
    if status: query=query.filter(Report.status==status)
    if q: query=query.join(Area).join(Building).filter((Area.name.ilike(f"%{q}%"))|(Report.description.ilike(f"%{q}%"))|(Building.name.ilike(f"%{q}%")))
    rows=query.order_by(desc(Report.created_at)).offset(skip).limit(limit).all()
    return [report_dict(r) for r in rows]
@router.get("/reports/{report_id}")
def get_report(report_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    r=visible_report(db,report_id,user)
    history=db.query(ReportHistory).filter_by(report_id=r.id).order_by(ReportHistory.created_at).all()
    return {**report_dict(r),"history":[{"old_status":h.old_status,"new_status":h.new_status,"remarks":h.remarks,"created_at":h.created_at} for h in history]}
@router.patch("/reports/{report_id}/status")
def update_status(report_id:int,data:StatusIn,db:Session=Depends(get_db),staff:User=Depends(require_roles("staff","admin"))):
    r=visible_report(db,report_id,staff)
    if data.status=="Unable to Resolve" and not (data.remarks and data.remarks.strip()): raise HTTPException(422,"A reason is required when a report cannot be resolved")
    old=r.status; r.status=data.status; r.updated_at=datetime.now(timezone.utc)
    db.add(ReportHistory(report_id=r.id,old_status=old,new_status=r.status,changed_by=staff.id,remarks=data.remarks))
    db.add(Notification(user_id=r.student_id,report_id=r.id,message=f"Your report #{r.id} is now {r.status}."))
    db.commit(); return {"message":"Status updated","status":r.status}

@router.get("/notifications")
def notifications(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [{"id":n.id,"report_id":n.report_id,"message":n.message,"is_read":n.is_read,"created_at":n.created_at} for n in db.query(Notification).filter_by(user_id=user.id).order_by(desc(Notification.created_at)).limit(100).all()]
@router.patch("/notifications/{notification_id}/read")
def read_notification(notification_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    n=db.query(Notification).filter_by(id=notification_id,user_id=user.id).first()
    if not n: raise HTTPException(404,"Notification not found")
    n.is_read=True; db.commit(); return {"message":"Marked as read"}

@router.get("/dashboard/{kind}")
def dashboard(kind:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if kind not in ("student","staff","admin"): raise HTTPException(404,"Dashboard not found")
    if kind!=user.role and user.role!="admin": raise HTTPException(403,"Not allowed")
    q=db.query(Report)
    if user.role=="student": q=q.filter(Report.student_id==user.id)
    elif user.role=="staff": q=q.filter(Report.assigned_staff_id==user.id)
    counts={s:q.filter(Report.status==s).count() for s in ["Submitted","Assigned","In Progress","Resolved","Unable to Resolve"]}
    total=q.count()
    top=db.query(Area.name,func.count(Report.id)).join(Report,Report.area_id==Area.id).group_by(Area.id,Area.name).order_by(func.count(Report.id).desc()).limit(5).all()
    return {"total":total,"counts":counts,"top_areas":[{"name":n,"reports":c} for n,c in top]}

@router.get("/users")
def users(db:Session=Depends(get_db),admin:User=Depends(require_roles("admin"))):
    return [UserOut.model_validate(u) for u in db.query(User).order_by(User.id.desc()).all()]
@router.post("/users/staff")
def create_staff(data:StaffIn,db:Session=Depends(get_db),admin:User=Depends(require_roles("admin"))):
    if db.query(User).filter(func.lower(User.email)==data.email.lower()).first(): raise HTTPException(409,"Email already exists")
    u=User(name=data.name,email=data.email.lower(),password_hash=hash_password(data.password),role="staff"); db.add(u); db.commit(); db.refresh(u); return UserOut.model_validate(u)
@router.post("/assignments")
def assign(data:AssignmentIn,db:Session=Depends(get_db),admin:User=Depends(require_roles("admin"))):
    if not db.get(Area,data.area_id): raise HTTPException(404,"Area not found")
    staff=db.get(User,data.staff_id)
    if not staff or staff.role!="staff": raise HTTPException(422,"Choose a valid staff account")
    db.query(AreaAssignment).filter_by(area_id=data.area_id,is_active=True).update({"is_active":False})
    a=AreaAssignment(area_id=data.area_id,staff_id=data.staff_id,assigned_by=admin.id); db.add(a)
    # Route existing unassigned reports for the area to the newly assigned staff member.
    pending=db.query(Report).filter_by(area_id=data.area_id,assigned_staff_id=None).all()
    for r in pending:
        r.assigned_staff_id=staff.id; r.status="Assigned"
        db.add(Notification(user_id=staff.id,report_id=r.id,message=f"Unassigned report #{r.id} has been assigned to your area."))
    db.commit(); return {"message":"Staff assigned to area","routed_reports":len(pending)}
@router.get("/assignments")
def assignments(db:Session=Depends(get_db),admin:User=Depends(require_roles("admin"))):
    rows=db.query(AreaAssignment).filter_by(is_active=True).all()
    return [{"id":a.id,"area_id":a.area_id,"area_name":db.get(Area,a.area_id).name,"staff_id":a.staff_id,"staff_name":db.get(User,a.staff_id).name} for a in rows]

@router.get("/tips")
def tips(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [{"id":t.id,"title":t.title,"content":t.content,"is_active":t.is_active} for t in db.query(AwarenessTip).filter_by(is_active=True).all()]
@router.post("/tips")
def add_tip(data:dict,db:Session=Depends(get_db),admin:User=Depends(require_roles("admin"))):
    title=str(data.get("title","")).strip(); content=str(data.get("content","")).strip()
    if not title or not content: raise HTTPException(422,"Title and content are required")
    t=AwarenessTip(title=title,content=content); db.add(t); db.commit(); db.refresh(t); return {"id":t.id,"title":t.title,"content":t.content}


# Preventive energy-management features: room checklists, staff inspections and campaigns.
def area_is_assigned(db, area_id, user_id):
    return db.query(AreaAssignment).filter_by(area_id=area_id, staff_id=user_id, is_active=True).first() is not None

@router.post("/checklists")
def create_checklist(data:dict, db:Session=Depends(get_db), user:User=Depends(require_roles("student","staff","admin"))):
    area_id=int(data.get("area_id", 0))
    area=db.get(Area, area_id)
    if not area: raise HTTPException(404,"Area not found")
    if user.role=="staff" and not area_is_assigned(db, area_id, user.id): raise HTTPException(403,"This area is not assigned to you")
    row=RoomChecklist(area_id=area_id, submitted_by=user.id, lights_off=bool(data.get("lights_off")), fans_off=bool(data.get("fans_off")), ac_off=bool(data.get("ac_off")), room_checked=bool(data.get("room_checked")), remarks=(str(data.get("remarks", "")).strip() or None))
    db.add(row); db.commit(); db.refresh(row)
    return {"id":row.id,"area_id":row.area_id,"lights_off":row.lights_off,"fans_off":row.fans_off,"ac_off":row.ac_off,"room_checked":row.room_checked,"created_at":row.created_at}

@router.get("/checklists")
def list_checklists(db:Session=Depends(get_db), user:User=Depends(current_user)):
    q=db.query(RoomChecklist).order_by(desc(RoomChecklist.created_at))
    if user.role=="student": q=q.filter(RoomChecklist.submitted_by==user.id)
    elif user.role=="staff":
        ids=[x[0] for x in db.query(AreaAssignment.area_id).filter_by(staff_id=user.id,is_active=True).all()]
        q=q.filter(RoomChecklist.area_id.in_(ids)) if ids else q.filter(RoomChecklist.id==-1)
    rows=q.limit(100).all()
    result=[]
    for r in rows:
        a=db.get(Area,r.area_id); b=db.get(Building,a.building_id) if a else None
        result.append({"id":r.id,"area_id":r.area_id,"area_name":a.name if a else "","building_name":b.name if b else "","lights_off":r.lights_off,"fans_off":r.fans_off,"ac_off":r.ac_off,"room_checked":r.room_checked,"remarks":r.remarks,"created_at":r.created_at})
    return result

@router.post("/inspections")
def create_inspection(data:dict, db:Session=Depends(get_db), user:User=Depends(require_roles("staff","admin"))):
    area_id=int(data.get("area_id",0)); area=db.get(Area,area_id)
    if not area: raise HTTPException(404,"Area not found")
    if user.role=="staff" and not area_is_assigned(db,area_id,user.id): raise HTTPException(403,"This area is not assigned to you")
    flags=[bool(data.get(k)) for k in ("lights_on_empty","fans_on_empty","ac_on_empty")]
    action="Issue found" if any(flags) else "No issue found"
    row=EnergyInspection(area_id=area_id,inspector_id=user.id,lights_on_empty=flags[0],fans_on_empty=flags[1],ac_on_empty=flags[2],action_taken=action,notes=(str(data.get("notes", "")).strip() or None))
    db.add(row); db.commit(); db.refresh(row)
    return {"id":row.id,"action_taken":row.action_taken,"created_at":row.created_at}

@router.get("/inspections")
def list_inspections(db:Session=Depends(get_db), user:User=Depends(current_user)):
    q=db.query(EnergyInspection).order_by(desc(EnergyInspection.created_at))
    if user.role=="student": raise HTTPException(403,"Inspections are available to staff and administrators")
    if user.role=="staff":
        ids=[x[0] for x in db.query(AreaAssignment.area_id).filter_by(staff_id=user.id,is_active=True).all()]
        q=q.filter(EnergyInspection.area_id.in_(ids)) if ids else q.filter(EnergyInspection.id==-1)
    rows=q.limit(150).all(); result=[]
    for r in rows:
        a=db.get(Area,r.area_id); b=db.get(Building,a.building_id) if a else None; inspector=db.get(User,r.inspector_id)
        result.append({"id":r.id,"area_id":r.area_id,"area_name":a.name if a else "","building_name":b.name if b else "","inspector_name":inspector.name if inspector else "","lights_on_empty":r.lights_on_empty,"fans_on_empty":r.fans_on_empty,"ac_on_empty":r.ac_on_empty,"action_taken":r.action_taken,"notes":r.notes,"created_at":r.created_at})
    return result

@router.get("/campaigns")
def list_campaigns(db:Session=Depends(get_db), user:User=Depends(current_user)):
    rows=db.query(EnergyCampaign).filter_by(is_active=True).order_by(desc(EnergyCampaign.created_at)).all()
    return [{"id":c.id,"title":c.title,"description":c.description,"start_date":c.start_date,"end_date":c.end_date,"pledges":db.query(CampaignPledge).filter_by(campaign_id=c.id).count(),"joined":db.query(CampaignPledge).filter_by(campaign_id=c.id,user_id=user.id).first() is not None} for c in rows]

@router.post("/campaigns")
def create_campaign(data:dict, db:Session=Depends(get_db), admin:User=Depends(require_roles("admin"))):
    title=str(data.get("title","")).strip(); description=str(data.get("description","")).strip()
    if not title or not description: raise HTTPException(422,"Title and description are required")
    c=EnergyCampaign(title=title,description=description,created_by=admin.id); db.add(c); db.commit(); db.refresh(c)
    return {"id":c.id,"title":c.title,"description":c.description,"pledges":0,"joined":False}

@router.post("/campaigns/{campaign_id}/pledge")
def pledge_campaign(campaign_id:int, db:Session=Depends(get_db), user:User=Depends(require_roles("student","staff"))):
    c=db.get(EnergyCampaign,campaign_id)
    if not c or not c.is_active: raise HTTPException(404,"Campaign not found")
    existing=db.query(CampaignPledge).filter_by(campaign_id=campaign_id,user_id=user.id).first()
    if existing: return {"message":"You have already joined this campaign"}
    db.add(CampaignPledge(campaign_id=campaign_id,user_id=user.id)); db.commit()
    return {"message":"Thank you for making an energy-saving pledge"}

@router.get("/energy/overview")
def energy_overview(db:Session=Depends(get_db), admin:User=Depends(require_roles("admin"))):
    total_checklists=db.query(RoomChecklist).count()
    complete_checklists=db.query(RoomChecklist).filter_by(lights_off=True,fans_off=True,ac_off=True,room_checked=True).count()
    inspections=db.query(EnergyInspection).count()
    issues=db.query(EnergyInspection).filter(EnergyInspection.action_taken=="Issue found").count()
    pledges=db.query(CampaignPledge).count()
    campaigns=db.query(EnergyCampaign).filter_by(is_active=True).count()
    return {"checklists":total_checklists,"completed_checklists":complete_checklists,"inspections":inspections,"issues_found":issues,"pledges":pledges,"active_campaigns":campaigns,"note":"These are recorded platform activities, not measured electricity savings."}
