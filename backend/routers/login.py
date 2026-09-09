import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, status

from schemas import LoginRequest, LoginResponse
from security import require_key

router = APIRouter(prefix="/login", tags=["auth"], dependencies=[Depends(require_key)])

USERNAME = os.environ.get("DRIVER_USERNAME", "driver")
PASSWORD = os.environ.get("DRIVER_PASSWORD", "")
DRIVER_NAME = os.environ.get("DRIVER_NAME", "Driver")


@router.post("", response_model=LoginResponse)
def login(body: LoginRequest):
    # compare_digest so a wrong guess takes the same time as a right one.
    if (not PASSWORD
            or not secrets.compare_digest(body.username, USERNAME)
            or not secrets.compare_digest(body.password, PASSWORD)):
        # Same message either way, so a wrong username cannot be told apart
        # from a wrong password.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")

    return LoginResponse(driver_name=DRIVER_NAME)
