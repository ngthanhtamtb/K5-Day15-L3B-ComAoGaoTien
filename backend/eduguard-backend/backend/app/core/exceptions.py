from fastapi import HTTPException
from app.core.response import ResponseCode, ResponseMessage, get_http_status

class SmartPPTException(HTTPException):
    def __init__(
        self,
        code: ResponseCode,
        message: str = None,
        errors: dict = None
    ):
        self.code = code
        self.message = message or getattr(ResponseMessage, code.value, "Unknown error")
        self.errors = errors
        super().__init__(
            status_code=get_http_status(code),
            detail={
                "success": False,
                "code": code.value,
                "message": self.message,
                "errors": errors
            }
        )

class ValidationException(SmartPPTException):
    def __init__(self, message: str = None, errors: dict = None):
        super().__init__(
            code=ResponseCode.VALIDATION_ERROR,
            message=message or ResponseMessage.VALIDATION_ERROR,
            errors=errors
        )

class NotFoundException(SmartPPTException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            code=ResponseCode.NOT_FOUND,
            message=f"{resource} not found"
        )

class UnauthorizedException(SmartPPTException):
    def __init__(self, message: str = None):
        super().__init__(
            code=ResponseCode.UNAUTHORIZED,
            message=message or ResponseMessage.UNAUTHORIZED
        )

class ForbiddenException(SmartPPTException):
    def __init__(self, message: str = None):
        super().__init__(
            code=ResponseCode.FORBIDDEN,
            message=message or ResponseMessage.FORBIDDEN
        )

class ConflictException(SmartPPTException):
    def __init__(self, message: str = None):
        super().__init__(
            code=ResponseCode.CONFLICT,
            message=message or ResponseMessage.CONFLICT
        )

class InsufficientCreditsException(SmartPPTException):
    def __init__(self):
        super().__init__(
            code=ResponseCode.INSUFFICIENT_CREDITS,
            message=ResponseMessage.INSUFFICIENT_CREDITS
        )

class AIServiceException(SmartPPTException):
    def __init__(self, message: str = None):
        super().__init__(
            code=ResponseCode.AI_SERVICE_ERROR,
            message=message or ResponseMessage.AI_SERVICE_ERROR
        )

class TemplateNotCompatibleException(SmartPPTException):
    def __init__(self):
        super().__init__(
            code=ResponseCode.TEMPLATE_NOT_COMPATIBLE,
            message=ResponseMessage.TEMPLATE_NOT_COMPATIBLE
        )

class PresentationLockedException(SmartPPTException):
    def __init__(self):
        super().__init__(
            code=ResponseCode.PRESENTATION_LOCKED,
            message=ResponseMessage.PRESENTATION_LOCKED
        )
