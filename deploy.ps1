# Script de despliegue para Azure Functions
# Asegúrate de tener Azure CLI instalado y estar logueado

# Variables - CAMBIA ESTOS VALORES
$RESOURCE_GROUP = "minecraft-rg"
$FUNCTION_APP_NAME = "minecraft-monitor-app"  # Debe ser único globalmente
$STORAGE_ACCOUNT = "minecraftmonitorstorage"  # Tu storage account existente
$SUBSCRIPTION_ID = "39626f70-6824-4598-96f7-cd57f0f39206"  # Tu subscription ID

Write-Host "Desplegando Azure Function App..." -ForegroundColor Green

# Crear Function App si no existe
Write-Host "Creando Function App..." -ForegroundColor Yellow
az functionapp create `
  --resource-group $RESOURCE_GROUP `
  --consumption-plan-location eastus `
  --runtime python `
  --runtime-version 3.11 `
  --functions-version 4 `
  --name $FUNCTION_APP_NAME `
  --storage-account $STORAGE_ACCOUNT `
  --os-type Linux

# Configurar variables de entorno
Write-Host "Configurando variables de entorno..." -ForegroundColor Yellow
az functionapp config appsettings set `
  --name $FUNCTION_APP_NAME `
  --resource-group $RESOURCE_GROUP `
  --settings "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"

# Habilitar identidad administrada
Write-Host "Habilitando identidad administrada..." -ForegroundColor Yellow
az functionapp identity assign `
  --name $FUNCTION_APP_NAME `
  --resource-group $RESOURCE_GROUP

# Desplegar código
Write-Host "Desplegando código..." -ForegroundColor Yellow
func azure functionapp publish $FUNCTION_APP_NAME --python

Write-Host "¡Despliegue completado!" -ForegroundColor Green
Write-Host "No olvides asignar permisos de Contributor a la identidad administrada en el resource group" -ForegroundColor Red