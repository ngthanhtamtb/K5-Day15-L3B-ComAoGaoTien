from typing import Any, Dict, Optional, Union
from pydantic import BaseModel
from fastapi import status
from enum import Enum


class ResponseCode(str, Enum):
    # Success codes
    SUCCESS = "SUCCESS"
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"

    # Client error codes
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Server error codes
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    AI_SERVICE_ERROR = "AI_SERVICE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

    # Business logic errors
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    TEMPLATE_NOT_COMPATIBLE = "TEMPLATE_NOT_COMPATIBLE"
    PRESENTATION_LOCKED = "PRESENTATION_LOCKED"
    EXPORT_FAILED = "EXPORT_FAILED"


class ResponseMessage:
    # Success messages
    SUCCESS = "Operation completed successfully"
    CREATED = "Resource created successfully"
    UPDATED = "Resource updated successfully"
    DELETED = "Resource deleted successfully"

    # Error messages
    BAD_REQUEST = "Invalid request parameters"
    UNAUTHORIZED = "Authentication required"
    FORBIDDEN = "Access denied"
    NOT_FOUND = "Resource not found"
    CONFLICT = "Resource already exists"
    VALIDATION_ERROR = "Validation failed"

    INTERNAL_ERROR = "Internal server error"
    SERVICE_UNAVAILABLE = "Service temporarily unavailable"
    AI_SERVICE_ERROR = "AI service error"
    DATABASE_ERROR = "Database operation failed"

    INSUFFICIENT_CREDITS = "Insufficient credits for this operation"
    TEMPLATE_NOT_COMPATIBLE = "Template is not compatible with this presentation"
    PRESENTATION_LOCKED = "Presentation is locked by another user"
    EXPORT_FAILED = "Export operation failed"


class StandardResponse(BaseModel):
    success: bool
    code: ResponseCode
    message: str
    data: Optional[Any] = None
    errors: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


def success_response(
        data: Any = None,
        message: str = ResponseMessage.SUCCESS,
        code: ResponseCode = ResponseCode.SUCCESS,
        meta: Optional[Dict[str, Any]] = None
) -> StandardResponse:
    return StandardResponse(
        success=True,
        code=code,
        message=message,
        data=data,
        meta=meta
    )


def error_response(
        message: str,
        code: ResponseCode,
        errors: Optional[Dict[str, Any]] = None,
        data: Any = None
) -> StandardResponse:
    return StandardResponse(
        success=False,
        code=code,
        message=message,
        data=data,
        errors=errors
    )


def paginated_response(
        data: list,
        page: int,
        limit: int,
        total: int,
        message: str = ResponseMessage.SUCCESS
) -> StandardResponse:
    total_pages = (total + limit - 1) // limit

    meta = PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )

    return StandardResponse(
        success=True,
        code=ResponseCode.SUCCESS,
        message=message,
        data=data,
        meta=meta.dict()
    )


STATUS_CODE_MAP = {
    ResponseCode.SUCCESS: status.HTTP_200_OK,
    ResponseCode.CREATED: status.HTTP_201_CREATED,
    ResponseCode.UPDATED: status.HTTP_200_OK,
    ResponseCode.DELETED: status.HTTP_200_OK,

    ResponseCode.BAD_REQUEST: status.HTTP_400_BAD_REQUEST,
    ResponseCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
    ResponseCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
    ResponseCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ResponseCode.CONFLICT: status.HTTP_409_CONFLICT,
    ResponseCode.VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,

    ResponseCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ResponseCode.SERVICE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ResponseCode.AI_SERVICE_ERROR: status.HTTP_502_BAD_GATEWAY,
    ResponseCode.DATABASE_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,

    ResponseCode.INSUFFICIENT_CREDITS: status.HTTP_402_PAYMENT_REQUIRED,
    ResponseCode.TEMPLATE_NOT_COMPATIBLE: status.HTTP_400_BAD_REQUEST,
    ResponseCode.PRESENTATION_LOCKED: status.HTTP_423_LOCKED,
    ResponseCode.EXPORT_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def get_http_status(code: ResponseCode) -> int:
    return STATUS_CODE_MAP.get(code, status.HTTP_500_INTERNAL_SERVER_ERROR)
