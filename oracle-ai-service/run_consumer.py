#oracle-ai-service/run_consumers.py
from app.messaging import consumers

if __name__ == "__main__":
    print("Starting all Oracle AI consumers...")
    consumers.run_all_consumers()
