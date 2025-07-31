import azure.functions as func
import json
import logging
import socket
import struct
import time
from datetime import datetime, timezone
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.data.tables import TableServiceClient, TableEntity
import os

# Configuración
RESOURCE_GROUP = "minecraft-rg"
CONTAINER_NAME = "minecraft-server"
MINECRAFT_PORT = 25565
SHUTDOWN_THRESHOLD_MINUTES = 6  # 2 checks de 3 minutos cada uno

app = func.FunctionApp()

def test_port_connection(ip_address, port, timeout=5):
    """Prueba si el puerto está abierto y accesible"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip_address, port))
        sock.close()
        return result == 0
    except Exception as e:
        logging.debug(f"Port test failed: {e}")
        return False

def get_minecraft_player_count(ip_address, port=25565, timeout=10):
    """
    Obtiene el número de jugadores conectados al servidor de Minecraft
    usando múltiples métodos para máxima compatibilidad
    """
    # Primero verificar si el puerto está abierto
    if not test_port_connection(ip_address, port, timeout=3):
        logging.warning(f"Port {port} is not accessible on {ip_address}")
        return -1
    
    logging.info(f"Port {port} is open, attempting protocol communication...")
    
    # Método 1: Protocolo moderno de Minecraft
    player_count = try_modern_protocol(ip_address, port, timeout)
    if player_count >= 0:
        return player_count
    
    # Método 2: Protocolo legacy (versiones más antiguas)
    player_count = try_legacy_protocol(ip_address, port, timeout)
    if player_count >= 0:
        return player_count
    
    # Método 3: Query protocol (si está habilitado)
    player_count = try_query_protocol(ip_address, port, timeout)
    if player_count >= 0:
        return player_count
    
    logging.warning("All protocol methods failed - server may be starting or using unsupported configuration")
    return -1

def try_modern_protocol(ip_address, port, timeout):
    """Intenta usar el protocolo moderno de Minecraft con implementación simplificada"""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip_address, port))
        
        logging.debug("Connected to server, sending handshake...")
        
        # Handshake packet más simple y compatible
        # Protocolo 47 (Minecraft 1.8) es muy compatible
        server_addr_bytes = ip_address.encode('utf-8')
        
        # Construir handshake: [packet_length][packet_id][protocol_version][server_address][server_port][next_state]
        handshake_data = struct.pack('B', 47)  # Protocol version
        handshake_data += struct.pack('B', len(server_addr_bytes)) + server_addr_bytes
        handshake_data += struct.pack('>H', port)
        handshake_data += struct.pack('B', 1)  # Next state: status
        
        # Crear packet completo
        packet_data = struct.pack('B', 0x00) + handshake_data  # 0x00 = handshake packet ID
        full_packet = struct.pack('B', len(packet_data)) + packet_data
        
        sock.send(full_packet)
        
        # Enviar status request
        status_request = struct.pack('BB', 0x01, 0x00)  # [length=1][packet_id=0x00]
        sock.send(status_request)
        
        logging.debug("Handshake and status request sent, waiting for response...")
        
        # Leer respuesta con manejo más robusto
        sock.settimeout(6)
        
        # Intentar leer la respuesta completa
        response_data = b''
        try:
            # Leer hasta 4KB de respuesta
            while len(response_data) < 4096:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                response_data += chunk
                
                # Si tenemos suficientes datos, intentar parsear
                if len(response_data) > 10:
                    try:
                        # Buscar el JSON en la respuesta
                        # El JSON típicamente empieza con '{'
                        json_start = response_data.find(b'{')
                        if json_start >= 0:
                            # Encontrar el final del JSON
                            json_end = response_data.rfind(b'}')
                            if json_end > json_start:
                                json_data = response_data[json_start:json_end + 1]
                                
                                try:
                                    server_info = json.loads(json_data.decode('utf-8'))
                                    players_info = server_info.get('players', {})
                                    player_count = players_info.get('online', 0)
                                    max_players = players_info.get('max', 0)
                                    
                                    logging.info(f"Modern protocol success: {player_count}/{max_players} players online")
                                    return player_count
                                    
                                except (json.JSONDecodeError, UnicodeDecodeError):
                                    continue  # Seguir leyendo más datos
                    except:
                        continue  # Seguir leyendo
                        
        except socket.timeout:
            logging.debug("Timeout waiting for server response")
            
        # Si llegamos aquí, no pudimos parsear la respuesta
        logging.debug(f"Could not parse server response (got {len(response_data)} bytes)")
        return -1
        
    except Exception as e:
        logging.debug(f"Modern protocol failed: {e}")
        return -1
    finally:
        if sock:
            try:
                sock.close()
            except:
                pass

def try_legacy_protocol(ip_address, port, timeout):
    """Intenta usar el protocolo legacy de Minecraft (pre-1.7)"""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip_address, port))
        
        # Legacy server list ping
        # Packet: 0xFE 0x01
        packet = struct.pack('BB', 0xFE, 0x01)
        sock.send(packet)
        
        # Leer respuesta
        sock.settimeout(3)
        response = sock.recv(1024)
        
        if len(response) < 3:
            return -1
        
        # La respuesta debería empezar con 0xFF
        if response[0] != 0xFF:
            return -1
        
        # Leer longitud del string
        string_length = struct.unpack('>H', response[1:3])[0]
        
        # Leer el string de respuesta
        string_data = response[3:3 + string_length * 2]  # UTF-16
        
        try:
            server_info = string_data.decode('utf-16be')
            # Formato: §1\x00protocol_version\x00server_version\x00motd\x00current_players\x00max_players
            parts = server_info.split('\x00')
            
            if len(parts) >= 5:
                current_players = int(parts[4])
                max_players = int(parts[5]) if len(parts) > 5 else 0
                
                logging.info(f"Legacy protocol success: {current_players}/{max_players} players online")
                return current_players
            
        except (UnicodeDecodeError, ValueError, IndexError) as e:
            logging.debug(f"Legacy protocol parsing failed: {e}")
            return -1
        
        return -1
        
    except Exception as e:
        logging.debug(f"Legacy protocol failed: {e}")
        return -1
    finally:
        if sock:
            try:
                sock.close()
            except:
                pass

def try_query_protocol(ip_address, port, timeout):
    """Intenta usar el query protocol de Minecraft (puerto 25565 + query habilitado)"""
    sock = None
    try:
        # Query protocol usa UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # Handshake query
        magic = struct.pack('>H', 0xFEFD)
        packet_type = struct.pack('B', 0x09)  # Handshake
        session_id = struct.pack('>I', 1)
        
        handshake_packet = magic + packet_type + session_id
        sock.sendto(handshake_packet, (ip_address, port))
        
        # Recibir token
        response, addr = sock.recvfrom(1024)
        if len(response) < 5:
            return -1
        
        # Extraer token
        token = response[5:].strip(b'\x00')
        
        # Basic stat query
        packet_type = struct.pack('B', 0x00)  # Stat
        stat_packet = magic + packet_type + session_id + token
        sock.sendto(stat_packet, (ip_address, port))
        
        # Recibir respuesta
        response, addr = sock.recvfrom(1024)
        
        # Parsear respuesta básica
        # Formato: [type][session_id][motd][gametype][map][numplayers][maxplayers][hostport][hostip]
        if len(response) > 5:
            data = response[5:].split(b'\x00')
            if len(data) >= 6:
                try:
                    current_players = int(data[4].decode('utf-8'))
                    max_players = int(data[5].decode('utf-8'))
                    
                    logging.info(f"Query protocol success: {current_players}/{max_players} players online")
                    return current_players
                    
                except (ValueError, UnicodeDecodeError, IndexError):
                    return -1
        
        return -1
        
    except Exception as e:
        logging.debug(f"Query protocol failed: {e}")
        return -1
    finally:
        if sock:
            try:
                sock.close()
            except:
                pass

def get_current_players_from_logs(subscription_id):
    """
    Intenta determinar el número actual de jugadores analizando los logs recientes
    """
    try:
        credential = DefaultAzureCredential()
        container_client = ContainerInstanceManagementClient(credential, subscription_id)
        
        logs = container_client.containers.list_logs(
            resource_group_name=RESOURCE_GROUP,
            container_group_name=CONTAINER_NAME,
            container_name=CONTAINER_NAME,
            tail=100
        )
        
        if not logs or not logs.content:
            return 0
        
        log_lines = logs.content.split('\n')
        
        # Buscar patrones de conexión/desconexión recientes
        connected_players = set()
        
        # Revisar las últimas líneas para encontrar jugadores conectados
        for line in reversed(log_lines[-50:]):  # Últimas 50 líneas
            line_lower = line.lower()
            
            # Buscar conexiones
            if 'joined the game' in line_lower or 'logged in' in line_lower:
                # Extraer nombre del jugador
                import re
                # Patrones comunes: "Player joined the game" o "[INFO]: Player joined the game"
                match = re.search(r'(\w+)\s+(?:joined the game|logged in)', line, re.IGNORECASE)
                if match:
                    player_name = match.group(1)
                    connected_players.add(player_name)
                    logging.debug(f"Found connected player: {player_name}")
            
            # Buscar desconexiones
            elif 'left the game' in line_lower or 'lost connection' in line_lower or 'disconnected' in line_lower:
                import re
                match = re.search(r'(\w+)\s+(?:left the game|lost connection|disconnected)', line, re.IGNORECASE)
                if match:
                    player_name = match.group(1)
                    connected_players.discard(player_name)  # Remover si estaba conectado
                    logging.debug(f"Found disconnected player: {player_name}")
        
        player_count = len(connected_players)
        if player_count > 0:
            logging.info(f"Estimated {player_count} players from logs: {list(connected_players)}")
        
        return player_count
        
    except Exception as e:
        logging.error(f"Error analyzing player logs: {e}")
        return 0

def check_recent_player_activity(subscription_id, minutes_back=10):
    """
    Verifica si ha habido actividad de jugadores en los logs del contenedor
    en los últimos X minutos
    """
    try:
        credential = DefaultAzureCredential()
        container_client = ContainerInstanceManagementClient(credential, subscription_id)
        
        # Obtener logs del contenedor (más líneas para mejor análisis)
        logs = container_client.containers.list_logs(
            resource_group_name=RESOURCE_GROUP,
            container_group_name=CONTAINER_NAME,
            container_name=CONTAINER_NAME,
            tail=200
        )
        
        if not logs or not logs.content:
            logging.warning("No logs available from container")
            return False
        
        log_lines = logs.content.split('\n')
        
        # Patrones específicos para servidores offline (itzg/minecraft-server)
        activity_patterns = [
            'joined the game',
            'left the game', 
            'logged in with entity id',
            'lost connection',
            '[Not Secure]',  # Chat messages en servidores offline
            'issued server command',
            'was slain',
            'drowned',
            'fell',
            'has made the advancement',
            'UUID of player',
            'moving too quickly',
            'tried to swim in lava',
            'went up in flames',
            'blew up',
            'hit the ground too hard',
            'was shot',
            'was killed',
            'starved to death',
            'suffocated',
            'experienced kinetic energy',
            'fell out of the world',
            'saving chunks',  # Indica actividad del servidor
            'automatic saving',
            'ThreadedAnvilChunkStorage'  # Actividad de guardado
        ]
        
        # Buscar cualquier actividad reciente
        recent_activity_found = False
        activity_count = 0
        
        for line in log_lines[-50:]:  # Revisar las últimas 50 líneas más recientes
            line_lower = line.lower()
            if any(pattern.lower() in line_lower for pattern in activity_patterns):
                activity_count += 1
                if not recent_activity_found:
                    logging.info(f"Player activity found in logs: {line.strip()}")
                    recent_activity_found = True
        
        if activity_count > 0:
            logging.info(f"Total player activity events found in recent logs: {activity_count}")
            return True
        
        # También buscar conexiones TCP recientes (indicativo de intentos de conexión)
        connection_patterns = [
            'connection',
            'disconnect',
            'timeout',
            'handshake'
        ]
        
        connection_count = 0
        for line in log_lines[-30:]:  # Revisar conexiones en las últimas 30 líneas
            line_lower = line.lower()
            if any(pattern in line_lower for pattern in connection_patterns):
                connection_count += 1
        
        if connection_count > 2:  # Múltiples eventos de conexión sugieren actividad
            logging.info(f"Recent connection activity detected: {connection_count} events")
            return True
        
        logging.info("No recent player activity found in container logs")
        return False
        
    except Exception as e:
        logging.error(f"Error checking container logs: {e}")
        # En caso de error, ser conservador y asumir que hay actividad
        return True

def get_container_info(subscription_id):
    """
    Obtiene información del contenedor de Minecraft
    """
    try:
        credential = DefaultAzureCredential()
        container_client = ContainerInstanceManagementClient(credential, subscription_id)
        
        container = container_client.container_groups.get(RESOURCE_GROUP, CONTAINER_NAME)
        
        if container.instance_view and container.instance_view.state == "Running":
            ip_address = container.ip_address.ip if container.ip_address else None
            return {
                "status": "Running",
                "ip_address": ip_address
            }
        else:
            return {
                "status": container.instance_view.state if container.instance_view else "Unknown",
                "ip_address": None
            }
            
    except Exception as e:
        logging.error(f"Error getting container info: {e}")
        return None

def stop_container(subscription_id):
    """
    Detiene el contenedor de Minecraft
    """
    try:
        credential = DefaultAzureCredential()
        container_client = ContainerInstanceManagementClient(credential, subscription_id)
        
        logging.info(f"Stopping container {CONTAINER_NAME} in resource group {RESOURCE_GROUP}")
        operation = container_client.container_groups.begin_stop(RESOURCE_GROUP, CONTAINER_NAME)
        operation.wait()
        
        logging.info("Container stopped successfully")
        return True
        
    except Exception as e:
        logging.error(f"Error stopping container: {e}")
        return False

def get_table_client():
    """
    Obtiene cliente de Azure Table Storage
    """
    try:
        connection_string = os.environ["AzureWebJobsStorage"]
        table_service = TableServiceClient.from_connection_string(connection_string)
        table_client = table_service.get_table_client("minecraftmonitor")
        return table_client
    except Exception as e:
        logging.error(f"Error creating table client: {e}")
        return None

def get_monitoring_state(table_client):
    """
    Obtiene el estado actual del monitoreo desde Table Storage
    """
    try:
        entity = table_client.get_entity("state", "current")
        return {
            "last_players_seen": entity.get("last_players_seen"),
            "consecutive_empty_checks": entity.get("consecutive_empty_checks", 0),
            "consecutive_failures": entity.get("consecutive_failures", 0),
            "last_check_time": entity.get("last_check_time")
        }
    except:
        # Primera ejecución o entidad no existe
        return {
            "last_players_seen": datetime.now(timezone.utc).isoformat(),
            "consecutive_empty_checks": 0,
            "last_check_time": None
        }

def update_monitoring_state(table_client, state):
    """
    Actualiza el estado del monitoreo en Table Storage
    """
    try:
        entity = TableEntity()
        entity["PartitionKey"] = "state"
        entity["RowKey"] = "current"
        entity["last_players_seen"] = state["last_players_seen"]
        entity["consecutive_empty_checks"] = state["consecutive_empty_checks"]
        entity["consecutive_failures"] = state.get("consecutive_failures", 0)
        entity["last_check_time"] = datetime.now(timezone.utc).isoformat()
        
        table_client.upsert_entity(entity)
        return True
    except Exception as e:
        logging.error(f"Error updating monitoring state: {e}")
        return False

@app.timer_trigger(schedule="0 */3 * * * *", arg_name="myTimer", run_on_startup=False,
                   use_monitor=False) 
def minecraft_monitor(myTimer: func.TimerRequest) -> None:
    """
    Función principal que se ejecuta cada 3 minutos para monitorear el servidor
    """
    logging.info('Minecraft monitor function started')
    
    # Obtener variables de entorno
    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription_id:
        logging.error("AZURE_SUBSCRIPTION_ID environment variable not set")
        return
    
    # Obtener cliente de tabla
    table_client = get_table_client()
    if not table_client:
        logging.error("Could not create table client")
        return
    
    # Crear tabla si no existe
    try:
        table_client.create_table()
    except:
        pass  # Tabla ya existe
    
    # Obtener estado actual
    state = get_monitoring_state(table_client)
    
    # Obtener información del contenedor
    container_info = get_container_info(subscription_id)
    if not container_info:
        logging.error("Could not get container information")
        return
    
    # Si el contenedor no está ejecutándose, no hacer nada
    if container_info["status"] != "Running":
        logging.info(f"Container is not running (status: {container_info['status']}), skipping check")
        return
    
    # Si no hay IP, no podemos verificar jugadores
    if not container_info["ip_address"]:
        logging.warning("Container is running but has no IP address")
        return
    
    # Para servidores offline, intentar protocolo pero depender principalmente de logs
    logging.info(f"Attempting to connect to Minecraft server at {container_info['ip_address']}:{MINECRAFT_PORT}")
    player_count = get_minecraft_player_count(container_info["ip_address"], MINECRAFT_PORT)
    
    # Verificar actividad en logs (método principal para servidores offline)
    recent_activity = check_recent_player_activity(subscription_id, minutes_back=5)
    current_players_from_logs = get_current_players_from_logs(subscription_id)
    
    if player_count == -1:
        logging.info("Server protocol not responding (likely offline-mode server)")
        
        # Para servidores offline, usar logs como fuente principal
        if recent_activity or current_players_from_logs > 0:
            logging.info(f"Player activity detected in logs: {current_players_from_logs} players estimated")
            player_count = current_players_from_logs
            state["consecutive_failures"] = 0
        else:
            # Incrementar contador de fallas solo si no hay actividad en logs
            consecutive_failures = state.get("consecutive_failures", 0) + 1
            state["consecutive_failures"] = consecutive_failures
            
            logging.info(f"No protocol response and no log activity. Consecutive checks: {consecutive_failures}")
            
            # Después de 2 intentos sin actividad (6 minutos), asumir vacío
            if consecutive_failures >= 2:
                logging.info("No activity detected for 6+ minutes in offline-mode server")
                player_count = 0  # Tratar como servidor vacío
                state["consecutive_failures"] = 0
            else:
                # Actualizar estado pero no continuar con lógica de apagado
                update_monitoring_state(table_client, state)
                return
    else:
        # Protocolo funcionó (servidor online-mode)
        logging.info("Server responded to protocol (online-mode server)")
        state["consecutive_failures"] = 0
    
    logging.info(f"Current player count: {player_count} (detected via {'protocol' if player_count >= 0 and state.get('consecutive_failures', 0) == 0 else 'log analysis'})")
    
    if player_count > 0:
        # Hay jugadores conectados
        state["last_players_seen"] = datetime.now(timezone.utc).isoformat()
        state["consecutive_empty_checks"] = 0
        state["consecutive_failures"] = 0
        logging.info(f"Players detected: {player_count}. Server staying online. Resetting all counters.")
    else:
        # No hay jugadores
        state["consecutive_empty_checks"] += 1
        logging.info(f"No players online. Consecutive empty checks: {state['consecutive_empty_checks']}")
        
        # Verificar si debemos apagar el servidor
        if state["consecutive_empty_checks"] >= 2:  # 2 checks * 3 minutos = 6 minutos
            logging.info(f"Server has been empty for {state['consecutive_empty_checks'] * 3} minutes.")
            
            # Verificación final de actividad antes del apagado
            final_activity_check = check_recent_player_activity(subscription_id, minutes_back=10)
            if final_activity_check:
                logging.info("Final activity check found recent player activity. Postponing shutdown.")
                state["consecutive_empty_checks"] = 0  # Resetear contador
                state["last_players_seen"] = datetime.now(timezone.utc).isoformat()
            else:
                logging.info("Final activity check confirmed no recent activity. Proceeding with shutdown...")
                
                if stop_container(subscription_id):
                    logging.info("Container shutdown initiated successfully")
                    # Resetear estado después del apagado exitoso
                    state["consecutive_empty_checks"] = 0
                    state["consecutive_failures"] = 0
                    state["last_players_seen"] = datetime.now(timezone.utc).isoformat()
                else:
                    logging.error("Failed to stop container")
        else:
            minutes_until_shutdown = (2 - state["consecutive_empty_checks"]) * 3
            logging.info(f"Server will shutdown in {minutes_until_shutdown} minutes if no players join")
    
    # Actualizar estado en storage
    update_monitoring_state(table_client, state)
    
    logging.info('Minecraft monitor function completed')
