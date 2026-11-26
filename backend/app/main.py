from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db import Base, engine
from app import models
from app.api.routes import router

app=FastAPI(title="Lights On, Nobody Home API",version="1.0.0",description="University electricity-wastage reporting and management")
origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
Path("uploads").mkdir(exist_ok=True)
app.mount("/uploads",StaticFiles(directory="uploads"),name="uploads")
app.include_router(router)
@app.on_event("startup")
def startup(): Base.metadata.create_all(bind=engine)
@app.get("/")
def root(): return {"name":"Lights On, Nobody Home API","docs":"/docs","status":"running"}
@app.get("/health")
def health(): return {"status":"ok"}
