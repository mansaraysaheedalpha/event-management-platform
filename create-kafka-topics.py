#!/usr/bin/env python3
"""
Kafka Topics Auto-Creation Script
Automatically creates all required Kafka topics for the Event Management Platform.
Skips topics that already exist.

Usage:
    python create-kafka-topics.py
"""

from confluent_kafka.admin import AdminClient, NewTopic, KafkaException
import sys

# Confluent Cloud Configuration
KAFKA_CONFIG = {
    'bootstrap.servers': 'pkc-oxqxx9.us-east-1.aws.confluent.cloud:9092',
    'security.protocol': 'SASL_SSL',
    'sasl.mechanism': 'PLAIN',
    'sasl.username': 'QVL53FWSBYUNPDPV',
    'sasl.password': 'cfltd61uXdHFWFgEWetCNpo/r6+dd4M4nozizgc60k6ByZpp7dcGiRXfE85HjqRw',
}

# All topics needed by the platform
TOPICS = [
    # Input topics (real-time-service → oracle-ai-service)
    {
        'name': 'real-time.network.connections',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,  # 7 days
        'description': 'Network connection events to trigger AI suggestions',
    },
    {
        'name': 'real-time.user.interactions',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'User interaction events for engagement predictions',
    },
    {
        'name': 'real-time.attendance.data',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Session attendance data for capacity forecasting',
    },
    {
        'name': 'real-time.session.feedback',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Session feedback for success insights',
    },

    # Output topics (oracle-ai-service → real-time-service)
    {
        'name': 'oracle.predictions.sentiment.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Sentiment analysis predictions for chat messages',
    },
    {
        'name': 'oracle.predictions.engagement-predictions',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Engagement score predictions',
    },
    {
        'name': 'oracle.predictions.capacity-forecasts',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Session capacity forecasts',
    },
    {
        'name': 'oracle.predictions.networking-suggestions',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'AI-powered networking suggestions (CRITICAL for suggestions feature)',
    },
    {
        'name': 'oracle.predictions.success-insights',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Event success insights and analytics',
    },

    # Platform events topics
    {
        'name': 'platform.events.chat.message.v1',
        'partitions': 5,
        'replication_factor': 3,
        'retention_ms': 2592000000,  # 30 days for chat messages
        'description': 'Chat messages for sentiment analysis',
    },
    {
        'name': 'giveaway.events.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Giveaway events',
    },
    {
        'name': 'lead.capture.events.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 2592000000,  # 30 days for leads
        'description': 'Lead capture events',
    },
    {
        'name': 'lead.intent.events.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 2592000000,
        'description': 'Lead intent signals',
    },
    {
        'name': 'registration.events.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 2592000000,
        'description': 'Event registration events',
    },
    {
        'name': 'waitlist.events.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 2592000000,
        'description': 'Waitlist events',
    },

    # Networking retention topics
    {
        'name': 'networking.follow-up-emails.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 2592000000,
        'description': 'Follow-up email events',
    },
    {
        'name': 'networking.follow-up-reminder.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Follow-up reminder notifications',
    },
    {
        'name': 'networking.stale-connection-nudge.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Stale connection nudge notifications',
    },
    {
        'name': 'networking.weekly-digest.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Weekly network digest emails',
    },
    {
        'name': 'networking.milestone.v1',
        'partitions': 3,
        'replication_factor': 3,
        'retention_ms': 604800000,
        'description': 'Networking milestone notifications',
    },
]


def create_topics():
    """Create all required Kafka topics, skipping ones that already exist."""

    print("=" * 80)
    print("🚀 Kafka Topics Auto-Creation Script")
    print("=" * 80)
    print()

    # Initialize Kafka Admin Client
    print("📡 Connecting to Confluent Cloud...")
    try:
        admin_client = AdminClient(KAFKA_CONFIG)
        # Test connection by listing topics
        metadata = admin_client.list_topics(timeout=10)
        print(f"✅ Connected successfully to {KAFKA_CONFIG['bootstrap.servers']}")
        print()
    except Exception as e:
        print(f"❌ Failed to connect to Kafka: {e}")
        sys.exit(1)

    # Get existing topics
    print("🔍 Fetching existing topics...")
    existing_topics = set(metadata.topics.keys())
    print(f"✅ Found {len(existing_topics)} existing topics")
    print()

    # Prepare topics to create
    topics_to_create = []
    topics_skipped = []

    print("📋 Analyzing topics...")
    print("-" * 80)

    for topic_config in TOPICS:
        topic_name = topic_config['name']
        if topic_name in existing_topics:
            topics_skipped.append(topic_name)
            print(f"⏭️  SKIP: {topic_name} (already exists)")
        else:
            new_topic = NewTopic(
                topic=topic_name,
                num_partitions=topic_config['partitions'],
                replication_factor=topic_config['replication_factor'],
                config={
                    'retention.ms': str(topic_config['retention_ms']),
                    'cleanup.policy': 'delete',
                }
            )
            topics_to_create.append(new_topic)
            print(f"➕ CREATE: {topic_name}")
            print(f"   └─ {topic_config['description']}")

    print("-" * 80)
    print()

    # Summary
    print(f"📊 Summary:")
    print(f"   • Total topics defined: {len(TOPICS)}")
    print(f"   • Already exist (skipped): {len(topics_skipped)}")
    print(f"   • Will be created: {len(topics_to_create)}")
    print()

    # Create topics if any
    if not topics_to_create:
        print("✅ All topics already exist! Nothing to create.")
        print()
        print("=" * 80)
        return

    print("🔨 Creating topics...")
    print("-" * 80)

    # Create topics asynchronously
    fs = admin_client.create_topics(topics_to_create, request_timeout=30)

    # Wait for each topic creation to complete
    success_count = 0
    failed_count = 0

    for topic, future in fs.items():
        try:
            future.result()  # Block until topic is created
            print(f"✅ Created: {topic}")
            success_count += 1
        except KafkaException as e:
            error_code = e.args[0].code()
            if error_code == 36:  # TOPIC_ALREADY_EXISTS
                print(f"⚠️  {topic} already exists (race condition)")
                success_count += 1
            else:
                print(f"❌ Failed to create {topic}: {e}")
                failed_count += 1
        except Exception as e:
            print(f"❌ Failed to create {topic}: {e}")
            failed_count += 1

    print("-" * 80)
    print()

    # Final summary
    print("=" * 80)
    print("🎉 Topic Creation Complete!")
    print("=" * 80)
    print(f"✅ Successfully created: {success_count} topics")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count} topics")
    print()

    # Critical topics check
    critical_topics = [
        'real-time.network.connections',
        'oracle.predictions.networking-suggestions',
    ]

    print("🔐 Verifying critical topics for suggestions feature...")
    metadata = admin_client.list_topics(timeout=10)
    current_topics = set(metadata.topics.keys())

    all_critical_exist = all(topic in current_topics for topic in critical_topics)

    if all_critical_exist:
        print("✅ All critical topics exist!")
        print("   • real-time.network.connections")
        print("   • oracle.predictions.networking-suggestions")
        print()
        print("🚀 Your suggestions feature should now work!")
    else:
        print("⚠️  Some critical topics are missing:")
        for topic in critical_topics:
            if topic not in current_topics:
                print(f"   ❌ {topic}")

    print()
    print("=" * 80)
    print("📝 Next Steps:")
    print("   1. Verify topics in Confluent Cloud Console")
    print("   2. Check ACL permissions for your API key")
    print("   3. Test the Connect button in your app")
    print("=" * 80)
    print()


if __name__ == '__main__':
    try:
        create_topics()
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
