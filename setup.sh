#!/bin/bash
# CoreSecFrame Setup Script - Local Installation Only
# Supports local installation and database management

set -e  # Exit on any error

# Set colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Configuration variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="coresecframe"
VENV_PATH="$SCRIPT_DIR/venv"
SYSTEMD_DIR="$SCRIPT_DIR/systemd"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${CYAN}$1${NC}"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to display banner
show_banner() {
    clear
    echo -e "${PURPLE}"
    cat << "EOF"
   ____                 ____            ______                      
  / __ \____  ________ / __/___  ____  / ____/________ _____ _____ 
 / /_/ / __ \/ ___/ _ \\_\ \/ _ \/ ___/ / /_  / ___/ __ `/ __ `/ __ \
/ ____/ /_/ / /  /  __/___/ __/ /___ / __/ / /  / /_/ / / / / /_/ /
\_____\____/_/   \___/_____\___/____//_/   /_/   \__,_/_/ /_/\__,_/ 
                                                                    
EOF
    echo -e "${NC}"
    echo -e "${WHITE}Professional Cybersecurity Framework${NC}"
    echo -e "${CYAN}Local Installation Setup Script v2.0${NC}"
    echo ""
}

# Function to check system requirements
check_requirements() {
    print_header "=== Checking System Requirements ==="
    
    local missing_deps=()
    local gui_missing=()
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    else
        python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        print_status "Python version: ${python_version}"
        
        # Check if version is >= 3.8
        if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
            print_error "Python 3.8 or higher is required"
            exit 1
        fi
    fi
    
    # Check tmux
    if ! command -v tmux &> /dev/null; then
        missing_deps+=("tmux")
    else
        print_status "tmux is available"
    fi
    
    # Check git
    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    else
        print_status "git is available"
    fi

    print_status "Checking noVNC requirements..."
    if ! command -v websockify &> /dev/null; then
        gui_missing+=("websockify")
    fi

    # Check if noVNC is available or can be installed
    if [ ! -d "/usr/share/novnc" ] && [ ! -d "./novnc" ]; then
        print_status "noVNC not found, will be installed automatically"
    fi
    
    if [ ${#gui_missing[@]} -ne 0 ]; then
        print_warning "Missing GUI dependencies: ${gui_missing[*]}"
        print_status "Installing GUI dependencies..."
        
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y "${gui_missing[@]}" python3-websockify novnc
        elif command -v yum &> /dev/null; then
            sudo yum install -y "${gui_missing[@]}" python3-websockify
            # Install noVNC manually for RHEL/CentOS
            install_novnc_manual
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y "${gui_missing[@]}" python3-websockify
            # Install noVNC manually for Fedora
            install_novnc_manual
        else
            print_error "Cannot install GUI dependencies automatically. Please install: ${gui_missing[*]}"
            print_warning "GUI module will be disabled without these dependencies"
        fi
    else
        print_success "GUI requirements satisfied"
    fi

    # Install noVNC if not available
    if [ ! -d "/usr/share/novnc" ] && [ ! -d "./novnc" ]; then
        install_novnc_manual
    fi

    # Install missing dependencies
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_warning "Missing dependencies: ${missing_deps[*]}"
        print_status "Installing missing dependencies..."
        
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y "${missing_deps[@]}"
        elif command -v yum &> /dev/null; then
            sudo yum install -y "${missing_deps[@]}"
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y "${missing_deps[@]}"
        else
            print_error "Cannot install dependencies automatically. Please install: ${missing_deps[*]}"
            exit 1
        fi
    fi
    
    print_success "System requirements satisfied"
    echo
}

# Function to initialize database
init_database() {
    print_header "=== Database Initialization ==="
    
    print_status "Initializing CoreSecFrame database..."
    
    # Create Python script for database initialization
    cat > "$SCRIPT_DIR/temp_init_db.py" << 'EOF'
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.auth.models import User
from app.modules.models import Module, ModuleCategory
from app.terminal.models import TerminalSession, TerminalLog, TerminalLogSummary
from app.core.models import SystemLog, LogSearchQuery, SystemMetric
from app.gui.models import GUIApplication, GUISession, GUICategory, GUISessionLog
from datetime import datetime

def initialize_database():
    """Initialize the CoreSecFrame database with clean structure"""
    
    app = create_app()
    
    with app.app_context():
        print("🚀 CoreSecFrame Database Initialization")
        print("=" * 50)
        
        # Drop all tables and recreate
        print("🗑️  Dropping all existing tables...")
        db.drop_all()
        
        print("🏗️  Creating all database tables...")
        db.create_all()
        
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
        
        # Create module categories
        print("\n📂 Creating module categories...")
        categories = [
            ModuleCategory(
                name='Reconnaissance',
                description='Information gathering and target discovery tools'
            ),
            ModuleCategory(
                name='Vulnerability Analysis',
                description='Security vulnerability scanning and analysis tools'
            ),
            ModuleCategory(
                name='Exploitation',
                description='Penetration testing and exploitation frameworks'
            ),
            ModuleCategory(
                name='Post Exploitation',
                description='Post-exploitation and persistence tools'
            ),
            ModuleCategory(
                name='Reporting',
                description='Report generation and documentation tools'
            ),
            ModuleCategory(
                name='Utils',
                description='Utility tools and helper scripts'
            )
        ]
        
        for category in categories:
            db.session.add(category)
            print(f"  ✅ {category.name}")
        
        # Create GUI categories (structure only, no example apps)
        print("\n🖥️  Creating GUI application categories...")
        gui_categories = [
            GUICategory(
                name='browsers',
                display_name='Web Browsers',
                description='Web browsing applications',
                icon_class='bi-globe',
                sort_order=1
            ),
            GUICategory(
                name='editors',
                display_name='Text Editors',
                description='Text and code editors',
                icon_class='bi-file-text',
                sort_order=2
            ),
            GUICategory(
                name='terminals',
                display_name='Terminal Emulators',
                description='Terminal applications',
                icon_class='bi-terminal',
                sort_order=3
            ),
            GUICategory(
                name='utilities',
                display_name='Utilities',
                description='System utilities and tools',
                icon_class='bi-tools',
                sort_order=4
            ),
            GUICategory(
                name='development',
                display_name='Development',
                description='Development tools and IDEs',
                icon_class='bi-code-slash',
                sort_order=5
            ),
            GUICategory(
                name='multimedia',
                display_name='Multimedia',
                description='Audio and video applications',
                icon_class='bi-play-btn',
                sort_order=6
            )
        ]
        
        for category in gui_categories:
            db.session.add(category)
            print(f"  ✅ GUI: {category.display_name}")
        
        # Commit the changes
        print("\n💾 Committing changes to database...")
        db.session.commit()
        
        print("\n🎉 Database initialization completed successfully!")
        print("\n📋 Summary:")
        print(f"  • Users: 2 (admin, user)")
        print(f"  • Module categories: {len(categories)}")
        print(f"  • GUI categories: {len(gui_categories)}")
        print(f"  • GUI applications: 0 (use 'flask gui-init' to add)")
        
        return True

if __name__ == '__main__':
    try:
        if initialize_database():
            print("✅ Database is ready for use!")
            print("\n🔧 Next steps:")
            print("  1. Start the application: python run.py")
            print("  2. Add GUI applications: flask gui-init")
            print("  3. Access web interface: http://localhost:5000")
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
    print_warning "⚠️  All existing data including users, sessions, and logs will be PERMANENTLY deleted!"
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

# Function to install noVNC manually
install_novnc_manual() {
    print_status "Installing noVNC manually..."
    
    if [ ! -d "$SCRIPT_DIR/novnc" ]; then
        print_status "Downloading noVNC..."
        if git clone https://github.com/novnc/noVNC.git "$SCRIPT_DIR/novnc"; then
            print_success "noVNC downloaded successfully"
            
            # Make sure it's accessible
            chmod -R 755 "$SCRIPT_DIR/novnc"
            
            print_status "noVNC installed to $SCRIPT_DIR/novnc"
        else
            print_warning "Failed to download noVNC. GUI module may have limited functionality."
            return 1
        fi
    else
        print_status "noVNC already exists in $SCRIPT_DIR/novnc"
    fi
    
    return 0
}

# Function to setup noVNC service
setup_novnc_service() {
    print_header "=== noVNC Web Service Setup ==="
    
    read -p "Would you like to set up noVNC web service for browser-based VNC access? (y/N): " setup_novnc
    
    if [[ $setup_novnc =~ ^[Yy]$ ]]; then
        print_status "Setting up noVNC service..."
        
        # Create systemd directory if it doesn't exist
        mkdir -p "$SYSTEMD_DIR"
        
        # Check if websockify is available
        if ! command -v websockify &> /dev/null; then
            print_error "websockify not found. Please install it first:"
            echo "  Ubuntu/Debian: sudo apt-get install websockify"
            echo "  RHEL/CentOS: sudo yum install python3-websockify"
            echo "  Fedora: sudo dnf install python3-websockify"
            return 1
        fi
        
        # Determine noVNC path
        NOVNC_PATH=""
        if [ -d "/usr/share/novnc" ]; then
            NOVNC_PATH="/usr/share/novnc"
        elif [ -d "$SCRIPT_DIR/novnc" ]; then
            NOVNC_PATH="$SCRIPT_DIR/novnc"
        else
            print_warning "noVNC not found. Installing it now..."
            install_novnc_manual
            NOVNC_PATH="$SCRIPT_DIR/novnc"
        fi
        
        # Create noVNC systemd service
        cat > "$SYSTEMD_DIR/novnc.service" << EOF
[Unit]
Description=noVNC Web Client
After=network.target
Wants=coresecframe.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$NOVNC_PATH
ExecStart=/usr/bin/websockify --web $NOVNC_PATH 6080 localhost:5900
Restart=always
RestartSec=3
Environment=HOME=/home/$USER

[Install]
WantedBy=multi-user.target
EOF

        # Install service
        if sudo cp "$SYSTEMD_DIR/novnc.service" /etc/systemd/system/; then
            sudo systemctl daemon-reload
            sudo systemctl enable novnc.service
            
            print_success "noVNC service created and enabled"
            print_status "noVNC will be available at: http://localhost:6080"
            print_status "Service commands:"
            echo "  Start:   sudo systemctl start novnc"
            echo "  Stop:    sudo systemctl stop novnc"
            echo "  Status:  sudo systemctl status novnc"
            
            read -p "Would you like to start the noVNC service now? (y/N): " start_novnc
            if [[ $start_novnc =~ ^[Yy]$ ]]; then
                if sudo systemctl start novnc; then
                    print_success "noVNC service started!"
                    print_status "Access noVNC at: http://localhost:6080"
                    
                    # Give it a moment to start
                    sleep 2
                    if systemctl is-active --quiet novnc; then
                        print_success "noVNC service is running correctly"
                    else
                        print_warning "noVNC service may not be running correctly"
                        print_status "Check status with: sudo systemctl status novnc"
                    fi
                else
                    print_error "Failed to start noVNC service"
                    print_status "Check logs with: sudo journalctl -u novnc -f"
                fi
            fi
        else
            print_error "Failed to install noVNC service"
        fi
    else
        print_status "Skipping noVNC web service setup"
        print_status "You can still use native VNC clients to connect directly"
    fi
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
    
    # Set up systemd service (optional)
    setup_systemd_service
    setup_novnc_service
    
    print_success "Local installation completed!"
    echo
    print_header "=== Installation Summary ==="
    echo -e "${WHITE}Application Location:${NC} $SCRIPT_DIR"
    echo -e "${WHITE}Virtual Environment:${NC} $VENV_PATH"
    echo -e "${WHITE}Database:${NC} SQLite (app.db)"
    echo -e "${WHITE}Default Admin:${NC} admin/admin"
    echo -e "${WHITE}Default User:${NC} user/password"
    echo
    echo -e "${CYAN}To start the application manually:${NC}"
    echo "  cd $SCRIPT_DIR"
    echo "  source venv/bin/activate"
    echo "  python run.py"
    echo
    echo -e "${CYAN}Application will be available at:${NC} http://localhost:5000"
    echo
}

# Function to setup systemd service
setup_systemd_service() {
    print_header "=== System Service Setup ==="
    
    read -p "Would you like to set up CoreSecFrame to start automatically on system boot? (y/N): " auto_start
    
    if [[ $auto_start =~ ^[Yy]$ ]]; then
        print_status "Creating systemd service..."
        
        # Create systemd directory
        mkdir -p "$SYSTEMD_DIR"
        
        # Create service file
        cat > "$SYSTEMD_DIR/coresecframe.service" << EOF
[Unit]
Description=CoreSecFrame Web Application
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$SCRIPT_DIR
Environment=PATH=$VENV_PATH/bin
ExecStart=$VENV_PATH/bin/python run.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

        # Install service
        sudo cp "$SYSTEMD_DIR/coresecframe.service" /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable coresecframe.service
        
        print_success "Systemd service created and enabled"
        print_status "Service commands:"
        echo "  Start:   sudo systemctl start coresecframe"
        echo "  Stop:    sudo systemctl stop coresecframe"
        echo "  Status:  sudo systemctl status coresecframe"
        echo "  Logs:    sudo journalctl -u coresecframe -f"
        echo
        
        read -p "Would you like to start the service now? (y/N): " start_now
        if [[ $start_now =~ ^[Yy]$ ]]; then
            sudo systemctl start coresecframe
            print_success "CoreSecFrame service started!"
            print_status "Service status:"
            sudo systemctl status coresecframe --no-pager -l
        fi
    else
        print_status "Skipping automatic startup setup"
    fi
    echo
}

# Main menu function
show_main_menu() {
    while true; do
        show_banner
        echo -e "${WHITE}Choose an option:${NC}"
        echo
        echo "  1) 🖥️  Local Installation"
        echo "  2) 🔄 Reset Database (DESTRUCTIVE)"
        echo "  3) ❌ Exit"
        echo
        read -p "Enter your choice (1-3): " choice
        
        case $choice in
            1)
                check_requirements
                install_local
                break
                ;;
            2)
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
            3)
                print_status "Goodbye!"
                exit 0
                ;;
            *)
                print_error "Invalid choice. Please select 1-3."
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