from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from app.deps import SessionLocal, bot
from app.storage.repo import get_all_users, get_user_messages
from app.services.cleanup import delete_user_history, delete_one
from app.config import config

app = FastAPI()
env = Environment(loader=FileSystemLoader("web/templates"))
from fastapi import Cookie, Response
from app.auth import create_token, verify_token
from fastapi import Form

def is_authed(request: Request):
    token = request.cookies.get("admin_token")
    return token and verify_token(token)

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    tpl = env.get_template("login.html")
    return HTMLResponse(tpl.render(error=""))

@app.post("/login")
async def login_post(request: Request, password: str = Form(...)):
    # simple password check
    if password == config.ADMIN_PASSWORD:
        token = create_token()
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie("admin_token", token, httponly=True, samesite="lax")
        return response
    tpl = env.get_template("login.html")
    return HTMLResponse(tpl.render(error="Неверный пароль"))


@app.get("/", response_class=HTMLResponse)
async def index():
    async with SessionLocal() as session:
        users = await get_all_users(session)
    tpl = env.get_template("index.html")
    return tpl.render(users=users)

@app.get("/dialog/{user_id}", response_class=HTMLResponse)
async def dialog(request: Request, user_id: int):
    if not is_authed(request):
        return RedirectResponse(url="/login")
    async with SessionLocal() as session:
        msgs = await get_user_messages(session, user_id)
    tpl = env.get_template("dialog.html")
    return HTMLResponse(tpl.render(user_id=user_id, messages=msgs))

# # @app.post("/delete_user")  # disabled to prevent deleting users from admin panel  # disabled to prevent deleting users from admin panel
async def delete_user_disabled(user_id: int = Form(...)):  # disabled

    async with SessionLocal() as session:
        msgs = await get_user_messages(session, user_id)
        await delete_user_history(bot, session, user_id, msgs)
    return RedirectResponse("/", status_code=302)

@app.post("/delete_msg")
async def delete_msg(user_id: int = Form(...), msg_id: int = Form(...)):
    async with SessionLocal() as session:
        msgs = await get_user_messages(session, user_id)
        msg = next((m for m in msgs if m.id == msg_id), None)
        if msg:
            await delete_one(bot, session, user_id, msg)
    return RedirectResponse(f"/dialog/{user_id}", status_code=302)
