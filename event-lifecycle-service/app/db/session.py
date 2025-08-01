from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# The engine is the entry point to the database. It's configured with the
# database URL and handles the connection pooling.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# SessionLocal is a factory for creating new Session objects.
# Think of a session as a temporary workspace for all your database
# operations within a single request.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# This is our dependency function.
# When an endpoint depends on this, FastAPI will execute this function
# before running the endpoint's code.
def get_db():
    db = SessionLocal()
    try:
        # 'yield' passes the session object to the endpoint.
        yield db
    finally:
        # This code runs after the endpoint has finished.
        # It ensures the database session is always closed, even if there was an error.
        db.close()
