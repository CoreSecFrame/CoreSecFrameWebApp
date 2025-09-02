"""
BetterMITM Routes
Flask routes for BetterMITM web interface
"""

import json
import time
from datetime import datetime
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from werkzeug.utils import secure_filename

from . import bettermitm_bp
from .forms import (
    NetworkScanForm, ARPSpoofingForm, DNSSpoofingForm, PacketSnifferForm,
    WiFiHandshakeForm, ProxyForm, DeviceTargetForm, BettercapScriptForm,
    NetworkConfigForm
)
from .simple_manager import simple_bettercap_manager as bettercap_manager
from .device_tracker import device_tracker


@bettermitm_bp.route('/')
@login_required
def index():
    """Main BetterMITM interface"""
    # Get all forms for the interface
    network_scan_form = NetworkScanForm()
    arp_spoof_form = ARPSpoofingForm()
    dns_spoof_form = DNSSpoofingForm()
    packet_sniffer_form = PacketSnifferForm()
    wifi_form = WiFiHandshakeForm()
    proxy_form = ProxyForm()
    device_form = DeviceTargetForm()
    script_form = BettercapScriptForm()
    config_form = NetworkConfigForm()
    
    # Populate interface choices
    interfaces = bettercap_manager.get_network_interfaces()
    interface_choices = [(iface['name'], f"{iface['name']} ({iface['ip']})") for iface in interfaces]
    
    # Update form choices
    for form in [network_scan_form, arp_spoof_form, dns_spoof_form, 
                 packet_sniffer_form, wifi_form, proxy_form]:
        if hasattr(form, 'interface'):
            form.interface.choices = interface_choices
    
    return render_template('bettermitm/index.html',
                         network_scan_form=network_scan_form,
                         arp_spoof_form=arp_spoof_form,
                         dns_spoof_form=dns_spoof_form,
                         packet_sniffer_form=packet_sniffer_form,
                         wifi_form=wifi_form,
                         proxy_form=proxy_form,
                         device_form=device_form,
                         script_form=script_form,
                         config_form=config_form,
                         interfaces=interfaces)


@bettermitm_bp.route('/api/status')
@login_required
def api_status():
    """Get current Bettercap status"""
    try:
        status = bettercap_manager.get_attack_status()
        discovered_hosts = device_tracker.get_all_devices()
        
        return jsonify({
            'success': True,
            'bettercap_running': status['is_running'],
            'active_attacks': status['active_attacks'],
            'discovered_hosts': discovered_hosts,
            'current_interface': status['current_interface'],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/start', methods=['POST'])
@login_required
def api_start_bettercap():
    """Start Bettercap instance"""
    try:
        data = request.get_json() or {}
        interface = data.get('interface')
        api_port = data.get('api_port', 8081)
        sudo_password = data.get('sudo_password')  # Optional sudo password
        
        # Check if Bettercap is installed first
        installed, check_message = bettercap_manager.check_bettercap_installed()
        if not installed:
            return jsonify({
                'success': False,
                'error': check_message
            }), 400
        
        # Try to start Bettercap
        success = bettercap_manager.start_bettercap(interface, api_port, sudo_password)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Bettercap started successfully',
                'interface': interface,
                'sudo_used': bool(sudo_password)
            })
        else:
            # Get more specific error from logs
            error_msg = 'Failed to start Bettercap. '
            if not sudo_password:
                error_msg += 'Try using sudo if you have permission issues.'
            else:
                error_msg += 'Check if the sudo password is correct and Bettercap has proper permissions.'
                
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }), 500


@bettermitm_bp.route('/api/stop', methods=['POST'])
@login_required
def api_stop_bettercap():
    """Stop Bettercap instance"""
    try:
        if bettercap_manager.stop_bettercap():
            return jsonify({
                'success': True,
                'message': 'Bettercap stopped successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to stop Bettercap'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/scan/start', methods=['POST'])
@login_required
def api_start_scan():
    """Start network discovery scan"""
    try:
        # Check if Bettercap is running
        if not bettercap_manager.is_running:
            return jsonify({
                'success': False,
                'error': 'Bettercap is not running. Please start Bettercap first.'
            }), 400
        
        data = request.get_json() or {}
        scan_type = data.get('scan_type', 'arp')
        target_range = data.get('target_range')
        
        # Try to start network discovery
        try:
            result = bettercap_manager.start_network_discovery()
            
            if result and result.get('success'):
                return jsonify({
                    'success': True,
                    'message': f'Network scan started ({scan_type})',
                    'scan_type': scan_type,
                    'target_range': target_range
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to start network scan: {result.get("error", "Unknown error") if result else "No response from Bettercap"}'
                }), 500
                
        except Exception as scan_error:
            return jsonify({
                'success': False,
                'error': f'Network scan error: {str(scan_error)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'General error: {str(e)}'
        }), 500


@bettermitm_bp.route('/api/scan/stop', methods=['POST'])
@login_required
def api_stop_scan():
    """Stop network discovery scan"""
    try:
        result = bettercap_manager.stop_network_discovery()
        
        return jsonify({
            'success': result['success'],
            'message': 'Network scan stopped' if result['success'] else 'Failed to stop scan'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/hosts')
@login_required
def api_get_hosts():
    """Get discovered network hosts"""
    try:
        hosts = device_tracker.get_all_devices()
        
        return jsonify({
            'success': True,
            'hosts': hosts,
            'count': len(hosts),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/arp/start', methods=['POST'])
@login_required
def api_start_arp_spoof():
    """Start ARP spoofing attack"""
    try:
        form = ARPSpoofingForm()
        if form.validate_on_submit():
            result = bettercap_manager.start_arp_spoofing(
                target_ip=form.target_ip.data,
                gateway_ip=form.gateway_ip.data,
                bidirectional=form.bidirectional.data
            )
            
            if result['success']:
                device_tracker.update_device_attack_status(
                    form.target_ip.data, 'arp_spoofing', True
                )
                
                return jsonify({
                    'success': True,
                    'message': f'ARP spoofing started against {form.target_ip.data}',
                    'attack_id': result['attack_id']
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'ARP spoofing failed')
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Form validation failed',
                'errors': form.errors
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/arp/stop', methods=['POST'])
@login_required
def api_stop_arp_spoof():
    """Stop ARP spoofing attack"""
    try:
        result = bettercap_manager.stop_arp_spoofing()
        
        # Update device attack statuses
        for device in device_tracker.get_all_devices():
            if device.get('attacks', {}).get('arp_spoofing'):
                device_tracker.update_device_attack_status(
                    device['ip'], 'arp_spoofing', False
                )
        
        return jsonify({
            'success': result['success'],
            'message': 'ARP spoofing stopped' if result['success'] else 'Failed to stop ARP spoofing'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/dns/start', methods=['POST'])
@login_required
def api_start_dns_spoof():
    """Start DNS spoofing attack"""
    try:
        form = DNSSpoofingForm()
        if form.validate_on_submit():
            result = bettercap_manager.start_dns_spoofing(
                domain=form.target_domain.data,
                spoofed_ip=form.spoofed_ip.data,
                all_domains=form.all_domains.data
            )
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': f'DNS spoofing started for {form.target_domain.data}',
                    'attack_id': result['attack_id']
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'DNS spoofing failed')
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Form validation failed',
                'errors': form.errors
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/dns/stop', methods=['POST'])
@login_required
def api_stop_dns_spoof():
    """Stop DNS spoofing attack"""
    try:
        result = bettercap_manager.stop_dns_spoofing()
        
        return jsonify({
            'success': result['success'],
            'message': 'DNS spoofing stopped' if result['success'] else 'Failed to stop DNS spoofing'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/sniffer/start', methods=['POST'])
@login_required
def api_start_sniffer():
    """Start packet sniffer"""
    try:
        # Check if Bettercap is running
        if not bettercap_manager.is_running:
            return jsonify({
                'success': False,
                'error': 'Bettercap is not running. Please start Bettercap first.'
            }), 400
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json() or {}
            protocols = data.get('protocols', ['tcp', 'udp'])
            bpf_filter = data.get('bpf_filter', '')
            max_packets = data.get('max_packets', 100)
        else:
            form = PacketSnifferForm()
            if not form.validate_on_submit():
                return jsonify({
                    'success': False,
                    'error': 'Form validation failed',
                    'errors': form.errors
                }), 400
            protocols = form.protocols.data
            bpf_filter = form.filter_expression.data
            max_packets = form.max_packets.data
        
        # Try to start packet sniffer
        try:
            result = bettercap_manager.start_packet_sniffer(
                protocols=protocols,
                bpf_filter=bpf_filter,
                max_packets=max_packets
            )
            
            if result and result.get('success'):
                return jsonify({
                    'success': True,
                    'message': 'Packet sniffer started'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to start sniffer: {result.get("error", "Unknown error") if result else "No response from Bettercap"}'
                }), 500
                
        except Exception as sniffer_error:
            return jsonify({
                'success': False,
                'error': f'Packet sniffer error: {str(sniffer_error)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'General error: {str(e)}'
        }), 500


@bettermitm_bp.route('/api/sniffer/stop', methods=['POST'])
@login_required
def api_stop_sniffer():
    """Stop packet sniffer"""
    try:
        result = bettercap_manager.stop_packet_sniffer()
        
        return jsonify({
            'success': result['success'],
            'message': 'Packet sniffer stopped' if result['success'] else 'Failed to stop sniffer'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/proxy/start', methods=['POST'])
@login_required
def api_start_proxy():
    """Start HTTP proxy"""
    try:
        form = ProxyForm()
        if form.validate_on_submit():
            result = bettercap_manager.start_http_proxy(
                port=form.proxy_port.data,
                transparent=form.transparent.data
            )
            
            return jsonify({
                'success': result['success'],
                'message': f'HTTP proxy started on port {form.proxy_port.data}' if result['success'] else 'Failed to start proxy'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Form validation failed',
                'errors': form.errors
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/proxy/stop', methods=['POST'])
@login_required
def api_stop_proxy():
    """Stop HTTP proxy"""
    try:
        result = bettercap_manager.stop_http_proxy()
        
        return jsonify({
            'success': result['success'],
            'message': 'HTTP proxy stopped' if result['success'] else 'Failed to stop proxy'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/command', methods=['POST'])
@login_required
def api_execute_command():
    """Execute custom Bettercap command"""
    try:
        data = request.get_json() or {}
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({
                'success': False,
                'error': 'No command provided'
            }), 400
        
        result = bettercap_manager.execute_command(command)
        
        return jsonify({
            'success': result['success'],
            'output': result.get('data'),
            'error': result.get('error'),
            'command': command,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/device/target', methods=['POST'])
@login_required
def api_target_device():
    """Target a specific device for attacks"""
    try:
        form = DeviceTargetForm()
        if form.validate_on_submit():
            device_info = {
                'mac': form.device_mac.data,
                'ip': form.device_ip.data,
                'name': form.device_name.data or 'Unknown Device',
                'targeted': True,
                'attack_types': form.attack_types.data,
                'targeted_at': datetime.now().isoformat()
            }
            
            device_tracker.add_device(device_info)
            
            return jsonify({
                'success': True,
                'message': f'Device {device_info["ip"]} targeted for attacks',
                'device': device_info
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Form validation failed',
                'errors': form.errors
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/interfaces')
@login_required
def api_get_interfaces():
    """Get available network interfaces"""
    try:
        interfaces = bettercap_manager.get_network_interfaces()
        
        return jsonify({
            'success': True,
            'interfaces': interfaces
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/logs')
@login_required
def api_get_logs():
    """Get recent Bettercap logs and events"""
    try:
        # This would typically read from log files or event streams
        logs = [
            {
                'timestamp': datetime.now().isoformat(),
                'level': 'info',
                'message': 'Sample log entry',
                'module': 'arp.spoof'
            }
        ]
        
        return jsonify({
            'success': True,
            'logs': logs
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/cleanup')
@login_required
def cleanup():
    """Cleanup and stop all operations"""
    try:
        bettercap_manager.cleanup()
        device_tracker.clear_all()
        
        flash('All operations stopped and cleaned up successfully', 'success')
        return redirect(url_for('bettermitm.index'))
        
    except Exception as e:
        flash(f'Error during cleanup: {str(e)}', 'error')
        return redirect(url_for('bettermitm.index'))


@bettermitm_bp.route('/api/diagnose')
@login_required
def api_diagnose():
    """Diagnose Bettercap installation and status"""
    try:
        diagnosis = {
            'timestamp': datetime.now().isoformat(),
            'system_info': {
                'platform': 'linux',  # Can be enhanced to detect actual platform
                'user': 'current_user'  # Can be enhanced to get actual user
            }
        }
        
        # Check Bettercap installation
        installed, install_message = bettercap_manager.check_bettercap_installed()
        diagnosis['bettercap_installed'] = installed
        diagnosis['install_message'] = install_message
        
        # Check if running
        diagnosis['is_running'] = bettercap_manager.is_running
        diagnosis['current_interface'] = bettercap_manager.current_interface
        
        # Check network interfaces
        try:
            interfaces = bettercap_manager.get_network_interfaces()
            diagnosis['available_interfaces'] = interfaces
        except Exception as e:
            diagnosis['interfaces_error'] = str(e)
            diagnosis['available_interfaces'] = []
        
        # Check API connectivity if running
        if bettercap_manager.is_running:
            try:
                import requests
                response = requests.get(f"{bettercap_manager.api_url}/api/session", timeout=2)
                diagnosis['api_status'] = response.status_code
                diagnosis['api_accessible'] = True
            except Exception as e:
                diagnosis['api_status'] = 'error'
                diagnosis['api_accessible'] = False
                diagnosis['api_error'] = str(e)
        
        return jsonify({
            'success': True,
            'diagnosis': diagnosis
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bettermitm_bp.route('/api/test')
@login_required
def api_test():
    """Test Bettercap API connection and basic commands"""
    try:
        result = bettercap_manager.test_api_connection()
        
        return jsonify({
            'success': True,
            'test_results': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500