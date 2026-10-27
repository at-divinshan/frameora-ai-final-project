"""Browser-bound Google endpoints with a fixed, sanitized frontend return."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.google_oidc import new_secret, rejected, require_configuration
from app.database.connection import get_db
from app.models.user import User
from app.schemas.google_auth import GoogleLinkConsent, GoogleLinkStart, GoogleRegistration, GoogleStart
from app.services import google_auth_service as service
from app.services.oauth_transaction_store import AUTH_TTL, COMPLETION_TTL, REGISTRATION_TTL, get_store


def google_ready(request: Request):
    require_configuration()
    if request.method == "POST":
        # Cookies alone never authorize a cross-origin POST, including registration/completion.
        if request.headers.get("origin") != settings.frontend_origin:
            raise HTTPException(403, "Origin is not permitted.")
        if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
            raise HTTPException(415, "A JSON request is required.")


router = APIRouter(prefix="/auth/google", tags=["Google Authentication"], dependencies=[Depends(google_ready)])


def cookie_name(part: str) -> str:
    prefix = "__Host-" if settings.oauth_cookie_secure else ""
    return prefix + "frameora-google-" + part


def set_cookie(response: Response, part: str, value: str, ttl: int):
    response.set_cookie(cookie_name(part), value, max_age=ttl, httponly=True,
                        secure=settings.oauth_cookie_secure, samesite="lax", path="/")


def clear_cookie(response: Response, part: str):
    response.delete_cookie(cookie_name(part), path="/", httponly=True,
                           secure=settings.oauth_cookie_secure, samesite="lax")


def browser_binding(request: Request) -> str:
    browser = request.cookies.get(cookie_name("binding"), "")
    if not browser or len(browser) > 128:
        raise rejected()
    return browser


def handle(request: Request, part: str) -> str:
    return request.cookies.get(cookie_name(part), "")


def rate_start(request: Request):
    # Trust only the ASGI peer; proxy forwarding must be restricted by deployment configuration.
    peer = request.client.host if request.client else "unknown"
    get_store().limit("start:" + peer, 30)


def clear_flow(response: Response):
    for part in ("binding", "completion", "registration", "link"):
        clear_cookie(response, part)


@router.post("/start")
def start(data: GoogleStart, request: Request, response: Response):
    rate_start(request)
    browser = new_secret()
    url = service.begin(browser, data.remember_me)
    clear_flow(response)
    set_cookie(response, "binding", browser, AUTH_TTL + REGISTRATION_TTL + COMPLETION_TTL)
    return {"authorization_url": url}


@router.get("/callback")
def callback(request: Request, db: Session = Depends(get_db)):
    # Parse manually so malformed provider responses never appear in validation error output.
    params = request.query_params
    try:
        if any(len(params.getlist(k)) > 1 for k in ("state", "code", "error")):
            raise rejected()
        state = params.get("state", "")
        result, part = service.callback(db, state, params.get("code"), params.get("error"), browser_binding(request))
    except Exception as failure:
        # Only fixed UI markers cross this boundary, never provider data or exception text.
        marker = "google-error"
        if isinstance(failure, HTTPException) and failure.status_code == 409:
            marker = "google-conflict"
        elif isinstance(failure, HTTPException) and failure.status_code == 400 and params.get("error") == "access_denied":
            marker = "google-cancelled"
        response = RedirectResponse(settings.google_completion_url + "#" + marker, status_code=303)
        clear_flow(response)
        return response
    response = RedirectResponse(settings.google_completion_url, status_code=303)
    set_cookie(response, part, result, COMPLETION_TTL)
    return response


@router.post("/complete")
def complete(request: Request, response: Response, db: Session = Depends(get_db)):
    result, registration = service.complete(db, handle(request, "completion"), browser_binding(request))
    clear_cookie(response, "completion")
    if registration:
        set_cookie(response, "registration", registration, REGISTRATION_TTL)
    else:
        clear_flow(response)
    return result


@router.post("/register")
def register(data: GoogleRegistration, request: Request, response: Response, db: Session = Depends(get_db)):
    result = service.register(db, handle(request, "registration"), browser_binding(request), data)
    clear_flow(response)
    return result


@router.post("/link/start")
def link_start(data: GoogleLinkStart, request: Request, response: Response,
               user: User = Depends(get_current_user)):
    rate_start(request)
    browser = new_secret()
    url = service.begin(browser, False, user, data.password, request.headers.get("authorization", ""))
    clear_flow(response)
    set_cookie(response, "binding", browser, AUTH_TTL + COMPLETION_TTL)
    return {"authorization_url": url}


@router.post("/link/complete")
def link_complete(data: GoogleLinkConsent, request: Request, response: Response,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = service.link(db, handle(request, "link"), browser_binding(request), user,
                          request.headers.get("authorization", ""))
    clear_flow(response)
    return result
