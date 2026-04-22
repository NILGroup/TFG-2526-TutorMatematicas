"""
Main entry point for the FastAPI backend.

This module defines the application factory and assembles the various
API routes that make up the math tutor service. The resulting `app`
instance can be executed with an ASGI server such as uvicorn.

Project structure:

- backend/ml/ contains ML logic (dataset transformer, BKT, chatbot), no HTTP code
- backend/app/routes/ contains FastAPI routers (HTTP endpoints)
- backend/scripts/ contains offline scripts (build dataset, train BKT)

Runtime:
- Start the API server: uvicorn backend.app.main:app --reload
"""

from fastapi import FastAPI

from app.routes import problems, sessions, tutor, users


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    Routers define their own prefixes (e.g., /tutor, /problems, /sessions),
    so we include them here without additional prefixing.
    """
    app = FastAPI(
        title="Math Tutor Backend",
        version="0.1.0",
        description=(
            "Backend API for the math tutor application. "
            "Provides endpoints for problems browsing, practice sessions, "
            "and a tutor chatbot grounded on each problem."
        ),
    )

    # Routers already define their prefixes + tags internally
    app.include_router(problems.router)
    app.include_router(sessions.router)
    app.include_router(tutor.router)
    app.include_router(users.router)

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    return app


# ASGI application entrypoint for uvicorn/gunicorn
app = create_app()
