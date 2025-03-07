#!/bin/bash
# This script deploys the BOSS monitoring service as a standalone service

# Print colored messages
print_info() {
    echo -e "\033[0;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[0;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[0;33m[WARNING]\033[0m $1"
}

# Default configuration
DATA_DIR="./monitoring_data"
HOST="0.0.0.0"
PORT=8080
LOG_FILE="monitoring.log"
SERVICE_NAME="boss_monitoring"
SYSTEMD_DIR="/etc/systemd/system"

# Process command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        --service-name)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --data-dir DIR      Data directory for monitoring data (default: ./monitoring_data)"
            echo "  --host HOST         Host to bind to (default: 0.0.0.0)"
            echo "  --port PORT         Port to listen on (default: 8080)"
            echo "  --log-file FILE     Log file path (default: monitoring.log)"
            echo "  --service-name NAME Name of the systemd service (default: boss_monitoring)"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if running as root (required for systemd service installation)
if [[ $EUID -ne 0 ]]; then
    print_warning "Not running as root. Systemd service installation may fail."
    print_warning "Consider re-running with sudo if you want to install as a service."
fi

# Get the absolute path of the project
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create data directory if it doesn't exist
print_info "Creating data directory: $DATA_DIR"
mkdir -p "$DATA_DIR"

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    print_error "Poetry is not installed. Please install it first."
    exit 1
fi

# Activate the virtual environment
print_info "Activating virtual environment"
source "$(poetry env info --path)/bin/activate"

# Create systemd service file
SYSTEMD_FILE="$SYSTEMD_DIR/$SERVICE_NAME.service"
print_info "Creating systemd service file: $SYSTEMD_FILE"

cat > "$SYSTEMD_FILE" << EOF
[Unit]
Description=BOSS Monitoring Service
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python -m boss.lighthouse.monitoring.start_monitoring --data-dir $DATA_DIR --host $HOST --port $PORT
Restart=on-failure
Environment=PYTHONPATH=$PROJECT_DIR

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd daemon
print_info "Reloading systemd daemon"
systemctl daemon-reload

# Enable and start the service
print_info "Enabling and starting $SERVICE_NAME service"
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

# Check service status
if systemctl is-active --quiet "$SERVICE_NAME"; then
    print_success "Monitoring service deployed successfully!"
    print_info "Service is running at http://$HOST:$PORT"
    print_info "To check service status: systemctl status $SERVICE_NAME"
    print_info "To view logs: journalctl -u $SERVICE_NAME -f"
    print_info "To stop service: systemctl stop $SERVICE_NAME"
else
    print_error "Failed to start the monitoring service."
    print_info "Check logs with: journalctl -u $SERVICE_NAME -e"
fi

exit 0 