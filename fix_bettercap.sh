#!/bin/bash
# Quick fix script for BetterMITM/Bettercap setup
# Run this script to configure Bettercap permissions and configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_header "BetterMITM Quick Fix Script"

# Check if bettercap is installed
if ! command -v bettercap &> /dev/null; then
    print_error "Bettercap is not installed!"
    print_status "Installing Bettercap..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y bettercap
    else
        print_error "Please install Bettercap manually:"
        echo "  Download from: https://github.com/bettercap/bettercap/releases"
        exit 1
    fi
fi

# Get bettercap path
BETTERCAP_PATH=$(which bettercap)
print_status "Bettercap found at: $BETTERCAP_PATH"

# Check and set network capabilities
print_header "Setting Network Capabilities"

if getcap "$BETTERCAP_PATH" | grep -q "cap_net_raw,cap_net_admin"; then
    print_success "Network capabilities are already set"
else
    print_status "Setting network capabilities..."
    if sudo setcap cap_net_raw,cap_net_admin=eip "$BETTERCAP_PATH"; then
        print_success "Network capabilities set successfully"
    else
        print_error "Failed to set network capabilities"
        print_warning "You may need to run BetterMITM as root"
    fi
fi

# Create configuration directory and file
print_header "Creating Bettercap Configuration"

CONFIG_DIR="$HOME/.bettercap"
CONFIG_FILE="$CONFIG_DIR/config.yml"

mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    print_warning "Configuration file already exists: $CONFIG_FILE"
    print_status "Backing up existing configuration..."
    cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%s)"
fi

print_status "Creating default configuration..."

cat > "$CONFIG_FILE" << 'EOF'
# Bettercap Configuration for BetterMITM
api:
  rest:
    enabled: true
    port: 8081
    username: admin
    password: admin123
    certificate: ""
    key: ""
    allow_origin: "*"

# Network interface (auto-detect by default)
interface: ""

# Logging
log:
  level: info
  output: ""

# Default modules
modules:
  net.recon:
    enabled: true
  net.probe:
    enabled: false
  arp.spoof:
    enabled: false
  dns.spoof:
    enabled: false
  http.proxy:
    enabled: false
  net.sniff:
    enabled: false
EOF

chmod 600 "$CONFIG_FILE"
print_success "Configuration file created: $CONFIG_FILE"

# Test bettercap startup
print_header "Testing Bettercap"

print_status "Testing basic Bettercap functionality..."
if timeout 5 bettercap -eval "help; quit" >/dev/null 2>&1; then
    print_success "Bettercap basic test passed"
else
    print_error "Bettercap basic test failed"
    print_warning "This might be normal if you're in a restricted environment"
fi

print_status "Testing Bettercap API startup..."
if timeout 10 bettercap -eval "api.rest on; set api.rest.port 8083; sleep 2; api.rest off; quit" >/dev/null 2>&1; then
    print_success "Bettercap API test passed"
else
    print_error "Bettercap API test failed"
    print_warning "Check the output manually: bettercap -eval 'api.rest on; help; quit'"
fi

# Show network interfaces
print_header "Network Interfaces"
print_status "Available network interfaces:"

if command -v ip &> /dev/null; then
    ip -4 addr show | grep -E "^[0-9]+:|inet " | while read line; do
        if [[ $line =~ ^[0-9]+: ]]; then
            interface=$(echo $line | cut -d' ' -f2 | cut -d':' -f1)
            printf "  Interface: %-10s" "$interface"
        elif [[ $line =~ inet ]]; then
            ip_addr=$(echo $line | awk '{print $2}' | cut -d'/' -f1)
            echo " IP: $ip_addr"
        fi
    done
else
    ifconfig | grep -E "^[a-zA-Z0-9]+|inet " | while read line; do
        if [[ $line =~ ^[a-zA-Z0-9]+ ]]; then
            interface=$(echo $line | cut -d' ' -f1 | cut -d':' -f1)
            printf "  Interface: %-10s" "$interface"
        elif [[ $line =~ inet ]]; then
            ip_addr=$(echo $line | awk '{print $2}')
            echo " IP: $ip_addr"
        fi
    done
fi

print_header "Setup Complete"
print_success "BetterMITM setup completed!"

echo
print_status "Next steps:"
echo "  1. Start your CoreSecFrame application"
echo "  2. Navigate to /bettermitm"
echo "  3. Click 'Start Bettercap' and select a network interface"
echo
print_status "If you still have issues:"
echo "  1. Run: python3 diagnose_bettermitm.py"
echo "  2. Check logs in the CoreSecFrame web interface"
echo "  3. Try running bettercap manually: bettercap -eval 'help; quit'"
echo
print_warning "Remember: BetterMITM should only be used on networks you own or have permission to test!"

print_header "Manual Test Commands"
echo "Test Bettercap manually:"
echo "  bettercap -version"
echo "  bettercap -eval 'help; quit'"  
echo "  bettercap -eval 'api.rest on; sleep 5; api.rest off; quit'"
echo
echo "Test API manually:"
echo "  # Terminal 1:"
echo "  bettercap -eval 'api.rest on'"
echo "  # Terminal 2:"
echo "  curl -X POST http://127.0.0.1:8081/api/session -d '{\"username\":\"admin\",\"password\":\"admin123\"}'"