# BetterMITM - Advanced Bettercap GUI Interface

BetterMITM es una interfaz web avanzada para Bettercap que proporciona una GUI completa para operaciones de seguridad de red y pruebas de penetración.

## Características Principales

### 🎯 **Gestión de Dispositivos**
- Descubrimiento automático de dispositivos en red
- Tracking en tiempo real de hosts activos
- Información detallada de cada dispositivo (MAC, IP, vendor, OS)
- Sistema de targeting para ataques específicos
- Visualización de mapa de red

### ⚡ **Módulos de Ataque**
- **ARP Spoofing**: Ataques man-in-the-middle bidireccionales
- **DNS Spoofing**: Redirección de dominios con reglas personalizadas
- **HTTP Proxy**: Proxy transparente con logging e inyección
- **Packet Sniffing**: Captura de paquetes con filtros BPF
- **Network Discovery**: Escaneo comprehensivo de redes

### 📊 **Monitoreo en Tiempo Real**
- Dashboard con estadísticas actualizadas
- Console interactiva para comandos Bettercap
- Logs de actividad y eventos de seguridad
- Notificaciones push para eventos importantes
- Estado de ataques activos

### 🔧 **Configuración Avanzada**
- Selección de interfaces de red
- Configuración de parámetros de ataque
- Scripts personalizados de Bettercap
- Exportación e importación de datos
- Control de emergencia (stop all)

## Requisitos del Sistema

### Software Necesario
```bash
# Instalar Bettercap
sudo apt update && sudo apt install bettercap

# O usando Go (recomendado para última versión)
go install github.com/bettercap/bettercap@latest
```

### Dependencias Python
Las dependencias se instalan automáticamente con el framework:
- `requests>=2.31.0` - Para comunicación con API de Bettercap
- `psutil>=5.9.8` - Para información de interfaces de red
- `flask-wtf>=1.2.1` - Para formularios web seguros

### Permisos del Sistema
```bash
# Dar permisos a Bettercap para operaciones de red
sudo setcap cap_net_raw,cap_net_admin=eip $(which bettercap)

# O ejecutar como root (no recomendado para producción)
sudo bettercap
```

## Configuración Inicial

### 1. Configurar Bettercap
```bash
# Crear archivo de configuración
mkdir -p ~/.bettercap
cat > ~/.bettercap/config.yml << EOF
api:
  rest:
    enabled: true
    port: 8081
    username: admin
    password: admin123
    certificate: ""
    key: ""
EOF
```

### 2. Verificar Interfaces de Red
```bash
# Listar interfaces disponibles
ip link show

# Para WiFi, habilitar modo monitor (opcional)
sudo airmon-ng start wlan0
```

## Uso de BetterMITM

### Inicio Rápido

1. **Acceder a la interfaz**: Navegar a `/bettermitm`
2. **Iniciar Bettercap**: Hacer clic en "Start Bettercap" y seleccionar interfaz
3. **Descubrir red**: Ir a "Network Discovery" y iniciar escaneo
4. **Configurar ataques**: Usar los módulos de ataque según necesidades

### Dashboard Principal

El dashboard proporciona:
- **Estado de Bettercap**: Running/Stopped con interfaz activa
- **Estadísticas**: Total de dispositivos, activos, targeted, bajo ataque
- **Mapa de red**: Visualización gráfica de dispositivos descubiertos
- **Acciones rápidas**: Botones para operaciones comunes

### Módulos de Ataque

#### ARP Spoofing
```
Target IP: 192.168.1.100 (dispositivo objetivo)
Gateway IP: 192.168.1.1 (router/gateway)
☑ Bidirectional: Ataque en ambas direcciones
☑ Continuous: Mantener ataque activo
```

#### DNS Spoofing
```
Target Domain: example.com
Spoofed IP: 192.168.1.50 (tu servidor)
☐ Spoof All Domains: Redirigir todos los dominios
```

#### HTTP Proxy
```
Proxy Port: 8080
☑ Transparent: Proxy transparente
☑ Log Requests: Registrar peticiones HTTP
Custom JS: alert('Intercepted!'); (opcional)
```

#### Packet Sniffer
```
Protocols: ☑ TCP ☑ UDP ☑ HTTP ☐ HTTPS
BPF Filter: host 192.168.1.100 or port 80
Max Packets: 1000 (0 para ilimitado)
```

### Consola Interactiva

La consola permite ejecutar comandos Bettercap directamente:
```
bettercap> help
bettercap> net.recon on
bettercap> net.show
bettercap> set arp.spoof.targets 192.168.1.100
bettercap> arp.spoof on
```

## Casos de Uso Comunes

### 1. Auditoria de Red Corporativa
```bash
1. Escanear red: Network Discovery → Start Scan
2. Identificar dispositivos críticos
3. Verificar segmentación de red
4. Documentar vulnerabilidades encontradas
```

### 2. Pruebas de Penetración WiFi
```bash
1. Configurar interfaz en modo monitor
2. Descubrir redes disponibles
3. Capturar handshakes WiFi
4. Analizar tráfico de red
```

### 3. Man-in-the-Middle Testing
```bash
1. ARP Spoof entre cliente y gateway
2. Activar HTTP proxy para interceptar tráfico
3. Analizar datos sensibles
4. DNS spoof para phishing tests
```

### 4. Análisis de Tráfico de Red
```bash
1. Configurar packet sniffer con filtros
2. Capturar tráfico específico
3. Analizar protocolos y servicios
4. Identificar anomalías
```

## Seguridad y Consideraciones

### ⚠️ **Advertencias Importantes**

1. **Solo para uso autorizado**: Usar únicamente en redes propias o con permiso explícito
2. **Impacto en red**: Los ataques pueden afectar el rendimiento de la red
3. **Detección**: Las herramientas de seguridad pueden detectar estas actividades
4. **Responsabilidad legal**: El uso no autorizado puede tener consecuencias legales

### 🔒 **Buenas Prácticas**

- Usar en entornos de laboratorio/testing
- Obtener autorizaciones por escrito
- Documentar todas las actividades
- Tener plan de rollback para emergencias
- No interceptar datos personales sin consentimiento

### 🛡️ **Medidas de Protección**

```python
# El sistema incluye protecciones automáticas:
- Rate limiting para prevenir abuso
- Logging completo de actividades
- Autenticación requerida
- CSRF protection habilitada
- Timeouts para operaciones largas
```

## Troubleshooting

### Errores Comunes

#### Bettercap no inicia
```bash
# Verificar permisos
getcap $(which bettercap)

# Verificar puerto disponible
netstat -tulnp | grep 8081

# Verificar interfaz válida
ip link show
```

#### No se descubren dispositivos
```bash
# Verificar conectividad
ping -c 1 192.168.1.1

# Verificar tabla ARP
arp -a

# Usar escaneo más agresivo
nmap -sn 192.168.1.0/24
```

#### Ataques no funcionan
```bash
# Verificar routing
route -n

# Verificar iptables
sudo iptables -L

# Verificar forwarding IP
cat /proc/sys/net/ipv4/ip_forward
```

### Logs y Debugging

Los logs se encuentran en:
- **Sistema**: `/var/log/coresecframe/`
- **Bettercap**: `~/.bettercap/log`
- **Aplicación**: Console tab en la interfaz

## API Reference

### Endpoints Principales

```http
GET    /bettermitm/api/status        # Estado actual
POST   /bettermitm/api/start         # Iniciar Bettercap
POST   /bettermitm/api/stop          # Detener Bettercap
GET    /bettermitm/api/hosts         # Dispositivos descubiertos
POST   /bettermitm/api/scan/start    # Iniciar escaneo
POST   /bettermitm/api/arp/start     # Iniciar ARP spoofing
POST   /bettermitm/api/dns/start     # Iniciar DNS spoofing
POST   /bettermitm/api/command       # Ejecutar comando custom
```

### Eventos WebSocket (Futuro)

```javascript
// Real-time events para actualizaciones
socket.on('device_discovered', (device) => {...});
socket.on('attack_status', (status) => {...});
socket.on('packet_captured', (packet) => {...});
```

## Desarrollo y Contribución

### Estructura del Código
```
app/bettermitm/
├── __init__.py           # Blueprint registration
├── routes.py             # API endpoints y web routes  
├── forms.py              # Formularios WTF
├── bettercap_manager.py  # Gestión de Bettercap
├── device_tracker.py     # Tracking de dispositivos
└── templates/
    └── bettermitm/
        └── index.html    # Interfaz principal
```

### Agregar Nuevas Funciones

1. **Nuevo módulo de ataque**: Agregar en `bettercap_manager.py`
2. **Nueva interfaz**: Modificar `templates/index.html` y `static/js/bettermitm.js`
3. **Nuevos formularios**: Agregar en `forms.py`
4. **Nuevas rutas API**: Agregar en `routes.py`

## Changelog

### v1.0.0 (Inicial)
- ✅ Dashboard con estadísticas en tiempo real
- ✅ Network Discovery y device tracking
- ✅ ARP/DNS/HTTP spoofing
- ✅ Packet sniffer con filtros
- ✅ Console interactiva
- ✅ Sistema de targeting de dispositivos
- ✅ Export/import de datos
- ✅ Emergency stop functionality

### Próximas Funciones (Roadmap)
- 🔄 WiFi handshake capture
- 🔄 Eventos WebSocket en tiempo real
- 🔄 Plugins personalizados
- 🔄 Reporting automático
- 🔄 Integration con otras herramientas
- 🔄 Mobile interface
- 🔄 Docker deployment

---

**⚠️ Disclaimer**: Esta herramienta está diseñada exclusivamente para pruebas de seguridad autorizadas y propósitos educativos. El uso indebido de esta herramienta puede violar leyes locales e internacionales. Los usuarios son completamente responsables del uso ético y legal de esta aplicación.