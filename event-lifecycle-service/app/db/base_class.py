# app/db/base_class.py

from sqlalchemy.ext.declarative import declarative_base

# This is the single source of truth for our declarative base.
# All SQLAlchemy models in the project will inherit from this class.
Base = declarative_base()
