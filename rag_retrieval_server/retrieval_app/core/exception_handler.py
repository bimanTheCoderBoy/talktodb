from .exceptions import CustomBaseException
from fastapi.responses import JSONResponse
from fastapi import Request

def exception_handler(request: Request, exception: Exception):
    if isinstance(exception, CustomBaseException):
        return JSONResponse(status_code=exception.status_code if exception.status_code else 500, content={"detail": exception.message if exception.message else "Internal Server Error"})
    else:
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
