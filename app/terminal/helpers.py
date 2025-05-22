# app/terminal/helpers.py
import os
import shutil
import platform
import psutil
from flask import current_app

class TerminalHelpers:
    """Helper functions for terminal commands"""
    
    @staticmethod
    def get_system_info():
        """Get basic system information"""
        info = {
            'os': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'python': platform.python_version(),
            'cpu_count': os.cpu_count(),
            'hostname': platform.node(),
            'machine': platform.machine(),
            'ip_address': '127.0.0.1',  # Placeholder
        }
        
        # Add memory info
        try:
            memory = psutil.virtual_memory()
            info['memory_total'] = f"{memory.total / (1024 * 1024 * 1024):.2f} GB"
            info['memory_used'] = f"{memory.used / (1024 * 1024 * 1024):.2f} GB"
            info['memory_percent'] = f"{memory.percent}%"
        except:
            info['memory'] = 'Unknown'
        
        return info
    
    @staticmethod
    def get_help_text():
        """Get help text for custom terminal commands"""
        return """
CoreSecFrame Terminal Help
=========================

Built-in Commands:
-----------------
help                  - Show this help text
clear                 - Clear the terminal screen
exit, logout, quit    - Close the terminal session

Navigation:
----------
cd [directory]        - Change directory
ls, dir               - List files and directories
pwd                   - Show current working directory

File Operations:
--------------
cat [file]            - Display file contents
cp [source] [dest]    - Copy files
mv [source] [dest]    - Move or rename files
rm [file]             - Remove files
mkdir [directory]     - Create directory
touch [file]          - Create empty file

System Info:
-----------
top                   - Show processes
ps                    - List processes
free                  - Show memory usage
df                    - Show disk usage
uname -a              - Show system information
whoami                - Show current user

Module Commands:
--------------
modules               - List available security modules
module install [name] - Install a module
module run [name]     - Run a module

Network Tools:
------------
ifconfig, ip addr     - Show network interfaces
ping [host]           - Ping a host
netstat               - Show network connections

Press Tab for command auto-completion.
Use Up/Down arrows to navigate command history.
"""
    
    @staticmethod
    def get_modules_list():
        """Get list of available modules"""
        from app.modules.models import Module
        
        modules = Module.query.all()
        result = "Available Modules:\n"
        result += "-----------------\n"
        
        for module in modules:
            status = "Installed" if module.installed else "Not Installed"
            result += f"{module.name} ({module.category}) - {status}\n"
            result += f"  {module.description}\n"
        
        return result