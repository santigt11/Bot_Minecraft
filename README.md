# Minecraft Server Auto-Shutdown Azure Function

Esta Azure Function monitorea automáticamente tu servidor de Minecraft y lo apaga cuando no hay jugadores conectados por más de 6 minutos.

## ¿Qué hace?

- **Monitorea cada 3 minutos** tu servidor de Minecraft
- **Cuenta jugadores conectados** usando el protocolo Server List Ping
- **Apaga automáticamente** el contenedor después de **6 minutos sin jugadores** (2 checks consecutivos)
- **Usa Azure Table Storage** para mantener el estado entre ejecuciones
- **Totalmente serverless** - no necesitas mantener tu PC prendida

## Configuración

### Información de tu setup:
- **Resource Group**: `minecraft-rg`
- **Container Name**: `minecraft-server`
- **Image**: `itzg/minecraft-server`
- **Puerto**: `25565`

### Requisitos previos

1. **Azure CLI** - [Instalar aquí](https://aka.ms/installazurecliwindows)
2. **Azure Functions Core Tools** - Instalar con:
   ```powershell
   npm install -g azure-functions-core-tools@4 --unsafe-perm true
   ```
3. **Python 3.11** (si quieres testear localmente)

## Instalación

### ✅ COMPLETADO - Tu Function App ya está desplegada

**Nombre de la Function App:** `minecraft-monitor-test123`  
**Estado:** Running  
**Ubicación:** East US  
**Configuración:** ✅ Variables de entorno configuradas  
**Permisos:** ✅ Identidad administrada con permisos de Contributor  
**Código:** ✅ Función desplegada y configurada para ejecutarse cada 3 minutos

### Comando utilizado para el despliegue:
```bash
# Se creó manualmente con estos comandos:
az functionapp create --resource-group minecraft-rg --consumption-plan-location eastus --runtime python --runtime-version 3.11 --functions-version 4 --name minecraft-monitor-test123 --os-type Linux --storage-account minecraftmonitorstorage
az functionapp config appsettings set --name minecraft-monitor-test123 --resource-group minecraft-rg --settings "AZURE_SUBSCRIPTION_ID=39626f70-6824-4598-96f7-cd57f0f39206"
az functionapp identity assign --name minecraft-monitor-test123 --resource-group minecraft-rg
az role assignment create --assignee [PRINCIPAL_ID] --role "Contributor" --scope "/subscriptions/39626f70-6824-4598-96f7-cd57f0f39206/resourceGroups/minecraft-rg"
func azure functionapp publish minecraft-monitor-test123 --python
```

### 3. (Opcional) Personalizar configuración

Si quieres cambiar nombres o ubicación:

```powershell
.\deploy.ps1 -SubscriptionId "TU_SUBSCRIPTION_ID" `
             -ResourceGroup "minecraft-rg" `
             -FunctionAppName "mi-minecraft-monitor" `
             -StorageAccountName "miminecraftstorage" `
             -Location "West US 2"
```

## Cómo funciona

### Flujo de monitoreo:

1. **Cada 3 minutos** la función se ejecuta automáticamente
2. **Verifica** si el contenedor está ejecutándose
3. **Obtiene la IP** del contenedor desde Azure
4. **Conecta** al servidor de Minecraft en el puerto 25565
5. **Cuenta jugadores** usando el protocolo Server List Ping
6. **Mantiene estado** en Azure Table Storage:
   - Si hay jugadores: resetea contador
   - Si no hay jugadores: incrementa contador
7. **Apaga contenedor** si han pasado 2 checks sin jugadores (6 minutos)

### Tiempo de apagado:
- **Mínimo**: 6 minutos sin jugadores
- **Máximo**: 9 minutos sin jugadores
- **Muy económico**: ~480 ejecuciones por día

## Monitoreo y logs

### Ver logs en Azure Portal:
1. Ir a [Azure Portal](https://portal.azure.com)
2. Buscar tu Function App (`minecraft-monitor-function`)
3. Ir a `Functions` → `minecraft_monitor` → `Monitor`
4. Ver logs en tiempo real y historial

### Logs típicos:
```
[INFO] Minecraft monitor function started
[INFO] Current player count: 2
[INFO] Players online: 2. Resetting empty check counter.
[INFO] Minecraft monitor function completed
```

```
[INFO] No players online. Consecutive empty checks: 1
[INFO] No players online. Consecutive empty checks: 2
[INFO] Server has been empty for 6 minutes. Shutting down...
[INFO] Container shutdown initiated successfully
```

## Testing local (opcional)

Si quieres probar localmente antes del despliegue:

### 1. Instalar dependencias:
```powershell
pip install -r requirements.txt
```

### 2. Configurar variables:
Edita `local.settings.json` y pon tu Subscription ID real.

### 3. Ejecutar localmente:
```powershell
func start
```

## Troubleshooting

### Problemas comunes:

**Error: "Could not connect to Minecraft server"**
- El servidor puede estar iniciándose aún
- La función esperará al próximo check

**Error: "AZURE_SUBSCRIPTION_ID not set"**
- Verifica que el Subscription ID esté configurado en la Function App
- Ve a Configuration → Application Settings en Azure Portal

**Error: "Access denied"**
- Verifica que la identidad administrada tenga permisos de Contributor
- El script de despliegue debería configurar esto automáticamente

### Re-desplegar:
Si necesitas actualizar el código:
```powershell
func azure functionapp publish minecraft-monitor-function --python
```

## Costos estimados

Con 480 ejecuciones por día:
- **Azure Functions**: ~$0.50 USD/mes
- **Table Storage**: ~$0.10 USD/mes
- **Total**: **< $1 USD/mes**

## Personalización

### Cambiar tiempo de apagado:
Edita `function_app.py` línea 13:
```python
SHUTDOWN_THRESHOLD_MINUTES = 6  # Cambiar a los minutos que quieras
```

### Cambiar frecuencia:
Edita `function_app.py` línea 157:
```python
@app.timer_trigger(schedule="0 */3 * * * *", ...)  # */3 = cada 3 minutos
```

## Seguridad

- Usa **Managed Identity** (no passwords)
- Permisos **mínimos necesarios** (solo Contributor en el resource group)
- **Logs seguros** (no expone información sensible)

¡Listo! Tu servidor de Minecraft ahora se apagará automáticamente para ahorrar costos cuando nadie esté jugando. 🎮
