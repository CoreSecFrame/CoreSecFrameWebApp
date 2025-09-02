"""
Simple Bettercap Manager
A more robust and simple implementation for managing Bettercap
"""

import subprocess
import time
import requests
import logging
from typing import Dict, List, Any, Optional


class SimpleBettercapManager:
    """Simple and robust Bettercap manager"""
    
    def __init__(self):
        self.api_url = "http://127.0.0.1:8081"
        self.username = "admin"
        self.password = "admin123"
        self.process = None
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        self.session_token = None
        
        # Simple state
        self.discovered_hosts = []
        self.active_attacks = {}
        self.current_interface = None
        
    def check_bettercap_installed(self) -> tuple[bool, str]:
        """Check if Bettercap is installed and accessible"""
        try:
            # Try to run bettercap --version
            result = subprocess.run(
                ["bettercap", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, f"Bettercap installed: {version}"
            else:
                return False, f"Bettercap command failed: {result.stderr}"
                
        except FileNotFoundError:
            return False, "Bettercap not found in PATH. Please install Bettercap."
        except subprocess.TimeoutExpired:
            return False, "Bettercap version check timed out"
        except Exception as e:
            return False, f"Error checking Bettercap: {e}"

    def start_bettercap(self, interface: str = None, api_port: int = 8081, sudo_password: str = None) -> bool:
        """Start Bettercap with given interface"""
        try:
            if self.is_running:
                return True
            
            # Check if Bettercap is installed
            installed, message = self.check_bettercap_installed()
            if not installed:
                self.logger.error(message)
                return False
            else:
                self.logger.info(message)
                
            # Build command with correct arguments
            cmd = ["bettercap"]
            if interface:
                cmd.extend(["-iface", interface])
            
            # Add REST API arguments
            cmd.extend([
                "-eval", f"set api.rest.on true; set api.rest.port {api_port}; set api.rest.username {self.username}; set api.rest.password {self.password}"
            ])
            
            self.logger.info(f"Starting Bettercap: {' '.join(cmd)}")
            
            if sudo_password:
                # Run with sudo
                sudo_cmd = ["sudo", "-S"] + cmd
                self.process = subprocess.Popen(
                    sudo_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                # Send password
                self.process.stdin.write(sudo_password + '\n')
                self.process.stdin.flush()
            else:
                # Run normally
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            # Wait for startup
            time.sleep(5)
            
            # Check if it's running
            if self.process.poll() is None:
                # Process is running, now test API
                time.sleep(2)  # Give API time to start
                
                # Test API connection
                try:
                    test_response = requests.get(f"{self.api_url}/api/session", timeout=3)
                    if test_response.status_code in [200, 401]:  # 401 means API is up but not authenticated
                        self.is_running = True
                        self.current_interface = interface
                        self.logger.info(f"Bettercap started successfully on {interface}")
                        return True
                except requests.RequestException:
                    pass
                
                # If we get here, API is not responding
                self.logger.warning("Bettercap process started but API is not responding")
                self.is_running = True  # Assume it's working for now
                self.current_interface = interface
                return True
            else:
                # Process failed to start
                try:
                    stdout, stderr = self.process.communicate(timeout=2)
                    error_output = stderr or stdout or "Unknown error"
                except subprocess.TimeoutExpired:
                    error_output = "Process startup timeout"
                    
                self.logger.error(f"Bettercap failed to start: {error_output}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting Bettercap: {e}")
            return False
    
    def stop_bettercap(self) -> bool:
        """Stop Bettercap"""
        try:
            if not self.is_running or not self.process:
                return True
                
            self.process.terminate()
            time.sleep(2)
            
            # Force kill if still running
            if self.process.poll() is None:
                self.process.kill()
                
            self.is_running = False
            self.current_interface = None
            self.session_token = None
            self.process = None
            
            self.logger.info("Bettercap stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping Bettercap: {e}")
            return False
    
    def sync_status(self) -> bool:
        """Synchronize status with actual Bettercap process"""
        try:
            # Check if process is actually running
            if self.process and self.process.poll() is None:
                # Process is running, check API
                try:
                    response = requests.get(f"{self.api_url}/api/session", timeout=2)
                    if response.status_code in [200, 401]:
                        self.is_running = True
                        return True
                except:
                    pass
                    
            # If we get here, either process is dead or API is not responding
            self.is_running = False
            self.current_interface = None
            self.session_token = None
            
            if self.process:
                try:
                    self.process.terminate()
                except:
                    pass
                self.process = None
                
            return False
            
        except Exception as e:
            self.logger.error(f"Status sync error: {e}")
            return False

    def get_attack_status(self) -> Dict[str, Any]:
        """Get current attack status"""
        # Sync status first
        self.sync_status()
        
        return {
            'is_running': self.is_running,
            'current_interface': self.current_interface,
            'active_attacks': self.active_attacks,
            'discovered_hosts': self.discovered_hosts
        }
    
    def get_network_interfaces(self) -> List[Dict[str, str]]:
        """Get available network interfaces"""
        try:
            import netifaces
            interfaces = []
            
            for interface in netifaces.interfaces():
                try:
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        ip = addrs[netifaces.AF_INET][0]['addr']
                        interfaces.append({
                            'name': interface,
                            'ip': ip
                        })
                except:
                    continue
                    
            return interfaces
        except ImportError:
            # Fallback method using system commands
            try:
                import os
                interfaces = []
                
                # Try ip command
                result = subprocess.run(['ip', '-4', 'addr', 'show'], 
                                      capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    current_interface = None
                    
                    for line in lines:
                        line = line.strip()
                        if ': ' in line and 'state UP' in line:
                            current_interface = line.split(':')[1].strip().split('@')[0]
                        elif 'inet ' in line and current_interface:
                            ip = line.split('inet ')[1].split('/')[0]
                            if not ip.startswith('127.'):
                                interfaces.append({
                                    'name': current_interface,
                                    'ip': ip
                                })
                            current_interface = None
                
                return interfaces
            except:
                # Ultimate fallback
                return [{'name': 'eth0', 'ip': '192.168.1.100'}]
    
    def authenticate(self) -> bool:
        """Authenticate with Bettercap API"""
        try:
            if not self.is_running:
                self.logger.error("Cannot authenticate: Bettercap is not running")
                return False
            
            # Check if we already have a valid session
            if self.session_token:
                # Test if session is still valid
                try:
                    cookies = {"session": self.session_token}
                    test_response = requests.get(f"{self.api_url}/api/session", cookies=cookies, timeout=3)
                    if test_response.status_code == 200:
                        self.logger.info("Existing session is still valid")
                        return True
                except:
                    self.logger.info("Existing session expired, re-authenticating")
                    self.session_token = None
            
            self.logger.info("Authenticating with Bettercap API")
            
            auth_data = {
                "username": self.username,
                "password": self.password
            }
            
            response = requests.post(
                f"{self.api_url}/api/session",
                json=auth_data,
                timeout=5
            )
            
            self.logger.info(f"Auth response status: {response.status_code}")
            
            if response.status_code == 200:
                self.session_token = response.cookies.get('session')
                if self.session_token:
                    self.logger.info("Authentication successful")
                    return True
                else:
                    self.logger.error("No session cookie received")
                    return False
            else:
                self.logger.error(f"Authentication failed with status: {response.status_code}")
                return False
            
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return False
    
    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a command via Bettercap API"""
        try:
            if not self.is_running:
                return {"success": False, "error": "Bettercap is not running"}
            
            self.logger.info(f"Executing command: {command}")
            
            # Ensure we have a valid session
            if not self.session_token:
                if not self.authenticate():
                    return {"success": False, "error": "Authentication failed"}
            
            cookies = {"session": self.session_token}
            
            # Use the correct endpoint for command execution
            response = requests.post(
                f"{self.api_url}/api/session",
                json={"cmd": command},
                cookies=cookies,
                timeout=10
            )
            
            self.logger.info(f"Command response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    self.logger.info(f"Command response data: {response_data}")
                    return {"success": True, "data": response_data}
                except ValueError as e:
                    # Response might not be JSON
                    self.logger.info(f"Command response (non-JSON): {response.text}")
                    return {"success": True, "data": response.text}
            elif response.status_code == 401:
                # Session expired, retry with new authentication
                self.logger.info("Session expired, re-authenticating and retrying")
                self.session_token = None
                if self.authenticate():
                    cookies = {"session": self.session_token}
                    response = requests.post(
                        f"{self.api_url}/api/session",
                        json={"cmd": command},
                        cookies=cookies,
                        timeout=10
                    )
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            return {"success": True, "data": response_data}
                        except ValueError:
                            return {"success": True, "data": response.text}
                
                return {"success": False, "error": "Authentication failed after retry"}
            else:
                self.logger.error(f"Command failed with status: {response.status_code}, response: {response.text}")
                return {"success": False, "error": f"Command failed: {response.status_code} - {response.text}"}
                
        except Exception as e:
            self.logger.error(f"Command execution error: {e}")
            return {"success": False, "error": str(e)}
    
    def start_network_discovery(self) -> Dict[str, Any]:
        """Start network discovery - simplified version"""
        try:
            if not self.is_running:
                return {"success": False, "error": "Bettercap is not running"}
            
            self.logger.info("Starting network discovery")
            
            # First ensure authentication
            if not self.authenticate():
                return {"success": False, "error": "Failed to authenticate with Bettercap API"}
            
            # Execute discovery commands one by one
            commands = ["net.recon on", "net.probe on"]
            failed_commands = []
            
            for cmd in commands:
                result = self.execute_command(cmd)
                self.logger.info(f"Command '{cmd}' result: {result}")
                
                if not result.get("success"):
                    failed_commands.append(cmd)
                    self.logger.error(f"Command '{cmd}' failed: {result.get('error')}")
                else:
                    self.logger.info(f"Command '{cmd}' executed successfully")
            
            if not failed_commands:
                self.active_attacks['network_discovery'] = True
                self.logger.info("Network discovery started successfully")
                return {"success": True, "message": "Network discovery started"}
            else:
                error_msg = f"Failed commands: {', '.join(failed_commands)}"
                self.logger.error(f"Network discovery failed: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            self.logger.error(f"Network discovery error: {e}")
            return {"success": False, "error": str(e)}
    
    def stop_network_discovery(self) -> Dict[str, Any]:
        """Stop network discovery"""
        try:
            result1 = self.execute_command("net.recon off")
            result2 = self.execute_command("net.probe off")
            
            self.active_attacks.pop('network_discovery', None)
            return {"success": True, "message": "Network discovery stopped"}
            
        except Exception as e:
            self.logger.error(f"Stop network discovery error: {e}")
            return {"success": False, "error": str(e)}
    
    def start_packet_sniffer(self, protocols: List[str], bpf_filter: str = "", max_packets: int = 0) -> Dict[str, Any]:
        """Start packet sniffer - simplified version"""
        try:
            if not self.is_running:
                return {"success": False, "error": "Bettercap is not running"}
            
            commands = []
            if bpf_filter:
                commands.append(f"set net.sniff.filter '{bpf_filter}'")
            
            commands.append("net.sniff on")
            
            for cmd in commands:
                result = self.execute_command(cmd)
                if not result.get("success"):
                    return {"success": False, "error": f"Command failed: {cmd}"}
            
            self.active_attacks['packet_sniffer'] = True
            return {"success": True, "message": "Packet sniffer started"}
            
        except Exception as e:
            self.logger.error(f"Packet sniffer error: {e}")
            return {"success": False, "error": str(e)}
    
    def stop_packet_sniffer(self) -> Dict[str, Any]:
        """Stop packet sniffer"""
        try:
            result = self.execute_command("net.sniff off")
            self.active_attacks.pop('packet_sniffer', None)
            return {"success": True, "message": "Packet sniffer stopped"}
            
        except Exception as e:
            self.logger.error(f"Stop packet sniffer error: {e}")
            return {"success": False, "error": str(e)}
    
    def start_arp_spoofing(self, target_ip: str, gateway_ip: str, bidirectional: bool = True) -> Dict[str, Any]:
        """Start ARP spoofing - simplified version"""
        try:
            if not self.is_running:
                return {"success": False, "error": "Bettercap is not running"}
            
            commands = [
                f"set arp.spoof.targets {target_ip}",
                "arp.spoof on"
            ]
            
            for cmd in commands:
                result = self.execute_command(cmd)
                if not result.get("success"):
                    return {"success": False, "error": f"Command failed: {cmd}"}
            
            self.active_attacks['arp_spoofing'] = {'target': target_ip, 'gateway': gateway_ip}
            return {"success": True, "message": "ARP spoofing started", "attack_id": "arp_1"}
            
        except Exception as e:
            self.logger.error(f"ARP spoofing error: {e}")
            return {"success": False, "error": str(e)}
    
    def stop_arp_spoofing(self) -> Dict[str, Any]:
        """Stop ARP spoofing"""
        try:
            result = self.execute_command("arp.spoof off")
            self.active_attacks.pop('arp_spoofing', None)
            return {"success": True, "message": "ARP spoofing stopped"}
            
        except Exception as e:
            self.logger.error(f"Stop ARP spoofing error: {e}")
            return {"success": False, "error": str(e)}
    
    def start_dns_spoofing(self, domain: str, spoofed_ip: str, all_domains: bool = False) -> Dict[str, Any]:
        """Start DNS spoofing - simplified version"""
        try:
            if not self.is_running:
                return {"success": False, "error": "Bettercap is not running"}
            
            commands = [
                f"set dns.spoof.address {spoofed_ip}",
                f"set dns.spoof.domains {domain}",
                "dns.spoof on"
            ]
            
            for cmd in commands:
                result = self.execute_command(cmd)
                if not result.get("success"):
                    return {"success": False, "error": f"Command failed: {cmd}"}
            
            self.active_attacks['dns_spoofing'] = {'domain': domain, 'spoofed_ip': spoofed_ip}
            return {"success": True, "message": "DNS spoofing started", "attack_id": "dns_1"}
            
        except Exception as e:
            self.logger.error(f"DNS spoofing error: {e}")
            return {"success": False, "error": str(e)}
    
    def stop_dns_spoofing(self) -> Dict[str, Any]:
        """Stop DNS spoofing"""
        try:
            result = self.execute_command("dns.spoof off")
            self.active_attacks.pop('dns_spoofing', None)
            return {"success": True, "message": "DNS spoofing stopped"}
            
        except Exception as e:
            self.logger.error(f"Stop DNS spoofing error: {e}")
            return {"success": False, "error": str(e)}
    
    def start_http_proxy(self, port: int = 8080, transparent: bool = False) -> Dict[str, Any]:
        """Start HTTP proxy - simplified version"""
        try:
            if not self.is_running:
                return {"success": False, "error": "Bettercap is not running"}
            
            commands = [
                f"set http.proxy.port {port}",
                "http.proxy on"
            ]
            
            for cmd in commands:
                result = self.execute_command(cmd)
                if not result.get("success"):
                    return {"success": False, "error": f"Command failed: {cmd}"}
            
            self.active_attacks['http_proxy'] = {'port': port}
            return {"success": True, "message": f"HTTP proxy started on port {port}"}
            
        except Exception as e:
            self.logger.error(f"HTTP proxy error: {e}")
            return {"success": False, "error": str(e)}
    
    def stop_http_proxy(self) -> Dict[str, Any]:
        """Stop HTTP proxy"""
        try:
            result = self.execute_command("http.proxy off")
            self.active_attacks.pop('http_proxy', None)
            return {"success": True, "message": "HTTP proxy stopped"}
            
        except Exception as e:
            self.logger.error(f"Stop HTTP proxy error: {e}")
            return {"success": False, "error": str(e)}
    
    def test_api_connection(self) -> Dict[str, Any]:
        """Test the API connection and basic commands"""
        try:
            if not self.is_running:
                return {"success": False, "error": "Bettercap is not running"}
            
            # Test authentication
            if not self.authenticate():
                return {"success": False, "error": "Authentication failed"}
            
            # Test basic commands
            test_results = {}
            
            # Test help command
            help_result = self.execute_command("help")
            test_results['help_command'] = help_result.get("success", False)
            
            # Test status command
            status_result = self.execute_command("active")
            test_results['status_command'] = status_result.get("success", False)
            
            # Test interface info
            iface_result = self.execute_command("net.show")
            test_results['interface_command'] = iface_result.get("success", False)
            
            success_count = sum(1 for v in test_results.values() if v)
            total_tests = len(test_results)
            
            return {
                "success": success_count > 0,
                "results": test_results,
                "summary": f"{success_count}/{total_tests} tests passed"
            }
            
        except Exception as e:
            self.logger.error(f"API test error: {e}")
            return {"success": False, "error": str(e)}

    def cleanup(self) -> bool:
        """Cleanup all operations"""
        try:
            # Stop all attacks
            self.stop_arp_spoofing()
            self.stop_dns_spoofing()
            self.stop_packet_sniffer()
            self.stop_http_proxy()
            self.stop_network_discovery()
            
            # Stop Bettercap
            self.stop_bettercap()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
            return False


# Global instance
simple_bettercap_manager = SimpleBettercapManager()