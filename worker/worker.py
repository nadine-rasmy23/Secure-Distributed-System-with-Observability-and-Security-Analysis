import os
import json
import time
import logging
import pika
import psycopg2

# ============================================
# Configuration
# ============================================
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "guest")
DB_HOST = os.environ.get("DB_HOST", "db")
DB_NAME = os.environ.get("DB_NAME", "audit_db")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "postgres")
QUEUE_NAME = "task_queue"
SERVICE_NAME = "worker"

# Valid API sources that can send tasks
VALID_SOURCES = ["api1", "api2", "api3"]

logging.basicConfig(level=logging.INFO,
                    format=f'[{SERVICE_NAME}] %(asctime)s - %(levelname)s - %(message)s')
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
# Task Processing
# ============================================
def validate_source(message):
    """Validate that the message came from a legitimate API instance."""
    source_api = message.get("source_api", "")
    if source_api not in VALID_SOURCES:
        raise ValueError(f"Invalid source: '{source_api}'. Expected one of {VALID_SOURCES}")
    return True


def process_task(task_data):
    """
    Simulate task processing.
    In a real system, this would perform actual work.
    """
    logger.info(f"Processing task: {task_data.get('task', 'unknown')}")
    # Simulate processing time (2 seconds)
    time.sleep(2)
    logger.info(f"Task processing complete for request_id: {task_data.get('request_id')}")
    return True


# ============================================
# RabbitMQ Consumer Callback
# ============================================
def callback(ch, method, properties, body):
    """Process incoming messages from RabbitMQ."""
    try:
        message = json.loads(body)
        request_id = message.get("request_id", "unknown")
        logger.info(f"Received message: request_id={request_id}")

        # ---- State: CONSUMED ----
        log_state(request_id, "CONSUMED", SERVICE_NAME, "Task consumed from RabbitMQ")
        log_audit(SERVICE_NAME, request_id, "Task consumed from queue", "success", SERVICE_NAME)

        # Validate source (service identity validation)
        try:
            validate_source(message)
            logger.info(f"Source validated: {message.get('source_api')}")
        except ValueError as e:
            log_state(request_id, "FAILED", SERVICE_NAME, str(e))
            log_audit(SERVICE_NAME, request_id, f"Source validation failed: {e}", "failure", SERVICE_NAME)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Process the task
        try:
            process_task(message)

            # ---- State: PROCESSED ----
            log_state(request_id, "PROCESSED", SERVICE_NAME,
                      f"Task '{message.get('task')}' processed successfully")
            log_audit(SERVICE_NAME, request_id, "Task processed successfully", "success", SERVICE_NAME)

        except Exception as e:
            # ---- State: FAILED ----
            log_state(request_id, "FAILED", SERVICE_NAME, f"Processing failed: {str(e)}")
            log_audit(SERVICE_NAME, request_id, f"Task processing failed: {e}", "failure", SERVICE_NAME)

        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode message: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


# ============================================
# Main: Connect to RabbitMQ and Start Consuming
# ============================================
def main():
    """Main function to start the worker."""
    logger.info("Worker starting...")

    # Wait for RabbitMQ to be ready
    while True:
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                credentials=credentials,
                heartbeat=600,
                connection_attempts=5,
                retry_delay=5
            )
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            logger.info("Connected to RabbitMQ")
            break
        except pika.exceptions.AMQPConnectionError:
            logger.warning("RabbitMQ not ready, retrying in 5 seconds...")
            time.sleep(5)

    # Declare the queue
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    # Fair dispatch: worker processes one message at a time
    channel.basic_qos(prefetch_count=1)

    # Start consuming
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

    logger.info(f"Worker is waiting for messages on queue '{QUEUE_NAME}'...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == '__main__':
    main()
