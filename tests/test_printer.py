"""Pruebas unitarias para services.printer."""

from types import SimpleNamespace
import pytest

from services import printer


def test_verificar_impresora_devuelve_true_si_ping_responde_0(monkeypatch):
    resultado = SimpleNamespace(returncode=0)
    mock_run = lambda *args, **kwargs: resultado
    monkeypatch.setattr(printer.subprocess, "run", mock_run)

    assert printer.verificar_impresora() is True


def test_verificar_impresora_devuelve_false_si_ping_falla(monkeypatch):
    resultado = SimpleNamespace(returncode=1)
    mock_run = lambda *args, **kwargs: resultado
    monkeypatch.setattr(printer.subprocess, "run", mock_run)

    assert printer.verificar_impresora() is False


def test_verificar_impresora_construye_comando_ping_correctamente(monkeypatch):
    llamadas = []

    def fake_run(*args, **kwargs):
        llamadas.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(printer.subprocess, "run", fake_run)

    assert printer.verificar_impresora() is True

    assert llamadas == [
        (
            (["ping", "-c", "1", "-W", "2", printer.PRINTER_IP],),
            {"stdout": printer.subprocess.DEVNULL, "stderr": printer.subprocess.DEVNULL},
        )
    ]


def test_enviar_a_cups_manda_comando_completo_para_todas_las_paginas(monkeypatch):
    llamadas = []

    def fake_run(*args, **kwargs):
        llamadas.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(printer.subprocess, "run", fake_run)

    printer.enviar_a_cups(
        "/tmp/documento.pdf",
        copias=3,
        color="RGB",
        duplex="DuplexNoTumble",
        paginas="all",
    )

    assert llamadas == [
        (
            (
                [
                    "lp",
                    "-d",
                    "Brother",
                    "-n",
                    "3",
                    "-o",
                    "ColorModel=RGB",
                    "-o",
                    "Duplex=DuplexNoTumble",
                    "/tmp/documento.pdf",
                ],
            ),
            {"check": True},
        )
    ]


def test_enviar_a_cups_agrega_rango_de_paginas(monkeypatch):
    llamadas = []

    def fake_run(*args, **kwargs):
        llamadas.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(printer.subprocess, "run", fake_run)

    printer.enviar_a_cups(
        "/tmp/documento.pdf",
        copias=2,
        color="Gray",
        duplex="None",
        paginas="1-5",
    )

    comando = llamadas[0][0][0]

    assert comando == [
        "lp",
        "-d",
        "Brother",
        "-n",
        "2",
        "-o",
        "ColorModel=Gray",
        "-o",
        "Duplex=None",
        "-P",
        "1-5",
        "/tmp/documento.pdf",
    ]
    assert llamadas[0][1] == {"check": True}


def test_enviar_a_cups_propaga_error_de_subprocess(monkeypatch):
    import subprocess

    error = subprocess.CalledProcessError(returncode=1, cmd=["lp"])

    def fake_run(*args, **kwargs):
        raise error

    monkeypatch.setattr(printer.subprocess, "run", fake_run)

    with pytest.raises(subprocess.CalledProcessError):
        printer.enviar_a_cups(
            "/tmp/documento.pdf",
            copias=1,
            color="RGB",
            duplex="None",
            paginas="all",
        )
