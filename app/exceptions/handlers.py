from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AccountNotFoundException(Exception):
    def __init__(self, account_id: int):
        self.account_id = account_id
        super().__init__(f"Account not found: {account_id}")


class InsufficientBalanceException(Exception):
    def __init__(self, account_id: int, balance, amount):
        self.account_id = account_id
        self.balance = balance
        self.amount = amount
        super().__init__(
            f"Insufficient balance for account {account_id}: "
            f"balance={balance}, amount={amount}"
        )


class DuplicateDocumentException(Exception):
    def __init__(self, document: str):
        self.document = document
        super().__init__(f"Document already exists: {document}")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AccountNotFoundException)
    async def account_not_found_handler(request: Request, exc: AccountNotFoundException):
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "message": str(exc),
                "status": 404,
            },
        )

    @app.exception_handler(InsufficientBalanceException)
    async def insufficient_balance_handler(request: Request, exc: InsufficientBalanceException):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Bad Request",
                "message": str(exc),
                "status": 400,
            },
        )

    @app.exception_handler(DuplicateDocumentException)
    async def duplicate_document_handler(request: Request, exc: DuplicateDocumentException):
        return JSONResponse(
            status_code=409,
            content={
                "error": "Conflict",
                "message": str(exc),
                "status": 409,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation Error",
                "message": "Invalid request data",
                "details": exc.errors(),
                "status": 422,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "status": 500,
            },
        )
