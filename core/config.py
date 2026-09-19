import os
from dotenv import load_dotenv

# --- CARGAR CONFIGURACIÓN ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
USUARIOS_PERMITIDOS = [int(uid.strip()) for uid in os.getenv("USUARIOS_PERMITIDOS").split(",")]
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PRINTER_IP = os.getenv("PRINTER_IP", "192.168.1.80")