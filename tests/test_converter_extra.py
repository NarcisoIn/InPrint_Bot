"""Pruebas adicionales para services.converter, centradas en entradas y archivos."""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from pypdf import PdfWriter

from services import converter


def _crear_pdf_bytes(numero_paginas=1):
    writer = PdfWriter()
    for _ in range(numero_paginas):
        writer.add_blank_page(width=72, height=72)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_con_extension_mayuscula_se_detecta_correctamente():
    dir_temp, ruta_pdf, saltar_paginas = converter.preparar_archivo(
        _crear_pdf_bytes(numero_paginas=2),
        "DOCUMENTO.PDF",
    )

    try:
        assert Path(ruta_pdf).exists()
        assert Path(ruta_pdf).suffix == ".PDF"
        assert saltar_paginas is False
    finally:
        __import__("shutil").rmtree(dir_temp, ignore_errors=True)


def test_pdf_de_una_sola_pagina_activa_saltar_paginas():
    dir_temp, ruta_pdf, saltar_paginas = converter.preparar_archivo(
        _crear_pdf_bytes(numero_paginas=1),
        "documento.pdf",
    )

    try:
        assert Path(ruta_pdf).exists()
        assert saltar_paginas is True
    finally:
        __import__("shutil").rmtree(dir_temp, ignore_errors=True)


def test_imagen_se_convierte_a_pdf_y_marca_saltar_paginas():
    imagen = Image.new("RGB", (100, 100), "white")
    buffer = BytesIO()
    imagen.save(buffer, format="PNG")

    dir_temp, ruta_pdf, saltar_paginas = converter.preparar_archivo(
        buffer.getvalue(),
        "foto.PNG",
    )

    try:
        assert Path(ruta_pdf).exists()
        assert Path(ruta_pdf).suffix == ".pdf"
        assert saltar_paginas is True
    finally:
        __import__("shutil").rmtree(dir_temp, ignore_errors=True)


def test_documento_office_invoca_libreoffice_con_la_ruta_temporal(monkeypatch):
    llamadas = []

    def fake_run(comando, check, stderr):
        llamadas.append((comando, check, stderr))

        dir_temp = comando[comando.index("--outdir") + 1]
        ruta_origen = comando[4]
        nombre_pdf = f"{Path(ruta_origen).stem}.pdf"
        ruta_pdf = Path(dir_temp) / nombre_pdf
        ruta_pdf.write_bytes(_crear_pdf_bytes(numero_paginas=1))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(converter.subprocess, "run", fake_run)

    dir_temp, ruta_pdf, saltar_paginas = converter.preparar_archivo(
        b"contenido de prueba",
        "reporte.docx",
    )

    try:
        assert llamadas
        comando, check, stderr = llamadas[0]
        assert comando[:3] == ["libreoffice", "--headless", "--convert-to"]
        assert comando[4].startswith(dir_temp)
        assert comando[-2:] == ["--outdir", dir_temp]
        assert check is True
        assert stderr is converter.subprocess.DEVNULL
        assert Path(ruta_pdf).name == "reporte.pdf"
        assert Path(ruta_pdf).exists()
        assert saltar_paginas is True
    finally:
        __import__("shutil").rmtree(dir_temp, ignore_errors=True)


def test_extension_no_soportada_no_invoca_conversion():
    dir_temp, ruta, saltar_paginas = converter.preparar_archivo(
        b"texto",
        "archivo.txt",
    )

    try:
        assert Path(ruta).exists()
        assert Path(ruta).name == "archivo.txt"
        assert saltar_paginas is False
    finally:
        __import__("shutil").rmtree(dir_temp, ignore_errors=True)
