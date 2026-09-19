"""Configuración común de pytest para InPrint.

Fija variables de entorno mínimas para que core.config pueda importarse
sin depender del archivo .env real ni de credenciales de producción.
"""

import os


# No dejamos que las pruebas dependan de la configuración real del equipo.
os.environ["TELEGRAM_TOKEN"] = "test-token"
os.environ["USUARIOS_PERMITIDOS"] = "1,2,3"
os.environ["ADMIN_ID"] = "1"
os.environ["PRINTER_IP"] = "192.0.2.80"
