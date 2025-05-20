# modules/example.py
from modules.core.base import ToolModule
from modules.core.colors import Colors

class Example(ToolModule):
    def _get_name(self):
        return "Example"
    
    def _get_category(self):
        return "Utils"
    
    def _get_description(self):
        return "Example module for demonstration purposes"
    
    def _get_command(self):
        return "echo"
    
    def _get_install_command(self, pkg_manager):
        return []  # No installation needed
    
    def run_guided(self):
        print(f"{Colors.GREEN}Running in guided mode...{Colors.ENDC}")
        print("This is an example module.")
        print("Press any key to continue...")
        input()
        print(f"{Colors.GREEN}Example completed!{Colors.ENDC}")
    
    def run_direct(self):
        print(f"{Colors.BLUE}Running in direct mode...{Colors.ENDC}")
        print("This is an example module.")
        print(f"{Colors.BLUE}Example completed!{Colors.ENDC}")