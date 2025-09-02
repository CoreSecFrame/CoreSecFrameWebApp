"""
BetterMITM Forms
Flask-WTF forms for network security operations
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, SelectField, TextAreaField, BooleanField,
    IntegerField, FloatField, SelectMultipleField, HiddenField
)
from wtforms.validators import DataRequired, IPAddress, Optional, NumberRange
from wtforms.widgets import CheckboxInput, ListWidget


class MultiCheckboxField(SelectMultipleField):
    """Custom field for multiple checkboxes"""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class NetworkScanForm(FlaskForm):
    """Form for network discovery and scanning"""
    interface = SelectField('Network Interface', validators=[DataRequired()])
    scan_type = SelectField(
        'Scan Type',
        choices=[
            ('arp', 'ARP Scan'),
            ('syn', 'SYN Scan'),
            ('comprehensive', 'Comprehensive Scan')
        ],
        default='arp'
    )
    target_range = StringField(
        'Target Range',
        validators=[Optional()],
        render_kw={'placeholder': '192.168.1.0/24 or leave empty for auto-detect'}
    )
    timeout = IntegerField(
        'Timeout (seconds)',
        validators=[NumberRange(min=1, max=300)],
        default=30
    )


class ARPSpoofingForm(FlaskForm):
    """Form for ARP spoofing attacks"""
    target_ip = StringField('Target IP', validators=[DataRequired(), IPAddress()])
    gateway_ip = StringField('Gateway IP', validators=[DataRequired(), IPAddress()])
    interface = SelectField('Network Interface', validators=[DataRequired()])
    bidirectional = BooleanField('Bidirectional Spoofing', default=True)
    continuous = BooleanField('Continuous Attack', default=True)
    packet_interval = FloatField(
        'Packet Interval (seconds)',
        validators=[NumberRange(min=0.1, max=60.0)],
        default=1.0
    )


class DNSSpoofingForm(FlaskForm):
    """Form for DNS spoofing attacks"""
    target_domain = StringField('Target Domain', validators=[DataRequired()])
    spoofed_ip = StringField('Spoofed IP', validators=[DataRequired(), IPAddress()])
    interface = SelectField('Network Interface', validators=[DataRequired()])
    all_domains = BooleanField('Spoof All Domains', default=False)
    custom_rules = TextAreaField(
        'Custom DNS Rules',
        render_kw={'placeholder': 'domain.com=1.2.3.4\\nexample.org=5.6.7.8'}
    )


class PacketSnifferForm(FlaskForm):
    """Form for packet sniffing configuration"""
    interface = SelectField('Network Interface', validators=[DataRequired()])
    protocols = MultiCheckboxField(
        'Protocols to Capture',
        choices=[
            ('tcp', 'TCP'),
            ('udp', 'UDP'),
            ('icmp', 'ICMP'),
            ('dns', 'DNS'),
            ('http', 'HTTP'),
            ('https', 'HTTPS'),
            ('ftp', 'FTP'),
            ('ssh', 'SSH')
        ],
        default=['tcp', 'udp', 'http']
    )
    filter_expression = StringField(
        'BPF Filter',
        render_kw={'placeholder': 'host 192.168.1.1 or port 80'}
    )
    max_packets = IntegerField(
        'Max Packets (0 for unlimited)',
        validators=[NumberRange(min=0)],
        default=1000
    )
    save_to_file = BooleanField('Save to PCAP file')
    filename = StringField('Output Filename')


class WiFiHandshakeForm(FlaskForm):
    """Form for WiFi handshake capture"""
    interface = SelectField('WiFi Interface', validators=[DataRequired()])
    target_bssid = StringField('Target BSSID (optional)')
    target_essid = StringField('Target ESSID (optional)')
    channel = SelectField(
        'Channel',
        choices=[('', 'Auto')] + [(str(i), str(i)) for i in range(1, 15)],
        default=''
    )
    deauth_attack = BooleanField('Enable Deauthentication Attack', default=True)
    deauth_interval = IntegerField(
        'Deauth Interval (seconds)',
        validators=[NumberRange(min=1, max=60)],
        default=5
    )


class ProxyForm(FlaskForm):
    """Form for HTTP/HTTPS proxy configuration"""
    interface = SelectField('Network Interface', validators=[DataRequired()])
    proxy_port = IntegerField(
        'Proxy Port',
        validators=[DataRequired(), NumberRange(min=1024, max=65535)],
        default=8080
    )
    transparent = BooleanField('Transparent Proxy', default=True)
    https_proxy = BooleanField('Enable HTTPS Proxy', default=True)
    log_requests = BooleanField('Log HTTP Requests', default=True)
    custom_scripts = TextAreaField(
        'Custom JavaScript Injection',
        render_kw={'placeholder': 'alert("Injected by BetterMITM");'}
    )


class DeviceTargetForm(FlaskForm):
    """Form for targeting specific devices"""
    device_mac = StringField('Device MAC Address', validators=[DataRequired()])
    device_ip = StringField('Device IP Address', validators=[DataRequired(), IPAddress()])
    device_name = StringField('Device Name/Alias')
    attack_types = MultiCheckboxField(
        'Attack Types',
        choices=[
            ('arp_spoof', 'ARP Spoofing'),
            ('dns_spoof', 'DNS Spoofing'),
            ('packet_sniff', 'Packet Sniffing'),
            ('mitm_proxy', 'MITM Proxy'),
            ('bandwidth_limit', 'Bandwidth Limiting')
        ]
    )


class BettercapScriptForm(FlaskForm):
    """Form for custom Bettercap scripts"""
    script_name = StringField('Script Name', validators=[DataRequired()])
    script_content = TextAreaField(
        'Script Content',
        validators=[DataRequired()],
        render_kw={'rows': 15}
    )
    auto_execute = BooleanField('Auto-execute on load')
    
    
class NetworkConfigForm(FlaskForm):
    """Form for network configuration"""
    gateway_override = StringField('Gateway Override (optional)')
    dns_servers = StringField(
        'DNS Servers',
        render_kw={'placeholder': '8.8.8.8,1.1.1.1'}
    )
    monitor_mode = BooleanField('Enable Monitor Mode')
    promiscuous_mode = BooleanField('Enable Promiscuous Mode')