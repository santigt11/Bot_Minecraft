import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import aiohttp
import json
import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
import logging
from typing import Optional

# Configuración
RESOURCE_GROUP = "minecraft-rg"
CONTAINER_NAME = "minecraft-server"
SUBSCRIPTION_ID = "39626f70-6824-4598-96f7-cd57f0f39206"

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Configurar intents del bot
intents = discord.Intents.default()
intents.message_content = True

# Crear bot con soporte para comandos slash
bot = commands.Bot(command_prefix='!', intents=intents)
tree = app_commands.CommandTree(bot)

class MinecraftManager:
    def __init__(self):
        # Configurar credenciales para Railway/Render
        if os.getenv('AZURE_CLIENT_ID'):
            # Usar Service Principal si está configurado
            from azure.identity import ClientSecretCredential
            self.credential = ClientSecretCredential(
                tenant_id=os.getenv('AZURE_TENANT_ID'),
                client_id=os.getenv('AZURE_CLIENT_ID'),
                client_secret=os.getenv('AZURE_CLIENT_SECRET')
            )
        else:
            # Usar DefaultAzureCredential para desarrollo local
            self.credential = DefaultAzureCredential()
        
        self.container_client = ContainerInstanceManagementClient(self.credential, SUBSCRIPTION_ID)
    
    async def get_server_status(self):
        """Obtiene el estado actual del servidor"""
        try:
            container = self.container_client.container_groups.get(RESOURCE_GROUP, CONTAINER_NAME)
            
            status = container.instance_view.state if container.instance_view else "Unknown"
            ip_address = container.ip_address.ip if container.ip_address else "No IP"
            
            return {
                "status": status,
                "ip_address": ip_address,
                "name": container.name
            }
        except Exception as e:
            logging.error(f"Error getting server status: {e}")
            return None
    
    async def start_server(self):
        """Inicia el servidor de Minecraft"""
        try:
            logging.info("Starting Minecraft server...")
            operation = self.container_client.container_groups.begin_start(RESOURCE_GROUP, CONTAINER_NAME)
            
            # Esperar a que complete (esto puede tomar unos minutos)
            result = operation.result()
            return True
        except Exception as e:
            logging.error(f"Error starting server: {e}")
            return False
    
    async def stop_server(self):
        """Detiene el servidor de Minecraft"""
        try:
            logging.info("Stopping Minecraft server...")
            operation = self.container_client.container_groups.begin_stop(RESOURCE_GROUP, CONTAINER_NAME)
            
            # Esperar a que complete
            result = operation.result()
            return True
        except Exception as e:
            logging.error(f"Error stopping server: {e}")
            return False

# Instancia del manager
minecraft_manager = MinecraftManager()

async def check_server_status(interaction: discord.Interaction):
    """Verifica el estado del servidor y devuelve la información"""
    await interaction.response.defer()
    
    status_info = await minecraft_manager.get_server_status()
    
    if not status_info:
        await interaction.followup.send("❌ Error al verificar el estado del servidor")
        return None
        
    return status_info

@bot.tree.command(name="status", description="Muestra el estado del servidor de Minecraft")
async def server_status(interaction: discord.Interaction):
    """Comando para ver el estado del servidor"""
    await interaction.response.defer()
    
    status_info = await check_server_status(interaction)
    if not status_info:
        return
    
    embed = discord.Embed(
        title="🎮 Estado del Servidor Minecraft",
        color=0x00ff00 if status_info["status"] == "Running" else 0xff0000
    )
    
    status_emoji = "🟢" if status_info["status"] == "Running" else "🔴"
    embed.add_field(name="Estado", value=f"{status_emoji} {status_info['status']}", inline=True)
    embed.add_field(name="IP", value=f"📡 {status_info['ip_address']}", inline=True)
    embed.add_field(name="Puerto", value="🔌 25565", inline=True)
    
    if status_info["status"] == "Running":
        embed.add_field(name="Conectar", value=f"`{status_info['ip_address']}:25565`", inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="start", description="Inicia el servidor de Minecraft")
async def start_server(interaction: discord.Interaction):
    """Comando para iniciar el servidor"""
    await interaction.response.defer()
    
    # Verificar estado actual
    status_info = await check_server_status(interaction)
    if not status_info:
        return
    
    if status_info["status"] == "Running":
        await interaction.followup.send("⚠️ El servidor ya está en ejecución")
        return
    
    # Enviar mensaje inicial
    await interaction.followup.send("🚀 Iniciando servidor de Minecraft... Esto puede tomar unos minutos.")
    
    # Iniciar el servidor
    success = await minecraft_manager.start_server()
    
    if not success:
        await interaction.followup.send("❌ Error al iniciar el servidor")
        return
    
    # Esperar y verificar el estado varias veces
    max_attempts = 12  # 12 intentos * 10 segundos = 2 minutos
    for attempt in range(max_attempts):
        await asyncio.sleep(10)  # Esperar 10 segundos entre intentos
        status_info = await minecraft_manager.get_server_status()
        
        if status_info and status_info["status"] == "Running" and status_info["ip_address"] != "No IP":
            embed = discord.Embed(
                title="✅ Servidor Iniciado",
                description="El servidor de Minecraft está ahora en línea!",
                color=0x00ff00
            )
            embed.add_field(name="IP del Servidor", value=f"`{status_info['ip_address']}:25565`", inline=False)
            embed.add_field(name="Estado", value="🟢 En línea y listo para jugar", inline=False)
            await interaction.followup.send(embed=embed)
            return
    
    # Si llegamos aquí, el servidor no se inició correctamente
    await interaction.followup.send("⚠️ El servidor está tardando más de lo esperado en iniciar. Por favor, verifica el estado en unos minutos.")

@bot.tree.command(name="stop", description="Detiene el servidor de Minecraft")
async def stop_server(interaction: discord.Interaction):
    """Comando para detener el servidor"""
    await interaction.response.defer()
    
    # Verificar estado actual
    status_info = await check_server_status(interaction)
    if not status_info:
        return
    
    if status_info["status"] != "Running":
        await interaction.followup.send("⚠️ El servidor no está en ejecución")
        return
    
    # Enviar mensaje inicial
    await interaction.followup.send("🛑 Deteniendo servidor de Minecraft...")
    
    # Detener el servidor
    success = await minecraft_manager.stop_server()
    
    if success:
        # Verificar que se detuvo correctamente
        await asyncio.sleep(5)  # Esperar un momento para que se complete la operación
        status_info = await minecraft_manager.get_server_status()
        
        if status_info and status_info["status"] != "Running":
            embed = discord.Embed(
                title="✅ Servidor Detenido",
                description="El servidor de Minecraft ha sido detenido correctamente.",
                color=0xff9900
            )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("⚠️ El servidor está tardando en detenerse. Por favor, verifica el estado en unos segundos.")
    else:
        await interaction.followup.send("❌ Error al detener el servidor")

@bot.tree.command(name="ayuda", description="Muestra todos los comandos disponibles")
async def help_minecraft(interaction: discord.Interaction):
    """Comando de ayuda personalizado"""
    embed = discord.Embed(
        title="🎮 Comandos del Bot Minecraft",
        description="Lista de comandos disponibles (usa `/` para ver los comandos):",
        color=0x0099ff
    )
    
    embed.add_field(
        name="/status", 
        value="🔍 Muestra el estado actual del servidor", 
        inline=False
    )
    embed.add_field(
        name="/start", 
        value="🚀 Inicia el servidor de Minecraft", 
        inline=False
    )
    embed.add_field(
        name="/stop", 
        value="⛔ Detiene el servidor de Minecraft", 
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f'{bot.user} ha iniciado sesión!')
    print(f'Bot está en {len(bot.guilds)} servidores')
    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

if __name__ == "__main__":
    # El token debe estar en una variable de entorno
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN no está configurado")
        print("Configura la variable de entorno DISCORD_BOT_TOKEN con el token de tu bot")
        exit(1)
    
    bot.run(TOKEN)