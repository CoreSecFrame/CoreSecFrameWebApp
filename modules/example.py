# modules/example.py
class Example:
    def __init__(self):
        pass
    
    def _get_name(self):
        return "Example"
    
    def _get_category(self):
        return "Demo"
    
    def _get_description(self):
        return "Example module for demonstration purposes"
    
    def _get_command(self):
        return "echo"
    
    def _get_install_command(self, pkg_manager):
        return []  # No installation needed
    
    def run_guided(self):
        print("Running in guided mode...")
        print("This is an example module.")
        print("Press any key to continue...")
        input()
        print("Example completed!")
    
    def run_direct(self):
        print("Running in direct mode...")
        print("This is an example module.")
        print("Example completed!")