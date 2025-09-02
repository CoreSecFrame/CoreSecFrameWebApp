"""
Device Tracker
Manages network device discovery and tracking
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
import logging


class DeviceTracker:
    """Tracks discovered network devices and their properties"""
    
    def __init__(self):
        self.devices = {}  # MAC -> device info
        self.ip_to_mac = {}  # IP -> MAC mapping
        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()
        
        # Device tracking settings
        self.device_timeout = 300  # 5 minutes
        self.cleanup_interval = 60  # 1 minute
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_stale_devices, daemon=True)
        self.cleanup_thread.start()

    def add_device(self, device_info: Dict[str, Any]) -> bool:
        """Add or update a device"""
        try:
            with self.lock:
                mac = device_info.get('mac', '').lower()
                ip = device_info.get('ip')
                
                if not mac and not ip:
                    return False
                
                # Generate MAC if not provided (for IP-only entries)
                if not mac and ip:
                    mac = f"unknown_{ip.replace('.', '_')}"
                
                # Update device info
                now = datetime.now()
                
                if mac in self.devices:
                    # Update existing device
                    existing = self.devices[mac]
                    existing.update(device_info)
                    existing['last_seen'] = now.isoformat()
                    existing['updated_at'] = now.isoformat()
                else:
                    # Add new device
                    self.devices[mac] = {
                        'mac': mac,
                        'ip': ip,
                        'hostname': device_info.get('hostname', ''),
                        'vendor': device_info.get('vendor', 'Unknown'),
                        'os': device_info.get('os', ''),
                        'device_type': device_info.get('device_type', 'Unknown'),
                        'first_seen': now.isoformat(),
                        'last_seen': now.isoformat(),
                        'updated_at': now.isoformat(),
                        'packets_sent': device_info.get('packets_sent', 0),
                        'packets_received': device_info.get('packets_received', 0),
                        'bytes_sent': device_info.get('bytes_sent', 0),
                        'bytes_received': device_info.get('bytes_received', 0),
                        'open_ports': device_info.get('open_ports', []),
                        'services': device_info.get('services', {}),
                        'is_gateway': device_info.get('is_gateway', False),
                        'is_broadcast': device_info.get('is_broadcast', False),
                        'targeted': device_info.get('targeted', False),
                        'attacks': device_info.get('attacks', {}),
                        'notes': device_info.get('notes', ''),
                        'risk_level': device_info.get('risk_level', 'low'),
                        'status': 'online'
                    }
                
                # Update IP mapping
                if ip:
                    self.ip_to_mac[ip] = mac
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error adding device: {e}")
            return False

    def get_device_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get device by IP address"""
        with self.lock:
            mac = self.ip_to_mac.get(ip)
            if mac:
                return self.devices.get(mac)
            return None

    def get_device_by_mac(self, mac: str) -> Optional[Dict[str, Any]]:
        """Get device by MAC address"""
        with self.lock:
            return self.devices.get(mac.lower())

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all tracked devices"""
        with self.lock:
            return list(self.devices.values())

    def get_active_devices(self, minutes: int = 10) -> List[Dict[str, Any]]:
        """Get devices active within the last N minutes"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        with self.lock:
            active_devices = []
            for device in self.devices.values():
                try:
                    last_seen = datetime.fromisoformat(device['last_seen'])
                    if last_seen > cutoff:
                        active_devices.append(device)
                except:
                    continue
            
            return active_devices

    def get_targeted_devices(self) -> List[Dict[str, Any]]:
        """Get devices marked for targeting"""
        with self.lock:
            return [device for device in self.devices.values() if device.get('targeted', False)]

    def update_device_stats(self, ip: str, packets_sent: int = 0, packets_received: int = 0,
                           bytes_sent: int = 0, bytes_received: int = 0) -> bool:
        """Update device network statistics"""
        try:
            device = self.get_device_by_ip(ip)
            if device:
                with self.lock:
                    device['packets_sent'] += packets_sent
                    device['packets_received'] += packets_received
                    device['bytes_sent'] += bytes_sent
                    device['bytes_received'] += bytes_received
                    device['last_seen'] = datetime.now().isoformat()
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error updating device stats: {e}")
            return False

    def update_device_attack_status(self, ip: str, attack_type: str, active: bool) -> bool:
        """Update device attack status"""
        try:
            device = self.get_device_by_ip(ip)
            if device:
                with self.lock:
                    if 'attacks' not in device:
                        device['attacks'] = {}
                    
                    device['attacks'][attack_type] = {
                        'active': active,
                        'started_at': datetime.now().isoformat() if active else device['attacks'].get(attack_type, {}).get('started_at'),
                        'stopped_at': None if active else datetime.now().isoformat()
                    }
                    
                    device['last_seen'] = datetime.now().isoformat()
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error updating attack status: {e}")
            return False

    def add_device_service(self, ip: str, port: int, service: str, version: str = '') -> bool:
        """Add discovered service to device"""
        try:
            device = self.get_device_by_ip(ip)
            if device:
                with self.lock:
                    if 'services' not in device:
                        device['services'] = {}
                    
                    device['services'][str(port)] = {
                        'service': service,
                        'version': version,
                        'discovered_at': datetime.now().isoformat()
                    }
                    
                    if port not in device.get('open_ports', []):
                        device.setdefault('open_ports', []).append(port)
                    
                    device['last_seen'] = datetime.now().isoformat()
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error adding service: {e}")
            return False

    def set_device_os(self, ip: str, os_info: str) -> bool:
        """Set device OS information"""
        try:
            device = self.get_device_by_ip(ip)
            if device:
                with self.lock:
                    device['os'] = os_info
                    device['last_seen'] = datetime.now().isoformat()
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting OS info: {e}")
            return False

    def set_device_vendor(self, mac: str, vendor: str) -> bool:
        """Set device vendor information"""
        try:
            device = self.get_device_by_mac(mac)
            if device:
                with self.lock:
                    device['vendor'] = vendor
                    device['last_seen'] = datetime.now().isoformat()
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error setting vendor: {e}")
            return False

    def mark_device_offline(self, ip: str) -> bool:
        """Mark device as offline"""
        try:
            device = self.get_device_by_ip(ip)
            if device:
                with self.lock:
                    device['status'] = 'offline'
                    device['last_seen'] = datetime.now().isoformat()
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error marking device offline: {e}")
            return False

    def remove_device(self, identifier: str) -> bool:
        """Remove device by IP or MAC"""
        try:
            with self.lock:
                # Try as IP first
                if identifier in self.ip_to_mac:
                    mac = self.ip_to_mac[identifier]
                    del self.ip_to_mac[identifier]
                    if mac in self.devices:
                        del self.devices[mac]
                    return True
                
                # Try as MAC
                mac = identifier.lower()
                if mac in self.devices:
                    # Remove IP mapping
                    device = self.devices[mac]
                    if device.get('ip') in self.ip_to_mac:
                        del self.ip_to_mac[device['ip']]
                    del self.devices[mac]
                    return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error removing device: {e}")
            return False

    def get_device_count(self) -> Dict[str, int]:
        """Get device count statistics"""
        with self.lock:
            total = len(self.devices)
            active = len(self.get_active_devices())
            targeted = len(self.get_targeted_devices())
            
            return {
                'total': total,
                'active': active,
                'targeted': targeted,
                'offline': total - active
            }

    def export_devices(self, format: str = 'json') -> str:
        """Export devices to various formats"""
        try:
            with self.lock:
                if format.lower() == 'json':
                    return json.dumps(self.devices, indent=2, default=str)
                elif format.lower() == 'csv':
                    import csv
                    import io
                    
                    output = io.StringIO()
                    if self.devices:
                        fieldnames = ['mac', 'ip', 'hostname', 'vendor', 'os', 'device_type', 
                                    'first_seen', 'last_seen', 'packets_sent', 'packets_received', 
                                    'status', 'targeted']
                        writer = csv.DictWriter(output, fieldnames=fieldnames)
                        writer.writeheader()
                        
                        for device in self.devices.values():
                            row = {field: device.get(field, '') for field in fieldnames}
                            writer.writerow(row)
                    
                    return output.getvalue()
                
            return ''
            
        except Exception as e:
            self.logger.error(f"Error exporting devices: {e}")
            return ''

    def import_devices(self, data: str, format: str = 'json') -> int:
        """Import devices from various formats"""
        try:
            imported_count = 0
            
            if format.lower() == 'json':
                devices_data = json.loads(data)
                
                for device_info in devices_data.values() if isinstance(devices_data, dict) else devices_data:
                    if self.add_device(device_info):
                        imported_count += 1
            
            return imported_count
            
        except Exception as e:
            self.logger.error(f"Error importing devices: {e}")
            return 0

    def clear_all(self):
        """Clear all tracked devices"""
        with self.lock:
            self.devices.clear()
            self.ip_to_mac.clear()

    def _cleanup_stale_devices(self):
        """Background thread to cleanup stale devices"""
        while True:
            try:
                time.sleep(self.cleanup_interval)
                
                cutoff = datetime.now() - timedelta(seconds=self.device_timeout)
                stale_devices = []
                
                with self.lock:
                    for mac, device in self.devices.items():
                        try:
                            last_seen = datetime.fromisoformat(device['last_seen'])
                            if last_seen < cutoff and not device.get('targeted', False):
                                stale_devices.append(mac)
                        except:
                            continue
                
                # Remove stale devices
                for mac in stale_devices:
                    try:
                        with self.lock:
                            if mac in self.devices:
                                device = self.devices[mac]
                                if device.get('ip') in self.ip_to_mac:
                                    del self.ip_to_mac[device['ip']]
                                del self.devices[mac]
                                self.logger.info(f"Removed stale device: {mac}")
                    except Exception as e:
                        self.logger.error(f"Error removing stale device {mac}: {e}")
                
            except Exception as e:
                self.logger.error(f"Cleanup thread error: {e}")
                time.sleep(60)  # Wait before retrying


# Global instance
device_tracker = DeviceTracker()