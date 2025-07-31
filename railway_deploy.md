# Desplegar Bot en Railway (GRATIS y Fácil)

Railway es una plataforma que te permite hospedar tu bot **GRATIS** sin necesidad de tener tu PC prendida.

## 1. Preparar el proyecto

Ya tienes todos los archivos necesarios:
- `discord_bot.py`
- `requirements_bot.txt` 
- `Dockerfile`

## 2. Crear cuenta en Railway

1. Ve a https://railway.app
2. Clic en "Start a New Project"
3. Conecta tu cuenta de GitHub

## 3. Subir código a GitHub

```bash
# Crear repositorio en GitHub (desde la web)
# Luego en tu PC:

git init
git add .
git commit -m "Discord bot para Minecraft"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/minecraft-discord-bot.git
git push -u origin main
```

## 4. Desplegar en Railway

1. En Railway, clic en "Deploy from GitHub repo"
2. Selecciona tu repositorio
3. Railway detectará automáticamente el Dockerfile
4. Antes de desplegar, configura las variables de entorno:
   - Ve a "Variables"
   - Agrega: `DISCORD_BOT_TOKEN` = tu_token_de_discord
   - Agrega: `AZURE_SUBSCRIPTION_ID` = 39626f70-6824-4598-96f7-cd57f0f39206
5. Clic en "Deploy"

## 5. Configurar autenticación de Azure

Para que el bot pueda controlar Azure desde Railway, necesitas crear un Service Principal:

```bash
# En tu PC, ejecuta:
az ad sp create-for-rbac --name "minecraft-discord-bot" --role contributor --scopes /subscriptions/39626f70-6824-4598-96f7-cd57f0f39206/resourceGroups/minecraft-rg
```

Esto te dará algo como:
```json
{
  "appId": "12345678-1234-1234-1234-123456789012",
  "displayName": "minecraft-discord-bot",
  "password": "tu-password-secreto",
  "tenant": "87654321-4321-4321-4321-210987654321"
}
```

Agrega estas variables en Railway:
- `AZURE_CLIENT_ID` = appId
- `AZURE_CLIENT_SECRET` = password  
- `AZURE_TENANT_ID` = tenant

## 6. ¡Listo!

Tu bot estará online 24/7 sin necesidad de tener tu PC prendida.

**Plan gratuito de Railway:**
- 500 horas/mes (suficiente para 24/7)
- $5 de crédito gratis mensual
- Perfecto para bots pequeños

## Alternativa: Render.com

Si prefieres otra opción gratuita:

1. Ve a https://render.com
2. Conecta GitHub
3. Crea "New Web Service"
4. Selecciona tu repo
5. Configura las mismas variables de entorno
6. Deploy

¡Ambas opciones son completamente gratuitas!