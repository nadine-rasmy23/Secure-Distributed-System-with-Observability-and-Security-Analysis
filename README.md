# 🔐 Secure Distributed System with Observability and Security Analysis

A fully containerized secure distributed system demonstrating load balancing, HTTPS communication, JWT authentication, asynchronous processing via RabbitMQ, rate limiting, persistent audit logging, full request state tracking, and Man-in-the-Middle (MITM) attack simulation.

---

## 📐 System Architecture

```
                          ┌──────────┐
                          │  Client  │
                          └────┬─────┘
                               │
                    HTTPS (Port 443)
                               │
                  ┌────────────▼────────────┐
                  │         Nginx           │
                  │  • HTTPS Termination    │
                  │  • Load Balancing       │
                  │  • Rate Limiting        │
                  │  • HTTP → HTTPS Redirect│
                  └────┬──────┬──────┬──────┘
                       │      │      │
              ┌────────▼┐ ┌───▼───┐ ┌▼────────┐
              │  API 1  │ │ API 2 │ │  API 3  │
              │ :5000   │ │ :5000 │ │  :5000  │
              └────┬────┘ └───┬───┘ └────┬────┘
                   │          │          │
                   │   JWT Validation    │
                   │   UUID Generation   │
                   │   Audit Logging     │
                   │          │          │
                   └──────────┼──────────┘
                              │
                    ┌─────────▼─────────┐
                    │     RabbitMQ      │
                    │   Message Broker  │
                    │   (task_queue)    │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │      Worker       │
                    │  • Consume Tasks  │
                    │  • Validate Source │
                    │  • Process Tasks  │
                    │  • Audit Logging  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │    PostgreSQL     │
                    │  • Audit Logs    │
                    │  • State Tracking│
                    └──────────────────┘
```

---

## 🧩 System Components

### 1. Nginx (Gateway Layer)
- **Reverse Proxy**: Routes client requests to backend API instances
- **Load Balancing**: Round-robin distribution across 3 API instances
- **Rate Limiting**: 5 requests/second per client IP with burst allowance of 10
- **HTTPS**: TLS 1.2/1.3 encryption with self-signed certificate
- **HTTP Redirect**: Automatically redirects HTTP (port 80) to HTTPS (port 443)

### 2. API Service (Flask/Python)
- **Endpoint**: `POST /task` — Create and queue a new task
- **Endpoint**: `POST /login` — Authenticate and receive JWT token
- **Endpoint**: `GET /health` — Health check
- **JWT Authentication**: Validates Bearer token on protected endpoints
- **UUID Tracking**: Generates unique Request ID for each incoming request
- **Audit Logging**: Logs all events and state transitions to PostgreSQL
- **RabbitMQ Publishing**: Sends tasks to the message broker queue

### 3. Multiple API Instances
Three independent instances (`api1`, `api2`, `api3`) run simultaneously:
- Each handles requests independently
- Each identifies itself in the response via `instance` field
- Nginx distributes traffic evenly across all three

### 4. RabbitMQ (Message Broker)
- Receives task messages from API instances
- Stores them in a durable queue (`task_queue`)
- Delivers them to the Worker service for processing
- Management UI available on port `15672`

### 5. Worker Service
- Consumes messages from the `task_queue`
- **Service Identity Validation**: Verifies tasks originate from legitimate API instances (`api1`, `api2`, `api3`)
- Processes tasks (simulated 2-second processing)
- Logs `CONSUMED` and `PROCESSED` (or `FAILED`) states to the database

### 6. PostgreSQL Database
- Runs as a separate Docker container
- Stores all **audit logs** (who did what, when, and the result)
- Stores all **request state transitions** with timestamps

---

## 📊 Database Schema

### `audit_logs` Table
| Column       | Type         | Description                          |
|-------------|-------------|--------------------------------------|
| id          | SERIAL (PK) | Auto-incremented primary key         |
| timestamp   | TIMESTAMPTZ | When the event occurred              |
| service_name| VARCHAR(50) | Service that logged the event        |
| request_id  | UUID        | Unique request identifier            |
| action      | VARCHAR(255)| Description of the action performed  |
| status      | VARCHAR(20) | `success` or `failure`               |
| source      | VARCHAR(50) | Origin (e.g., `client`, `api1`)      |

### `request_states` Table
| Column       | Type         | Description                          |
|-------------|-------------|--------------------------------------|
| id          | SERIAL (PK) | Auto-incremented primary key         |
| request_id  | UUID        | Unique request identifier            |
| state       | VARCHAR(20) | Current state of the request         |
| service_name| VARCHAR(50) | Service that set this state          |
| timestamp   | TIMESTAMPTZ | When the state was set               |
| details     | TEXT        | Additional context                   |

### Request States
| State          | Set By  | Description                        |
|---------------|---------|-------------------------------------|
| `RECEIVED`      | API     | Request received from client        |
| `AUTHENTICATED` | API     | JWT token validated successfully    |
| `QUEUED`        | API     | Task published to RabbitMQ          |
| `CONSUMED`      | Worker  | Task consumed from queue            |
| `PROCESSED`     | Worker  | Task processed successfully         |
| `FAILED`        | Any     | An error occurred at any step       |

---

## 🔄 Functional Flow

```
 1. Client sends HTTPS POST /task (with JWT Bearer token)
 2. Nginx receives request and forwards to one API instance (round-robin)
 3. API validates the JWT token
 4. API generates a unique Request ID (UUID)
 5. API logs RECEIVED and AUTHENTICATED states → Database
 6. API publishes task to RabbitMQ
 7. API logs QUEUED state → Database
 8. Worker consumes task from RabbitMQ
 9. Worker validates source service identity
10. Worker logs CONSUMED state → Database
11. Worker processes the task
12. Worker logs PROCESSED state → Database
```

---

## 📁 Project Structure

```
secure-distributed-system/
├── .gitignore
├── README.md
├── docker-compose.yml              # Primary: HTTPS mode
├── docker-compose.http.yml         # Override: HTTP mode (for MITM demo)
│
├── nginx/
│   ├── nginx.conf                  # HTTPS + Load Balancing + Rate Limiting
│   ├── nginx.http.conf             # HTTP only (for Wireshark capture)
│   └── certs/
│       ├── server.crt              # Self-signed SSL certificate
│       └── server.key              # Private key
│
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                      # Flask API service
│
├── worker/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── worker.py                   # RabbitMQ consumer & processor
│
├── db/
│   └── init.sql                    # PostgreSQL schema
│
├── client/
│   ├── requirements.txt
│   └── test_client.py              # Automated test script
│
└── report/
    └── report.md                   # Assignment report template
```

---

## 🛠️ Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Docker Compose)
- [Python 3.x](https://www.python.org/downloads/) (for running the test client)
- [OpenSSL](https://www.openssl.org/) (for generating SSL certificates)
- [Wireshark](https://www.wireshark.org/) (for MITM attack demonstration)

---

## 🚀 Getting Started

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/secure-distributed-system.git
cd secure-distributed-system
```

### Step 2: Generate SSL Certificates

```bash
cd nginx/certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout server.key -out server.crt \
  -subj "/CN=localhost"
cd ../..
```

### Step 3: Start the System (HTTPS Mode)

```bash
docker-compose up --build -d
```

Wait for all 8 containers to be running:

```bash
docker-compose ps
```

Expected output:
| Container       | Status  | Ports                    |
|----------------|---------|--------------------------|
| nginx_gateway  | Running | 0.0.0.0:80→80, 0.0.0.0:443→443 |
| api1           | Running | 5000 (internal)          |
| api2           | Running | 5000 (internal)          |
| api3           | Running | 5000 (internal)          |
| rabbitmq       | Running | 5672, 15672              |
| worker         | Running | —                        |
| audit_db       | Running | 5432                     |

### Step 4: Install Test Client Dependencies

```bash
cd client
pip install -r requirements.txt
```

### Step 5: Run the Tests

```bash
python test_client.py
```

---

## 🧪 Testing

The test client (`client/test_client.py`) automatically runs 6 test scenarios:

| Test | Description | Expected Result |
|------|------------|-----------------|
| **Test 1** | Login & JWT Token | ✅ Returns valid JWT token |
| **Test 2** | Normal Task Creation | ✅ Task created with unique Request ID |
| **Test 3** | Load Balancing | ✅ Requests distributed across api1, api2, api3 |
| **Test 4** | Unauthorized Request (no token) | ✅ Returns 401 Unauthorized |
| **Test 4b** | Invalid Token | ✅ Returns 401 Unauthorized |
| **Test 5** | Rate Limiting | ✅ Returns 429 Too Many Requests |
| **Test 6** | Database Logs | ✅ Audit logs and state transitions stored |

### Manual API Testing with curl

**Login:**
```bash
curl -k -X POST https://localhost/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**Create Task (replace `<TOKEN>` with the token from login):**
```bash
curl -k -X POST https://localhost/task \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"task":"process_data","payload":{"key":"value"}}'
```

**Unauthorized Request:**
```bash
curl -k -X POST https://localhost/task \
  -H "Content-Type: application/json" \
  -d '{"task":"test"}'
```

### Valid Test Credentials

| Username | Password  |
|----------|-----------|
| admin    | admin123  |
| user     | user123   |
| test     | test123   |

---

## 🔍 Monitoring & Verification

### RabbitMQ Management UI
- **URL**: http://localhost:15672
- **Username**: `guest`
- **Password**: `guest`

### Database Queries

```bash
# View audit logs
docker exec -it audit_db psql -U postgres -d audit_db \
  -c "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10;"

# View request states
docker exec -it audit_db psql -U postgres -d audit_db \
  -c "SELECT * FROM request_states ORDER BY timestamp DESC LIMIT 10;"

# View full state chain for a specific request
docker exec -it audit_db psql -U postgres -d audit_db \
  -c "SELECT state, service_name, timestamp, details FROM request_states WHERE request_id = '<REQUEST_ID>' ORDER BY timestamp;"
```

### View Container Logs

```bash
docker-compose logs api1 api2 api3    # API instance logs
docker-compose logs worker            # Worker logs
docker-compose logs nginx             # Nginx logs
```

---

## 🕵️ MITM Attack Simulation (Wireshark)

### Step 1: HTTP Mode (Traffic Exposed)

Switch the system to HTTP (unencrypted) mode:

```bash
docker-compose down
docker-compose -f docker-compose.yml -f docker-compose.http.yml up -d
```

In `client/test_client.py`, change line 28 to:
```python
BASE_URL = HTTP_BASE_URL
```

**Wireshark Setup:**
1. Open Wireshark → Capture on `Adapter for loopback traffic capture`
2. Apply filter: `http`
3. Run: `python test_client.py`

**What you will see:**
- ✅ HTTP requests in plain text (`POST /task`, `POST /login`)
- ✅ JWT token visible in `Authorization` header
- ✅ JSON payload fully readable
- ⚠️ **This proves that HTTP is vulnerable to MITM attacks**

### Step 2: HTTPS Mode (Traffic Encrypted)

Switch back to HTTPS (encrypted) mode:

```bash
docker-compose down
docker-compose up -d
```

In `client/test_client.py`, change line 28 back to:
```python
BASE_URL = HTTPS_BASE_URL
```

**Wireshark Setup:**
1. Open Wireshark → Capture on `Adapter for loopback traffic capture`
2. Apply filter: `tcp.port == 443`
3. Run: `python test_client.py`

**What you will see:**
- ✅ TLS Handshake (`Client Hello`, `Server Hello`)
- ✅ Encrypted `Application Data` packets
- ✅ No readable payload, headers, or JWT tokens
- 🔒 **This proves that HTTPS protects against MITM attacks**

### Comparison Summary

| Aspect           | HTTP Mode          | HTTPS Mode          |
|-----------------|-------------------|---------------------|
| Request Headers | Visible in plain text | Encrypted          |
| JWT Token       | Fully exposed      | Not visible         |
| Request Payload | Readable JSON      | Encrypted data      |
| MITM Attack Risk| **HIGH** ⚠️        | **LOW** 🔒          |

---

## 🛑 Stopping the System

```bash
docker-compose down
```

To also remove stored data (database volumes):

```bash
docker-compose down -v
```

---

## ⚙️ Technology Stack

| Component     | Technology                |
|--------------|--------------------------|
| Gateway      | Nginx (Alpine)           |
| API Service  | Python 3.11 / Flask      |
| Auth         | JWT (PyJWT)              |
| Message Broker | RabbitMQ 3 (Management)|
| Worker       | Python 3.11              |
| Database     | PostgreSQL 15 (Alpine)   |
| Container    | Docker / Docker Compose  |

---

## 📜 License

This project was developed as an academic assignment for the **Security of Distributed Systems** course.
