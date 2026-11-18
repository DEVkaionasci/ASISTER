import json
import os
import tempfile
from pathlib import Path


ARQUIVO_TAREFAS = Path(__file__).resolve().parent / "tarefas.json"


def carregar_tarefas():
    if not ARQUIVO_TAREFAS.exists():
        return []

    with ARQUIVO_TAREFAS.open("r", encoding="utf-8") as arquivo:
        conteudo = arquivo.read()

    if not conteudo.strip():
        return []

    tarefas = json.loads(conteudo)

    if not isinstance(tarefas, list):
        raise ValueError("O arquivo de tarefas precisa conter uma lista.")

    return tarefas


def salvar_tarefas(tarefas):
    dados = [
        {
            "titulo": tarefa.titulo,
            "concluida": tarefa.concluida,
            "data": tarefa.data.isoformat() if getattr(tarefa, "data", None) else None,
        }
        for tarefa in tarefas
    ]

    arquivo_temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=ARQUIVO_TAREFAS.parent,
            delete=False,
        ) as arquivo:
            arquivo_temporario = Path(arquivo.name)
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.flush()
            os.fsync(arquivo.fileno())

        os.replace(arquivo_temporario, ARQUIVO_TAREFAS)
    finally:
        if arquivo_temporario and arquivo_temporario.exists():
            arquivo_temporario.unlink()