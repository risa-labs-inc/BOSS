# Monitoring Service Deployment Guide

This document provides instructions for deploying the BOSS Monitoring Service as a standalone service. The monitoring service provides real-time monitoring of system health, performance metrics, component status, and alerting capabilities.

## Prerequisites

- Linux system with systemd (for service deployment)
- Python 3.10 or higher
- Poetry package manager
- Sudo access (for systemd service installation)

## Deployment Options

The monitoring service can be deployed in several ways:

1. **As a systemd service** - For production environments
2. **As a standalone process** - For development or testing
3. **As a Docker container** - For containerized environments

## Using the Deployment Script

The easiest way to deploy the monitoring service is to use the provided deployment script:

```bash
sudo ./scripts/deploy_monitoring_service.sh
```

### Configuration Options

The deployment script accepts several command-line options:

| Option | Description | Default |
|--------|-------------|---------|
| `--data-dir DIR` | Data directory for monitoring data | `./monitoring_data` |
| `--host HOST` | Host to bind to | `0.0.0.0` |
| `--port PORT` | Port to listen on | `8080` |
| `--log-file FILE` | Log file path | `monitoring.log` |
| `--service-name NAME` | Name of the systemd service | `boss_monitoring` |

Example with custom configuration:

```bash
sudo ./scripts/deploy_monitoring_service.sh \
    --data-dir /var/lib/boss/monitoring \
    --host 127.0.0.1 \
    --port 9090 \
    --log-file /var/log/boss/monitoring.log \
    --service-name boss_monitoring_prod
```

## Manual Deployment

### As a systemd service

1. Create a systemd service file:

```bash
sudo nano /etc/systemd/system/boss_monitoring.service
```

2. Add the following content (adjust paths as needed):

```ini
[Unit]
Description=BOSS Monitoring Service
After=network.target

[Service]
User=boss
WorkingDirectory=/path/to/boss
ExecStart=/path/to/boss/.venv/bin/python -m boss.lighthouse.monitoring.start_monitoring \
    --data-dir /var/lib/boss/monitoring \
    --host 0.0.0.0 \
    --port 8080
Restart=on-failure
Environment=PYTHONPATH=/path/to/boss

[Install]
WantedBy=multi-user.target
```

3. Reload systemd daemon:

```bash
sudo systemctl daemon-reload
```

4. Enable and start the service:

```bash
sudo systemctl enable boss_monitoring
sudo systemctl start boss_monitoring
```

5. Check service status:

```bash
sudo systemctl status boss_monitoring
```

### As a standalone process

You can run the monitoring service as a standalone process:

```bash
python -m boss.lighthouse.monitoring.start_monitoring \
    --data-dir ./monitoring_data \
    --host 0.0.0.0 \
    --port 8080
```

For production use, consider using a process manager like `supervisor` or `pm2` to ensure the service stays running.

### As a Docker container

A Dockerfile is provided in the `deployment/docker` directory. There are two ways to deploy the monitoring service using Docker:

#### Option 1: Using Docker Compose (Recommended)

1. Navigate to the deployment directory:

```bash
cd deployment/docker
```

2. Start the service using Docker Compose:

```bash
docker-compose up -d
```

This will build the image and start the container with all the necessary configurations.

3. View logs:

```bash
docker-compose logs -f
```

4. Stop the service:

```bash
docker-compose down
```

#### Option 2: Using Docker directly

1. Build the Docker image:

```bash
docker build -t boss-monitoring -f deployment/docker/monitoring.Dockerfile .
```

2. Run the container:

```bash
docker run -d \
    -p 8080:8080 \
    -v boss_monitoring_data:/app/monitoring_data \
    --name boss-monitoring \
    boss-monitoring
```

3. View logs:

```bash
docker logs -f boss-monitoring
```

4. Stop the container:

```bash
docker stop boss-monitoring
docker rm boss-monitoring
```

## Service Management

### Viewing logs

For systemd service:

```bash
journalctl -u boss_monitoring -f
```

For standalone process:
Logs will be written to the specified log file (default: monitoring.log)

### Stopping the service

For systemd service:

```bash
sudo systemctl stop boss_monitoring
```

For Docker:

```bash
docker stop boss-monitoring
```

### Updating the service

1. Pull the latest code
2. Restart the service:

```bash
sudo systemctl restart boss_monitoring
```

## API Access

Once deployed, the monitoring API will be available at:

```
http://{host}:{port}/
```

For API documentation, visit:

```
http://{host}:{port}/docs
```

## Monitoring the monitoring service

It's often useful to monitor the monitoring service itself. For high-availability setups, consider:

1. Setting up a health check endpoint monitor
2. Configuring alerts for the monitoring service
3. Setting up a failover instance

## Troubleshooting

### Service fails to start

Check the logs for more information:

```bash
journalctl -u boss_monitoring -e
```

Common issues include:
- Incorrect paths in the service file
- Port already in use
- Insufficient permissions
- Missing dependencies

### API is not accessible

- Verify the service is running: `systemctl status boss_monitoring`
- Check if the port is open: `ss -tuln | grep 8080`
- Ensure firewall rules allow access to the port

## Security Considerations

- The monitoring service provides access to sensitive system information
- Consider running behind a reverse proxy with authentication
- Use HTTPS for production deployments
- Limit access to the API to trusted networks
- Use a dedicated user account with minimal privileges for the service 