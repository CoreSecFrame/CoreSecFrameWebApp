# modules/core/base.py - Enhanced Version
"""
Enhanced webapp-compatible base class for CoreSecFrame modules
Improved version with better flexibility, error handling, and compatibility
"""

import sys
import os
import subprocess
import shutil
import tempfile
import json
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Tuple, Union
from .colors import Colors

class ToolModule(ABC):
    """
    Enhanced base class for all CoreSecFrame modules in webapp environment.
    Provides comprehensive functionality with improved compatibility and error handling.
    """
    
    def __init__(self):
        self.name: str = self._get_name()
        self.command: str = self._get_command()
        self.description: str = self._get_description()
        self.dependencies: List[str] = self._get_dependencies()
        self._installed: Optional[bool] = None
        self._working_directory: Optional[Path] = None
        self._environment_vars: Dict[str, str] = {}
        
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
    
    # Enhanced execution methods
    def execute_command_advanced(self, 
                                command: Union[str, List[str]], 
                                working_dir: Optional[Union[str, Path]] = None,
                                environment: Optional[Dict[str, str]] = None,
                                show_output: bool = True,
                                capture_output: bool = True,
                                shell: bool = True,
                                timeout: Optional[int] = None) -> Tuple[bool, str, str]:
        """
        Advanced command execution with full control over environment
        
        Args:
            command: Command to execute (string or list)
            working_dir: Working directory for command execution
            environment: Environment variables to set
            show_output: Whether to show output in real time
            capture_output: Whether to capture output for return
            shell: Whether to use shell for execution
            timeout: Command timeout in seconds
            
        Returns:
            Tuple[bool, str, str]: (success, stdout, stderr)
        """
        try:
            # Prepare command
            if isinstance(command, list):
                cmd = command
                cmd_str = ' '.join(command)
            else:
                cmd = command
                cmd_str = command
            
            if show_output:
                print(f"{Colors.CYAN}[*] Executing: {cmd_str}{Colors.ENDC}")
            
            # Setup environment
            env = os.environ.copy()
            if environment:
                env.update(environment)
            if self._environment_vars:
                env.update(self._environment_vars)
            
            # Setup working directory
            cwd = working_dir or self._working_directory or os.getcwd()
            if isinstance(cwd, Path):
                cwd = str(cwd)
            
            # Execute command
            if show_output and capture_output:
                # Real-time output with capture
                process = subprocess.Popen(
                    cmd,
                    shell=shell,
                    cwd=cwd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    bufsize=1
                )
                
                stdout_lines = []
                stderr_lines = []
                
                # Read output in real-time
                while True:
                    stdout_line = process.stdout.readline()
                    stderr_line = process.stderr.readline()
                    
                    if stdout_line:
                        print(stdout_line.rstrip())
                        stdout_lines.append(stdout_line)
                    
                    if stderr_line:
                        print(f"{Colors.WARNING}{stderr_line.rstrip()}{Colors.ENDC}")
                        stderr_lines.append(stderr_line)
                    
                    if process.poll() is not None:
                        break
                
                # Get remaining output
                remaining_stdout, remaining_stderr = process.communicate()
                if remaining_stdout:
                    stdout_lines.append(remaining_stdout)
                if remaining_stderr:
                    stderr_lines.append(remaining_stderr)
                
                stdout = ''.join(stdout_lines)
                stderr = ''.join(stderr_lines)
                return_code = process.returncode
                
            else:
                # Standard execution
                result = subprocess.run(
                    cmd,
                    shell=shell,
                    cwd=cwd,
                    env=env,
                    capture_output=capture_output,
                    text=True,
                    timeout=timeout
                )
                
                stdout = result.stdout or ""
                stderr = result.stderr or ""
                return_code = result.returncode
                
                if show_output:
                    if stdout:
                        print(stdout)
                    if stderr:
                        print(f"{Colors.WARNING}{stderr}{Colors.ENDC}")
            
            success = return_code == 0
            return success, stdout, stderr
            
        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after {timeout} seconds"
            if show_output:
                self.print_error(error_msg)
            return False, "", error_msg
        except Exception as e:
            error_msg = f"Error executing command: {e}"
            if show_output:
                self.print_error(error_msg)
            return False, "", error_msg
    
    def execute_in_directory(self, 
                            command: Union[str, List[str]], 
                            directory: Union[str, Path],
                            **kwargs) -> Tuple[bool, str, str]:
        """
        Execute command in specific directory
        
        Args:
            command: Command to execute
            directory: Directory to execute in
            **kwargs: Additional arguments for execute_command_advanced
            
        Returns:
            Tuple[bool, str, str]: (success, stdout, stderr)
        """
        return self.execute_command_advanced(command, working_dir=directory, **kwargs)
    
    def execute_with_retry(self, 
                          command: Union[str, List[str]], 
                          max_retries: int = 3,
                          retry_delay: float = 1.0,
                          **kwargs) -> Tuple[bool, str, str]:
        """
        Execute command with automatic retry on failure
        
        Args:
            command: Command to execute
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            **kwargs: Additional arguments for execute_command_advanced
            
        Returns:
            Tuple[bool, str, str]: (success, stdout, stderr)
        """
        import time
        
        last_error = ""
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"{Colors.WARNING}[*] Retry attempt {attempt}/{max_retries}...{Colors.ENDC}")
                time.sleep(retry_delay)
            
            success, stdout, stderr = self.execute_command_advanced(command, **kwargs)
            
            if success:
                return success, stdout, stderr
            
            last_error = stderr or "Unknown error"
        
        print(f"{Colors.FAIL}[!] Command failed after {max_retries} retries{Colors.ENDC}")
        return False, "", last_error
    
    def run_script_enhanced(self, 
                           cmd: Union[str, List[str]], 
                           working_dir: Optional[Union[str, Path]] = None,
                           show_output: bool = True) -> bool:
        """
        Enhanced version of run_script with directory support
        
        Args:
            cmd: Command to execute
            working_dir: Working directory (optional)
            show_output: Whether to show output
            
        Returns:
            bool: True if successful, False otherwise
        """
        success, stdout, stderr = self.execute_command_advanced(
            cmd, 
            working_dir=working_dir, 
            show_output=show_output
        )
        return success
    
    # Backward compatibility
    def run_script(self, cmd: Union[str, List[str]], show_output: bool = True) -> bool:
        """
        Original run_script method for backward compatibility
        
        Args:
            cmd: Command to execute
            show_output: Whether to show output in real time
            
        Returns:
            bool: True if execution was successful, False otherwise
        """
        return self.run_script_enhanced(cmd, show_output=show_output)
    
    def execute_command(self, command: str, show_output: bool = True) -> Tuple[bool, str]:
        """
        Original execute_command method for backward compatibility
        
        Args:
            command: Command to execute
            show_output: Whether to show output
            
        Returns:
            Tuple[bool, str]: (success, combined_output)
        """
        success, stdout, stderr = self.execute_command_advanced(
            command, 
            show_output=show_output
        )
        combined_output = (stdout + stderr).strip()
        return success, combined_output
    
    # Directory and environment management
    def set_working_directory(self, directory: Union[str, Path]) -> None:
        """Set default working directory for commands"""
        self._working_directory = Path(directory) if isinstance(directory, str) else directory
    
    def add_environment_variable(self, key: str, value: str) -> None:
        """Add environment variable for command execution"""
        self._environment_vars[key] = value
    
    def clear_environment_variables(self) -> None:
        """Clear all custom environment variables"""
        self._environment_vars.clear()
    
    # Node.js/npm specific helpers
    def execute_npm_command(self, 
                           npm_command: str, 
                           working_dir: Optional[Union[str, Path]] = None,
                           use_legacy_peer_deps: bool = False) -> Tuple[bool, str, str]:
        """
        Execute npm command with common options
        
        Args:
            npm_command: npm command to execute (e.g., "install", "start")
            working_dir: Working directory
            use_legacy_peer_deps: Whether to use --legacy-peer-deps
            
        Returns:
            Tuple[bool, str, str]: (success, stdout, stderr)
        """
        cmd = f"npm {npm_command}"
        if use_legacy_peer_deps and npm_command.startswith(('install', 'update')):
            cmd += " --legacy-peer-deps"
        
        return self.execute_command_advanced(cmd, working_dir=working_dir)
    
    def execute_nodejs_script(self, 
                             script_path: Union[str, Path], 
                             args: Optional[List[str]] = None,
                             working_dir: Optional[Union[str, Path]] = None) -> Tuple[bool, str, str]:
        """
        Execute Node.js script with arguments
        
        Args:
            script_path: Path to the script
            args: Script arguments
            working_dir: Working directory
            
        Returns:
            Tuple[bool, str, str]: (success, stdout, stderr)
        """
        cmd = ["nodejs", str(script_path)]
        if args:
            cmd.extend(args)
        
        return self.execute_command_advanced(cmd, working_dir=working_dir)
    
    # File management helpers
    def create_temp_file(self, content: str, suffix: str = ".tmp") -> str:
        """
        Create temporary file with content
        
        Args:
            content: File content
            suffix: File suffix
            
        Returns:
            str: Path to temporary file
        """
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=suffix) as f:
            f.write(content)
            return f.name
    
    def patch_file(self, 
                   file_path: Union[str, Path], 
                   old_content: str, 
                   new_content: str,
                   backup: bool = True) -> bool:
        """
        Patch file content by replacing old_content with new_content
        
        Args:
            file_path: Path to file
            old_content: Content to replace
            new_content: Replacement content
            backup: Whether to create backup
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            file_path = Path(file_path)
            
            # Create backup if requested
            if backup:
                backup_path = file_path.with_suffix(file_path.suffix + '.backup')
                shutil.copy2(file_path, backup_path)
                print(f"{Colors.CYAN}[*] Backup created: {backup_path}{Colors.ENDC}")
            
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if old content exists
            if old_content not in content:
                print(f"{Colors.WARNING}[!] Content to replace not found in {file_path}{Colors.ENDC}")
                return False
            
            # Replace content
            new_file_content = content.replace(old_content, new_content)
            
            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_file_content)
            
            print(f"{Colors.GREEN}[✓] Successfully patched {file_path}{Colors.ENDC}")
            return True
            
        except Exception as e:
            print(f"{Colors.FAIL}[!] Error patching file {file_path}: {e}{Colors.ENDC}")
            return False
    
    # Installation verification methods
    def check_installation(self) -> bool:
        """
        Enhanced installation check with better dependency verification
        """
        try:
            # Check dependencies first
            missing_deps = []
            for dep in self._get_dependencies():
                if not self.check_command_available(dep):
                    missing_deps.append(dep)
            
            if missing_deps:
                print(f"{Colors.WARNING}[!] Missing system dependencies: {', '.join(missing_deps)}{Colors.ENDC}")
                self._installed = False
                return False
            
            # Check main command if specified
            if self.command and not self.check_command_available(self.command):
                # Check script path if available
                script_path = self._get_script_path()
                if script_path and not Path(script_path).exists():
                    self._installed = False
                    return False
            
            # Run custom installation check if implemented
            if hasattr(self, '_custom_installation_check'):
                if not self._custom_installation_check():
                    self._installed = False
                    return False
            
            self._installed = True
            return True
            
        except Exception as e:
            print(f"{Colors.FAIL}[!] Error checking installation: {e}{Colors.ENDC}")
            self._installed = False
            return False
    
    def check_command_available(self, command: str) -> bool:
        """Check if a command is available in the system"""
        return shutil.which(command) is not None
    
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
    
    # Utility methods for module execution
    def print_banner(self, title: str = None):
        """Print a banner for the module"""
        title = title or self._get_name()
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.CYAN}{title.center(60)}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
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
            "category": self._get_category(),
            "working_directory": str(self._working_directory) if self._working_directory else None,
            "environment_vars": self._environment_vars.copy()
        }


# Backward compatibility alias
GetModule = ToolModule

# Enhanced package manager for webapp compatibility
class PackageManager:
    """Enhanced package manager for webapp compatibility"""
    
    @staticmethod
    def check_package_installed(package_name: str) -> bool:
        """Check if a package is installed"""
        return shutil.which(package_name) is not None
    
    @staticmethod
    def install_package(package_name: str) -> bool:
        """Install a package (placeholder - actual installation handled by webapp)"""
        print(f"{Colors.CYAN}[*] Package installation should be handled through the webapp interface{Colors.ENDC}")
        return PackageManager.check_package_installed(package_name)