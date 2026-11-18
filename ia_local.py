from datetime import datetime
import json
from urllib.request import Request, urlopen

OLLAMA_URL = "http://localhost:11434/api/chat"
MODELO = "llama3.2"

INTENCOES_VALIDAS = [
    "criar",
    "listar",
    "concluir",
    "excluir",
    "editar",
    "conversa",
    "esclarecer",
    "desconhecido",
]

CAMPOS_VALIDOS = ["titulo", "data", "todas", "todas_data", None]

FORMATO_RESPOSTA = {
    "type": "object",
    "properties": {
        "intencao": {"type": "string", "enum": INTENCOES_VALIDAS},
        "titulo": {"type": ["string", "null"]},
        "numero": {"type": ["integer", "null"]},
        "campo": {"type": ["string", "null"], "enum": CAMPOS_VALIDOS},
        "valor": {"type": ["string", "null"]},
        "resposta": {"type": "string"},
    },
    "required": ["intencao", "titulo", "numero", "campo", "valor", "resposta"],
    "additionalProperties": False,
}


def _construir_mensagens_base(data_hoje: str) -> list[dict]:
    """Monta o prompt de sistema e exemplos few-shot fixos para maximizar o KV Cache do Ollama."""
    system_prompt = f"""Você é o interpretador de intenções de um gerenciador de tarefas em português.
Data de hoje: {data_hoje}.

Classifique a mensagem do usuário em uma das intenções:
- criar: adicionar nova tarefa (extraia apenas o nome limpo da tarefa em "titulo").
- listar: ver/mostrar tarefas existentes.
- concluir: marcar tarefa como feita (use "numero" se indicar posição/número, ex: "primeira" = 1; ou "titulo" se citar o nome).
- excluir: apagar tarefa(s). Se for todas, use campo="todas". Se for por data, use campo="todas_data" e valor="DD/MM/AAAA". Se citar número, use "numero". Se citar nome, preserve o trecho em "titulo".
- editar: alterar tarefa existente. Identifique por "numero" ou "titulo" atual. Use campo="titulo" ou campo="data" e coloque o novo conteúdo em "valor".
- esclarecer: pedido de ação incompleto ou ambíguo (pergunte o que falta em "resposta").
- conversa: saudações ou papo geral sem ação em tarefas (responda brevemente).
- desconhecido: pedidos fora do escopo do aplicativo.

Regra crítica: Nunca afirme que já executou a ação (ex: não diga "Tarefa criada!"). Diga o que vai fazer (ex: "Vou criar a tarefa..."), pois o sistema executará após validar seu JSON."""

    # Exemplos concretos ensinam modelos 3B muito melhor que regras longas
    exemplos = [
        (
            "preciso lembrar de estudar ponteiros em C",
            {
                "intencao": "criar",
                "titulo": "Estudar ponteiros em C",
                "numero": None,
                "campo": None,
                "valor": None,
                "resposta": "Vou adicionar a tarefa 'Estudar ponteiros em C'.",
            },
        ),
        (
            "o que eu tenho pra fazer?",
            {
                "intencao": "listar",
                "titulo": None,
                "numero": None,
                "campo": None,
                "valor": None,
                "resposta": "Vou listar suas tarefas.",
            },
        ),
        (
            "já terminei a segunda",
            {
                "intencao": "concluir",
                "titulo": None,
                "numero": 2,
                "campo": None,
                "valor": None,
                "resposta": "Vou marcar a tarefa 2 como concluída.",
            },
        ),
        (
            "apaga aquela de pagar internet",
            {
                "intencao": "excluir",
                "titulo": "pagar internet",
                "numero": None,
                "campo": None,
                "valor": None,
                "resposta": "Vou excluir a tarefa 'pagar internet'.",
            },
        ),
        (
            "limpa todas as tarefas de hoje",
            {
                "intencao": "excluir",
                "titulo": None,
                "numero": None,
                "campo": "todas_data",
                "valor": data_hoje,
                "resposta": f"Vou apagar todas as tarefas do dia {data_hoje}.",
            },
        ),
        (
            "zera minha lista de tarefas",
            {
                "intencao": "excluir",
                "titulo": None,
                "numero": None,
                "campo": "todas",
                "valor": None,
                "resposta": "Vou apagar todas as suas tarefas.",
            },
        ),
        (
            "muda o nome da tarefa 3 para Revisar SQL",
            {
                "intencao": "editar",
                "titulo": None,
                "numero": 3,
                "campo": "titulo",
                "valor": "Revisar SQL",
                "resposta": "Vou alterar o título da tarefa 3 para 'Revisar SQL'.",
            },
        ),
        (
            "conclui a tarefa",
            {
                "intencao": "esclarecer",
                "titulo": None,
                "numero": None,
                "campo": None,
                "valor": None,
                "resposta": "Qual tarefa você quer concluir? Informe o número ou o nome dela.",
            },
        ),
        (
            "e aí, tudo certo?",
            {
                "intencao": "conversa",
                "titulo": None,
                "numero": None,
                "campo": None,
                "valor": None,
                "resposta": "Tudo ótimo! Como posso ajudar a organizar suas tarefas?",
            },
        ),
    ]

    mensagens = [{"role": "system", "content": system_prompt}]
    for entrada, saida in exemplos:
        mensagens.append({"role": "user", "content": entrada})
        mensagens.append(
            {"role": "assistant", "content": json.dumps(saida, ensure_ascii=False)}
        )

    return mensagens


def _limpar_texto_opcional(valor) -> str | None:
    """Converte strings vazias ou 'null' literal em None."""
    if not isinstance(valor, str):
        return None
    limpo = valor.strip()
    if not limpo or limpo.lower() == "null":
        return None
    return limpo


def interpretar_mensagem(texto_usuario: str) -> dict:
    texto_limpo = texto_usuario.strip()
    if not texto_limpo:
        return {
            "intencao": "esclarecer",
            "titulo": None,
            "numero": None,
            "campo": None,
            "valor": None,
            "resposta": "Não recebi nenhuma mensagem. O que você gostaria de fazer?",
        }

    data_hoje = datetime.now().strftime("%d/%m/%Y")
    mensagens = _construir_mensagens_base(data_hoje)
    mensagens.append({"role": "user", "content": texto_limpo})

    dados = {
        "model": MODELO,
        "stream": False,
        "format": FORMATO_RESPOSTA,
        "keep_alive": -1,
        "options": {
            "temperature": 0.0,  # Zero aleatoriedade: essencial para extração de comandos
            "num_ctx": 2048,
            "num_predict": 160,  # Impede que o modelo trave gerando texto infinito
        },
        "messages": mensagens,
    }

    requisicao = Request(
        OLLAMA_URL,
        data=json.dumps(dados).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(requisicao, timeout=30) as resposta_http:
        resposta_ollama = json.loads(resposta_http.read().decode("utf-8"))

    interpretacao = json.loads(resposta_ollama["message"]["content"])

    intencao = interpretacao.get("intencao")
    titulo = _limpar_texto_opcional(interpretacao.get("titulo"))
    campo = _limpar_texto_opcional(interpretacao.get("campo"))
    valor = _limpar_texto_opcional(interpretacao.get("valor"))
    numero = interpretacao.get("numero")
    resposta = (interpretacao.get("resposta") or "").strip()

    if intencao not in INTENCOES_VALIDAS:
        raise ValueError(f"Intenção inválida retornada pelo modelo: {intencao}")

    if numero is not None and (
        not isinstance(numero, int) or isinstance(numero, bool)
    ):
        numero = None

    if campo not in CAMPOS_VALIDOS:
        campo = None

    return {
        "intencao": intencao,
        "titulo": titulo,
        "numero": numero,
        "campo": campo,
        "valor": valor,
        "resposta": resposta,
    }


if __name__ == "__main__":
    testes = [
        "Crie uma tarefa para estudar Python",
        "bota aí pra eu ir na academia às 18h",
        "marca a primeira como feita",
        "tira a tarefa de ir na academia",
        "altera a data da tarefa 1 para 25/11/2026",
        "apaga tudo",
        "edita a tarefa 2",
    ]
    for t in testes:
        print(f"Usuário: {t}")
        print(f"Saída:   {interpretar_mensagem(t)}\n")