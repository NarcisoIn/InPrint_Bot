"""Regresiones de seguridad para nombres de archivo.

Este caso queda marcado como xfail porque el converter actual todavía no
sanea `nombre_original` antes de pasarlo a os.path.join().

Pruebas de seguridad para services.converter.
"""

from pathlib import Path
import shutil
import uuid

from services.converter import preparar_archivo

def test_nombre_archivo_no_puede_escapar_del_directorio_temporal():
    nombre = f"../inprint-security-{uuid.uuid4().hex}.txt"

    dir_temp, ruta, _ = preparar_archivo(
        b"seguro",
        nombre,
    )

    try:
        ruta_resuelta = Path(ruta).resolve()
        dir_temp_resuelto = Path(dir_temp).resolve()

        # El archivo debe permanecer dentro del directorio temporal.
        assert ruta_resuelta.parent == dir_temp_resuelto

        # El componente "../" no debe formar parte de la ruta resultante.
        assert ruta_resuelta.name.startswith("inprint-security-")
        assert ruta_resuelta.name.endswith(".txt")

        # El nombre original no debe conservar el traversal.
        assert ".." not in ruta_resuelta.name

    finally:
        shutil.rmtree(
            dir_temp,
            ignore_errors=True,
        )


def test_nombre_vacio_usa_nombre_seguro_por_defecto():
    dir_temp, ruta, _ = preparar_archivo(
        b"seguro",
        "",
    )

    try:
        ruta_resuelta = Path(ruta).resolve()
        dir_temp_resuelto = Path(dir_temp).resolve()

        assert ruta_resuelta.parent == dir_temp_resuelto
        assert ruta_resuelta.name == "archivo_sin_nombre"

    finally:
        shutil.rmtree(
            dir_temp,
            ignore_errors=True,
        )


def test_nombre_formado_por_puntos_usa_nombre_seguro_por_defecto():
    dir_temp, ruta, _ = preparar_archivo(
        b"seguro",
        "...",
    )

    try:
        ruta_resuelta = Path(ruta).resolve()
        dir_temp_resuelto = Path(dir_temp).resolve()

        assert ruta_resuelta.parent == dir_temp_resuelto
        assert ruta_resuelta.name == "archivo_sin_nombre"

    finally:
        shutil.rmtree(
            dir_temp,
            ignore_errors=True,
        )