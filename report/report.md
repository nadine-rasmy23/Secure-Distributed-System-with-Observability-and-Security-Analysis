# Secure Distributed System - Report

## 1. Introduction

This project implements a secure distributed system that demonstrates key concepts in distributed systems security, including load balancing, encrypted communication, authentication, asynchronous processing, rate limiting, and comprehensive audit logging.

## 2. System Architecture

The system consists of the following components:

- **Nginx Gateway**: Acts as a reverse proxy with HTTPS termination, load balancing (round-robin) across 3 API instances, and rate limiting (5 requests/second per IP).
- **API Service (3 instances)**: Flask-based REST API that handles authentication via JWT tokens, generates unique Request IDs (UUID), and publishes tasks to RabbitMQ.
- **RabbitMQ**: Message broker that queues tasks for asynchronous processing by the worker service.
- **Worker Service**: Consumes tasks from RabbitMQ, validates the source service identity, processes tasks, and logs all state transitions.
- **PostgreSQL Database**: Stores all audit logs and request state transitions with timestamps.

All components run as Docker containers orchestrated by Docker Compose.

## 3. Security Features

### 3.1 HTTPS Communication
- Nginx terminates SSL using a self-signed certificate
- All client-to-server traffic is encrypted with TLS 1.2/1.3
- HTTP traffic is automatically redirected to HTTPS

### 3.2 JWT Authentication
- Users must authenticate via `/login` endpoint to obtain a JWT token
- All `/task` requests require a valid Bearer token in the Authorization header
- Tokens expire after 1 hour
- Invalid or missing tokens return 401 Unauthorized

### 3.3 Rate Limiting
- Nginx enforces rate limiting at 5 requests/second per client IP
- Burst allowance of 10 requests
- Exceeded limits return 429 Too Many Requests

### 3.4 Service Identity Validation
- Worker validates that tasks originate from legitimate API instances (api1, api2, api3)
- Invalid source identifiers cause task rejection

## 4. Audit Logging & State Tracking

### 4.1 Audit Log Fields
Each audit entry records: Timestamp, Service Name, Request ID, Action, Status (success/failure), Source.

### 4.2 State Transitions
Each request follows these states:
1. **RECEIVED** - API receives the client request
2. **AUTHENTICATED** - JWT token validated successfully
3. **QUEUED** - Task published to RabbitMQ
4. **CONSUMED** - Worker picks up the task
5. **PROCESSED** - Task processed successfully
6. **FAILED** - Any step that encountered an error

## 5. MITM Attack Analysis

### 5.1 HTTP Mode (Vulnerable)
When HTTPS is disabled:
- Wireshark can capture all HTTP traffic in plain text
- JWT tokens are visible in request headers
- Request payloads (JSON data) are fully readable
- An attacker can intercept and read all communication

### 5.2 HTTPS Mode (Secure)
When HTTPS is enabled:
- Wireshark only captures encrypted TLS packets
- No readable payload or headers
- JWT tokens are protected
- Man-in-the-Middle attacks cannot read the data

### 5.3 Comparison

| Aspect           | HTTP Mode         | HTTPS Mode        |
|------------------|-------------------|-------------------|
| Headers          | Visible           | Encrypted         |
| JWT Token        | Exposed           | Protected         |
| Payload          | Readable          | Encrypted         |
| MITM Risk        | High              | Low               |

## 6. Testing Results

### 6.1 Functional Tests
- ✅ Login and JWT token generation
- ✅ Task creation with valid JWT
- ✅ Load balancing across 3 API instances
- ✅ Unauthorized request rejection (401)
- ✅ Rate limiting enforcement (429)
- ✅ Message flow through RabbitMQ
- ✅ Database audit log storage
- ✅ Complete state chain tracking

## 7. Screenshots

*(Insert screenshots here)*

### 7.1 Load Balancing
*(Screenshot showing requests distributed across api1, api2, api3)*

### 7.2 RabbitMQ Management
*(Screenshot of RabbitMQ showing task_queue activity)*

### 7.3 Database Logs
*(Screenshot of audit_logs and request_states tables)*

### 7.4 Wireshark - HTTP Mode
*(Screenshot showing visible JWT token and payload)*

### 7.5 Wireshark - HTTPS Mode
*(Screenshot showing encrypted TLS packets)*

## 8. Conclusion

This project successfully implements a secure distributed system with all required components. The MITM analysis clearly demonstrates the importance of HTTPS in protecting sensitive data. The comprehensive audit logging provides full observability across all services, and state tracking ensures every request can be traced through the entire system.
