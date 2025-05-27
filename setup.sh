#!/bin/bash

# CoreSecFrame Setup Script - Simplified Version
# Supports local installation and Docker deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Global variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"
DOCKER_DIR="$SCRIPT_DIR/docker"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Docker configuration variables
DOCKER_CONTAINER_NAME="coresecframe-app"
docker_cpus=""
docker_memory=""
docker_storage_gb=""
docker_web_port=""

# Utility functions
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_header() {
    echo -e "${PURPLE}$1${NC}"
}

# Banner function
show_banner() {
    clear
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    🚀 CoreSecFrame Setup                     ║"
    echo "║              Cybersecurity Framework Installer               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo
}

# Function to check system requirements
check_requirements() {
    print_header "=== System Requirements Check ==="
    
    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    python_version=$(python3 --version | cut -d' ' -f2)
    print_success "Python $python_version found"
    
    # Check pip
    if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
        print_error "pip is required but not installed"
        exit 1
    fi
    print_success "pip found"
    
    # Check git
    if ! command -v git &> /dev/null; then
        print_warning "git not found - some features may be limited"
    else
        print_success "git found"
    fi
    
    # Check if requirements.txt exists
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found in current directory"
        exit 1
    fi
    print_success "requirements.txt found"
    
    echo
}

# Function to check Docker requirements
check_docker_requirements() {
    print_header "=== Docker Requirements Check ==="
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        print_status "Please install Docker first:"
        echo "  Ubuntu/Debian: sudo apt-get install docker.io"
        echo "  RHEL/CentOS: sudo yum install docker"
        echo "  Fedora: sudo dnf install docker"
        exit 1
    fi
    print_success "Docker found"
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed"
        print_status "Please install Docker Compose"
        exit 1
    fi
    print_success "Docker Compose found"
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        print_status "Please start Docker daemon:"
        echo "  sudo systemctl start docker"
        exit 1
    fi
    print_success "Docker daemon is running"
    
    # Check if user can run Docker commands
    if ! docker ps &> /dev/null; then
        print_warning "Current user cannot run Docker commands"
        print_status "You may need to add your user to the docker group:"
        echo "  sudo usermod -aG docker $USER"
        echo "  Then log out and log back in"
    else
        print_success "Docker permissions OK"
    fi
    
    echo
}

# Function to get Docker configuration
get_docker_config() {
    print_header "=== Docker Configuration ==="
    
    # Get container name
    read -p "Enter container name (default: coresecframe-app): " container_name
    DOCKER_CONTAINER_NAME=${container_name:-coresecframe-app}
    
    # Get CPU configuration
    echo
    print_status "CPU Configuration:"
    echo "Available CPU cores: $(nproc)"
    read -p "Enter number of CPU cores to allocate (default: 2): " cpu_cores
    docker_cpus=${cpu_cores:-2}
    
    # Validate CPU cores
    if ! [[ "$docker_cpus" =~ ^[0-9]+$ ]] || [ "$docker_cpus" -lt 1 ] || [ "$docker_cpus" -gt "$(nproc)" ]; then
        print_warning "Invalid CPU cores. Using default: 2"
        docker_cpus=2
    fi
    
    # Get memory configuration
    echo
    print_status "Memory Configuration:"
    available_memory=$(free -g | awk '/^Mem:/{print $2}')
    echo "Available memory: ${available_memory}GB"
    read -p "Enter memory limit in GB (default: 4): " memory_gb
    memory_gb=${memory_gb:-4}
    
    # Validate memory
    if ! [[ "$memory_gb" =~ ^[0-9]+$ ]] || [ "$memory_gb" -lt 1 ]; then
        print_warning "Invalid memory size. Using default: 4GB"
        memory_gb=4
    fi
    docker_memory="${memory_gb}G"
    
    # Get storage configuration
    echo
    print_status "Storage Configuration:"
    available_storage=$(df -BG "$SCRIPT_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
    echo "Available storage: ${available_storage}GB"
    read -p "Enter storage limit in GB (default: 20): " storage_gb
    docker_storage_gb=${storage_gb:-20}
    
    # Validate storage
    if ! [[ "$docker_storage_gb" =~ ^[0-9]+$ ]] || [ "$docker_storage_gb" -lt 5 ]; then
        print_warning "Invalid storage size. Using default: 20GB"
        docker_storage_gb=20
    fi
    
    # Get port configuration
    echo
    print_status "Port Configuration:"
    read -p "Enter web interface port (default: 5000): " web_port
    docker_web_port=${web_port:-5000}
    
    # Validate web port
    if ! [[ "$docker_web_port" =~ ^[0-9]+$ ]] || [ "$docker_web_port" -lt 1024 ] || [ "$docker_web_port" -gt 65535 ]; then
        print_warning "Invalid port. Using default: 5000"
        docker_web_port=5000
    fi
    
    # Check if port is available
    if netstat -tuln 2>/dev/null | grep -q ":${docker_web_port} "; then
        print_warning "Port ${docker_web_port} appears to be in use"
        read -p "Continue anyway? (y/N): " continue_port
        if [[ ! $continue_port =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi
    
    # Summary
    echo
    print_header "=== Configuration Summary ==="
    echo -e "${WHITE}Container Name:${NC} $DOCKER_CONTAINER_NAME"
    echo -e "${WHITE}CPU Cores:${NC} $docker_cpus"
    echo -e "${WHITE}Memory:${NC} $docker_memory"
    echo -e "${WHITE}Storage Limit:${NC} ${docker_storage_gb}GB"
    echo -e "${WHITE}Web Port:${NC} $docker_web_port"
    echo -e "${WHITE}Base Image:${NC} Python 3.13 Slim"
    echo
    
    read -p "Proceed with this configuration? (Y/n): " confirm
    if [[ $confirm =~ ^[Nn]$ ]]; then
        return 1
    fi
    
    return 0
}

# Function to create Docker files
create_docker_files() {
    print_header "=== Creating Docker Files ==="
    
    # Create docker directory
    mkdir -p "$DOCKER_DIR"
    
    # Create Dockerfile
    print_status "Creating Dockerfile..."
    cat > "$DOCKER_DIR/Dockerfile" << 'EOF'
FROM python:3.13-slim

# Set environment variables for development
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=run.py
ENV FLASK_ENV=development
ENV FLASK_DEBUG=true
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sudo \
    git \
    curl \
    tmux \
    xvfb \
    x11vnc \
    fluxbox \
    python3-websockify \
    novnc \
    net-tools \
    x11-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create user
RUN useradd -ms /bin/bash coresecframe && \
    echo "coresecframe ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    mkdir -p /app /app/logs /app/modules /app/instance && \
    chown -R coresecframe:coresecframe /app

# Set working directory
WORKDIR /app

# Switch to non-root user for dependency installation
USER coresecframe

# Copy requirements first (for better caching)
COPY --chown=coresecframe:coresecframe requirements.txt /app/

# Install Python dependencies including email_validator
RUN pip install --no-cache-dir --user -r requirements.txt && \
    pip install --no-cache-dir --user email_validator

# Copy application code
COPY --chown=coresecframe:coresecframe . /app/

# Switch back to root to set permissions for entrypoint
USER root
RUN chmod +x /app/entrypoint.sh && \
    chown -R coresecframe:coresecframe /app

# Switch back to app user
USER coresecframe

# Expose ports
EXPOSE 5000 5900 6080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000 || exit 1

# Entry point
ENTRYPOINT ["/app/entrypoint.sh"]
EOF

    # Create entrypoint script
    print_status "Creating entrypoint script..."
    cat > "$SCRIPT_DIR/entrypoint.sh" << 'EOF'
#!/bin/bash

# Function to log messages
log() {
    echo "[$(date)] $1"
}

# Set environment variables for development (same as local)
export FLASK_ENV=development
export FLASK_DEBUG=true
export PYTHONWARNINGS=ignore::DeprecationWarning
export FLASK_SKIP_DOTENV=1

log "🚀 Starting CoreSecFrame Docker Container (Development Mode)..."

# Set proper permissions for app directories
log "Setting up directory permissions..."
mkdir -p /app/logs /app/modules /app/instance
chown -R coresecframe:coresecframe /app/logs /app/modules /app/instance 2>/dev/null || true

# Initialize database if needed
if [ ! -f /app/app.db ]; then
    log "📋 Initializing database..."
    python3 -c "
import sys, os
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '/app')
try:
    from app import create_app, db
    from app.auth.models import User
    from app.modules.models import ModuleCategory
    from app.gui.models import GUICategory
    from datetime import datetime
    
    print('Creating Flask application context...')
    app = create_app()
    with app.app_context():
        print('Creating database tables...')
        db.create_all()
        print('Creating admin user...')
        admin = User(username='admin', email='admin@coresecframe.local', role='admin', created_at=datetime.utcnow())
        admin.set_password('admin')
        db.session.add(admin)
        print('Creating regular user...')
        user = User(username='user', email='user@coresecframe.local', role='user', created_at=datetime.utcnow())
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        print('✅ Database initialized successfully')
except Exception as e:
    print(f'❌ Database initialization error: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
"
else
    log "📋 Database already exists, skipping initialization"
fi

# Wait a moment for everything to settle
sleep 2

# Start the Flask application in development mode (like local installation)
log "🌐 Starting CoreSecFrame web application (Development Mode)..."
log "📍 Application will be available at: http://localhost:5000"
log "👤 Default credentials: admin/admin or user/password"
log "🔧 Running in development mode - same as local installation"

# Execute the application directly (like local setup)
exec python3 run.py
EOF

    chmod +x "$SCRIPT_DIR/entrypoint.sh"
    
    # Create docker-compose.yml
    print_status "Creating docker-compose.yml..."
    
    # Check if storage limits are supported
    storage_opts=""
    if docker info 2>/dev/null | grep -q "xfs" && docker info 2>/dev/null | grep -q "pquota"; then
        storage_opts="    storage_opt:
      size: ${docker_storage_gb}G"
        print_status "Storage limits will be enforced"
    else
        print_warning "Storage limits not supported on this system (requires XFS with pquota)"
        print_status "Container will use available disk space without hard limits"
    fi
    
    cat > "$DOCKER_DIR/docker-compose.yml" << EOF
services:
  coresecframe:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: ${DOCKER_CONTAINER_NAME}
    hostname: coresecframe
    restart: unless-stopped
    
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '${docker_cpus}'
          memory: ${docker_memory}
        reservations:
          cpus: '0.5'
          memory: 512M
    
${storage_opts}
    
    # Network configuration
    ports:
      - "${docker_web_port}:5000"    # Web interface
      - "5900:5900"                  # VNC direct access
      - "6080:6080"                  # noVNC web interface
    
    # Volume mounts
    volumes:
      - coresecframe_data:/app/instance
      - coresecframe_logs:/app/logs
      - coresecframe_modules:/app/modules
    
    # Environment variables
    environment:
      - DISPLAY=:1
      - FLASK_ENV=development
      - FLASK_DEBUG=true
      - PYTHONPATH=/app
      - TZ=Europe/Madrid
      - FLASK_RUN_HOST=0.0.0.0
      - FLASK_RUN_PORT=5000
      - PYTHONWARNINGS=ignore::DeprecationWarning
      - FLASK_SKIP_DOTENV=1
    
    # Security options
    security_opt:
      - seccomp:unconfined
    
    # Capabilities
    cap_add:
      - SYS_PTRACE
      - NET_ADMIN
      - NET_RAW
    
    # Network mode
    networks:
      - coresecframe_network
    
    # Health check
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:5000/ || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

# Networks
networks:
  coresecframe_network:
    driver: bridge

# Volumes
volumes:
  coresecframe_data:
    driver: local
    name: ${DOCKER_CONTAINER_NAME}_data
  coresecframe_logs:
    driver: local
    name: ${DOCKER_CONTAINER_NAME}_logs
  coresecframe_modules:
    driver: local
    name: ${DOCKER_CONTAINER_NAME}_modules
EOF

    # Create .dockerignore
    print_status "Creating .dockerignore..."
    cat > "$SCRIPT_DIR/.dockerignore" << 'EOF'
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.mypy_cache
.pytest_cache
.hypothesis
.DS_Store
.vscode
venv/
.env
docker/
*.db
logs/
modules/
instance/
setup.sh
!entrypoint.sh
EOF

    print_success "Docker files created successfully"
}

# Function to clean Docker resources
clean_docker_resources() {
    print_header "=== Cleaning Docker Resources ==="
    
    print_status "Stopping and removing existing containers..."
    if [ -f "$DOCKER_DIR/docker-compose.yml" ]; then
        cd "$DOCKER_DIR"
        docker-compose down -v 2>/dev/null || true
        cd "$SCRIPT_DIR"
    fi
    
    # Remove specific volumes if they exist
    print_status "Cleaning volumes..."
    docker volume rm "${DOCKER_CONTAINER_NAME}_data" "${DOCKER_CONTAINER_NAME}_logs" "${DOCKER_CONTAINER_NAME}_modules" 2>/dev/null || true
    
    print_status "Removing dangling images..."
    docker image prune -f 2>/dev/null || true
    
    print_status "Removing unused networks..."
    docker network prune -f 2>/dev/null || true
    
    print_success "Docker resources cleaned"
}

# Function to build and deploy Docker container
deploy_docker() {
    print_header "=== Building and Deploying Docker Container ==="
    
    # Verify docker files exist
    if [ ! -f "$DOCKER_DIR/docker-compose.yml" ]; then
        print_error "Docker configuration files not found!"
        return 1
    fi
    
    # Clean previous resources
    clean_docker_resources
    
    # Change to docker directory
    cd "$DOCKER_DIR"
    
    # Build the image
    print_status "Building Docker image (this may take several minutes)..."
    if docker-compose build --no-cache; then
        print_success "Docker image built successfully"
    else
        print_error "Failed to build Docker image"
        print_status "Checking logs..."
        docker-compose logs 2>/dev/null || true
        cd "$SCRIPT_DIR"
        return 1
    fi
    
    # Start the container
    print_status "Starting Docker container..."
    if docker-compose up -d; then
        print_success "Docker container started successfully"
    else
        print_error "Failed to start Docker container"
        print_status "Container logs:"
        docker-compose logs 2>/dev/null || true
        cd "$SCRIPT_DIR"
        return 1
    fi
    
    # Wait for container to be ready
    print_status "Waiting for container to initialize..."
    
    # Monitor container startup
    for i in {1..24}; do
        if docker-compose ps | grep -q "Up"; then
            sleep 5
            if curl -f -s "http://localhost:${docker_web_port}/" >/dev/null 2>&1; then
                print_success "Container is ready and responding"
                break
            fi
        fi
        
        if [ $i -eq 24 ]; then
            print_warning "Container may still be initializing. Check manually in a few minutes."
        else
            echo -n "."
            sleep 5
        fi
    done
    echo ""
    
    # Return to original directory
    cd "$SCRIPT_DIR"
    
    print_success "Docker deployment completed!"
    echo
    print_header "=== Docker Deployment Summary ==="
    echo -e "${WHITE}Container Name:${NC} $DOCKER_CONTAINER_NAME"
    echo -e "${WHITE}Base Image:${NC} Python 3.13 Slim"
    echo -e "${WHITE}Environment:${NC} Development (like local)"
    echo -e "${WHITE}CPU Cores:${NC} $docker_cpus"
    echo -e "${WHITE}Memory:${NC} $docker_memory"
    echo -e "${WHITE}Storage Limit:${NC} ${docker_storage_gb}GB"
    echo -e "${WHITE}Web Interface:${NC} http://localhost:${docker_web_port}"
    echo -e "${WHITE}VNC Direct:${NC} localhost:5900"
    echo -e "${WHITE}noVNC Interface:${NC} http://localhost:6080"
    echo -e "${WHITE}Default Admin:${NC} admin/admin"
    echo -e "${WHITE}Default User:${NC} user/password"
    echo
    echo -e "${CYAN}Docker Management Commands:${NC}"
    echo "  Start:    cd $DOCKER_DIR && docker-compose start"
    echo "  Stop:     cd $DOCKER_DIR && docker-compose stop"
    echo "  Restart:  cd $DOCKER_DIR && docker-compose restart"
    echo "  Logs:     cd $DOCKER_DIR && docker-compose logs -f"
    echo "  Status:   cd $DOCKER_DIR && docker-compose ps"
    echo "  Shell:    docker exec -it $DOCKER_CONTAINER_NAME /bin/bash"
    echo "  Remove:   cd $DOCKER_DIR && docker-compose down -v"
    echo
}

# Function to manage Docker container
manage_docker() {
    while true; do
        show_banner
        print_header "=== Docker Container Management ==="
        
        # Check if docker directory exists
        if [ ! -d "$DOCKER_DIR" ]; then
            print_error "Docker configuration not found. Please run Docker deployment first."
            echo
            read -p "Press Enter to return to main menu..."
            return
        fi
        
        # Check container status
        cd "$DOCKER_DIR"
        if docker-compose ps | grep -q "$DOCKER_CONTAINER_NAME"; then
            container_status=$(docker-compose ps --format "table {{.Status}}" | tail -n +2)
            if echo "$container_status" | grep -q "Up"; then
                status_color="${GREEN}Running${NC}"
            else
                status_color="${RED}Stopped${NC}"
            fi
        else
            status_color="${YELLOW}Not Created${NC}"
        fi
        cd "$SCRIPT_DIR"
        
        echo -e "${WHITE}Container Status:${NC} $status_color"
        echo
        echo "Choose an action:"
        echo
        echo "  1) 📊 Show container status"
        echo "  2) 📈 Show resource usage"
        echo "  3) 📋 Show logs"
        echo "  4) ▶️  Start container"
        echo "  5) ⏹️  Stop container"
        echo "  6) 🔄 Restart container"
        echo "  7) 💻 Open shell in container"
        echo "  8) 🗑️  Remove container (keeps data)"
        echo "  9) 💥 Complete removal (removes data)"
        echo "  10) 🔄 Rebuild and restart"
        echo "  11) 🔙 Back to main menu"
        echo
        
        read -p "Enter your choice (1-11): " docker_choice
        
        case $docker_choice in
            1)
                print_header "=== Container Status ==="
                cd "$DOCKER_DIR"
                docker-compose ps
                cd "$SCRIPT_DIR"
                ;;
            2)
                print_header "=== Resource Usage ==="
                if docker ps | grep -q "$DOCKER_CONTAINER_NAME"; then
                    docker stats --no-stream "$DOCKER_CONTAINER_NAME"
                else
                    print_warning "Container is not running"
                fi
                ;;
            3)
                print_header "=== Container Logs ==="
                cd "$DOCKER_DIR"
                docker-compose logs --tail=50
                cd "$SCRIPT_DIR"
                ;;
            4)
                print_status "Starting container..."
                cd "$DOCKER_DIR"
                if docker-compose start; then
                    print_success "Container started successfully"
                else
                    print_error "Failed to start container"
                fi
                cd "$SCRIPT_DIR"
                ;;
            5)
                print_status "Stopping container..."
                cd "$DOCKER_DIR"
                if docker-compose stop; then
                    print_success "Container stopped successfully"
                else
                    print_error "Failed to stop container"
                fi
                cd "$SCRIPT_DIR"
                ;;
            6)
                print_status "Restarting container..."
                cd "$DOCKER_DIR"
                if docker-compose restart; then
                    print_success "Container restarted successfully"
                else
                    print_error "Failed to restart container"
                fi
                cd "$SCRIPT_DIR"
                ;;
            7)
                print_status "Opening shell in container..."
                if docker ps | grep -q "$DOCKER_CONTAINER_NAME"; then
                    docker exec -it "$DOCKER_CONTAINER_NAME" /bin/bash
                else
                    print_error "Container is not running"
                fi
                ;;
            8)
                print_warning "This will remove the container but keep the data volumes."
                read -p "Continue? (y/N): " confirm_remove
                if [[ $confirm_remove =~ ^[Yy]$ ]]; then
                    cd "$DOCKER_DIR"
                    docker-compose down
                    cd "$SCRIPT_DIR"
                    print_success "Container removed (data preserved)"
                fi
                ;;
            9)
                print_warning "This will PERMANENTLY remove the container and ALL data!"
                read -p "Type 'DELETE' to confirm: " confirm_delete
                if [ "$confirm_delete" = "DELETE" ]; then
                    cd "$DOCKER_DIR"
                    docker-compose down -v
                    cd "$SCRIPT_DIR"
                    clean_docker_resources
                    print_success "Container and data removed completely"
                fi
                ;;
            10)
                print_warning "This will rebuild the Docker image and restart the container."
                read -p "Continue? (y/N): " confirm_rebuild
                if [[ $confirm_rebuild =~ ^[Yy]$ ]]; then
                    print_status "Stopping and removing current container..."
                    cd "$DOCKER_DIR"
                    docker-compose down -v
                    
                    print_status "Rebuilding Docker image..."
                    if docker-compose build --no-cache; then
                        print_status "Starting container with new image..."
                        if docker-compose up -d; then
                            print_success "Container rebuilt and restarted successfully!"
                        else
                            print_error "Failed to start rebuilt container"
                        fi
                    else
                        print_error "Failed to rebuild Docker image"
                    fi
                    cd "$SCRIPT_DIR"
                fi
                ;;
            11)
                return 0
                ;;
            *)
                print_error "Invalid choice. Please select 1-11."
                ;;
        esac
        
        echo
        read -p "Press Enter to continue..."
    done
}

# Function to initialize database
init_database() {
    print_header "=== Database Initialization ==="
    
    print_status "Creating database initialization script..."
    
    # Create temporary initialization script
    cat > "$SCRIPT_DIR/temp_init_db.py" << 'EOF'
#!/usr/bin/env python3

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app, db
    from app.auth.models import User
    from app.modules.models import ModuleCategory
    from app.gui.models import GUICategory
    from datetime import datetime
    
    def initialize_database():
        print("🔧 Initializing CoreSecFrame database...")
        
        app = create_app()
        
        with app.app_context():
            # Create all tables
            print("\n📋 Creating database tables...")
            db.create_all()
            print("  ✅ Database tables created")
            
            # Create essential users
            print("\n👥 Creating essential users...")
            
            # Admin user
            admin = User(
                username='admin', 
                email='admin@coresecframe.local', 
                role='admin',
                created_at=datetime.utcnow()
            )
            admin.set_password('admin')
            db.session.add(admin)
            print("  ✅ Admin user (admin/admin)")
            
            # Regular user
            user = User(
                username='user', 
                email='user@coresecframe.local', 
                role='user',
                created_at=datetime.utcnow()
            )
            user.set_password('password')
            db.session.add(user)
            print("  ✅ Regular user (user/password)")
            
            # Commit the changes
            print("\n💾 Committing changes to database...")
            db.session.commit()
            
            print("\n🎉 Database initialization completed successfully!")
            return True

    if __name__ == '__main__':
        if initialize_database():
            print("✅ Database is ready for use!")
        else:
            print("❌ Database initialization failed!")
            sys.exit(1)
            
except Exception as e:
    print(f"❌ Fatal error during database initialization: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

    # Execute database initialization
    source "$VENV_PATH/bin/activate"
    python3 "$SCRIPT_DIR/temp_init_db.py"
    
    # Clean up temporary file
    rm -f "$SCRIPT_DIR/temp_init_db.py"
    
    print_success "Database initialized successfully"
    echo
}

# Function to reset database
reset_database() {
    print_header "=== Database Reset ==="
    print_warning "⚠️  WARNING: This will completely reset the database!"
    print_warning "⚠️  All existing data will be PERMANENTLY deleted!"
    echo
    
    read -p "Are you absolutely sure you want to reset the database? (type 'RESET' to confirm): " confirm
    
    if [ "$confirm" != "RESET" ]; then
        print_status "Database reset cancelled."
        return
    fi
    
    print_status "Resetting database..."
    init_database
    print_success "Database has been reset successfully!"
    echo
    echo -e "${YELLOW}Default credentials after reset:${NC}"
    echo "  Admin: admin/admin"
    echo "  User:  user/password"
    echo
}

# Function for local installation
install_local() {
    print_header "=== Local Installation ==="
    
    # Create virtual environment
    print_status "Creating Python virtual environment..."
    python3 -m venv "$VENV_PATH"
    source "$VENV_PATH/bin/activate"
    print_success "Virtual environment created and activated"
    
    # Install dependencies
    print_status "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    print_success "Dependencies installed"
    
    # Create required directories
    print_status "Creating required directories..."
    mkdir -p logs modules instance
    chmod -R 755 .
    chmod -R 777 logs modules instance
    print_success "Directories created with proper permissions"
    
    # Initialize database
    init_database
    
    print_success "Local installation completed!"
    echo
    print_header "=== Installation Summary ==="
    echo -e "${WHITE}Application Location:${NC} $SCRIPT_DIR"
    echo -e "${WHITE}Virtual Environment:${NC} $VENV_PATH"
    echo -e "${WHITE}Database:${NC} SQLite (app.db)"
    echo -e "${WHITE}Default Admin:${NC} admin/admin"
    echo -e "${WHITE}Default User:${NC} user/password"
    echo
    echo -e "${CYAN}To start the application:${NC}"
    echo "  cd $SCRIPT_DIR"
    echo "  source venv/bin/activate"
    echo "  python run.py"
    echo
    echo -e "${CYAN}Application will be available at:${NC} http://localhost:5000"
    echo
}

# Main menu function
show_main_menu() {
    while true; do
        show_banner
        echo -e "${WHITE}Choose an option:${NC}"
        echo
        echo "  1) 🖥️  Local Installation"
        echo "  2) 🐳 Docker Deployment"
        echo "  3) 🔧 Manage Docker Container"
        echo "  4) 🔄 Reset Database (DESTRUCTIVE)"
        echo "  5) ❌ Exit"
        echo
        read -p "Enter your choice (1-5): " choice
        
        case $choice in
            1)
                check_requirements
                install_local
                break
                ;;
            2)
                check_docker_requirements
                if get_docker_config; then
                    create_docker_files
                    deploy_docker
                fi
                break
                ;;
            3)
                manage_docker
                ;;
            4)
                # Check if local installation exists
                if [ -d "$VENV_PATH" ] && [ -f "$SCRIPT_DIR/app.db" ]; then
                    source "$VENV_PATH/bin/activate" 2>/dev/null || true
                    reset_database
                else
                    print_error "No local installation found. Please run local installation first."
                    echo "Press Enter to continue..."
                    read
                fi
                ;;
            5)
                print_status "Goodbye!"
                exit 0
                ;;
            *)
                print_error "Invalid choice. Please select 1-5."
                sleep 2
                ;;
        esac
    done
}

# Script entry point
main() {
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_error "Please do not run this script as root!"
        exit 1
    fi
    
    # Show main menu
    show_main_menu
}

# Run main function
main "$@"