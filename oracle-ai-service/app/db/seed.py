# app/db/seed.py
from .database import SessionLocal, engine
from . import models


def get_seed_data():
    """This contains the data from our old knowledge base simulations."""
    return [
        models.KnowledgeBaseItem(
            category="competitors",
            key="EventCorp",
            data={
                "strengths": ["Strong brand recognition"],
                "weaknesses": ["Slow to adopt new tech"],
            },
        ),
        models.KnowledgeBaseItem(
            category="competitors",
            key="Virtual-First Inc.",
            data={
                "strengths": ["Excellent virtual platform"],
                "weaknesses": ["Smaller brand"],
            },
        ),
        models.KnowledgeBaseItem(
            category="cultural_rules",
            key="Japan",
            data={
                "sensitivities": ["Avoid direct criticism."],
                "customs": ["Punctuality is valued."],
                "replacements": {"bad idea": "concern worth discussing"},
            },
        ),
        models.KnowledgeBaseItem(
            category="market_data",
            key="Germany_Tech",
            data={
                "market_size_usd_millions": 150000,
                "growth_rate": 0.06,
                "key_segments": ["Cloud Computing", "Automotive Tech"],
            },
        ),
        models.KnowledgeBaseItem(
            category="market_data",
            key="Japan_Finance",
            data={
                "market_size_usd_millions": 300000,
                "growth_rate": 0.04,
                "key_segments": ["DeFi", "Insurtech"],
            },
        ),
        # --- ADD THE MODEL REGISTRY DATA ---
        models.KnowledgeBaseItem(
            category="model_registry",
            key="sentiment_analysis_v2",
            data={
                "model_id": "sentiment_analysis_v2",
                "model_name": "DistilBERT-SST2",
                "version": "2.1.3",
                "status": "active",
                "created_at": "2025-07-15T10:00:00Z",
            },
        ),
        models.KnowledgeBaseItem(
            category="model_registry",
            key="churn_prediction_xgb",
            data={
                "model_id": "churn_prediction_xgb",
                "model_name": "XGBoost Churn Classifier",
                "version": "1.4.0",
                "status": "active",
                "created_at": "2025-06-20T14:30:00Z",
            },
        ),
    ]


def seed_database():
    db = SessionLocal()
    try:
        print("Seeding database...")
        # Create tables
        models.Base.metadata.create_all(bind=engine)

        # Check if data already exists
        if db.query(models.KnowledgeBaseItem).first():
            print("Database already seeded.")
            return

        seed_items = get_seed_data()
        db.add_all(seed_items)
        db.commit()
        print("Database seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
