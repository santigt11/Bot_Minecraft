# Script para configurar autenticación de Azure para el bot

Write-Host "Configurando autenticación de Azure para Discord Bot..." -ForegroundColor Green

# Variables
$SUBSCRIPTION_ID = "39626f70-6824-4598-96f7-cd57f0f39206"
$RESOURCE_GROUP = "minecraft-rg"
$SP_NAME = "minecraft-discord-bot"

Write-Host "Creando Service Principal..." -ForegroundColor Yellow

# Crear Service Principal
$sp = az ad sp create-for-rbac --name $SP_NAME --role contributor --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" | ConvertFrom-Json

if ($sp) {
    Write-Host "✅ Service Principal creado exitosamente!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 Copia estas variables de entorno para Railway/Render:" -ForegroundColor Cyan
    Write-Host "AZURE_CLIENT_ID=$($sp.appId)" -ForegroundColor White
    Write-Host "AZURE_CLIENT_SECRET=$($sp.password)" -ForegroundColor White  
    Write-Host "AZURE_TENANT_ID=$($sp.tenant)" -ForegroundColor White
    Write-Host "AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID" -ForegroundColor White
    Write-Host ""
    Write-Host "⚠️  IMPORTANTE: Guarda el CLIENT_SECRET, no se puede recuperar después!" -ForegroundColor Red
} else {
    Write-Host "❌ Error creando Service Principal" -ForegroundColor Red
    Write-Host "Asegúrate de estar logueado: az login" -ForegroundColor Yellow
}