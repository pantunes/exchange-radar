from collections.abc import Callable
from functools import wraps

from starlette.exceptions import HTTPException, WebSocketException
from starlette.requests import Request


class RaiseValidationException:
    def __init__(self, request: Request, message: str):
        if request.scope["type"] == "http":
            raise HTTPException(400, detail=message)
        elif request.scope["type"] == "websocket":
            raise WebSocketException(code=1008, reason=None)
        raise HTTPException(400, detail="Invalid request type")


def validate(serializer) -> Callable:
    def decorator(f: Callable):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            data = None
            request: Request = args[-1]
            try:
                data = serializer(**request.path_params)
            except AttributeError:
                # object has no attribute 'path_params'
                pass
            except TypeError:
                RaiseValidationException(request=request, message="Mandatory fields are missing")
            except ValueError as error:
                RaiseValidationException(request=request, message=str(error))
            return await f(data=data, *args, **kwargs)

        return wrapper

    return decorator
