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
tree = bot.tree

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
    
    def _get_server_status_sync(self):
        """Versión síncrona de get_server_status para ejecutar en un hilo separado"""
        try:
            container = self.container_client.container_groups.get(RESOURCE_GROUP, CONTAINER_NAME)
            status = container.instance_view.state if container.instance_view else "Unknown"
            ip_address = container.ip_address.ip if container.ip_address else "No IP"
            return {"status": status, "ip_address": ip_address, "name": container.name}
        except Exception as e:
            logging.error(f"Error getting server status: {e}")
            return None
            
    async def get_server_status(self):
        """Obtiene el estado actual del servidor"""
        return await self._run_in_executor(self._get_server_status_sync)
    
    async def _run_in_executor(self, func, *args):
        """Ejecuta una función síncrona en un ejecutor de hilos"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args)

    def _start_server_sync(self):
        """Versión síncrona de start_server para ejecutar en un hilo separado"""
        try:
            operation = self.container_client.container_groups.begin_start(
                resource_group_name=RESOURCE_GROUP,
                container_group_name=CONTAINER_NAME
            )
            result = operation.result()
            return True
        except Exception as e:
            logging.error(f"Error al iniciar el servidor: {e}")
            return False
            
    async def start_server(self):
        """Inicia el servidor de Minecraft"""
        return await self._run_in_executor(self._start_server_sync)
    
    def _stop_server_sync(self):
        """Versión síncrona de stop_server para ejecutar en un hilo separado"""
        try:
            # Primero intentamos detener el contenedor usando la API de reinicio con estado detenido
            container = self.container_client.container_groups.get(
                resource_group_name=RESOURCE_GROUP,
                container_group_name=CONTAINER_NAME
            )
            
            # Si el contenedor ya está detenido, no hacemos nada
            if container.instance_view and container.instance_view.state.lower() != 'running':
                return True
                
            # Detener el contenedor
            self.container_client.container_groups.stop(
                resource_group_name=RESOURCE_GROUP,
                container_group_name=CONTAINER_NAME
            )
            
            # Verificar que se detuvo
            max_attempts = 12
            for _ in range(max_attempts):
                container = self.container_client.container_groups.get(
                    resource_group_name=RESOURCE_GROUP,
                    container_group_name=CONTAINER_NAME
                )
                if container.instance_view and container.instance_view.state.lower() != 'running':
                    return True
                time.sleep(5)
                
            logging.warning("El contenedor no se detuvo en el tiempo esperado")
            return False
            
        except Exception as e:
            logging.error(f"Error al detener el servidor: {e}")
            return False
            
    async def stop_server(self):
        """Detiene el servidor de Minecraft"""
        return await self._run_in_executor(self._stop_server_sync)

# Instancia del manager
minecraft_manager = MinecraftManager()

async def check_server_status(interaction: discord.Interaction):
    """Verifica el estado del servidor y devuelve la información"""
    # Solo diferir la respuesta si no se ha respondido aún
    if not interaction.response.is_done():
        await interaction.response.defer()
    
    status_info = await minecraft_manager.get_server_status()
    
    if not status_info:
        if interaction.response.is_done():
            await interaction.followup.send("❌ Error al verificar el estado del servidor")
        else:
            await interaction.response.send_message("❌ Error al verificar el estado del servidor")
        return None
        
    return status_info

@bot.tree.command(name="statusminecraft", description="Muestra el estado del servidor de Minecraft")
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

@bot.tree.command(name="startminecraft", description="Inicia el servidor de Minecraft")
async def start_server(interaction: discord.Interaction):
    """Comando para iniciar el servidor"""
    try:
        # Diferir la respuesta si no se ha respondido
        if not interaction.response.is_done():
            await interaction.response.defer()
        
        # Verificar estado actual
        status_info = await minecraft_manager.get_server_status()
        
        if not status_info:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Error al verificar el estado del servidor")
            else:
                await interaction.response.send_message("❌ Error al verificar el estado del servidor")
            return
        
        if status_info["status"] == "Running":
            msg = "⚠️ El servidor ya está en ejecución"
            if interaction.response.is_done():
                await interaction.followup.send(msg)
            else:
                await interaction.response.send_message(msg)
            return
        
        # Enviar mensaje inicial
        msg = "🚀 Iniciando servidor de Minecraft... Esto puede tomar unos minutos."
        if interaction.response.is_done():
            await interaction.followup.send(msg)
        else:
            await interaction.response.send_message(msg)
        
        # Iniciar el servidor
        success = await minecraft_manager.start_server()
        
        if not success:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Error al iniciar el servidor")
            else:
                await interaction.response.send_message("❌ Error al iniciar el servidor")
            return
        
        # Esperar y verificar el estado varias veces
        max_attempts = 12  # 12 intentos * 10 segundos = 2 minutos
        for attempt in range(max_attempts):
            await asyncio.sleep(10)  # Esperar 10 segundos entre intentos
            status_info = await minecraft_manager.get_server_status()
            
            if status_info and status_info["status"] == "Running" and status_info["ip_address"] != "No IP":
                msg = (f"✅ **¡Servidor Iniciado!**\n\n"
                      f"🔗 **IP del Servidor:** `minecraftsanti.eastus.azurecontainer.io`\n"
                      f"🟢 **Estado:** En línea y listo para jugar")
                
                if interaction.response.is_done():
                    await interaction.followup.send(msg)
                else:
                    await interaction.response.send_message(msg)
                return
        
        # Si llegamos aquí, el servidor no se inició correctamente
        msg = "⚠️ El servidor está tardando más de lo esperado en iniciar. Por favor, verifica el estado en unos minutos."
        if interaction.response.is_done():
            await interaction.followup.send(msg)
        else:
            await interaction.response.send_message(msg)
    
    except Exception as e:
        error_msg = f"❌ Error inesperado: {str(e)}"
        if interaction.response.is_done():
            await interaction.followup.send(error_msg)
        else:
            await interaction.response.send_message(error_msg)
        logging.error(f"Error en start_server: {e}")

@bot.tree.command(name="stopminecraft", description="Detiene el servidor de Minecraft")
async def stop_server(interaction: discord.Interaction):
    """Comando para detener el servidor"""
    try:
        # Diferir la respuesta si no se ha respondido
        if not interaction.response.is_done():
            await interaction.response.defer()
        
        # Verificar estado actual
        status_info = await minecraft_manager.get_server_status()
        
        if not status_info:
            msg = "❌ No se pudo obtener el estado del servidor"
            if interaction.response.is_done():
                await interaction.followup.send(msg)
            else:
                await interaction.response.send_message(msg)
            return
            
        status_text = "🟢 En línea" if status_info["status"].lower() == "running" else "🔴 Detenido"
        msg = (
            f"📊 **Estado del Servidor**\n\n"
            f"🖥️ **Estado:** {status_text}\n"
            f"🌐 **IP:** `{status_info.get('ip_address', 'No disponible')}:25565`\n"
            f"📅 **Última actualización:** <t:{int(time.time())}:R>"
        )
        
        if interaction.response.is_done():
            await interaction.followup.send(msg)
        else:
            await interaction.response.send_message(msg)
            
        # Detener el servidor
        success = await minecraft_manager.stop_server()
        
        if not success:
            if interaction.response.is_done():
                await interaction.followup.send("❌ Error al detener el servidor")
            else:
                await interaction.response.send_message("❌ Error al detener el servidor")
            return
        
        # Verificar que se detuvo correctamente
        await asyncio.sleep(5)  # Esperar un momento para que se complete la operación
        status_info = await minecraft_manager.get_server_status()
        
        if status_info and status_info["status"] != "Running":
            msg = ("✅ **¡Servidor Detenido!**\n\n"
                  "🔴 El servidor de Minecraft ha sido detenido correctamente.")
            if interaction.response.is_done():
                await interaction.followup.send(msg)
            else:
                await interaction.response.send_message(msg)
        else:
            msg = "⚠️ El servidor está tardando en detenerse. Por favor, verifica el estado en unos segundos."
            if interaction.response.is_done():
                await interaction.followup.send(msg)
            else:
                await interaction.response.send_message(msg)
    
    except Exception as e:
        error_msg = f"❌ Error inesperado: {str(e)}"
        if interaction.response.is_done():
            await interaction.followup.send(error_msg)
        else:
            await interaction.response.send_message(error_msg)
        logging.error(f"Error en stop_server: {e}")

@bot.tree.command(name="ayudaminecraft", description="Muestra todos los comandos disponibles para Minecraft")
async def help_minecraft(interaction: discord.Interaction):
    """Comando de ayuda personalizado"""
    embed = discord.Embed(
        title="🎮 Comandos del Bot Minecraft",
        description="Lista de comandos disponibles (usa `/` para ver los comandos):",
        color=0x0099ff
    )
    
    embed.add_field(
        name="/statusminecraft", 
        value="🔍 Muestra el estado actual del servidor", 
        inline=False
    )
    embed.add_field(
        name="/startminecraft", 
        value="🚀 Inicia el servidor de Minecraft", 
        inline=False
    )
    embed.add_field(
        name="/stopminecraft", 
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

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # No responder a comandos con prefijo, ya que ahora usamos comandos slash
        return
    await ctx.send(f"❌ Error: {str(error)}")
    logging.error(f"Command error: {error}")

# Sincronizar comandos al iniciar
@bot.event
async def setup_hook():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

@bot.event
async def on_ready():
    print(f'✅ {bot.user} ha iniciado sesión!')
    print(f'🌐 Conectado a {len(bot.guilds)} servidores')
    print('🔍 Usa /ayuda para ver los comandos disponibles')
    
    # Intentar sincronizar comandos al iniciar
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos sincronizados")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

if __name__ == "__main__":
    # El token debe estar en una variable de entorno
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN no está configurado")
        print("🔧 Configura la variable de entorno DISCORD_BOT_TOKEN con el token de tu bot")
        exit(1)
    
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Error de autenticación: Token inválido")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")