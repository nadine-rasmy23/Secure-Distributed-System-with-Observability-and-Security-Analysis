import os
import uuid
import json
import time
import logging
import jwt
import pika
import psycopg2
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, request, jsonify

# ============================================
# Configuration
# ============================================
app = Flask(__name__)

API_INSTANCE = os.environ.get("API_INSTANCE", "api_unknown")
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-for-jwt-2024")
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "guest")
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "audit_db")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "postgres")
QUEUE_NAME = "task_queue"

logging.basicConfig(level=logging.INFO,
                    format=f'[{API_INSTANCE}] %(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================
# Database Helper
# ============================================
def get_db_connection():
    """Create a new database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )


def log_audit(service_name, request_id, action, status, source):
    """Insert an entry into the audit_logs table."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO audit_logs (service_name, request_id, action, status, source)
               VALUES (%s, %s, %s, %s, %s)""",
            (service_name, request_id, action, status, source)
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Audit log: {action} - {status} [request_id={request_id}]")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


def log_state(request_id, state, service_name, details=None):
    """Insert an entry into the request_states table."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO request_states (request_id, state, service_name, details)
               VALUES (%s, %s, %s, %s)""",
            (request_id, state, service_name, details)
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"State: {state} [request_id={request_id}]")
    except Exception as e:
        logger.error(f"Failed to write state log: {e}")


# ============================================
# RabbitMQ Helper
# ============================================
def get_rabbitmq_connection():
    """Create a new RabbitMQ connection with retry logic."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        credentials=credentials,
        heartbeat=600,
        connection_attempts=5,
        retry_delay=5
    )
    return pika.BlockingConnection(parameters)


def publish_to_queue(message):
    """Publish a message to the task queue."""
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_publish(
        exchange='',
        routing_key=QUEUE_NAME,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2)  # persistent message
    )
    connection.close()


# ============================================
# JWT Authentication Decorator
# ============================================
def token_required(f):
    """Decorator to validate JWT token from the Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')

        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({
                "error": "Token is missing",
                "message": "Authorization header with Bearer token is required"
            }), 401

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            request.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({
                "error": "Token expired",
                "message": "Please login again to get a new token"
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "error": "Invalid token",
                "message": "The provided token is not valid"
            }), 401

        return f(*args, **kwargs)
    return decorated


# ============================================
# Routes
# ============================================
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "instance": API_INSTANCE,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


@app.route('/login', methods=['POST'])
def login():
    """
    Login endpoint to generate JWT tokens.
    Accepts JSON body: {"username": "...", "password": "..."}
    For demo purposes, accepts any username/password.
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Username and password are required"}), 400

    # For demo: accept predefined credentials
    valid_users = {
        "admin": "admin123",
        "user": "user123",
        "test": "test123"
    }

    username = data['username']
    password = data['password']

    if username not in valid_users or valid_users[username] != password:
        return jsonify({"error": "Invalid credentials"}), 401

    # Generate JWT token
    token = jwt.encode(
        {
            "user": username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc)
        },
        JWT_SECRET,
        algorithm="HS256"
    )

    logger.info(f"User '{username}' logged in successfully via {API_INSTANCE}")

    return jsonify({
        "token": token,
        "instance": API_INSTANCE,
        "message": "Login successful"
    }), 200


@app.route('/task', methods=['POST'])
@token_required
def create_task():
    """
    Main task endpoint.
    Validates JWT, generates request ID, logs states, and publishes to RabbitMQ.
    """
    request_id = str(uuid.uuid4())
    user = request.user.get('user', 'unknown')

    try:
        # ---- State: RECEIVED ----
        log_state(request_id, "RECEIVED", API_INSTANCE, f"Request received from user '{user}'")
        log_audit(API_INSTANCE, request_id, "Request received", "success", "client")

        # ---- State: AUTHENTICATED ----
        log_state(request_id, "AUTHENTICATED", API_INSTANCE, f"JWT validated for user '{user}'")
        log_audit(API_INSTANCE, request_id, "JWT authentication", "success", API_INSTANCE)

        # Get task data from request body
        data = request.get_json() or {}
        task_data = data.get('task', 'default_task')
        task_payload = data.get('payload', {})

        # Prepare message for RabbitMQ
        message = {
            "request_id": request_id,
            "task": task_data,
            "payload": task_payload,
            "user": user,
            "source_api": API_INSTANCE,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Publish to RabbitMQ
        publish_to_queue(message)

        # ---- State: QUEUED ----
        log_state(request_id, "QUEUED", API_INSTANCE, "Task published to RabbitMQ")
        log_audit(API_INSTANCE, request_id, "Task queued to RabbitMQ", "success", API_INSTANCE)

        logger.info(f"Task created: request_id={request_id}, task={task_data}")

        return jsonify({
            "message": "Task created successfully",
            "request_id": request_id,
            "instance": API_INSTANCE,
            "task": task_data,
            "status": "QUEUED"
        }), 201

    except Exception as e:
        # ---- State: FAILED ----
        log_state(request_id, "FAILED", API_INSTANCE, str(e))
        log_audit(API_INSTANCE, request_id, f"Task creation failed: {str(e)}", "failure", API_INSTANCE)
        logger.error(f"Error creating task: {e}")

        return jsonify({
            "error": "Task creation failed",
            "request_id": request_id,
            "instance": API_INSTANCE,
            "details": str(e)
        }), 500


# ============================================
# Application Entry Point
# ============================================
if __name__ == '__main__':
    logger.info(f"Starting {API_INSTANCE} on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)
