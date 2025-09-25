import json
import time
import random
from kafka import KafkaProducer

# --- CONFIGURATION ---
KAFKA_BROKER_URL = "localhost:9092"
# IMPORTANT: Replace this with a real event ID from your dashboard
EVENT_ID = "evt_893be87e6385"
# ---------------------

# A list of fake names to use for the simulation
FAKE_NAMES = [
    "Alex Johnson",
    "Maria Garcia",
    "Chen Wei",
    "Fatima Al-Fassi",
    "Sam Miller",
    "Priya Patel",
    "John Smith",
    "Olga Ivanova",
    "Kenji Tanaka",
    "Sofia Rossi",
]

print("--- Event Check-in Simulator ---")
print(f"Connecting to Kafka at {KAFKA_BROKER_URL}...")

try:
    # Set up the connection to your Kafka container
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER_URL,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    print("✅ Successfully connected to Kafka.")
    print(f"Simulating check-ins for Event ID: {EVENT_ID}")
    print("Press Ctrl+C to stop.")

    check_in_count = 0
    while True:
        # Pick a random name
        attendee_name = random.choice(FAKE_NAMES)
        check_in_count += 1
        attendee_id = f"user_{check_in_count}"

        # This is the exact data structure your backend expects for a check-in
        payload = {
            "type": "CHECK_IN_PROCESSED",
            "eventId": EVENT_ID,
            "organizationId": "org_placeholder",  # Not used by the dashboard, can be a placeholder
            "checkInData": {"id": attendee_id, "name": attendee_name},
        }

        # Send the message to the Kafka topic
        topic = "platform.analytics.check-in.v1"
        producer.send(topic, value=payload)
        producer.flush()  # Ensure the message is sent immediately

        print(f"Sent check-in: {attendee_name}")

        # Wait for a random time between 2 and 7 seconds
        time.sleep(random.randint(2, 7))

except Exception as e:
    print(f"\n❌ Error: Could not connect to Kafka or send message.")
    print(
        "   Please ensure your Docker containers are running and Kafka is accessible at localhost:9092."
    )
    print(f"   Details: {e}")
