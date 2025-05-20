#!/bin/bash

# Default configuration
DEFAULT_INTERVAL=1800  # 30 minutes
CHANGE_MAC=false
CHANGE_IP=false
USE_TOR=false
INTERFACE=""
TOR_USER="debian-tor"

# TOR configuration
TORRC="/etc/tor/torghostrc"
RESOLV="/etc/resolv.conf"
TORRC_CONFIG="
VirtualAddrNetwork 10.0.0.0/10
AutomapHostsOnResolve 1
TransPort 9040
DNSPort 5353
ControlPort 9051
RunAsDaemon 1
"
DNS_CONFIG="nameserver 127.0.0.1"

# Help function
show_help() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -h, --help           Show this help message"
    echo "  -i, --interface      Specify network interface (e.g., wlan0)"
    echo "  -t, --time           Interval in seconds between changes"
    echo "  -m, --mac            Enable MAC address change"
    echo "  -p, --ip             Enable IP address change"
    echo "  -T, --tor            Enable TOR routing"
    echo "  -s, --switch-tor     Switch TOR exit node"
    echo "  -x, --stop           Stop all services"
    echo ""
    echo "Example:"
    echo "  $0 -i wlan0 -t 600 -m -p -T"
    echo "  (Changes MAC, IP and uses TOR every 10 minutes on wlan0)"
}

# Function to get current public IP
get_current_ip() {
    curl -s https://api.ipify.org/?format=json | grep -o '"ip":"[^"]*' | cut -d'"' -f4
}

# Function to generate random MAC address
generate_random_mac() {
    printf '02:%02x:%02x:%02x:%02x:%02x\n' $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256))
}

# Configure TOR
setup_tor() {
    echo "📡 Setting up TOR..."
    
    # Backup original DNS
    cp $RESOLV ${RESOLV}.backup

    # Configure torrc file
    echo "$TORRC_CONFIG" > $TORRC
    
    # Configure DNS
    echo "$DNS_CONFIG" > $RESOLV
    
    # Stop existing TOR services
    systemctl stop tor
    fuser -k 9051/tcp > /dev/null 2>&1
    
    # Start TOR with new configuration
    sudo -u $TOR_USER tor -f $TORRC > /dev/null 2>&1 &
    
    # Configure iptables for TOR
    NON_TOR="192.168.1.0/24 192.168.0.0/24"
    TOR_UID=$(id -ur $TOR_USER)
    TRANS_PORT="9040"

    # Clear existing rules
    iptables -F
    iptables -t nat -F

    # Configure new rules
    iptables -t nat -A OUTPUT -m owner --uid-owner $TOR_UID -j RETURN
    iptables -t nat -A OUTPUT -p udp --dport 53 -j REDIRECT --to-ports 5353
    
    for NET in $NON_TOR 127.0.0.0/9 127.128.0.0/10; do
        iptables -t nat -A OUTPUT -d $NET -j RETURN
    done
    
    iptables -t nat -A OUTPUT -p tcp --syn -j REDIRECT --to-ports $TRANS_PORT
    iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    
    for NET in $NON_TOR 127.0.0.0/8; do
        iptables -A OUTPUT -d $NET -j ACCEPT
    done
    
    iptables -A OUTPUT -m owner --uid-owner $TOR_UID -j ACCEPT
    iptables -A OUTPUT -j REJECT

    echo "✅ TOR configured and activated"
}

# Function to switch TOR exit node
switch_tor_node() {
    echo "🔄 Switching TOR exit node..."
    # Use TOR control port to request new circuit
    echo -e "AUTHENTICATE\r\nSIGNAL NEWNYM\r\nQUIT" | nc 127.0.0.1 9051
    sleep 5  # Wait for new circuit to establish
    echo "✅ Exit node switched"
}

# Stop TOR and restore configuration
stop_tor() {
    echo "🛑 Stopping TOR..."
    
    # Restore original DNS
    if [ -f ${RESOLV}.backup ]; then
        mv ${RESOLV}.backup $RESOLV
    fi
    
    # Clean iptables
    iptables -P INPUT ACCEPT
    iptables -P FORWARD ACCEPT
    iptables -P OUTPUT ACCEPT
    iptables -t nat -F
    iptables -t mangle -F
    iptables -F
    iptables -X
    
    # Stop TOR process
    fuser -k 9051/tcp > /dev/null 2>&1
    systemctl stop tor
    
    echo "✅ TOR stopped and configuration restored"
}

# Function to change MAC address
change_mac() {
    local interface=$1
    local new_mac=$(generate_random_mac)
    
    echo "📱 Changing MAC address for $interface..."
    ip link set dev $interface down
    ip link set dev $interface address $new_mac
    ip link set dev $interface up
    
    echo "✅ New MAC: $new_mac"
}

# Function to change IP
change_ip() {
    local interface=$1
    echo "🌐 Changing IP address for $interface..."
    
    dhclient -r $interface
    dhclient $interface
    
    local new_ip=$(ip addr show dev $interface | grep 'inet ' | awk '{print $2}')
    echo "✅ New local IP: $new_ip"
}

# Verify root permissions
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "❌ This script must be run as root"
        exit 1
    fi
}

# Verify interface exists
check_interface() {
    if ! ip link show "$1" >/dev/null 2>&1; then
        echo "❌ Interface $1 does not exist"
        exit 1
    fi
}

# Check dependencies
check_dependencies() {
    local deps=("tor" "curl" "dhclient" "iptables")
    for dep in "${deps[@]}"; do
        if ! command -v $dep >/dev/null 2>&1; then
            echo "❌ Missing dependency: $dep"
            echo "📦 Install package using: apt install $dep"
            exit 1
        fi
    done
}

# Process arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -i|--interface)
            INTERFACE="$2"
            shift 2
            ;;
        -t|--time)
            DEFAULT_INTERVAL="$2"
            shift 2
            ;;
        -m|--mac)
            CHANGE_MAC=true
            shift
            ;;
        -p|--ip)
            CHANGE_IP=true
            shift
            ;;
        -T|--tor)
            USE_TOR=true
            shift
            ;;
        -s|--switch-tor)
            switch_tor_node
            exit 0
            ;;
        -x|--stop)
            stop_tor
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main function
main() {
    check_root
    check_dependencies
    
    # If no interface specified, detect the main one
    if [[ -z "$INTERFACE" ]]; then
        INTERFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
        echo "🔍 Using detected interface: $INTERFACE"
    fi
    
    check_interface "$INTERFACE"
    
    # Verify that at least one option is selected
    if ! $CHANGE_MAC && ! $CHANGE_IP && ! $USE_TOR; then
        echo "❌ You must specify at least one option (-m for MAC, -p for IP, or -T for TOR)"
        show_help
        exit 1
    fi
    
    echo "🚀 Starting script with the following configuration:"
    echo "- Interface: $INTERFACE"
    echo "- Interval: $DEFAULT_INTERVAL seconds"
    echo "- Change MAC: $CHANGE_MAC"
    echo "- Change IP: $CHANGE_IP"
    echo "- Use TOR: $USE_TOR"
    echo ""
    
    if $USE_TOR; then
        setup_tor
    fi
    
    while true; do
        echo "⏰ $(date): Starting changes..."
        
        if $CHANGE_MAC; then
            change_mac "$INTERFACE"
        fi
        
        if $CHANGE_IP; then
            change_ip "$INTERFACE"
        fi
        
        if $USE_TOR; then
            echo "🌍 Current public IP: $(get_current_ip)"
            switch_tor_node
            echo "🌍 New public IP: $(get_current_ip)"
        fi
        
        echo "💤 Waiting $DEFAULT_INTERVAL seconds..."
        sleep $DEFAULT_INTERVAL
    done
}

# Handle interruption signal
trap 'echo "⚠️ Stopping services..."; stop_tor; exit' INT

# Start the script
main
