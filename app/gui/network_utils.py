# app/gui/network_utils.py
import socket
import netifaces
import ipaddress
from flask import request, current_app
from typing import Optional, List, Dict

class NetworkDetector:
    """Detector de información de red para GUI sessions"""
    
    @staticmethod
    def get_server_ip() -> str:
        """
        Obtiene la IP del servidor que debe usarse para conexiones VNC.
        Prioriza interfaces en este orden:
        1. IP desde la cual el cliente está accediendo (si es LAN)
        2. IP de interfaz ethernet principal
        3. IP de interfaz WiFi
        4. IP de cualquier interfaz activa
        5. localhost como fallback
        """
        try:
            # Intentar obtener la IP desde el request actual
            client_ip = NetworkDetector.get_client_ip()
            server_ip_for_client = NetworkDetector.get_best_server_ip_for_client(client_ip)
            
            if server_ip_for_client and server_ip_for_client != '127.0.0.1':
                current_app.logger.info(f"Using server IP {server_ip_for_client} for client {client_ip}")
                return server_ip_for_client
            
            # Fallback: obtener la mejor IP disponible
            best_ip = NetworkDetector.get_primary_network_ip()
            current_app.logger.info(f"Using primary network IP: {best_ip}")
            return best_ip
            
        except Exception as e:
            current_app.logger.error(f"Error detecting server IP: {e}")
            return '127.0.0.1'  # Ultimate fallback
    
    @staticmethod
    def get_client_ip() -> str:
        """Obtiene la IP real del cliente"""
        try:
            # Revisar headers de proxy primero
            forwarded_ips = request.headers.getlist("X-Forwarded-For")
            if forwarded_ips:
                # Tomar la primera IP (la original del cliente)
                client_ip = forwarded_ips[0].split(',')[0].strip()
                if NetworkDetector.is_valid_ip(client_ip):
                    return client_ip
            
            # Revisar otros headers comunes
            for header in ['X-Real-IP', 'X-Forwarded-For', 'CF-Connecting-IP']:
                if header in request.headers:
                    ip = request.headers[header].split(',')[0].strip()
                    if NetworkDetector.is_valid_ip(ip):
                        return ip
            
            # Usar la IP directa de Flask
            return request.remote_addr or '127.0.0.1'
            
        except Exception as e:
            current_app.logger.error(f"Error getting client IP: {e}")
            return '127.0.0.1'
    
    @staticmethod
    def get_best_server_ip_for_client(client_ip: str) -> Optional[str]:
        """
        Determina la mejor IP del servidor para un cliente específico
        """
        try:
            if not client_ip or client_ip == '127.0.0.1':
                return NetworkDetector.get_primary_network_ip()
            
            # Si el cliente es local, usar localhost
            if NetworkDetector.is_localhost(client_ip):
                return '127.0.0.1'
            
            # Obtener todas las interfaces del servidor
            server_interfaces = NetworkDetector.get_all_server_interfaces()
            
            # Si el cliente está en la misma red que alguna interfaz, usar esa IP
            for interface_ip, interface_info in server_interfaces.items():
                if NetworkDetector.are_in_same_network(client_ip, interface_ip, interface_info.get('netmask')):
                    current_app.logger.info(f"Client {client_ip} is in same network as interface {interface_ip}")
                    return interface_ip
            
            # Si no hay coincidencia de red, usar la IP principal
            return NetworkDetector.get_primary_network_ip()
            
        except Exception as e:
            current_app.logger.error(f"Error determining best server IP for client {client_ip}: {e}")
            return NetworkDetector.get_primary_network_ip()
    
    @staticmethod
    def get_primary_network_ip() -> str:
        """
        Obtiene la IP principal de la interfaz de red activa
        Prioriza: ethernet > wifi > cualquier otra
        """
        try:
            interfaces = NetworkDetector.get_all_server_interfaces()
            
            # Prioridades de interfaces
            priority_prefixes = ['eth', 'en', 'wlan', 'wlp', 'wifi']
            
            best_ip = None
            best_priority = 999
            
            for ip, info in interfaces.items():
                interface_name = info.get('interface', '').lower()
                
                # Saltar loopback
                if ip.startswith('127.') or interface_name.startswith('lo'):
                    continue
                
                # Asignar prioridad basada en el nombre de la interfaz
                priority = 999
                for i, prefix in enumerate(priority_prefixes):
                    if interface_name.startswith(prefix):
                        priority = i
                        break
                
                # Preferir interfaces con gateway
                if info.get('has_gateway'):
                    priority -= 100
                
                if priority < best_priority:
                    best_priority = priority
                    best_ip = ip
            
            if best_ip:
                return best_ip
            
            # Fallback: conectar a un servidor externo para determinar la IP de salida
            return NetworkDetector.get_outbound_ip()
            
        except Exception as e:
            current_app.logger.error(f"Error getting primary network IP: {e}")
            return '127.0.0.1'
    
    @staticmethod
    def get_all_server_interfaces() -> Dict[str, Dict]:
        """Obtiene todas las interfaces de red del servidor con su información"""
        interfaces = {}
        
        try:
            for interface_name in netifaces.interfaces():
                # Saltar interfaces loopback y virtuales comunes
                if interface_name.startswith(('lo', 'docker', 'br-', 'veth')):
                    continue
                
                interface_info = netifaces.ifaddresses(interface_name)
                
                # Buscar direcciones IPv4
                if netifaces.AF_INET in interface_info:
                    for addr_info in interface_info[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        if ip and not ip.startswith('127.'):
                            # Verificar si la interfaz tiene gateway (está conectada)
                            has_gateway = False
                            try:
                                gateways = netifaces.gateways()
                                if 'default' in gateways and netifaces.AF_INET in gateways['default']:
                                    default_gateway = gateways['default'][netifaces.AF_INET]
                                    if default_gateway[1] == interface_name:
                                        has_gateway = True
                            except:
                                pass
                            
                            interfaces[ip] = {
                                'interface': interface_name,
                                'netmask': addr_info.get('netmask'),
                                'broadcast': addr_info.get('broadcast'),
                                'has_gateway': has_gateway
                            }
            
            return interfaces
            
        except Exception as e:
            current_app.logger.error(f"Error getting server interfaces: {e}")
            return {}
    
    @staticmethod
    def get_outbound_ip() -> str:
        """Obtiene la IP que se usa para conexiones salientes"""
        try:
            # Conectar a un servidor DNS público para determinar la IP de salida
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            try:
                # Método alternativo
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)
            except Exception:
                return '127.0.0.1'
    
    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """Verifica si una string es una IP válida"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_localhost(ip: str) -> bool:
        """Verifica si una IP es localhost"""
        try:
            addr = ipaddress.ip_address(ip)
            return addr.is_loopback
        except ValueError:
            return ip in ['localhost', '127.0.0.1', '::1']
    
    @staticmethod
    def are_in_same_network(ip1: str, ip2: str, netmask: str = None) -> bool:
        """Verifica si dos IPs están en la misma red"""
        try:
            if not netmask:
                # Usar máscara por defecto basada en la clase de red
                addr = ipaddress.ip_address(ip2)
                if addr.is_private:
                    if str(addr).startswith('192.168.'):
                        netmask = '255.255.255.0'
                    elif str(addr).startswith('10.'):
                        netmask = '255.0.0.0'
                    elif str(addr).startswith('172.'):
                        netmask = '255.255.0.0'
                    else:
                        netmask = '255.255.255.0'
                else:
                    return False
            
            # Crear la red
            network = ipaddress.IPv4Network(f"{ip2}/{netmask}", strict=False)
            client_addr = ipaddress.IPv4Address(ip1)
            
            return client_addr in network
            
        except Exception as e:
            current_app.logger.error(f"Error checking if IPs {ip1} and {ip2} are in same network: {e}")
            return False
    
    @staticmethod
    def get_network_info() -> Dict:
        """Obtiene información completa de la red para debugging"""
        try:
            client_ip = NetworkDetector.get_client_ip()
            server_ip = NetworkDetector.get_server_ip()
            interfaces = NetworkDetector.get_all_server_interfaces()
            
            return {
                'client_ip': client_ip,
                'server_ip': server_ip,
                'recommended_host': server_ip,
                'interfaces': interfaces,
                'is_remote_client': not NetworkDetector.is_localhost(client_ip),
                'detection_method': 'automatic'
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting network info: {e}")
            return {
                'client_ip': '127.0.0.1',
                'server_ip': '127.0.0.1', 
                'recommended_host': '127.0.0.1',
                'interfaces': {},
                'is_remote_client': False,
                'detection_method': 'fallback',
                'error': str(e)
            }

class VNCConnectionHelper:
    """Helper para generar URLs y conexiones VNC con IPs correctas"""
    
    @staticmethod
    def get_vnc_host() -> str:
        """Obtiene el host que debe usarse para conexiones VNC"""
        return NetworkDetector.get_server_ip()
    
    @staticmethod
    def get_vnc_connection_string(port: int) -> str:
        """Genera string de conexión VNC"""
        host = VNCConnectionHelper.get_vnc_host()
        return f"{host}:{port}"
    
    @staticmethod
    def get_vnc_url(port: int) -> str:
        """Genera URL VNC"""
        host = VNCConnectionHelper.get_vnc_host()
        return f"vnc://{host}:{port}"
    
    @staticmethod
    def get_novnc_url(port: int, base_url: str = None) -> str:
        """Genera URL para noVNC web client"""
        host = VNCConnectionHelper.get_vnc_host()
        
        if not base_url:
            # Usar el mismo host que la webapp pero puerto diferente
            base_url = f"http://{host}:6080"
        
        return f"{base_url}/vnc.html?host={host}&port={port}&autoconnect=true&resize=scale"
    
    @staticmethod
    def get_connection_info(port: int, display_number: int = None) -> Dict:
        """Genera información completa de conexión"""
        host = VNCConnectionHelper.get_vnc_host()
        
        return {
            'host': host,
            'port': port,
            'display': f":{display_number}" if display_number else None,
            'connection_string': f"{host}:{port}",
            'vnc_url': f"vnc://{host}:{port}",
            'novnc_url': VNCConnectionHelper.get_novnc_url(port),
            'is_remote': not NetworkDetector.is_localhost(NetworkDetector.get_client_ip())
        }