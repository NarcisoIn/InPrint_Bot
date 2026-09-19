import os
import subprocess
import tempfile

from PIL import Image
from pypdf import PdfReader


def preparar_archivo(file_bytes, nombre_original):
    """Crea un directorio temporal y procesa el documento o imagen."""

    dir_temp = tempfile.mkdtemp(prefix="inprint-job-")

    # Sanitizar el nombre para impedir path traversal.
    nombre_seguro = os.path.basename(nombre_original or "").strip()

    # Evitar nombres vacíos o formados únicamente por puntos
    # (".", "..", "...", etc.).
    if not nombre_seguro or not nombre_seguro.strip("."):
        nombre_seguro = "archivo_sin_nombre"

    ruta_original = os.path.join(dir_temp, nombre_seguro)

    # Guardamos los bytes descargados
    with open(ruta_original, "wb") as f:
        f.write(file_bytes)

    ext = os.path.splitext(nombre_seguro)[1].lower()
    saltar_paginas = False
    ruta_pdf = ruta_original

    if ext in [".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"]:
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                ruta_original,
                "--outdir",
                dir_temp,
            ],
            check=True,
            stderr=subprocess.DEVNULL,
        )

        ruta_pdf = os.path.join(
            dir_temp,
            f"{os.path.splitext(nombre_seguro)[0]}.pdf",
        )

    elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
        saltar_paginas = True

        imagen = Image.open(ruta_original)
        imagen_rgb = imagen.convert("RGB")

        ruta_pdf = os.path.join(
            dir_temp,
            f"{os.path.splitext(nombre_seguro)[0]}.pdf",
        )

        imagen_rgb.save(ruta_pdf)

    # Revisar páginas si procede
    if not saltar_paginas and ruta_pdf.endswith(".pdf"):
        try:
            reader = PdfReader(ruta_pdf)

            if len(reader.pages) <= 1:
                saltar_paginas = True

        except Exception:
            pass

    return dir_temp, ruta_pdf, saltar_paginas
