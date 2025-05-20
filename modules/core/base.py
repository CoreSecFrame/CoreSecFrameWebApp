# modules/core/base.py
class ToolModule:
    """Base class for all tool modules"""
    
    def __init__(self):
        """Initialize the tool module"""
        pass
    
    def _get_name(self):
        """Get the name of the module"""
        return self.__class__.__name__
    
    def _get_category(self):
        """Get the category of the module"""
        return "Uncategorized"
    
    def _get_description(self):
        """Get the description of the module"""
        return "No description provided"
    
    def _get_command(self):
        """Get the command to run the module"""
        return ""
    
    def _get_install_command(self, pkg_manager):
        """Get the command to install the module's dependencies"""
        return []
    
    def _get_uninstall_command(self, pkg_manager):
        """Get the command to uninstall the module's dependencies"""
        return []
    
    def check_installation(self):
        """Check if the module is installed"""
        return True
    
    def run_guided(self):
        """Run the module in guided mode"""
        print("This module does not implement guided mode")
    
    def run_direct(self):
        """Run the module in direct mode"""
        print("This module does not implement direct mode")