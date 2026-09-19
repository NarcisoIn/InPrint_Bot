import os
import tempfile
from services.converter import preparar_archivo

def test_preparar_archivo_imagen_falsa():
    """
    Verifica que la función procese correctamente un archivo simulado 
    y devuelva los valores esperados sin romper el flujo.
    """
    # Creamos un archivo de texto temporal para simular una subida
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"contenido de prueba")
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            file_bytes = f.read()
            
        # Probamos enviando un archivo con extensión aleatoria
        # Nota: Como no es office ni imagen válida, evaluamos que maneje el flujo por defecto
        dir_temp, ruta_pdf, saltar_paginas = preparar_archivo(file_bytes, "archivo_prueba.txt")
        
        # Aserciones lógicas de lo que esperamos que ocurra
        assert os.path.exists(dir_temp)
        assert os.path.exists(ruta_pdf)
        
        # Limpieza manual de la carpeta temporal creada por la función de prueba
        import shutil
        shutil.rmtree(dir_temp)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)