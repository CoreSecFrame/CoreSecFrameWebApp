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
TEMP_FILE=""

# Cleanup function for temporary files
cleanup() {
    if [ -n "$TEMP_FILE" ] && [ -f "$TEMP_FILE" ]; then
        rm -f "$TEMP_FILE"
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

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
        
        if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
            print_error "Python 3.8 or higher is required"
            exit 1
        fi
    fi

    # Add required system dependencies for Python development
    missing_deps+=("build-essential" "python3-dev" "python3-pip" "python3-venv")

    
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

    # ========== NUEVA SECCIÓN: GUI DEPENDENCIES ==========
    print_status "Checking GUI module requirements..."
    
    # Check Xvfb (Virtual X11 server)
    if ! command -v Xvfb &> /dev/null; then
        gui_missing+=("xvfb")
    else
        print_status "Xvfb is available"
    fi
    
    # Check x11vnc (VNC server for X11)
    if ! command -v x11vnc &> /dev/null; then
        gui_missing+=("x11vnc")
    else
        print_status "x11vnc is available"
    fi
    
    # Check X11 utilities
    if ! command -v xdpyinfo &> /dev/null; then
        gui_missing+=("x11-utils")
    else
        print_status "X11 utilities are available"
    fi
    
    # Check Fluxbox window manager
    if ! command -v fluxbox &> /dev/null; then
        gui_missing+=("fluxbox")
    else
        print_status "Fluxbox window manager is available"
    fi
    
    # Check websockify for noVNC
    if ! command -v websockify &> /dev/null; then
        gui_missing+=("websockify")
    else
        print_status "websockify is available"
    fi

    # Check if noVNC is available or can be installed
    if [ ! -d "/usr/share/novnc" ] && [ ! -d "./novnc" ]; then
        print_status "noVNC not found, will be installed automatically"
    else
        print_status "noVNC is available"
    fi
    
    # Install GUI dependencies if missing
    if [ ${#gui_missing[@]} -ne 0 ]; then
        print_warning "Missing GUI dependencies: ${gui_missing[*]}"
        print_status "Installing GUI dependencies..."
        
        if command -v apt-get &> /dev/null; then
            # Debian/Ubuntu/Kali Linux
            print_status "Using apt-get package manager..."
            sudo apt-get update
            
            # Map generic names to specific packages
            local apt_packages=()
            for dep in "${gui_missing[@]}"; do
                case $dep in
                    "xvfb")
                        apt_packages+=("xvfb")
                        ;;
                    "x11vnc")
                        apt_packages+=("x11vnc")
                        ;;
                    "x11-utils")
                        apt_packages+=("x11-utils" "x11-xserver-utils")
                        ;;
                    "fluxbox")
                        apt_packages+=("fluxbox")
                        ;;
                    "websockify")
                        apt_packages+=("websockify" "python3-websockify")
                        ;;
                    "build-essential")
                        apt_packages+=("build-essential")
                        ;;
                    "python3-dev")
                        apt_packages+=("python3-dev")
                        ;;                        
                    "python3-pip")
                        apt_packages+=("python3-pip")
                        ;;                        
                    "python3-venv")
                        apt_packages+=("python3-venv")
                        ;;
                esac
            done
            
            # Add noVNC if available in repos
            apt_packages+=("novnc")
            
            # Install packages
            if sudo apt-get install -y "${apt_packages[@]}"; then
                print_success "GUI dependencies installed successfully"
            else
                print_warning "Some GUI packages may not have been installed correctly"
            fi
            
        elif command -v yum &> /dev/null; then
            # RHEL/CentOS
            print_status "Using yum package manager..."
            
            local yum_packages=()
            for dep in "${gui_missing[@]}"; do
                case $dep in
                    "xvfb")
                        yum_packages+=("xorg-x11-server-Xvfb")
                        ;;
                    "x11vnc")
                        yum_packages+=("x11vnc")
                        ;;
                    "x11-utils")
                        yum_packages+=("xorg-x11-utils")
                        ;;
                    "fluxbox")
                        yum_packages+=("fluxbox")
                        ;;
                    "websockify")
                        yum_packages+=("python3-websockify")
                        ;;
                esac
            done
            
            sudo yum install -y "${yum_packages[@]}"
            install_novnc_manual  # noVNC not in RHEL repos
            
        elif command -v dnf &> /dev/null; then
            # Fedora
            print_status "Using dnf package manager..."
            
            local dnf_packages=()
            for dep in "${gui_missing[@]}"; do
                case $dep in
                    "xvfb")
                        dnf_packages+=("xorg-x11-server-Xvfb")
                        ;;
                    "x11vnc")
                        dnf_packages+=("x11vnc")
                        ;;
                    "x11-utils")
                        dnf_packages+=("xorg-x11-utils")
                        ;;
                    "fluxbox")
                        dnf_packages+=("fluxbox")
                        ;;
                    "websockify")
                        dnf_packages+=("python3-websockify")
                        ;;
                esac
            done
            
            sudo dnf install -y "${dnf_packages[@]}"
            install_novnc_manual  # Install noVNC manually
            
        else
            print_error "Cannot install GUI dependencies automatically."
            print_error "Please install manually:"
            echo "  - Xvfb (virtual X11 server)"
            echo "  - x11vnc (VNC server)"
            echo "  - x11-utils (X11 utilities)"
            echo "  - fluxbox (window manager)"
            echo "  - websockify (noVNC proxy)"
            print_warning "GUI module will be disabled without these dependencies"
        fi
    else
        print_success "All GUI requirements satisfied"
    fi

    # Install noVNC if not available
    if [ ! -d "/usr/share/novnc" ] && [ ! -d "./novnc" ]; then
        install_novnc_manual
    fi

    # Install missing basic dependencies
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_warning "Missing basic dependencies: ${missing_deps[*]}"
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
    
    # ========== NUEVA SECCIÓN: INSTALL COMMON GUI APPS ==========
    print_status "Installing common GUI applications for testing..."
    
    if command -v apt-get &> /dev/null; then
        # Install common applications that work well with the GUI module
        local gui_apps=("firefox-esr" "gedit" "gnome-calculator" "xterm")
        
        print_status "Installing GUI applications: ${gui_apps[*]}"
        if sudo apt-get install -y "${gui_apps[@]}" 2>/dev/null; then
            print_success "GUI applications installed successfully"
        else
            print_warning "Some GUI applications may not be available"
        fi
    fi
    
    print_success "System requirements satisfied"
    echo
}

# Function to initialize database
init_database() {
    print_header "=== Database Initialization ==="
    
    print_status "Initializing CoreSecFrame database..."
    
    # Check if init_db.py exists
    if [ -f "$SCRIPT_DIR/init_db.py" ]; then
        # Use the existing init_db.py file
        source "$VENV_PATH/bin/activate"
        if python3 "$SCRIPT_DIR/init_db.py"; then
            print_success "Database initialized successfully"
        else
            print_error "Database initialization failed"
            return 1
        fi
    else
        print_error "init_db.py not found in $SCRIPT_DIR"
        return 1
    fi
    
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
    if [ $? -eq 0 ]; then
        print_success "Database has been reset successfully!"
        echo
        echo -e "${YELLOW}Default credentials after reset:${NC}"
        echo "  Admin: admin/admin"
        echo "  User:  user/password"
        echo
    else
        print_error "Database reset failed"
    fi
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
            
            # Create a symbolic link for easier access
            if [ -w "/usr/local/bin" ]; then
                sudo ln -sf "$SCRIPT_DIR/novnc/utils/novnc_proxy" /usr/local/bin/novnc_proxy 2>/dev/null || true
            fi
            
            print_status "noVNC installed to $SCRIPT_DIR/novnc"
            
            # Test noVNC installation
            if [ -f "$SCRIPT_DIR/novnc/utils/novnc_proxy" ]; then
                print_success "noVNC proxy script is available"
            else
                print_warning "noVNC proxy script not found, checking for websockify..."
                if command -v websockify &> /dev/null; then
                    print_status "websockify is available as fallback"
                else
                    print_error "Neither noVNC proxy nor websockify found"
                fi
            fi
        else
            print_warning "Failed to download noVNC. GUI module may have limited functionality."
            print_status "You can install it manually later with:"
            echo "  cd $SCRIPT_DIR"
            echo "  git clone https://github.com/novnc/noVNC.git novnc"
            return 1
        fi
    else
        print_status "noVNC already exists in $SCRIPT_DIR/novnc"
    fi
    
    return 0
}

# Function to verify GUI installation
verify_gui_installation() {
    print_header "=== GUI Installation Verification ==="
    
    local all_good=true
    
    print_status "Verifying GUI components..."
    
    # Check Xvfb
    if command -v Xvfb &> /dev/null; then
        print_success "✓ Xvfb is installed"
    else
        print_error "✗ Xvfb is NOT installed"
        all_good=false
    fi
    
    # Check x11vnc
    if command -v x11vnc &> /dev/null; then
        print_success "✓ x11vnc is installed"
    else
        print_error "✗ x11vnc is NOT installed"
        all_good=false
    fi
    
    # Check X11 utils
    if command -v xdpyinfo &> /dev/null; then
        print_success "✓ X11 utilities are installed"
    else
        print_error "✗ X11 utilities are NOT installed"
        all_good=false
    fi
    
    # Check Fluxbox
    if command -v fluxbox &> /dev/null; then
        print_success "✓ Fluxbox window manager is installed"
    else
        print_warning "⚠ Fluxbox is not installed (optional but recommended)"
    fi
    
    # Check websockify
    if command -v websockify &> /dev/null; then
        print_success "✓ websockify is installed"
    else
        print_error "✗ websockify is NOT installed"
        all_good=false
    fi
    
    # Check noVNC
    if [ -d "/usr/share/novnc" ] || [ -d "$SCRIPT_DIR/novnc" ]; then
        print_success "✓ noVNC is available"
    else
        print_error "✗ noVNC is NOT available"
        all_good=false
    fi
    
    # Test GUI applications
    print_status "Checking GUI applications..."
    if command -v firefox-esr &> /dev/null || command -v firefox &> /dev/null; then
        print_success "✓ Firefox browser is available"
    else
        print_warning "⚠ Firefox browser not found"
    fi
    
    if command -v gedit &> /dev/null; then
        print_success "✓ Text editor (gedit) is available"
    else
        print_warning "⚠ Text editor not found"
    fi
    
    if command -v xterm &> /dev/null; then
        print_success "✓ Terminal emulator (xterm) is available"
    else
        print_warning "⚠ Terminal emulator not found"
    fi
    
    echo
    if [ "$all_good" = true ]; then
        print_success "🎉 GUI module installation verification PASSED!"
        print_status "You can now use the GUI module to run applications in virtual displays"
        echo
        print_status "Quick test commands after starting the application:"
        echo "  1. Start CoreSecFrame: python run.py"
        echo "  2. Initialize GUI apps: flask gui-init"
        echo "  3. Access web interface: http://localhost:5000/gui"
    else  
        print_error "❌ GUI module installation verification FAILED!"
        print_status "Some required components are missing. Please install them manually."
        echo
        print_status "For Kali Linux/Debian/Ubuntu:"
        echo "  sudo apt update"
        echo "  sudo apt install -y xvfb x11vnc x11-utils fluxbox websockify novnc"
        echo "  sudo apt install -y firefox-esr gedit xterm gnome-calculator"
    fi
    
    echo
}

# Function to setup noVNC service
setup_novnc_service() {
    print_header "=== noVNC Web Service Setup ==="
    
    # Detect if we are in WSL
    if grep -qiE "(microsoft|wsl)" /proc/sys/kernel/osrelease 2>/dev/null; then
        print_status "Detected WSL environment - Skipping noVNC systemd service setup"
        return
    fi

    print_status "Non-WSL environment detected - Proceeding with noVNC service setup"

    # Create systemd directory if it doesn't exist
    mkdir -p "$SYSTEMD_DIR"
    
    # Check if websockify is available
    if ! command -v websockify &> /dev/null; then
        print_error "websockify not found. Please install it first:"
        echo "  Ubuntu/Debian: sudo apt-get install websockify"
        echo "  RHEL/CentOS: sudo yum install python3-websockify"
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

    # Install and start service
    if sudo cp "$SYSTEMD_DIR/novnc.service" /etc/systemd/system/; then
        sudo systemctl daemon-reload
        sudo systemctl enable novnc.service
        sudo systemctl start novnc.service
        
        print_success "noVNC systemd service installed and started automatically"
        print_status "You can access it at: http://localhost:6080"
        print_status "Manage it with:"
        echo "  sudo systemctl start|stop|status novnc"
    else
        print_error "Failed to install noVNC service"
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
    
    # Verify GUI installation
    verify_gui_installation
    
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
    echo -e "${CYAN}To initialize GUI applications:${NC}"
    echo "  flask gui-init"
    echo
    echo -e "${CYAN}Application will be available at:${NC} http://localhost:5000"
    echo -e "${CYAN}GUI module will be available at:${NC} http://localhost:5000/gui"
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