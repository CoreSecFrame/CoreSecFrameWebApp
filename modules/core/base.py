# modules/core/base.py
"""
Webapp-compatible base class for CoreSecFrame modules
Simplified version that maintains compatibility with existing modules
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Tuple
from .colors import Colors

class ToolModule(ABC):
    """
    Base class for all CoreSecFrame modules in webapp environment.
    Provides essential functionality while maintaining compatibility with existing modules.
    """
    
    def __init__(self):
        self.name: str = self._get_name()
        self.command: str = self._get_command()
        self.description: str = self._get_description()
        self.dependencies: List[str] = self._get_dependencies()
        self._installed: Optional[bool] = None
        
    # Abstract methods that all modules must implement
    @abstractmethod
    def _get_name(self) -> str:
        """Return the tool name"""
        pass
    
    @abstractmethod
    def _get_category(self) -> str:
        """Return the tool category"""
        pass
    
    @abstractmethod
    def _get_command(self) -> str:
        """Return the main command for the tool"""
        pass
    
    @abstractmethod
    def _get_description(self) -> str:
        """Return the tool description"""
        pass
    
    @abstractmethod
    def _get_dependencies(self) -> List[str]:
        """Return list of dependencies"""
        return []
    
    @abstractmethod
    def get_help(self) -> Dict:
        """Return help documentation for the module"""
        return {
            'title': self._get_name(),
            'description': self._get_description(),
            'usage': f"Use {self._get_name()} through CoreSecFrame webapp",
            'modes': {
                'Guided': 'Interactive step-by-step mode',
                'Direct': 'Direct execution mode'
            }
        }
    
    @abstractmethod
    def run_guided(self) -> None:
        """Run the tool in guided mode"""
        pass
    
    @abstractmethod
    def run_direct(self) -> None:
        """Run the tool in direct mode"""
        pass
    
    # Optional methods with default implementations
    def _get_install_command(self, pkg_manager: str) -> List[str]:
        """Return installation commands for the package manager"""
        return []
    
    def _get_uninstall_command(self, pkg_manager: str) -> List[str]:
        """Return uninstallation commands for the package manager"""
        return []
    
    def _get_update_command(self, pkg_manager: str) -> List[str]:
        """Return update commands for the package manager"""
        return []
    
    def _get_script_path(self) -> str:
        """Return path to the tool's script"""
        return ""
    
    # Compatibility methods for existing modules
    def run_script(self, cmd: list, show_output: bool = True) -> bool:
        """
        Execute a script command (compatibility method for old modules)
        
        Args:
            cmd: List with command and arguments
            show_output: Whether to show output in real time
            
        Returns:
            bool: True if execution was successful, False otherwise
        """
        try:
            if isinstance(cmd, str):
                cmd = [cmd]
            
            print(f"{Colors.CYAN}[*] Executing: {' '.join(cmd)}{Colors.ENDC}")
            
            if show_output:
                # Real-time output for webapp terminal
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                output_lines = []
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        print(output.strip())
                        output_lines.append(output.strip())
                
                return_code = process.wait()
                return return_code == 0
            else:
                # Silent execution
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                return result.returncode == 0
                
        except Exception as e:
            print(f"{Colors.FAIL}[!] Error executing command: {e}{Colors.ENDC}")
            return False
    
    def check_installation(self) -> bool:
        """
        Check if the tool is installed
        
        Returns:
            bool: True if installed, False otherwise
        """
        try:
            # Check dependencies first
            missing_deps = []
            for dep in self._get_dependencies():
                if not shutil.which(dep):
                    missing_deps.append(dep)
            
            if missing_deps:
                self._installed = False
                return False
            
            # Check main command
            if self.command and shutil.which(self.command):
                self._installed = True
                return True
            
            # Check script path if available
            script_path = self._get_script_path()
            if script_path and Path(script_path).exists():
                self._installed = True
                return True
            
            # If no command or script, assume it's a Python-only module
            if not self.command and not script_path:
                self._installed = True
                return True
            
            self._installed = False
            return False
            
        except Exception as e:
            print(f"{Colors.FAIL}[!] Error checking installation: {e}{Colors.ENDC}")
            self._installed = False
            return False
    
    def check_ssh_dependencies(self) -> bool:
        """
        Check if SSH dependencies are available
        
        Returns:
            bool: True if SSH can be used, False otherwise
        """
        required_tools = ['ssh', 'scp']
        optional_tools = ['sshpass']  # For password authentication
        
        missing_required = []
        missing_optional = []
        
        for tool in required_tools:
            if not shutil.which(tool):
                missing_required.append(tool)
        
        for tool in optional_tools:
            if not shutil.which(tool):
                missing_optional.append(tool)
        
        if missing_required:
            print(f"{Colors.FAIL}[!] Missing required SSH tools: {', '.join(missing_required)}{Colors.ENDC}")
            print(f"{Colors.CYAN}[*] Install with: sudo apt-get install openssh-client{Colors.ENDC}")
            return False
        
        if missing_optional:
            print(f"{Colors.WARNING}[!] Missing optional SSH tools: {', '.join(missing_optional)}{Colors.ENDC}")
            print(f"{Colors.CYAN}[*] Install with: sudo apt-get install sshpass{Colors.ENDC}")
            print(f"{Colors.YELLOW}[*] Password authentication will not be available{Colors.ENDC}")
        
        return True
    
    @property
    def installed(self) -> bool:
        """Property indicating if the tool is installed"""
        if self._installed is None:
            self.check_installation()
        return self._installed
    
    def get_status(self) -> Dict[str, any]:
        """Return current module status"""
        return {
            "name": self.name,
            "command": self.command,
            "description": self.description,
            "installed": self.installed,
            "dependencies": self.dependencies,
            "category": self._get_category()
        }
    
    # Utility methods for module execution
    def print_banner(self, title: str = None):
        """Print a banner for the module"""
        title = title or self._get_name()
        print(f"\n{Colors.PRIMARY}{'='*60}{Colors.ENDC}")
        print(f"{Colors.CYAN}{title.center(60)}{Colors.ENDC}")
        print(f"{Colors.PRIMARY}{'='*60}{Colors.ENDC}")
        print(f"{Colors.YELLOW}{self._get_description()}{Colors.ENDC}\n")
    
    def print_error(self, message: str):
        """Print an error message"""
        print(f"{Colors.FAIL}[!] Error: {message}{Colors.ENDC}")
    
    def print_success(self, message: str):
        """Print a success message"""
        print(f"{Colors.GREEN}[✓] {message}{Colors.ENDC}")
    
    def print_info(self, message: str):
        """Print an info message"""
        print(f"{Colors.CYAN}[*] {message}{Colors.ENDC}")
    
    def print_warning(self, message: str):
        """Print a warning message"""
        print(f"{Colors.WARNING}[!] {message}{Colors.ENDC}")
    
    def get_user_input(self, prompt: str, default: str = None) -> str:
        """Get user input with optional default value"""
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            return user_input if user_input else default
        else:
            return input(f"{prompt}: ").strip()
    
    def confirm_action(self, message: str) -> bool:
        """Ask user for confirmation"""
        response = input(f"{message} (y/N): ").strip().lower()
        return response in ['y', 'yes']
    
    def execute_command(self, command: str, show_output: bool = True) -> Tuple[bool, str]:
        """
        Execute a single command
        
        Args:
            command: Command to execute
            show_output: Whether to show output
            
        Returns:
            Tuple[bool, str]: (success, output)
        """
        try:
            if show_output:
                print(f"{Colors.CYAN}[*] Executing: {command}{Colors.ENDC}")
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True
            )
            
            output = result.stdout + result.stderr
            
            if show_output and output:
                print(output)
            
            return result.returncode == 0, output
            
        except Exception as e:
            error_msg = f"Error executing command: {e}"
            if show_output:
                self.print_error(error_msg)
            return False, error_msg
    
    # SSH and Remote Execution Methods
    def connect_ssh(self, host: str, user: str, use_password: bool = False, key_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Establishes SSH connection with specified credentials
        
        Args:
            host: Remote host
            user: Remote user
            use_password: Whether to use password authentication
            key_path: Path to SSH key file (optional)
            
        Returns:
            Tuple[bool, Optional[str]]: (Success status, Error message if any)
        """
        try:
            # Check SSH dependencies first
            if not self.check_ssh_dependencies():
                error_msg = "SSH dependencies not available"
                if self.handle_ssh_error(error_msg):
                    # Retry after installation
                    return self.connect_ssh(host, user, use_password, key_path)
                return False, error_msg
            
            # Check if sshpass is available for password auth
            if use_password and not shutil.which('sshpass'):
                error_msg = "Password authentication requested but sshpass not available"
                print(f"{Colors.WARNING}[!] sshpass not available for password authentication{Colors.ENDC}")
                
                # Offer alternatives
                print(f"{Colors.CYAN}[*] Available options:{Colors.ENDC}")
                print("  1. Install sshpass for password authentication")
                print("  2. Use SSH key authentication instead")
                
                choice = input("Choose option (1/2) or press Enter to cancel: ").strip()
                
                if choice == '1':
                    if self.install_ssh_dependencies():
                        # Retry with sshpass installed
                        return self.connect_ssh(host, user, use_password, key_path)
                    else:
                        return False, "Failed to install sshpass"
                elif choice == '2':
                    print(f"{Colors.CYAN}[*] Switching to key-based authentication{Colors.ENDC}")
                    # Check for default key
                    default_key = os.path.expanduser("~/.ssh/id_rsa")
                    if Path(default_key).exists():
                        print(f"{Colors.GREEN}[*] Found SSH key at {default_key}{Colors.ENDC}")
                        return self.connect_ssh(host, user, False, default_key)
                    else:
                        key_path = self.get_user_input("Enter path to SSH private key")
                        if key_path and Path(key_path).exists():
                            return self.connect_ssh(host, user, False, key_path)
                        else:
                            return False, "SSH key not found"
                else:
                    return False, "SSH connection cancelled by user"
            
            print(f"{Colors.CYAN}[*] Connecting to {user}@{host}...{Colors.ENDC}")
            
            if use_password:
                import getpass
                password = getpass.getpass("Enter SSH password: ")
                # Test connection with password
                test_cmd = f"sshpass -p '{password}' ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {user}@{host} 'echo SSH_CONNECTION_TEST'"
            else:
                # Use key-based authentication
                key_option = f"-i {key_path}" if key_path else ""
                test_cmd = f"ssh {key_option} -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {user}@{host} 'echo SSH_CONNECTION_TEST'"
            
            result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and "SSH_CONNECTION_TEST" in result.stdout:
                # Store connection info for later use
                self._ssh_info = {
                    'host': host,
                    'user': user,
                    'use_password': use_password,
                    'password': password if use_password else None,
                    'key_path': key_path
                }
                print(f"{Colors.GREEN}[✓] SSH connection established to {user}@{host}{Colors.ENDC}")
                return True, None
            else:
                error_msg = f"SSH connection failed: {result.stderr.strip()}"
                print(f"{Colors.FAIL}[!] {error_msg}{Colors.ENDC}")
                
                # Provide helpful suggestions
                if "Permission denied" in result.stderr:
                    print(f"{Colors.YELLOW}[*] Permission denied - check username/password or SSH key{Colors.ENDC}")
                elif "Connection refused" in result.stderr:
                    print(f"{Colors.YELLOW}[*] Connection refused - check if SSH service is running on {host}{Colors.ENDC}")
                elif "No route to host" in result.stderr:
                    print(f"{Colors.YELLOW}[*] No route to host - check network connectivity to {host}{Colors.ENDC}")
                
                return False, error_msg
                
        except Exception as e:
            error_msg = f"SSH connection error: {e}"
            print(f"{Colors.FAIL}[!] {error_msg}{Colors.ENDC}")
            return False, error_msg
    
    def execute_remote_command(self, command: str, use_sudo: bool = False) -> Tuple[int, str, str]:
        """
        Executes a command on the remote host
        
        Args:
            command: Command to execute
            use_sudo: Whether to execute with sudo
            
        Returns:
            Tuple[int, str, str]: (Exit status, stdout, stderr)
        """
        try:
            if not hasattr(self, '_ssh_info'):
                return 1, "", "No SSH connection established"
            
            ssh_info = self._ssh_info
            
            # Handle sudo execution properly
            if use_sudo:
                if ssh_info['use_password']:
                    # Use sudo -S to read password from stdin
                    command = f"echo '{ssh_info['password']}' | sudo -S {command}"
                else:
                    # For key-based auth, assume passwordless sudo or will prompt
                    command = f"sudo {command}"
            
            # Build SSH command
            if ssh_info['use_password']:
                ssh_cmd = f"sshpass -p '{ssh_info['password']}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {ssh_info['user']}@{ssh_info['host']} '{command}'"
            else:
                key_option = f"-i {ssh_info['key_path']}" if ssh_info.get('key_path') else ""
                ssh_cmd = f"ssh {key_option} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {ssh_info['user']}@{ssh_info['host']} '{command}'"
            
            print(f"{Colors.CYAN}[*] Executing remotely: {command}{Colors.ENDC}")
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
            
            return result.returncode, result.stdout, result.stderr
            
        except Exception as e:
            return 1, "", f"Remote execution error: {e}"
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        Uploads a file to the remote host
        
        Args:
            local_path: Path to local file
            remote_path: Path where to store file on remote host
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not hasattr(self, '_ssh_info'):
                print(f"{Colors.FAIL}[!] No SSH connection established{Colors.ENDC}")
                return False
            
            ssh_info = self._ssh_info
            
            if ssh_info['use_password']:
                scp_cmd = f"sshpass -p '{ssh_info['password']}' scp -o StrictHostKeyChecking=no '{local_path}' {ssh_info['user']}@{ssh_info['host']}:'{remote_path}'"
            else:
                key_option = f"-i {ssh_info['key_path']}" if ssh_info.get('key_path') else ""
                scp_cmd = f"scp {key_option} -o StrictHostKeyChecking=no '{local_path}' {ssh_info['user']}@{ssh_info['host']}:'{remote_path}'"
            
            result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"{Colors.GREEN}[✓] File uploaded successfully{Colors.ENDC}")
                return True
            else:
                print(f"{Colors.FAIL}[!] Upload failed: {result.stderr}{Colors.ENDC}")
                return False
                
        except Exception as e:
            print(f"{Colors.FAIL}[!] Upload error: {e}{Colors.ENDC}")
            return False
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        Downloads a file from the remote host
        
        Args:
            remote_path: Path to remote file
            local_path: Path where to store file locally
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not hasattr(self, '_ssh_info'):
                print(f"{Colors.FAIL}[!] No SSH connection established{Colors.ENDC}")
                return False
            
            ssh_info = self._ssh_info
            
            if ssh_info['use_password']:
                scp_cmd = f"sshpass -p '{ssh_info['password']}' scp -o StrictHostKey Checking=no {ssh_info['user']}@{ssh_info['host']}:'{remote_path}' '{local_path}'"
            else:
                key_option = f"-i {ssh_info['key_path']}" if ssh_info.get('key_path') else ""
                scp_cmd = f"scp {key_option} -o StrictHostKeyChecking=no {ssh_info['user']}@{ssh_info['host']}:'{remote_path}' '{local_path}'"
            
            result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"{Colors.GREEN}[✓] File downloaded successfully{Colors.ENDC}")
                return True
            else:
                print(f"{Colors.FAIL}[!] Download failed: {result.stderr}{Colors.ENDC}")
                return False
                
        except Exception as e:
            print(f"{Colors.FAIL}[!] Download error: {e}{Colors.ENDC}")
            return False
    
    def install_ssh_dependencies(self) -> bool:
        """
        Guide user through SSH dependencies installation
        
        Returns:
            bool: True if dependencies were installed successfully
        """
        print(f"\n{Colors.CYAN}[*] Checking SSH dependencies...{Colors.ENDC}")
        
        if self.check_ssh_dependencies():
            print(f"{Colors.GREEN}[✓] All SSH dependencies are available{Colors.ENDC}")
            return True
        
        print(f"\n{Colors.YELLOW}[*] SSH dependencies need to be installed{Colors.ENDC}")
        if not self.confirm_action("Do you want to install SSH dependencies now?"):
            return False
        
        try:
            # Install required packages
            commands = [
                "sudo apt-get update",
                "sudo apt-get install -y openssh-client sshpass"
            ]
            
            for cmd in commands:
                print(f"{Colors.CYAN}[*] Executing: {cmd}{Colors.ENDC}")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"{Colors.FAIL}[!] Failed to execute: {cmd}{Colors.ENDC}")
                    print(f"{Colors.FAIL}Error: {result.stderr}{Colors.ENDC}")
                    return False
                
                if result.stdout:
                    print(result.stdout)
            
            # Verify installation
            if self.check_ssh_dependencies():
                print(f"{Colors.GREEN}[✓] SSH dependencies installed successfully{Colors.ENDC}")
                return True
            else:
                print(f"{Colors.FAIL}[!] SSH dependencies installation verification failed{Colors.ENDC}")
                return False
                
        except Exception as e:
            print(f"{Colors.FAIL}[!] Error installing SSH dependencies: {e}{Colors.ENDC}")
            return False
    
    def get_remote_connection_info(self) -> Optional[Dict]:
        """
        Interactive method to get remote connection information
        
        Returns:
            Optional[Dict]: Connection info or None if cancelled
        """
        try:
            print(f"\n{Colors.CYAN}[*] Setting up remote connection{Colors.ENDC}")
            
            host = self.get_user_input("Enter remote host")
            if not host:
                return None
            
            user = self.get_user_input("Enter SSH user")
            if not user:
                return None
            
            use_password = input("Use password authentication? (y/N): ").strip().lower() == 'y'
            
            key_path = None
            if not use_password:
                key_path = self.get_user_input("Enter path to SSH key (leave empty for default)", "~/.ssh/id_rsa")
                if key_path.startswith("~"):
                    key_path = os.path.expanduser(key_path)
                
                if not Path(key_path).exists():
                    print(f"{Colors.WARNING}[!] SSH key not found at {key_path}{Colors.ENDC}")
                    if not self.confirm_action("Continue with password authentication instead?"):
                        return None
                    use_password = True
                    key_path = None
            
            return {
                'host': host,
                'user': user,
                'use_password': use_password,
                'key_path': key_path
            }
            
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}[!] Connection setup cancelled{Colors.ENDC}")
            return None
    
    # Session and Terminal Management Methods
    def cleanup_tmux_session(self):
        """
        Cleanup tmux sessions - webapp compatible version
        """
        try:
            # Check if tmux is available
            if not shutil.which('tmux'):
                return
            
            # Get list of sessions
            result = subprocess.run(['tmux', 'list-sessions'], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                print(f"\n{Colors.CYAN}[*] Active tmux sessions detected{Colors.ENDC}")
                # For webapp, we'll be more conservative about cleanup
                # Only suggest cleanup rather than automatically doing it
                print(f"{Colors.YELLOW}[*] You can manually cleanup tmux sessions with: tmux kill-server{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.WARNING}[!] Error checking tmux sessions: {e}{Colors.ENDC}")
    
    def execute_with_cleanup(self, func, *args, **kwargs):
        """
        Wrapper to execute any function and ensure cleanup afterwards
        
        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        """
        try:
            # Execute the function
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}[!] Operation interrupted by user{Colors.ENDC}")
            raise
        except Exception as e:
            print(f"{Colors.FAIL}[!] Error during execution: {e}{Colors.ENDC}")
            raise
        finally:
            # Ensure cleanup
            try:
                self.cleanup_tmux_session()
                if hasattr(self, '_ssh_info'):
                    self.close_ssh()
            except Exception as cleanup_error:
                print(f"{Colors.WARNING}[!] Cleanup warning: {cleanup_error}{Colors.ENDC}")
    
    def open_interactive_terminal(self, session_name: str = "framework-terminal") -> bool:
        """
        Opens an interactive terminal session (webapp compatible)
        
        Args:
            session_name: Name for the terminal session
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if tmux is available
            if not shutil.which('tmux'):
                print(f"{Colors.FAIL}[!] tmux is not available{Colors.ENDC}")
                return False
            
            print(f"{Colors.CYAN}[*] Opening interactive terminal: {session_name}{Colors.ENDC}")
            print(f"{Colors.YELLOW}[*] Use Ctrl+B then D to detach from session{Colors.ENDC}")
            print(f"{Colors.YELLOW}[*] Use 'tmux attach -t {session_name}' to reattach{Colors.ENDC}")
            
            # Create new tmux session
            cmd = ['tmux', 'new-session', '-s', session_name]
            subprocess.run(cmd)
            
            return True
            
        except Exception as e:
            print(f"{Colors.FAIL}[!] Error opening terminal: {e}{Colors.ENDC}")
            return False


# Backward compatibility alias
GetModule = ToolModule

# Legacy compatibility for modules that might import this way
class PackageManager:
    """Simplified package manager for webapp compatibility"""
    
    @staticmethod
    def check_package_installed(package_name: str) -> bool:
        """Check if a package is installed"""
        return shutil.which(package_name) is not None
    
    @staticmethod
    def install_package(package_name: str) -> bool:
        """Install a package (placeholder - actual installation handled by webapp)"""
        print(f"{Colors.CYAN}[*] Package installation should be handled through the webapp interface{Colors.ENDC}")
        return PackageManager.check_package_installed(package_name)