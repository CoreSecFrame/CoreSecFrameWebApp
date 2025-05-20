from core.base import ToolModule
from core.colors import Colors
import subprocess
import platform
import os
from typing import List, Dict, Optional
from pathlib import Path

class NmapModule(ToolModule):
    def _get_name(self) -> str:
        return "Nmap"

    def _get_category(self) -> str:
        return "Network"

    def _get_command(self) -> str:
        return "nmap"

    def _get_description(self) -> str:
        return "Advanced network scanner and security auditing tool"

    def _get_dependencies(self) -> List[str]:
        return ["nmap"]

    def _get_script_path(self) -> str:
        """Returns path to script if applicable"""
        return ""  # Nmap is a binary, no script needed

    def get_help(self) -> dict:
        return {
            "title": "Nmap - Network Scanner",
            "usage": "use nmap",
            "desc": "Advanced network scanner for security auditing and network exploration",
            "modes": {
                "Guided": "Interactive mode that guides through scan configuration",
                "Direct": "Direct command execution with full nmap syntax support"
            },
            "options": {
                "-sS": "TCP SYN scan (default)",
                "-sT": "TCP connect scan",
                "-sU": "UDP scan",
                "-sV": "Version detection",
                "-O": "OS detection",
                "-A": "Aggressive scan (OS detection, version detection, script scanning, traceroute)",
                "-p": "Port specification (e.g., -p 80,443 or -p-)",
                "-T<0-5>": "Timing template (higher is faster)",
                "--script": "NSE script selection",
                "-oN": "Output to normal format",
                "-oX": "Output to XML format"
            },
            "examples": [
                "nmap -sS -sV 192.168.1.0/24",
                "nmap -A -T4 example.com",
                "nmap -p 1-65535 -sV -sS -T4 target",
                "nmap -sU -sS -p U:53,111,137,T:21-25,80,139,8080 target",
                "nmap --script vuln target"
            ],
            "notes": [
                "Some scans require root/sudo privileges",
                "Higher timing templates may affect accuracy",
                "Version detection (-sV) may increase scan time significantly",
                "Use with caution on production networks"
            ]
        }

    def _get_install_command(self, pkg_manager: str) -> List[str]:
        """Returns installation commands for different package managers"""
        commands = {
            'apt': [
                "sudo apt-get update",
                "sudo apt-get install -y nmap"
            ],
            'yum': [
                "sudo yum update",
                "sudo yum install -y nmap"
            ],
            'dnf': [
                "sudo dnf update",
                "sudo dnf install -y nmap"
            ],
            'pacman': [
                "sudo pacman -Sy",
                "sudo pacman -S nmap --noconfirm"
            ]
        }
        return commands.get(pkg_manager, [])

    def _get_update_command(self, pkg_manager: str) -> List[str]:
        """Returns update commands for different package managers"""
        return self._get_install_command(pkg_manager)  # Same as install for nmap

    def _get_uninstall_command(self, pkg_manager: str) -> List[str]:
        """Returns uninstallation commands for different package managers"""
        commands = {
            'apt': [
                "sudo apt-get remove -y nmap",
                "sudo apt-get autoremove -y"
            ],
            'yum': [
                "sudo yum remove -y nmap",
                "sudo yum autoremove -y"
            ],
            'dnf': [
                "sudo dnf remove -y nmap",
                "sudo dnf autoremove -y"
            ],
            'pacman': [
                "sudo pacman -Rs nmap --noconfirm"
            ]
        }
        return commands.get(pkg_manager, [])

    def _show_banner(self):
        """Display the module banner"""
        banner = f'''
{Colors.CYAN}╔══════════════════════════════════════════╗
║             NMAP SCANNER                 ║
║    "Network Mapper - Security Scanner"   ║
╚══════════════════════════════════════════╝{Colors.ENDC}'''
        print(banner)

    def _get_target(self) -> Optional[str]:
        """Get and validate scan target"""
        while True:
            target = input(f"\n{Colors.BOLD}[+] Target (IP/domain/range): {Colors.ENDC}").strip()
            if not target:
                print(f"{Colors.FAIL}[!] Target is required{Colors.ENDC}")
                continue
            return target

    def _get_scan_profile(self) -> str:
        """Get scan profile from predefined options"""
        print(f"\n{Colors.CYAN}[*] Select Scan Profile:{Colors.ENDC}")
        profiles = {
            "1": ("Quick Scan", "-T4 --top-ports 100", "Fast scan of most common ports"),
            "2": ("Basic Network Scan", "-sV -T4", "Version detection on default ports"),
            "3": ("Full System Scan", "-sS -sV -O -T4", "Comprehensive system scan"),
            "4": ("Vulnerability Scan", "-sV --script vuln -T4", "Check for known vulnerabilities"),
            "5": ("Stealth Scan", "-sS -T2", "Slower, stealthier scan"),
            "6": ("UDP Service Scan", "-sU -sV --top-ports 100", "Scan UDP services"),
            "7": ("Complete Scan", "-sS -sU -T4 -A -v", "Full-featured scan"),
            "8": ("Custom Scan", "", "Define custom options")
        }

        for key, (name, _, desc) in profiles.items():
            print(f"{Colors.GREEN}{key}:{Colors.ENDC} {name} - {desc}")

        while True:
            choice = input(f"\n{Colors.BOLD}[+] Select profile (1-8): {Colors.ENDC}").strip()
            if choice in profiles:
                return profiles[choice][1]
            print(f"{Colors.FAIL}[!] Invalid choice{Colors.ENDC}")

    def _get_output_options(self) -> str:
        """Configure output options"""
        options = []
        
        if input(f"\n{Colors.BOLD}[+] Save results to file? (y/N): {Colors.ENDC}").lower() == 'y':
            while True:
                filename = input(f"{Colors.BOLD}[+] Enter filename (without extension): {Colors.ENDC}").strip()
                if filename:
                    # Create output directory if it doesn't exist
                    output_dir = Path("nmap_scans")
                    output_dir.mkdir(exist_ok=True)
                    
                    # Add output options for both normal and XML formats
                    normal_file = output_dir / f"{filename}.txt"
                    xml_file = output_dir / f"{filename}.xml"
                    options.extend(["-oN", str(normal_file), "-oX", str(xml_file)])
                    break
                print(f"{Colors.FAIL}[!] Filename is required{Colors.ENDC}")

        return " ".join(options)

    def _execute_scan(self, command: str) -> bool:
        """
        Execute nmap scan with real-time output
        
        Returns:
            bool: True if user wants to perform another scan, False otherwise
        """
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            # Show real-time output
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.strip())

            # Check for errors
            if process.returncode != 0:
                stderr = process.stderr.read()
                if stderr:
                    print(f"{Colors.FAIL}[!] Errors during scan:{Colors.ENDC}")
                    print(stderr)
            else:
                print(f"\n{Colors.GREEN}[✓] Scan completed successfully{Colors.ENDC}")

            # Ask user if they want to perform another scan
            while True:
                choice = input(f"\n{Colors.BOLD}[?] Would you like to perform another scan? (y/N): {Colors.ENDC}").lower()
                if choice in ['y', 'n', '']:
                    return choice == 'y'
                print(f"{Colors.FAIL}[!] Please enter 'y' for yes or 'n' for no{Colors.ENDC}")

        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}[!] Scan interrupted by user{Colors.ENDC}")
            process.terminate()
            return False
        except Exception as e:
            print(f"{Colors.FAIL}[!] Error during scan: {e}{Colors.ENDC}")
            return False

    def run_guided(self) -> None:
        """Interactive guided mode for nmap"""
        self._show_banner()

        while True:
            try:
                # Get target
                target = self._get_target()
                if not target:
                    return

                # Get scan profile
                profile = self._get_scan_profile()
                
                # For custom scan, get additional options
                if not profile:
                    print(f"\n{Colors.CYAN}[*] Common Options:{Colors.ENDC}")
                    print("  -sS: TCP SYN scan")
                    print("  -sV: Version detection")
                    print("  -O:  OS detection")
                    print("  -A:  Aggressive scan")
                    print("  -T4: Faster timing")
                    profile = input(f"\n{Colors.BOLD}[+] Enter custom options: {Colors.ENDC}").strip()

                # Get output options
                output_opts = self._get_output_options()

                # Build and execute command
                command = f"sudo nmap {profile} {output_opts} {target}"
                
                print(f"\n{Colors.CYAN}[*] Executing scan:{Colors.ENDC}")
                print(f"{Colors.BOLD}{command}{Colors.ENDC}\n")

                # Execute scan and check if user wants to continue
                if not self._execute_scan(command):
                    break

            except KeyboardInterrupt:
                print(f"\n{Colors.WARNING}[!] Operation cancelled by user{Colors.ENDC}")
                break

    def run_direct(self) -> None:
        """Direct command execution mode for nmap"""
        self._show_banner()
        
        print(f"\n{Colors.CYAN}[*] Direct Mode - Enter nmap commands directly{Colors.ENDC}")
        print(f"{Colors.CYAN}[*] Example commands:{Colors.ENDC}")
        print("  • nmap -sS -sV target")
        print("  • nmap -A -T4 target")
        print("  • nmap -p- -sV target")
        print("  • nmap --script vuln target")
        print(f"\n{Colors.CYAN}[*] Type 'examples' for more examples, 'help' for options, or 'exit' to quit{Colors.ENDC}")

        while True:
            try:
                command = input(f"\n{Colors.BOLD}nmap > {Colors.ENDC}").strip()
                
                if not command:
                    continue
                if command.lower() == 'exit':
                    break
                if command.lower() == 'help':
                    subprocess.run(['nmap', '--help'])
                    continue
                if command.lower() == 'examples':
                    print(f"\n{Colors.CYAN}[*] Common Examples:{Colors.ENDC}")
                    print("1. Quick scan of top ports:")
                    print("   nmap -T4 --top-ports 100 target")
                    print("\n2. Detailed scan with version detection:")
                    print("   nmap -sS -sV -T4 target")
                    print("\n3. Full vulnerability scan:")
                    print("   nmap -sV --script vuln target")
                    print("\n4. Comprehensive system audit:")
                    print("   nmap -sS -sV -O -A -T4 target")
                    print("\n5. Stealth scan:")
                    print("   nmap -sS -T2 target")
                    continue

                if not command.startswith('nmap '):
                    command = f"nmap {command}"
                if not command.startswith('sudo '):
                    command = f"sudo {command}"

                # Execute scan and check if user wants to continue
                if not self._execute_scan(command):
                    break

            except KeyboardInterrupt:
                print("\n")
                continue
