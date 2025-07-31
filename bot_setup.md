# Configuración del Bot de Discord

## 1. Crear Bot en Discord

1. Ve a https://discord.com/developers/applications
2. Clic en "New Application"
3. Dale un nombre (ej: "Minecraft Server Manager")
4. Ve a la sección "Bot"
5. Clic en "Add Bot"
6. Copia el **Token** (lo necesitarás después)

## 2. Configurar Permisos

En la sección "OAuth2" > "URL Generator":
- **Scopes**: `bot`
- **Bot Permissions**: 
  - Send Messages
  - Use Slash Commands
  - Embed Links
  - Read Message History

Copia la URL generada y úsala para invitar el bot a tu servidor.

## 3. Instalar y Ejecutar

```bash
# Instalar dependencias
pip install -r requirements_bot.txt

# Configurar token (Windows PowerShell)
$env:DISCORD_BOT_TOKEN="tu_token_aqui"

# Configurar token (Windows CMD)
set DISCORD_BOT_TOKEN=tu_token_aqui

# Configurar token (Linux/Mac)
export DISCORD_BOT_TOKEN=tu_token_aqui

# Ejecutar bot
python discord_bot.py
```

## 4. Comandos Disponibles

- `!status` - Ver estado del servidor
- `!start` - Iniciar servidor
- `!stop` - Detener servidor  
- `!help_minecraft` - Ver ayuda

## 5. Desplegar en Azure (Opcional)

Para que el bot esté siempre online, puedes desplegarlo en Azure Container Instances:

```bash
# Crear imagen Docker
docker build -t minecraft-discord-bot .

# Subir a Azure Container Registry
az acr build --registry tu-registry --image minecraft-bot .

# Crear container instance
az container create \
  --resource-group minecraft-rg \
  --name minecraft-discord-bot \
  --image tu-registry.azurecr.io/minecraft-bot \
  --environment-variables DISCORD_BOT_TOKEN=tu_token \
  --restart-policy Always
```