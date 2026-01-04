"""
Phase 0 Integration Test
Tests that all infrastructure components are properly connected
"""
import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.core.redis_client import RedisClient
from app.db.timescale import engine, init_db
from sqlalchemy import text


async def test_configuration():
    """Test 1: Verify configuration is loaded correctly"""
    print("\n" + "="*60)
    print("TEST 1: Configuration Loading")
    print("="*60)

    settings = get_settings()
    print(f"✓ Settings loaded successfully")
    print(f"  - Database URL: {settings.DATABASE_URL}")
    print(f"  - Redis URL: {settings.REDIS_URL}")
    print(f"  - Engagement Threshold: {settings.ENGAGEMENT_THRESHOLD}")

    assert settings.DATABASE_URL == "postgresql://postgres:password@localhost:5437/agent_db", \
        "DATABASE_URL should point to agent_db on port 5437"
    print("✓ Database URL is correct")

    return True


async def test_redis_connection():
    """Test 2: Connect to Redis"""
    print("\n" + "="*60)
    print("TEST 2: Redis Connection")
    print("="*60)

    settings = get_settings()
    redis = RedisClient(settings.REDIS_URL)

    try:
        await redis.connect()
        print("✓ Connected to Redis successfully")

        # Test ping
        await redis.client.ping()
        print("✓ Redis ping successful")

        # Test publish/subscribe
        await redis.publish("test:channel", "Hello from agent-service")
        print("✓ Redis publish successful")

        await redis.disconnect()
        print("✓ Disconnected from Redis")
        return True

    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        return False


async def test_database_connection():
    """Test 3: Connect to TimescaleDB"""
    print("\n" + "="*60)
    print("TEST 3: TimescaleDB Connection")
    print("="*60)

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"✓ Connected to PostgreSQL: {version[:50]}...")

            # Check TimescaleDB extension
            result = await conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';")
            )
            row = result.fetchone()
            if row:
                print(f"✓ TimescaleDB extension installed: v{row[1]}")
            else:
                print("✗ TimescaleDB extension not found")
                return False

        return True

    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check if postgres-agent container is running:")
        print("     docker ps --filter 'name=postgres-agent'")
        print("  2. Check container logs:")
        print("     docker logs postgres-agent")
        print("  3. Try connecting manually:")
        print("     docker exec -it postgres-agent psql -U postgres -d agent_db")
        return False


async def test_database_initialization():
    """Test 4: Initialize database and create tables"""
    print("\n" + "="*60)
    print("TEST 4: Database Initialization")
    print("="*60)

    try:
        await init_db()
        print("✓ Database initialized successfully")

        # Check if tables were created
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public';")
            )
            tables = [row[0] for row in result.fetchall()]

            expected_tables = ['engagement_metrics', 'interventions', 'agent_performance']

            for table in expected_tables:
                if table in tables:
                    print(f"✓ Table '{table}' created")
                else:
                    print(f"✗ Table '{table}' missing")
                    return False

            # Check hypertables
            result = await conn.execute(
                text("SELECT hypertable_name FROM timescaledb_information.hypertables;")
            )
            hypertables = [row[0] for row in result.fetchall()]

            print(f"\n✓ Hypertables created: {len(hypertables)}")
            for ht in hypertables:
                print(f"  - {ht}")

        return True

    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_models_import():
    """Test 5: Verify models can be imported"""
    print("\n" + "="*60)
    print("TEST 5: Model Imports")
    print("="*60)

    try:
        from app.db.models import EngagementMetric, Intervention, AgentPerformance
        print("✓ EngagementMetric model imported")
        print("✓ Intervention model imported")
        print("✓ AgentPerformance model imported")

        # Check model structure
        print(f"\nEngagementMetric columns:")
        for col in EngagementMetric.__table__.columns:
            print(f"  - {col.name}: {col.type}")

        return True

    except Exception as e:
        print(f"✗ Model import failed: {e}")
        return False


async def run_all_tests():
    """Run all Phase 0 tests"""
    print("\n" + "="*60)
    print("🧪 PHASE 0 INTEGRATION TESTS")
    print("="*60)
    print("Testing agent-service infrastructure...\n")

    results = []

    # Test 1: Configuration
    try:
        results.append(("Configuration", await test_configuration()))
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        results.append(("Configuration", False))

    # Test 2: Redis
    try:
        results.append(("Redis Connection", await test_redis_connection()))
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        results.append(("Redis Connection", False))

    # Test 3: Database Connection
    try:
        results.append(("Database Connection", await test_database_connection()))
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        results.append(("Database Connection", False))

    # Test 4: Database Initialization
    try:
        results.append(("Database Initialization", await test_database_initialization()))
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        results.append(("Database Initialization", False))

    # Test 5: Model Imports
    try:
        results.append(("Model Imports", await test_models_import()))
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        results.append(("Model Imports", False))

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Phase 0 is production-ready.")
        print("\nNext steps:")
        print("1. Start the agent service: python app/main.py")
        print("2. Test health endpoint: curl http://localhost:8003/health")
        print("3. Move to Phase 1: Signal Collection Pipeline")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix issues before proceeding.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
