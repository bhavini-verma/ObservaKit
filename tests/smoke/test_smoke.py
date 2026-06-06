"""
ObservaKit — End-to-End Smoke Test
Boots the docker-compose.test.yml stack, initializes the database,
seeds sample warehouse tables, runs freshness & quality checks,
and asserts successful execution.
"""

import subprocess
import time

import httpx
import psycopg2
import pytest

# Configuration
API_URL = "http://localhost:8005"
API_KEY = "test_smoke_key"
DB_CONN_STR = "postgresql://observakit:test_password@localhost:5434/observakit"

def is_docker_running() -> bool:
    """Check if the Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

@pytest.fixture(scope="module", autouse=True)
def docker_stack():
    """Fixture to boot up the Docker Compose testing stack and shut it down after tests."""
    if not is_docker_running():
        pytest.fail(
            "Docker daemon is not running or unreachable. "
            "Please start Docker Desktop/daemon to run the end-to-end smoke test stack."
        )

    print("\n[Smoke Test] Starting docker-compose.test.yml stack...")

    # Force pull/rebuild and start services in background
    up_cmd = ["docker", "compose", "-f", "docker-compose.test.yml", "up", "-d", "--build"]
    result = subprocess.run(up_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        pytest.fail(f"Failed to start Docker Compose stack: {result.stderr}")

    # Wait for backend and DB readiness
    max_retries = 30
    ready = False
    print("[Smoke Test] Waiting for backend readiness at http://localhost:8005/healthz...")

    for i in range(max_retries):
        try:
            # Check the /healthz endpoint of backend
            response = httpx.get(f"{API_URL}/healthz", timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok" and data.get("database") == "ok":
                    ready = True
                    print(f"[Smoke Test] Stack is healthy and ready after {i+1} seconds!")
                    break
        except Exception:
            pass
        time.sleep(1.0)

    if not ready:
        # Capture logs before failing
        logs = subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml", "logs"], stdout=subprocess.PIPE, text=True)
        print("\n=== Docker Compose Logs ===\n", logs.stdout)

        # Stop stack
        subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml", "down", "-v"])
        pytest.fail("Backend or Database service failed to become ready within the timeout period.")

    # Setup the mock warehouse tables in the same Postgres database
    try:
        setup_warehouse_tables()
    except Exception as e:
        # Capture logs and teardown
        logs = subprocess.run(["docker", "compose", "-p", "teststack", "-f", "docker-compose.test.yml", "logs"], stdout=subprocess.PIPE, text=True)
        print("\n=== Docker Compose Logs ===\n", logs.stdout)
        subprocess.run(["docker", "compose", "-p", "teststack", "-f", "docker-compose.test.yml", "down", "-v"])
        pytest.fail(f"Failed to setup target warehouse tables in database: {e}")

    yield

    print("\n[Smoke Test] Tearing down docker-compose.test.yml stack...")
    subprocess.run(["docker", "compose", "-p", "teststack", "-f", "docker-compose.test.yml", "down", "-v"])

def setup_warehouse_tables():
    """Create sample target tables in the testing database to act as the warehouse."""
    print("[Smoke Test] Connecting to warehouse database at localhost:5434...")
    conn = psycopg2.connect(DB_CONN_STR)
    conn.autocommit = True
    with conn.cursor() as cur:
        # Create schema public tables
        print("[Smoke Test] Creating sample warehouse tables...")

        # 1. Orders table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                amount NUMERIC(10, 2),
                status VARCHAR(50),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 2. Order items table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INT REFERENCES orders(id),
                price NUMERIC(10, 2),
                quantity INT
            );
        """)

        # 3. Customers table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # Seed data
        print("[Smoke Test] Seeding sample data...")
        cur.execute("DELETE FROM order_items;")
        cur.execute("DELETE FROM orders;")
        cur.execute("DELETE FROM customers;")

        # Insert customers
        cur.execute("INSERT INTO customers (id, name) VALUES (1, 'Alice'), (2, 'Bob');")

        # Insert orders
        cur.execute("INSERT INTO orders (id, amount, status) VALUES (1, 99.99, 'completed'), (2, 49.50, 'pending');")

        # Insert order items (no orphans to satisfy quality custom check)
        cur.execute("INSERT INTO order_items (order_id, price, quantity) VALUES (1, 99.99, 1), (2, 49.50, 1);")

    conn.close()
    print("[Smoke Test] Seed data applied successfully.")

@pytest.mark.smoke
def test_health_endpoint():
    """Verify that calling the healthz endpoint returns HTTP 200 and healthy status."""
    response = httpx.get(f"{API_URL}/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"

@pytest.mark.smoke
def test_freshness_poll():
    """Verify that triggering a freshness check executes successfully."""
    headers = {"X-API-Key": API_KEY}
    response = httpx.post(f"{API_URL}/freshness/poll", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "checked" in data
    assert data["checked"] > 0

    # Assert that public.orders was checked successfully
    checked_tables = [res["table"] for res in data["results"] if "error" not in res]
    assert "public.orders" in checked_tables

@pytest.mark.smoke
def test_quality_checks_run():
    """Verify that running quality checks executes successfully."""
    headers = {"X-API-Key": API_KEY}
    response = httpx.post(f"{API_URL}/checks/run", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "checks_run" in data
    assert data["checks_run"] > 0

    # Assert that results are returned
    results = data["results"]
    assert len(results) > 0

    # Verify our seeded tables passed the custom SQL check
    custom_sql_passes = [res for res in results if res.get("engine") == "custom_sql" and res.get("passed") is True]
    assert len(custom_sql_passes) > 0

@pytest.mark.smoke
def test_status_endpoint():
    """Verify that retrieving the system status returns details about our tables."""
    response = httpx.get(f"{API_URL}/status")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "tables" in data

    # The summary should show healthy tables
    summary = data["summary"]
    assert (summary["healthy"] + summary["warn"] + summary["fail"]) > 0
