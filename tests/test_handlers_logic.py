"""Pruebas unitarias de la lógica de estado que no requieren Telegram real."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from telegram.ext import ConversationHandler

from handlers import bot_handlers


def _run(coroutine):
    return asyncio.run(coroutine)


def test_recibir_paginas_convierte_todas_a_all():
    update = SimpleNamespace(
        message=SimpleNamespace(
            text="  Todas ",
            reply_text=AsyncMock(),
        )
    )
    context = SimpleNamespace(user_data={})

    estado = _run(bot_handlers.recibir_paginas(update, context))

    assert context.user_data["paginas"] == "all"
    assert estado == bot_handlers.COPIAS
    update.message.reply_text.assert_awaited_once()


def test_recibir_paginas_conserva_intervalo_especificado():
    update = SimpleNamespace(
        message=SimpleNamespace(
            text=" 1-5 ",
            reply_text=AsyncMock(),
        )
    )
    context = SimpleNamespace(user_data={})

    estado = _run(bot_handlers.recibir_paginas(update, context))

    assert context.user_data["paginas"] == "1-5"
    assert estado == bot_handlers.COPIAS


def test_preguntar_duplex_guarda_color_y_cambia_a_estado_duplex():
    query = SimpleNamespace(
        data="RGB",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(user_data={})

    estado = _run(bot_handlers.preguntar_duplex(update, context))

    assert context.user_data["color"] == "RGB"
    assert estado == bot_handlers.DUPLEX
    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()


def test_preguntar_paginas_para_imagen_salta_estado_de_paginas():
    query = SimpleNamespace(
        data="None",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(user_data={"saltar_paginas": True})

    estado = _run(bot_handlers.preguntar_paginas(update, context))

    assert context.user_data["duplex"] == "None"
    assert context.user_data["paginas"] == "all"
    assert estado == bot_handlers.COPIAS


def test_preguntar_paginas_para_pdf_muestra_entrada_de_paginas():
    query = SimpleNamespace(
        data="DuplexNoTumble",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(user_data={"saltar_paginas": False})

    estado = _run(bot_handlers.preguntar_paginas(update, context))

    assert context.user_data["duplex"] == "DuplexNoTumble"
    assert estado == bot_handlers.PAGINAS

    texto = query.edit_message_text.await_args.kwargs["text"]
    assert "¿Qué páginas quieres imprimir?" in texto


def test_cancelar_operacion_elimina_directorio_temporal(tmp_path):
    directorio = tmp_path / "inprint-job-test"
    directorio.mkdir()
    (directorio / "documento.pdf").write_bytes(b"pdf")

    update = SimpleNamespace(
        callback_query=None,
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    context = SimpleNamespace(
        user_data={
            "usuario": "UsuarioTest",
            "nombre_archivo": "documento.pdf",
            "dir_temp": str(directorio),
        }
    )

    estado = _run(bot_handlers.cancelar_operacion(update, context))

    assert estado == ConversationHandler.END
    assert not directorio.exists()
    update.message.reply_text.assert_awaited_once()


def test_ejecutar_impresion_envia_a_cups_y_limpia_trabajo(tmp_path, monkeypatch):
    directorio = tmp_path / "inprint-job-test"
    directorio.mkdir()
    ruta_pdf = directorio / "documento.pdf"
    ruta_pdf.write_bytes(b"pdf")

    mock_verificar = lambda: True
    # enviar_a_cups es síncrona, por lo que usamos una función simple que registre la llamada.
    llamadas = []

    def fake_enviar(ruta, copias, color, duplex, paginas):
        llamadas.append((ruta, copias, color, duplex, paginas))

    monkeypatch.setattr(bot_handlers, "verificar_impresora", mock_verificar)
    monkeypatch.setattr(bot_handlers, "enviar_a_cups", fake_enviar)

    query = SimpleNamespace(
        data="2",
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(
        user_data={
            "ruta": str(ruta_pdf),
            "color": "RGB",
            "duplex": "DuplexNoTumble",
            "paginas": "1-3",
            "usuario": "UsuarioTest",
            "usuario_id": 2,
            "nombre_archivo": "documento.pdf",
            "dir_temp": str(directorio),
        },
        bot=SimpleNamespace(send_message=AsyncMock()),
    )

    estado = _run(bot_handlers.ejecutar_impresion(update, context))

    assert estado == ConversationHandler.END
    assert context.user_data["copias"] == "2"
    assert llamadas == [
        (str(ruta_pdf), "2", "RGB", "DuplexNoTumble", "1-3")
    ]
    assert not directorio.exists()
