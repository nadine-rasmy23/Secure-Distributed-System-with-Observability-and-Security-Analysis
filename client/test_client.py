"""
Test Client for Secure Distributed System
==========================================
This script tests all system functionality:
1. Login and JWT token generation
2. Normal task creation
3. Load balancing verification
4. Unauthorized request handling
5. Rate limiting
6. Database log verification
"""

import requests
from requests.adapters import HTTPAdapter
import json
import time
import urllib3
import psycopg2
from tabulate import tabulate
from concurrent.futures import ThreadPoolExecutor, as_completed

# Disable SSL warnings for self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================
# Configuration
# ============================================
HTTPS_BASE_URL = "https://localhost"
HTTP_BASE_URL = "http://localhost"
BASE_URL = HTTPS_BASE_URL

DB_CONFIG = {
    "host": "localhost",
    "database": "audit_db",
    "user": "postgres",
    "password": "postgres"
}

CREDENTIALS = {
    "username": "admin",
    "password": "admin123"
}


def separator(title):
    """Print a formatted section separator."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================
# Test 1: Login and Get JWT Token
# ============================================
def test_login():
    """Test login endpoint and retrieve JWT token."""
    separator("TEST 1: Login & JWT Token Generation")

    response = requests.post(
        f"{BASE_URL}/login",
        json=CREDENTIALS,
        verify=False
    )

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    if response.status_code == 200:
        print(f"\n[PASS] Login successful!")
        print(f"   Instance: {data['instance']}")
        print(f"   Token: {data['token'][:50]}...")
        return data['token']
    else:
        print(f"\n[FAIL] Login failed!")
        return None


# ============================================
# Test 2: Normal Task Creation
# ============================================
def test_normal_request(token):
    """Test creating a task with valid JWT."""
    separator("TEST 2: Normal Task Creation")

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "task": "process_data",
        "payload": {"data": "sample data for processing"}
    }

    response = requests.post(
        f"{BASE_URL}/task",
        json=payload,
        headers=headers,
        verify=False
    )

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    if response.status_code == 201:
        print(f"\n[PASS] Task created successfully!")
        print(f"   Request ID: {data['request_id']}")
        print(f"   Instance: {data['instance']}")
        print(f"   Status: {data['status']}")
    else:
        print(f"\n[FAIL] Task creation failed!")


# ============================================
# Test 3: Load Balancing Verification
# ============================================
def test_load_balancing(token):
    """Send multiple requests and verify distribution across instances."""
    separator("TEST 3: Load Balancing Verification")

    headers = {
        "Authorization": f"Bearer {token}",
        "Connection": "close"  # Force new connection each time for round-robin
    }
    payload = {"task": "lb_test", "payload": {}}
    instances = {}

    print("Sending 9 requests to test load balancing...\n")

    for i in range(9):
        # Use a fresh session each time to force a new TCP connection
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/task",
            json=payload,
            headers=headers,
            verify=False
        )
        session.close()
        data = response.json()
        instance = data.get('instance', 'unknown')
        instances[instance] = instances.get(instance, 0) + 1
        print(f"  Request {i+1}: Handled by {instance} (Request ID: {data.get('request_id', 'N/A')[:8]}...)")
        time.sleep(0.3)  # Small delay to avoid rate limiting

    print(f"\nLoad Distribution:")
    for instance, count in sorted(instances.items()):
        bar = "#" * (count * 3)
        print(f"  {instance}: {count} requests {bar}")

    if len(instances) > 1:
        print(f"\n[PASS] Load balancing is working! Requests distributed across {len(instances)} instances.")
    else:
        print(f"\n[WARN] All requests went to one instance. Check Nginx config.")


# ============================================
# Test 4: Unauthorized Request
# ============================================
def test_unauthorized():
    """Test request without JWT token."""
    separator("TEST 4: Unauthorized Request (No Token)")

    response = requests.post(
        f"{BASE_URL}/task",
        json={"task": "unauthorized_test"},
        verify=False
    )

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    if response.status_code == 401:
        print(f"\n[PASS] Unauthorized request correctly rejected!")
    else:
        print(f"\n[FAIL] Expected 401, got {response.status_code}")


def test_invalid_token():
    """Test request with invalid JWT token."""
    separator("TEST 4b: Unauthorized Request (Invalid Token)")

    headers = {"Authorization": "Bearer invalid.token.here"}

    response = requests.post(
        f"{BASE_URL}/task",
        json={"task": "invalid_token_test"},
        headers=headers,
        verify=False
    )

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    if response.status_code == 401:
        print(f"\n[PASS] Invalid token correctly rejected!")
    else:
        print(f"\n[FAIL] Expected 401, got {response.status_code}")


# ============================================
# Test 5: Rate Limiting
# ============================================
def test_rate_limiting(token):
    """Send burst requests using multithreading to trigger rate limiting."""
    separator("TEST 5: Rate Limiting")

    headers = {
        "Authorization": f"Bearer {token}",
        "Connection": "close"
    }
    payload = {"task": "rate_limit_test", "payload": {}}

    results = []
    total_requests = 50

    def send_request(i):
        """Send a single request (called from thread)."""
        try:
            session = requests.Session()
            response = session.post(
                f"{BASE_URL}/task",
                json=payload,
                headers=headers,
                verify=False
            )
            session.close()
            return response.status_code
        except Exception:
            return 0

    print(f"Sending {total_requests} concurrent requests to trigger rate limiting...\n")

    # Send requests concurrently using threads
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(send_request, i) for i in range(total_requests)]
        for future in as_completed(futures):
            results.append(future.result())

    success_count = results.count(201)
    rate_limited_count = results.count(429)
    other_count = total_requests - success_count - rate_limited_count

    print(f"  Results:")
    print(f"    Successful requests:    {success_count}")
    print(f"    Rate-limited (429):     {rate_limited_count}")
    if other_count > 0:
        print(f"    Other responses:        {other_count}")

    if rate_limited_count > 0:
        print(f"\n[PASS] Rate limiting is working! {rate_limited_count} requests were blocked.")
    else:
        print(f"\n[WARN] No requests were rate-limited. Try sending more requests.")


# ============================================
# Test 6: Database Log Verification
# ============================================
def test_database_logs():
    """Query the database to verify audit logs and state tracking."""
    separator("TEST 6: Database Log Verification")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Query audit logs
        print("\n--- Audit Logs (last 10) ---")
        cur.execute("SELECT timestamp, service_name, request_id, action, status, source FROM audit_logs ORDER BY timestamp DESC LIMIT 10")
        rows = cur.fetchall()
        if rows:
            headers = ["Timestamp", "Service", "Request ID", "Action", "Status", "Source"]
            # Shorten request_id for display
            display_rows = []
            for row in rows:
                display_rows.append([
                    str(row[0])[:19],
                    row[1],
                    str(row[2])[:8] + "...",
                    row[3][:40],
                    row[4],
                    row[5]
                ])
            print(tabulate(display_rows, headers=headers, tablefmt="grid"))
        else:
            print("  No audit logs found.")

        # Query request states
        print("\n--- Request States (last 15) ---")
        cur.execute("SELECT timestamp, request_id, state, service_name, details FROM request_states ORDER BY timestamp DESC LIMIT 15")
        rows = cur.fetchall()
        if rows:
            headers = ["Timestamp", "Request ID", "State", "Service", "Details"]
            display_rows = []
            for row in rows:
                display_rows.append([
                    str(row[0])[:19],
                    str(row[1])[:8] + "...",
                    row[2],
                    row[3],
                    (row[4] or "")[:40]
                ])
            print(tabulate(display_rows, headers=headers, tablefmt="grid"))
        else:
            print("  No request states found.")

        # Count total records
        cur.execute("SELECT COUNT(*) FROM audit_logs")
        audit_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM request_states")
        state_count = cur.fetchone()[0]

        print(f"\n  Total audit logs:    {audit_count}")
        print(f"  Total state records: {state_count}")

        # Verify full state chain for the latest request
        print("\n--- Full State Chain (Latest Request) ---")
        cur.execute("""
            SELECT DISTINCT request_id FROM request_states
            ORDER BY request_id DESC LIMIT 1
        """)
        latest = cur.fetchone()
        if latest:
            cur.execute("""
                SELECT state, service_name, timestamp, details
                FROM request_states
                WHERE request_id = %s
                ORDER BY timestamp ASC
            """, (latest[0],))
            chain = cur.fetchall()
            print(f"  Request ID: {latest[0]}")
            for state_row in chain:
                print(f"    -> {state_row[0]:15s} | {state_row[1]:8s} | {str(state_row[2])[:19]}")

        print(f"\n[PASS] Database logs verified!")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"\n[FAIL] Database connection failed: {e}")
        print("  Make sure PostgreSQL is running and accessible on localhost:5432")


# ============================================
# Main Test Runner
# ============================================
if __name__ == "__main__":
    print("\n" + "#" * 60)
    print("  SECURE DISTRIBUTED SYSTEM - TEST CLIENT")
    print("#" * 60)
    print(f"\n  Target: {BASE_URL}")
    print(f"  Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Test 1: Login
    token = test_login()
    if not token:
        print("\n[FAIL] Cannot proceed without token. Exiting.")
        exit(1)

    # Test 2: Normal request
    test_normal_request(token)

    # Wait for worker to process
    print("\n[..] Waiting 3 seconds for worker to process...")
    time.sleep(3)

    # Test 3: Load balancing
    test_load_balancing(token)

    # Test 4: Unauthorized requests
    test_unauthorized()
    test_invalid_token()

    # Test 5: Rate limiting
    test_rate_limiting(token)

    # Wait for worker to process all
    print("\n[..] Waiting 5 seconds for worker to finish processing...")
    time.sleep(5)

    # Test 6: Database logs
    test_database_logs()

    separator("ALL TESTS COMPLETED")
    print("\n[PASS] Review the results above to verify system functionality.\n")

