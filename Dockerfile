FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements_bot.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements_bot.txt

# Copiar código del bot
COPY discord_bot.py .

# Comando para ejecutar el bot
CMD ["python", "discord_bot.py"]