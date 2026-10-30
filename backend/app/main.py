import json
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import auth, ingest
from .config import MAX_UPLOAD_BYTES
from .db import init_db, pool
from .rag import run_chat


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    pool.open()
    yield
    pool.close()


app = FastAPI(title="IT Helpdesk Assistant", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])


class RegisterOrg(BaseModel):
    org_name: str = Field(min_length=2, max_length=100)
    email: str
    password: str = Field(min_length=8)


class Login(BaseModel):
    email: str
    password: str


class NewUser(BaseModel):
    email: str
    password: str = Field(min_length=8)
    role: str = Field(default="employee", pattern="^(admin|employee)$")


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@app.post("/auth/register-org")
def register_org(body: RegisterOrg):
    with pool.connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=%s", (body.email,)).fetchone():
            raise HTTPException(409, "Email already registered")
        org = conn.execute("INSERT INTO orgs(name) VALUES (%s) RETURNING id", (body.org_name,)).fetchone()
        user = conn.execute(
            "INSERT INTO users(org_id,email,password_hash,role) VALUES (%s,%s,%s,'admin') RETURNING id",
            (org["id"], body.email, auth.hash_password(body.password))).fetchone()
    return {"access_token": auth.make_token(user["id"], org["id"], "admin")}


@app.post("/auth/login")
def login(body: Login):
    with pool.connection() as conn:
        u = conn.execute("SELECT * FROM users WHERE email=%s", (body.email,)).fetchone()
    if not u or not auth.verify_password(body.password, u["password_hash"]):
        raise HTTPException(401, "Bad credentials")
    return {"access_token": auth.make_token(u["id"], u["org_id"], u["role"]), "role": u["role"]}


@app.post("/users", status_code=201)
def create_user(body: NewUser, admin=Depends(auth.require_admin)):
    with pool.connection() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=%s", (body.email,)).fetchone():
            raise HTTPException(409, "Email already registered")
        row = conn.execute(
            "INSERT INTO users(org_id,email,password_hash,role) VALUES (%s,%s,%s,%s) RETURNING id",
            (admin["org_id"], body.email, auth.hash_password(body.password), body.role)).fetchone()
    return {"id": row["id"]}


@app.post("/documents", status_code=202)
async def upload_document(background: BackgroundTasks, file: UploadFile = File(...),
                          admin=Depends(auth.require_admin)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large")
    if not (file.filename or "").lower().endswith((".pdf", ".md", ".txt")):
        raise HTTPException(400, "Use .pdf, .md or .txt")
    doc_id = ingest.create_document(admin["org_id"], file.filename)
    background.add_task(ingest.ingest_document, admin["org_id"], doc_id, file.filename, data)
    return {"document_id": doc_id, "status": "processing"}


@app.get("/documents")
def list_documents(admin=Depends(auth.require_admin)):
    with pool.connection() as conn:
        return conn.execute(
            "SELECT id, filename, status, error, created_at FROM documents WHERE org_id=%s ORDER BY id DESC",
            (admin["org_id"],)).fetchall()


@app.post("/chat")
def chat(body: ChatIn, user=Depends(auth.current_user)):
    def gen():
        for ev in run_chat(user["org_id"], user["user_id"], body.question):
            yield f"data: {json.dumps(ev, default=str)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/tickets")
def list_tickets(user=Depends(auth.current_user)):
    sql = "SELECT * FROM tickets WHERE org_id=%s"
    params = [user["org_id"]]
    if user["role"] != "admin":
        sql += " AND user_id=%s"
        params.append(user["user_id"])
    with pool.connection() as conn:
        return conn.execute(sql + " ORDER BY id DESC", params).fetchall()


@app.get("/logs")
def list_logs(admin=Depends(auth.require_admin)):
    with pool.connection() as conn:
        return conn.execute(
            "SELECT * FROM request_logs WHERE org_id=%s ORDER BY id DESC LIMIT 200", (admin["org_id"],)).fetchall()
