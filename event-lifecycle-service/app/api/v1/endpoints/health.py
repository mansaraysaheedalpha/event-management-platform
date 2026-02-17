# app/api/v1/endpoints/health.py
"""
Health check endpoints for monitoring system status.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.redis import redis_client

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check():
    """Basic health check - API is responding."""
    return {"status": "healthy", "service": "event-lifecycle-service"}


@router.get("/db")
def database_health(db: Session = Depends(get_db)):
    """Check database connectivity."""
    try:
        # Simple query to verify DB connection
        db.execute("SELECT 1")
        return {"status": "healthy", "component": "database"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database unhealthy: {str(e)}",
        )


@router.get("/redis")
def redis_health():
    """Check Redis connectivity."""
    try:
        redis_client.ping()
        return {"status": "healthy", "component": "redis"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Redis unhealthy: {str(e)}",
        )


@router.get("/celery")
def celery_health():
    """Check if Celery workers are responsive."""
    from app.worker import celery_app

    try:
        # Inspect active workers
        inspect = celery_app.control.inspect()
        stats = inspect.stats()

        if not stats:
            raise HTTPException(
                status_code=503,
                detail="No Celery workers available",
            )

        # Get active tasks
        active = inspect.active()
        active_count = sum(len(tasks) for tasks in active.values()) if active else 0

        # Get scheduled tasks
        scheduled = inspect.scheduled()
        scheduled_count = sum(len(tasks) for tasks in scheduled.values()) if scheduled else 0

        # Get registered tasks
        registered = inspect.registered()
        task_names = list(registered.values())[0] if registered else []

        return {
            "status": "healthy",
            "component": "celery",
            "workers": list(stats.keys()),
            "worker_count": len(stats),
            "active_tasks": active_count,
            "scheduled_tasks": scheduled_count,
            "registered_tasks": len(task_names),
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Celery unhealthy: {str(e)}",
        )


@router.get("/celery/scheduled")
def celery_scheduled_tasks():
    """Get list of scheduled periodic tasks."""
    from app.worker import celery_app

    try:
        beat_schedule = celery_app.conf.beat_schedule

        tasks = []
        for name, config in beat_schedule.items():
            tasks.append({
                "name": name,
                "task": config["task"],
                "schedule_seconds": config["schedule"],
            })

        return {
            "scheduled_tasks": tasks,
            "count": len(tasks),
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to get scheduled tasks: {str(e)}",
        )
