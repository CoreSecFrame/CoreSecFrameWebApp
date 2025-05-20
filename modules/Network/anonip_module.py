from core.base import ToolModule
import subprocess
import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional

class AnonIPModule(ToolModule):
    def __init__(self):
        self.repo_url = "https://github.com/sPROFFEs/AnonIP/releases/download/English/AnonIP_ENG.sh"
        self.scripts_dir = Path(__file__).parent.parent.parent / "scripts" / "Network" / "AnonIP"
        super().__init__()

    def _get_name(self) -> str:
        return "anonip"

    def _get_category(self) -> str:
        return "Network"

    def _get_command(self) -> str:
        return "anonip"

    def _get_description(self) -> str:
        return "Tool to anonymize the connection through IP changes, MAC changes and routing through TOR"

    def _get_dependencies(self) -> list:
        return ["tor", "wget", "iptables"]

    def _get_script_path(self) -> str:
        """Returns path to script"""
        return str(self.scripts_dir / "anonip.sh")

    def _get_update_command(self, pkg_manager: str) -> str:
        commands = {
            'apt': "sudo apt-get update && sudo apt-get install -y tor wget  iptables",
            'yum': "sudo yum update -y tor wget  iptables",
            'dnf': "sudo dnf update -y tor wget  iptables",
            'pacman': "sudo pacman -Syu tor wget  iptables"
        }
        return commands.get(pkg_manager, '')

    def _get_install_command(self, pkg_manager: str) -> List[str]:
        """Returns installation commands for different package managers"""
        
        # Create category-specific scripts directory
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = self.scripts_dir / "anonip.sh"
        
        commands = {
            'apt': [
                "sudo apt-get update",
                "sudo apt-get install -y tor wget iptables",
                f"wget -O {script_path} {self.repo_url}",
                f"chmod +x {script_path}"
            ],
            'yum': [
                "sudo yum update",
                "sudo yum install -y tor wget dhclient iptables",
                f"wget -O {script_path} {self.repo_url}",
                f"chmod +x {script_path}"
            ],
            'pacman': [
                "sudo pacman -Sy",
                "sudo pacman -S tor wget dhclient iptables --noconfirm",
                f"wget -O {script_path} {self.repo_url}",
                f"chmod +x {script_path}"
            ]
        }
        return commands.get(pkg_manager, [])

    def _get_uninstall_command(self, pkg_manager: str) -> str:
        script_path = self.scripts_dir / "anonip.sh"        
        commands = {
            'apt': f"""
                sudo systemctl stop tor &&
                sudo systemctl disable tor &&
                sudo apt-get autoremove -y &&
                rm -f {script_path}
            """,
            'yum': f"""
                sudo systemctl stop tor &&
                sudo systemctl disable tor &&
                sudo yum remove -y tor  &&
                sudo yum autoremove -y &&
                rm -f {script_path}
            """,
            'pacman': f"""
                sudo systemctl stop tor &&
                sudo systemctl disable tor &&
                sudo pacman -R tor &&
                rm -f {script_path}
            """
        }
        return commands.get(pkg_manager, '')

    def get_help(self) -> dict:
        return {
            "title": "TEST",
            "usage": "TEST",
            "desc": "TEST",
            "modes": {
                "Guiado": "Modo interactivo que solicita la información necesaria paso a paso",
                "Directo": "Modo que acepta todos los parámetros en la línea de comandos"
            },
            "options": {
                "TEST"
            },
            "examples": [
                "TEST"
            ],
            "notes": [
                "TEST"
            ]
        }

    def run_guided(self) -> None:
        """Ejecuta la herramienta en modo guiado"""
        options = []
        
        print("\nConfiguración de AnonIP")
        print("----------------------")
        
        # Solicitar interfaz de red
        interface = input("\nInterfaz de red (Enter para autodetectar): ").strip()
        if interface:
            options.extend(["-i", interface])
        
        # Solicitar intervalo de tiempo
        interval = input("\nIntervalo en segundos entre cambios (Enter para 1800): ").strip()
        if interval:
            options.extend(["-t", interval])
        
        # Opciones booleanas
        if input("\n¿Cambiar dirección MAC? (s/N): ").lower() == 's':
            options.append("-m")
        
        if input("¿Cambiar dirección IP? (s/N): ").lower() == 's':
            options.append("-p")
        
        if input("¿Usar TOR? (s/N): ").lower() == 's':
            options.append("-T")
        
        # Ejecutar el script con las opciones seleccionadas
        self._execute_script(options)

    def run_direct(self) -> None:
        """Ejecuta la herramienta en modo directo"""
        print("\nOptions available:")
        print("  -h, --help           Show this help message")
        print("  -i, --interface      Specify network interface (e.g., wlan0)")
        print("  -t, --time           Interval in seconds between changes")
        print("  -m, --mac            Enable MAC address change")
        print("  -p, --ip             Enable IP address change")
        print("  -T, --tor            Enable TOR routing")
        print("  -s, --switch-tor     Switch TOR exit node")
        print("  -x, --stop           Stop all services")
        print("\nExample:")
        print("anonip.sh -i wlan0 -t 600 -m -p -T")
        print("(Changes MAC, IP and uses TOR every 10 minutes on wlan0)")
        
        options = input("\nSelect options: ").split()
        self._execute_script(options)

    def _execute_script(self, options: list) -> None:
        """Ejecuta el script localmente con las opciones especificadas"""
        script_path = self._get_script_path()
        cmd = ["sudo", script_path] + options
        
        print("\nEjecutando AnonIP...")
        self.run_script(cmd)  # Usamos el método heredado de GetModule
            
    def stop(self) -> None:
        """Detiene los servicios de la herramienta"""
        cmd = [self._get_script_path(), "-x"]
        self.run_script(cmd)  # Usamos el método heredado de GetModule
