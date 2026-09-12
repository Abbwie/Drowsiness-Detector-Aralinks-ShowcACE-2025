from fastapi import APIRouter, Depends, HTTPException, status

from config import DRIVER_NAME, DRIVER_PASSWORD, DRIVER_USERNAME
from schemas import LoginRequest, LoginResponse
from security import matches, require_key

router = APIRouter(prefix="/login", tags=["auth"], dependencies=[Depends(require_key)])


@router.post("", response_model=LoginResponse)
def login(body: LoginRequest):
    # Both fields are compared even when the first already failed, so a wrong
    # guess takes the same time as a right one.
    ok_user = matches(body.username, DRIVER_USERNAME)
    ok_pass = matches(body.password, DRIVER_PASSWORD)

    if not DRIVER_PASSWORD or not ok_user or not ok_pass:
        # Same message either way, so a wrong username cannot be told apart
        # from a wrong password.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")

    return LoginResponse(driver_name=DRIVER_NAME)
