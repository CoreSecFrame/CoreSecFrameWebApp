#!/usr/bin/env python3
"""
BetterMITM Diagnostic Script
Helps diagnose issues with BetterMITM module and Bettercap integration
"""

import sys
import os
import subprocess
import time
import json
from pathlib import Path

# Try to import optional dependencies
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[WARNING] psutil not available. Network interface detection will be limited.")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[WARNING] requests not available. API testing will be skipped.")

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_status(message):
    print(f"[INFO] {message}")

def print_error(message):
    print(f"[ERROR] {message}")

def print_success(message):
    print(f"[SUCCESS] {message}")

def print_warning(message):
    print(f"[WARNING] {message}")

def check_bettercap_installation():
    print_header("Checking Bettercap Installation")
    
    # Check if bettercap is in PATH
    if subprocess.run(['which', 'bettercap'], capture_output=True).returncode == 0:
        bettercap_path = subprocess.run(['which', 'bettercap'], capture_output=True, text=True).stdout.strip()
        print_success(f"Bettercap found at: {bettercap_path}")
        
        # Check version
        try:
            result = subprocess.run(['bettercap', '-version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print_success(f"Version: {result.stdout.strip()}")
            else:
                print_warning(f"Version check failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            print_warning("Bettercap version check timed out")
        except Exception as e:
            print_error(f"Error checking version: {e}")
            
        # Check capabilities
        try:
            result = subprocess.run(['getcap', bettercap_path], capture_output=True, text=True)
            if 'cap_net_raw,cap_net_admin' in result.stdout:
                print_success("Network capabilities are set correctly")
            else:
                print_warning("Network capabilities not set - may need to run as root")
                print_status(f"Run: sudo setcap cap_net_raw,cap_net_admin=eip {bettercap_path}")
        except Exception as e:
            print_error(f"Error checking capabilities: {e}")
            
    else:
        print_error("Bettercap not found in PATH")
        return False
        
    return True

def check_network_interfaces():
    print_header("Checking Network Interfaces")
    
    if not PSUTIL_AVAILABLE:
        print_status("Using system commands to check interfaces...")
        try:
            # Use ip command as fallback
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                interfaces = []
                current_interface = None
                
                for line in lines:
                    if ': ' in line and 'inet ' not in line:
                        parts = line.split(': ')
                        if len(parts) >= 2:
                            current_interface = parts[1].split('@')[0]
                    elif 'inet ' in line and current_interface:
                        inet_part = line.strip().split(' ')[1]
                        ip = inet_part.split('/')[0]
                        interfaces.append({'name': current_interface, 'ip': ip})
                        print_success(f"  {current_interface}: {ip}")
                
                if interfaces:
                    print_status(f"Found {len(interfaces)} network interfaces with IP addresses")
                    return interfaces
                else:
                    print_error("No valid interfaces found")
                    return False
            else:
                print_error("Failed to get network interfaces")
                return False
        except Exception as e:
            print_error(f"Error checking interfaces: {e}")
            return False
    
    try:
        interfaces = psutil.net_if_addrs()
        print_status(f"Found {len(interfaces)} network interfaces:")
        
        valid_interfaces = []
        for interface, addrs in interfaces.items():
            has_ipv4 = False
            for addr in addrs:
                if addr.family == 2:  # IPv4
                    has_ipv4 = True
                    valid_interfaces.append({
                        'name': interface,
                        'ip': addr.address,
                        'netmask': addr.netmask
                    })
                    print_success(f"  {interface}: {addr.address}/{addr.netmask}")
                    break
            
            if not has_ipv4:
                print_warning(f"  {interface}: No IPv4 address")
        
        if not valid_interfaces:
            print_error("No valid IPv4 interfaces found")
            return False
            
        return valid_interfaces
        
    except Exception as e:
        print_error(f"Error checking interfaces: {e}")
        return False

def test_bettercap_start():
    print_header("Testing Bettercap Startup")
    
    # Test basic startup
    print_status("Testing basic Bettercap startup...")
    
    try:
        # Start Bettercap with API
        cmd = [
            'bettercap',
            '-eval',
            'api.rest on; set api.rest.port 8082; set api.rest.username admin; set api.rest.password admin123; sleep 2; api.rest off; quit'
        ]
        
        print_status(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print_success("Bettercap started and stopped successfully")
            if 'REST API server starting on' in result.stdout:
                print_success("REST API was enabled successfully")
            return True
        else:
            print_error(f"Bettercap failed to start: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print_error("Bettercap startup timed out")
        return False
    except Exception as e:
        print_error(f"Error testing Bettercap: {e}")
        return False

def test_api_connection():
    print_header("Testing Bettercap API Connection")
    
    if not REQUESTS_AVAILABLE:
        print_warning("Requests library not available, skipping API test")
        print_status("You can test manually with:")
        print_status("  1. Start bettercap: bettercap -eval 'api.rest on'")
        print_status("  2. Test: curl -X POST http://127.0.0.1:8081/api/session -d '{\"username\":\"admin\",\"password\":\"admin123\"}'")
        return True  # Don't fail the test if we can't run it
    
    print_status("Starting Bettercap with API...")
    
    # Start Bettercap in background
    try:
        process = subprocess.Popen([
            'bettercap',
            '-eval',
            'api.rest on; set api.rest.port 8082; set api.rest.username admin; set api.rest.password admin123'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for API to start
        time.sleep(3)
        
        # Test API connection
        try:
            response = requests.post(
                'http://127.0.0.1:8082/api/session',
                json={'username': 'admin', 'password': 'admin123'},
                timeout=5
            )
            
            if response.status_code == 200:
                print_success("API authentication successful")
                
                # Test command execution
                session_cookie = response.cookies.get('session')
                if session_cookie:
                    cmd_response = requests.post(
                        'http://127.0.0.1:8082/api/session',
                        json={'cmd': 'help'},
                        cookies={'session': session_cookie},
                        timeout=5
                    )
                    
                    if cmd_response.status_code == 200:
                        print_success("Command execution successful")
                        return True
                    else:
                        print_error(f"Command execution failed: {cmd_response.status_code}")
                else:
                    print_error("No session cookie received")
            else:
                print_error(f"API authentication failed: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print_error("Could not connect to Bettercap API")
        except requests.exceptions.Timeout:
            print_error("API connection timed out")
        except Exception as e:
            print_error(f"API test error: {e}")
        
    except Exception as e:
        print_error(f"Error starting Bettercap: {e}")
    finally:
        # Clean up process
        if 'process' in locals():
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass
    
    return False

def check_bettercap_config():
    print_header("Checking Bettercap Configuration")
    
    config_path = Path.home() / '.bettercap' / 'config.yml'
    
    if config_path.exists():
        print_success(f"Config file found: {config_path}")
        try:
            with open(config_path, 'r') as f:
                content = f.read()
                if 'api:' in content and 'rest:' in content:
                    print_success("API configuration found in config file")
                else:
                    print_warning("API configuration not found in config file")
        except Exception as e:
            print_error(f"Error reading config file: {e}")
    else:
        print_warning("No Bettercap config file found")
        print_status("Creating default configuration...")
        
        try:
            config_path.parent.mkdir(exist_ok=True)
            
            config_content = """# Bettercap Configuration for BetterMITM
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
"""
            
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            config_path.chmod(0o600)
            print_success(f"Default config created at: {config_path}")
            
        except Exception as e:
            print_error(f"Error creating config file: {e}")

def check_permissions():
    print_header("Checking Permissions")
    
    # Check if running as root
    if os.geteuid() == 0:
        print_warning("Running as root - this should work but is not recommended")
    else:
        print_status("Running as non-root user")
        
        # Check capabilities
        bettercap_path = subprocess.run(['which', 'bettercap'], capture_output=True, text=True).stdout.strip()
        if bettercap_path:
            try:
                result = subprocess.run(['getcap', bettercap_path], capture_output=True, text=True)
                if 'cap_net_raw,cap_net_admin' in result.stdout:
                    print_success("Network capabilities are properly set")
                else:
                    print_error("Network capabilities not set")
                    print_status("Run this to fix:")
                    print_status(f"sudo setcap cap_net_raw,cap_net_admin=eip {bettercap_path}")
            except Exception as e:
                print_error(f"Error checking capabilities: {e}")

def main():
    print("BetterMITM Diagnostic Tool")
    print("=" * 50)
    
    # Run all checks
    checks = [
        check_bettercap_installation,
        check_network_interfaces,
        check_permissions,
        check_bettercap_config,
        test_bettercap_start,
        test_api_connection
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print_error(f"Check failed with exception: {e}")
            results.append(False)
    
    # Summary
    print_header("Diagnostic Summary")
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print_status(f"Checks passed: {passed}/{total}")
    
    if passed == total:
        print_success("All checks passed! BetterMITM should work correctly.")
    elif passed >= total - 1:
        print_warning("Most checks passed. BetterMITM might work with minor issues.")
    else:
        print_error("Multiple checks failed. BetterMITM likely won't work properly.")
        print_status("\nCommon solutions:")
        print_status("1. Install Bettercap: sudo apt install bettercap")
        print_status("2. Set capabilities: sudo setcap cap_net_raw,cap_net_admin=eip $(which bettercap)")
        print_status("3. Check network interfaces: ip link show")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Diagnostic interrupted by user")
    except Exception as e:
        print_error(f"Diagnostic failed: {e}")
        sys.exit(1)