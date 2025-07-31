import discord
from discord.ext import commands
import asyncio
import aiohttp
import json
import os
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
import logging

# Configuración
RESOURCE_GROUP = "minecraft-rg"
CONTAINER_NAME = "minecraft-server"
SUBSCRIPTION_ID = "39626f70-6824-4598-96f7-cd57f0f39206"

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Configurar intents del bot
intents = discord.Intents.default()
intents.message_content = True

# Crear bot
bot = commands.Bot(command_prefix='!', intents=intents)

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

@bot.event
async def on_ready():
    print(f'{bot.user} ha iniciado sesión!')
    print(f'Bot está en {len(bot.guilds)} servidores')

@bot.command(name='status', help='Muestra el estado del servidor de Minecraft')
async def server_status(ctx):
    """Comando para ver el estado del servidor"""
    await ctx.send("🔍 Verificando estado del servidor...")
    
    status_info = await minecraft_manager.get_server_status()
    
    if status_info:
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
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Error al obtener el estado del servidor")

@bot.command(name='start', help='Inicia el servidor de Minecraft')
async def start_server(ctx):
    """Comando para iniciar el servidor"""
    # Verificar estado actual
    status_info = await minecraft_manager.get_server_status()
    
    if not status_info:
        await ctx.send("❌ Error al verificar el estado del servidor")
        return
    
    if status_info["status"] == "Running":
        await ctx.send("⚠️ El servidor ya está ejecutándose!")
        return
    
    await ctx.send("🚀 Iniciando servidor de Minecraft... Esto puede tomar unos minutos.")
    
    success = await minecraft_manager.start_server()
    
    if success:
        # Esperar un poco y verificar el estado
        await asyncio.sleep(10)
        status_info = await minecraft_manager.get_server_status()
        
        embed = discord.Embed(
            title="✅ Servidor Iniciado",
            description="El servidor de Minecraft se está iniciando",
            color=0x00ff00
        )
        
        if status_info and status_info["ip_address"] != "No IP":
            embed.add_field(name="IP del Servidor", value=f"`{status_info['ip_address']}:25565`", inline=False)
            embed.add_field(name="Nota", value="El servidor puede tardar 2-3 minutos en estar completamente listo", inline=False)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Error al iniciar el servidor")

@bot.command(name='stop', help='Detiene el servidor de Minecraft')
async def stop_server(ctx):
    """Comando para detener el servidor"""
    # Verificar estado actual
    status_info = await minecraft_manager.get_server_status()
    
    if not status_info:
        await ctx.send("❌ Error al verificar el estado del servidor")
        return
    
    if status_info["status"] != "Running":
        await ctx.send("⚠️ El servidor no está ejecutándose")
        return
    
    await ctx.send("🛑 Deteniendo servidor de Minecraft...")
    
    success = await minecraft_manager.stop_server()
    
    if success:
        embed = discord.Embed(
            title="✅ Servidor Detenido",
            description="El servidor de Minecraft ha sido detenido exitosamente",
            color=0xff9900
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Error al detener el servidor")

@bot.command(name='help_minecraft', help='Muestra todos los comandos disponibles')
async def help_minecraft(ctx):
    """Comando de ayuda personalizado"""
    embed = discord.Embed(
        title="🎮 Comandos del Bot Minecraft",
        description="Lista de comandos disponibles:",
        color=0x0099ff
    )
    
    embed.add_field(
        name="!status", 
        value="🔍 Muestra el estado actual del servidor", 
        inline=False
    )
    embed.add_field(
        name="!start", 
        value="🚀 Inicia el servidor de Minecraft", 
        inline=False
    )
    embed.add_field(
        name="!stop", 
        value="🛑 Detiene el servidor de Minecraft", 
        inline=False
    )
    
    embed.set_footer(text="Bot creado para gestionar el servidor de Minecraft")
    
    await ctx.send(embed=embed)

# Manejo de errores
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Comando no encontrado. Usa `!help_minecraft` para ver los comandos disponibles.")
    else:
        await ctx.send(f"❌ Error: {str(error)}")
        logging.error(f"Command error: {error}")

if __name__ == "__main__":
    # El token debe estar en una variable de entorno
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN no está configurado")
        print("Configura la variable de entorno DISCORD_BOT_TOKEN con el token de tu bot")
        exit(1)
    
    bot.run(TOKEN)