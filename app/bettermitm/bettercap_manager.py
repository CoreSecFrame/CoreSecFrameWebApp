"""
Bettercap Manager
Handles communication with Bettercap via REST API and command execution
"""

import json
import time
import requests
import subprocess
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import psutil
import os
import signal


class BettercapManager:
    """Manages Bettercap instances and API communication"""
    
    def __init__(self):
        self.api_url = "http://127.0.0.1:8081"
        self.username = "admin"
        self.password = "admin123"
        self.session_token = None
        self.process = None
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        
        # Configure logging
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # State tracking
        self.discovered_hosts = {}
        self.active_attacks = {}
        self.captured_packets = []
        self.network_interfaces = []
        self.current_interface = None
        
        # Callbacks for real-time updates
        self.callbacks = {
            'host_discovered': [],
            'packet_captured': [],
            'attack_status': [],
            'error': []
        }

    def start_bettercap(self, interface: str = None, api_port: int = 8081, sudo_password: str = None) -> bool:
        """Start Bettercap with REST API enabled"""
        try:
            if self.is_running:
                self.logger.warning("Bettercap is already running")
                return True
            
            # Check if bettercap is available
            base_cmd = ['bettercap'] if not sudo_password else ['sudo', '-S', 'bettercap']
            try:
                test_cmd = ['bettercap', '-version'] if not sudo_password else ['sudo', '-n', 'bettercap', '-version']
                subprocess.run(test_cmd, capture_output=True, check=True, timeout=5)
            except subprocess.CalledProcessError as e:
                if sudo_password:
                    self.logger.info("Sudo access required for Bettercap (this is normal)")
                else:
                    self.logger.error(f"Bettercap version check failed: {e}")
                    return False
            except subprocess.TimeoutExpired:
                self.logger.error("Bettercap version check timed out")
                return False
            except FileNotFoundError:
                self.logger.error("Bettercap not found in PATH. Please install bettercap first.")
                return False
                
            # Build command
            cmd = base_cmd.copy()
            
            if interface:
                # Validate interface exists
                available_interfaces = [iface['name'] for iface in self.get_network_interfaces()]
                if interface not in available_interfaces:
                    self.logger.error(f"Interface '{interface}' not found. Available: {available_interfaces}")
                    return False
                cmd.extend(["-iface", interface])
                self.current_interface = interface
                
            # Enable REST API with more robust configuration
            api_config = [
                "api.rest on",
                f"set api.rest.port {api_port}",
                f"set api.rest.username {self.username}",
                f"set api.rest.password {self.password}",
                "set api.rest.allow-origin *"
            ]
            
            cmd.extend(["-eval", "; ".join(api_config)])
            
            # Start process
            self.logger.info(f"Starting Bettercap: {' '.join(cmd)}")
            
            if sudo_password:
                # Start process with sudo and password
                self.process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                # Send password to sudo
                try:
                    self.process.stdin.write(sudo_password + '\n')
                    self.process.stdin.flush()
                    self.process.stdin.close()
                except Exception as e:
                    self.logger.error(f"Failed to send sudo password: {e}")
                    self.process.terminate()
                    return False
            else:
                # Start process normally
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
            
            # Wait for process to start and check if it's still running
            time.sleep(2)
            if self.process.poll() is not None:
                # Process has already terminated
                stdout, stderr = self.process.communicate()
                self.logger.error(f"Bettercap process terminated immediately:")
                self.logger.error(f"STDOUT: {stdout}")
                self.logger.error(f"STDERR: {stderr}")
                return False
            
            # Update API URL
            self.api_url = f"http://127.0.0.1:{api_port}"
            
            # Wait for API to be ready with multiple attempts
            max_attempts = 10
            for attempt in range(max_attempts):
                self.logger.info(f"Attempting API connection (attempt {attempt + 1}/{max_attempts})")
                time.sleep(1)
                
                if self.authenticate():
                    self.is_running = True
                    self.logger.info("Bettercap started successfully")
                    
                    # Start monitoring thread
                    monitor_thread = threading.Thread(target=self._monitor_bettercap, daemon=True)
                    monitor_thread.start()
                    
                    return True
                
                # Check if process is still running
                if self.process.poll() is not None:
                    stdout, stderr = self.process.communicate()
                    self.logger.error(f"Bettercap process died during startup:")
                    self.logger.error(f"STDOUT: {stdout}")
                    self.logger.error(f"STDERR: {stderr}")
                    return False
            
            self.logger.error("Failed to authenticate with Bettercap API after multiple attempts")
            self.stop_bettercap()
            return False
                
        except Exception as e:
            self.logger.error(f"Failed to start Bettercap: {e}")
            if hasattr(self, 'process') and self.process:
                try:
                    stdout, stderr = self.process.communicate(timeout=1)
                    self.logger.error(f"Process output - STDOUT: {stdout}")
                    self.logger.error(f"Process output - STDERR: {stderr}")
                except:
                    pass
            return False

    def stop_bettercap(self) -> bool:
        """Stop Bettercap process"""
        try:
            if self.process:
                self.process.terminate()
                time.sleep(2)
                
                if self.process.poll() is None:
                    self.process.kill()
                    
                self.process = None
                
            self.is_running = False
            self.session_token = None
            self.logger.info("Bettercap stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping Bettercap: {e}")
            return False

    def authenticate(self) -> bool:
        """Authenticate with Bettercap API"""
        try:
            auth_data = {
                "username": self.username,
                "password": self.password
            }
            
            response = requests.post(
                f"{self.api_url}/api/session",
                json=auth_data,
                timeout=5
            )
            
            if response.status_code == 200:
                self.session_token = response.cookies.get('session')
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return False

    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a command via Bettercap API"""
        try:
            if not self.session_token:
                if not self.authenticate():
                    return {"success": False, "error": "Authentication failed"}
            
            cookies = {"session": self.session_token}
            
            response = requests.post(
                f"{self.api_url}/api/session",
                json={"cmd": command},
                cookies=cookies,
                timeout=10
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            return {"success": False, "error": str(e)}

    def get_network_interfaces(self) -> List[Dict[str, str]]:
        """Get available network interfaces"""
        interfaces = []
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == 2:  # IPv4
                        interfaces.append({
                            'name': interface,
                            'ip': addr.address,
                            'netmask': addr.netmask
                        })
                        break
        except Exception as e:
            self.logger.error(f"Error getting interfaces: {e}")
        
        return interfaces

    def start_network_discovery(self) -> Dict[str, Any]:
        """Start network discovery"""
        commands = [
            "net.recon on",
            "net.probe on"
        ]
        
        results = []
        for cmd in commands:
            result = self.execute_command(cmd)
            results.append(result)
        
        return {"success": all(r["success"] for r in results), "results": results}

    def stop_network_discovery(self) -> Dict[str, Any]:
        """Stop network discovery"""
        commands = [
            "net.recon off",
            "net.probe off"
        ]
        
        results = []
        for cmd in commands:
            result = self.execute_command(cmd)
            results.append(result)
        
        return {"success": all(r["success"] for r in results), "results": results}

    def get_discovered_hosts(self) -> List[Dict[str, Any]]:
        """Get list of discovered network hosts"""
        result = self.execute_command("net.show")
        
        if result["success"]:
            try:
                # Parse hosts from the response
                hosts = []
                # Implementation depends on Bettercap's response format
                return hosts
            except Exception as e:
                self.logger.error(f"Error parsing hosts: {e}")
        
        return []

    def start_arp_spoofing(self, target_ip: str, gateway_ip: str, bidirectional: bool = True) -> Dict[str, Any]:
        """Start ARP spoofing attack"""
        try:
            commands = [
                f"set arp.spoof.targets {target_ip}",
                "arp.spoof on"
            ]
            
            if bidirectional:
                commands.insert(1, f"set arp.spoof.fullduplex true")
            
            attack_id = f"arp_{target_ip}_{int(time.time())}"
            
            results = []
            for cmd in commands:
                result = self.execute_command(cmd)
                results.append(result)
            
            if all(r["success"] for r in results):
                self.active_attacks[attack_id] = {
                    'type': 'arp_spoofing',
                    'target_ip': target_ip,
                    'gateway_ip': gateway_ip,
                    'bidirectional': bidirectional,
                    'started': datetime.now(),
                    'status': 'active'
                }
                
                self._trigger_callback('attack_status', {
                    'attack_id': attack_id,
                    'type': 'arp_spoofing',
                    'status': 'started',
                    'target': target_ip
                })
            
            return {
                "success": all(r["success"] for r in results),
                "attack_id": attack_id,
                "results": results
            }
            
        except Exception as e:
            self.logger.error(f"ARP spoofing start failed: {e}")
            return {"success": False, "error": str(e)}

    def stop_arp_spoofing(self) -> Dict[str, Any]:
        """Stop ARP spoofing attack"""
        result = self.execute_command("arp.spoof off")
        
        # Update active attacks
        for attack_id, attack in self.active_attacks.items():
            if attack['type'] == 'arp_spoofing':
                attack['status'] = 'stopped'
                self._trigger_callback('attack_status', {
                    'attack_id': attack_id,
                    'type': 'arp_spoofing',
                    'status': 'stopped'
                })
        
        return result

    def start_dns_spoofing(self, domain: str, spoofed_ip: str, all_domains: bool = False) -> Dict[str, Any]:
        """Start DNS spoofing attack"""
        try:
            commands = []
            
            if all_domains:
                commands.append("set dns.spoof.all true")
            else:
                commands.append(f"set dns.spoof.domains {domain}")
                
            commands.extend([
                f"set dns.spoof.address {spoofed_ip}",
                "dns.spoof on"
            ])
            
            attack_id = f"dns_{domain}_{int(time.time())}"
            
            results = []
            for cmd in commands:
                result = self.execute_command(cmd)
                results.append(result)
            
            if all(r["success"] for r in results):
                self.active_attacks[attack_id] = {
                    'type': 'dns_spoofing',
                    'domain': domain,
                    'spoofed_ip': spoofed_ip,
                    'all_domains': all_domains,
                    'started': datetime.now(),
                    'status': 'active'
                }
                
                self._trigger_callback('attack_status', {
                    'attack_id': attack_id,
                    'type': 'dns_spoofing',
                    'status': 'started',
                    'domain': domain
                })
            
            return {
                "success": all(r["success"] for r in results),
                "attack_id": attack_id,
                "results": results
            }
            
        except Exception as e:
            self.logger.error(f"DNS spoofing start failed: {e}")
            return {"success": False, "error": str(e)}

    def stop_dns_spoofing(self) -> Dict[str, Any]:
        """Stop DNS spoofing attack"""
        result = self.execute_command("dns.spoof off")
        
        # Update active attacks
        for attack_id, attack in self.active_attacks.items():
            if attack['type'] == 'dns_spoofing':
                attack['status'] = 'stopped'
                self._trigger_callback('attack_status', {
                    'attack_id': attack_id,
                    'type': 'dns_spoofing',
                    'status': 'stopped'
                })
        
        return result

    def start_packet_sniffer(self, protocols: List[str], bpf_filter: str = "", max_packets: int = 0) -> Dict[str, Any]:
        """Start packet sniffing"""
        try:
            commands = []
            
            if bpf_filter:
                commands.append(f"set net.sniff.filter '{bpf_filter}'")
            
            commands.append("net.sniff on")
            
            results = []
            for cmd in commands:
                result = self.execute_command(cmd)
                results.append(result)
            
            return {"success": all(r["success"] for r in results), "results": results}
            
        except Exception as e:
            self.logger.error(f"Packet sniffer start failed: {e}")
            return {"success": False, "error": str(e)}

    def stop_packet_sniffer(self) -> Dict[str, Any]:
        """Stop packet sniffing"""
        return self.execute_command("net.sniff off")

    def start_http_proxy(self, port: int = 8080, transparent: bool = True) -> Dict[str, Any]:
        """Start HTTP proxy"""
        try:
            commands = [
                f"set http.proxy.port {port}",
                "http.proxy on"
            ]
            
            if transparent:
                commands.insert(1, "set http.proxy.transparent true")
            
            results = []
            for cmd in commands:
                result = self.execute_command(cmd)
                results.append(result)
            
            return {"success": all(r["success"] for r in results), "results": results}
            
        except Exception as e:
            self.logger.error(f"HTTP proxy start failed: {e}")
            return {"success": False, "error": str(e)}

    def stop_http_proxy(self) -> Dict[str, Any]:
        """Stop HTTP proxy"""
        return self.execute_command("http.proxy off")

    def get_attack_status(self) -> Dict[str, Any]:
        """Get status of all active attacks"""
        return {
            'is_running': self.is_running,
            'active_attacks': self.active_attacks,
            'discovered_hosts': len(self.discovered_hosts),
            'current_interface': self.current_interface
        }

    def register_callback(self, event_type: str, callback):
        """Register callback for real-time events"""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)

    def _trigger_callback(self, event_type: str, data: Any):
        """Trigger callbacks for an event"""
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")

    def _monitor_bettercap(self):
        """Monitor Bettercap process and events"""
        while self.is_running and self.process:
            try:
                # Check if process is still running
                if self.process.poll() is not None:
                    self.is_running = False
                    self._trigger_callback('error', "Bettercap process terminated")
                    break
                
                # Poll for events/updates
                # This would typically involve reading from Bettercap's event stream
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")
                time.sleep(5)

    def cleanup(self):
        """Cleanup resources"""
        try:
            self.stop_bettercap()
            self.callbacks.clear()
            self.active_attacks.clear()
            self.discovered_hosts.clear()
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")


# Global instance
bettercap_manager = BettercapManager()