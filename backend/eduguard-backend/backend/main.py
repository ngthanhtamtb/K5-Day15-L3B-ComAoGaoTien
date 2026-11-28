from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.core.response import error_response, ResponseCode
from app.core.exceptions import SmartPPTException
from app.api.v1.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models  # noqa: F401  — register every table before create_all
    import app.edu.billing.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    from app.core.jobs import jobs
    jobs.start()
    yield
    await jobs.stop()


app = FastAPI(
    title="SmartPPT API",
    description="AI-powered presentation generator",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api-docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api-redoc" if settings.ENVIRONMENT != "production" else None,
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_access_log = logging.getLogger("eduguard.access")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Never log headers or bodies: they carry bearer tokens and uploaded documents.
    try:
        response = await call_next(request)
    except Exception as e:
        _access_log.error("%s %s -> %s", request.method, request.url.path, type(e).__name__)
        raise
    _access_log.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response

import os
os.makedirs(settings.EDU_DATA_DIR, exist_ok=True)
# EduGuard files first (more specific path), then the original RAGslides static dir.
app.mount("/static/edu", StaticFiles(directory=settings.EDU_DATA_DIR), name="static-edu")
os.makedirs("data", exist_ok=True)
app.mount("/static", StaticFiles(directory="data"), name="static")
if settings.EDU_UI_DIR and os.path.isdir(settings.EDU_UI_DIR):
    # Same origin as the API: the UI calls /api/v1/edu/... with relative URLs, no CORS needed.
    app.mount("/ui", StaticFiles(directory=settings.EDU_UI_DIR, html=True), name="ui")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for validation errors to safely handle binary data in multipart requests.
    """
    print(f"=== RequestValidationError Handler ===")
    print(f"Request URL: {request.url}")
    print(f"Request Method: {request.method}")
    print(f"Errors: {exc.errors()}")

    errors = []
    for error in exc.errors():
        error_dict = {
            "loc": error.get("loc", []),
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        }
        # Safely handle input field - avoid encoding binary data
        if "input" in error:
            input_value = error["input"]
            # Check if it's binary data (bytes)
            if isinstance(input_value, bytes):
                error_dict["input"] = "<binary data>"
            else:
                try:
                    # Try to convert to string safely
                    error_dict["input"] = str(input_value)[:100]  # Limit length
                except Exception:
                    error_dict["input"] = "<non-serializable data>"

        errors.append(error_dict)

    return JSONResponse(
        status_code=422,
        content=error_response(
            message="Validation error",
            code=ResponseCode.VALIDATION_ERROR,
            errors={"detail": errors}
        ).model_dump()
    )

@app.exception_handler(SmartPPTException)
async def smartppt_exception_handler(request: Request, exc: SmartPPTException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    print(f"=== HTTPException Handler ===")
    print(f"Status Code: {exc.status_code}")
    print(f"Detail: {exc.detail}")
    print(f"Request URL: {request.url}")
    print(f"Request Method: {request.method}")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            message=str(exc.detail),
            code=ResponseCode.BAD_REQUEST if exc.status_code == 400 else ResponseCode.INTERNAL_ERROR
        ).model_dump()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=error_response(
            message="Internal server error",
            code=ResponseCode.INTERNAL_ERROR,
            errors={"detail": str(exc) if settings.DEBUG else "An unexpected error occurred"}
        ).model_dump()
    )


app.include_router(api_router, prefix="/api/v1")


@app.get("/api/health")
async def health_check():
    return {
        "success": True,
        "code": "SUCCESS",
        "message": "Service is healthy",
        "data": {
            "status": "healthy",
            "service": "SmartPPT API",
            "version": "1.0.0"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8077)
