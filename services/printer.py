import subprocess
from core.config import PRINTER_IP

def verificar_impresora():
    ping = subprocess.run(["ping", "-c", "1", "-W", "2", PRINTER_IP], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ping.returncode == 0

def enviar_a_cups(ruta_pdf, copias, color, duplex, paginas):
    comando = [
        "lp", "-d", "Brother", 
        "-n", str(copias), 
        "-o", f"ColorModel={color}", 
        "-o", f"Duplex={duplex}"
    ]
    if paginas != 'all':
        comando.extend(["-P", str(paginas)])
    comando.append(ruta_pdf)

    subprocess.run(comando, check=True)