import re
import threading
import unicodedata
from datetime import date, timedelta

from banco import carregar_tarefas, salvar_tarefas
from ia_local import interpretar_mensagem

MESES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


ORDINAIS = {
    "primeira": 1, "segunda": 2, "terceira": 3, "quarta": 4, "quinta": 5,
    "sexta": 6, "setima": 7, "oitava": 8, "nona": 9, "decima": 10,
}


def _resolver_alvo(alvo):
    """Converte o alvo de um comando em (numero, titulo): aceita número,
    ordinal ("primeira") ou parte do título."""
    alvo = re.sub(r"^(?:(?:a|essa|esta)\s+)?(?:tarefa\s+)?(?:(?:a|essa|esta)\s+)?", "", alvo.strip())
    if alvo in ORDINAIS:
        return ORDINAIS[alvo], None
    numero = re.fullmatch(r"(?:n(?:umero|o)?\.?\s*)?(\d+)", alvo)
    if numero:
        return int(numero.group(1)), None
    return None, alvo


def parse_data_tarefa(texto):
    if not isinstance(texto, str):
        return date.today()

    texto_limpo = texto.strip().lower()
    normalizado = "".join(
        caractere for caractere in unicodedata.normalize("NFD", texto_limpo)
        if unicodedata.category(caractere) != "Mn"
    )
    if not texto_limpo:
        return date.today()

    frases_relativas = [
        ("semana que vem", 7),
        ("proxima semana", 7),
        ("depois de amanha", 2),
        ("depois de amanhã", 2),
        ("hoje", 0),
        ("hje", 0),
        ("amanha", 1),
        ("amanhã", 1),
    ]
    for chave, deslocamento in frases_relativas:
        if chave in normalizado:
            return date.today() + timedelta(days=deslocamento)

    dias = {"segunda-feira": 0, "segunda": 0, "terca-feira": 1, "terca": 1,
            "quarta-feira": 2, "quarta": 2, "quinta-feira": 3, "quinta": 3,
            "sexta-feira": 4, "sexta": 4, "sabado": 5, "domingo": 6}
    for nome, dia_semana in dias.items():
        if re.search(rf"\b(?:proxima|prox(?:ima)?|na|para)\s+{nome}\b", normalizado):
            deslocamento = (dia_semana - date.today().weekday()) % 7
            if deslocamento == 0 or "proxim" in normalizado:
                deslocamento = deslocamento or 7
            return date.today() + timedelta(days=deslocamento)
        if re.search(rf"\b{nome}\b", normalizado):
            deslocamento = (dia_semana - date.today().weekday()) % 7
            return date.today() + timedelta(days=deslocamento)

    texto_limpo = normalizado
    padroes = [
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
        r"\b(?:no\s+)?dia\s+(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?\b",
        r"\b(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?\b",
        r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b",
    ]

    for padrao in padroes:
        busca = re.search(padrao, texto_limpo)
        if not busca:
            continue

        grupos = busca.groups()
        if len(grupos) == 3 and grupos[0].isdigit() and grupos[1].isalpha():
            dia, nome_mes, ano = grupos
            mes = MESES.get(nome_mes)
            if mes is None:
                continue
            ano_numero = int(ano) if ano else date.today().year
            try:
                return date(ano_numero, mes, int(dia))
            except ValueError:
                continue

        if len(grupos) == 3 and grupos[0].isdigit() and grupos[1].isdigit() and len(grupos[0]) == 4:
            ano, mes, dia = grupos
            try:
                return date(int(ano), int(mes), int(dia))
            except ValueError:
                continue

        if len(grupos) == 3 and grupos[0].isdigit() and grupos[1].isdigit():
            primeiro, segundo, terceiro = grupos
            if terceiro and terceiro.isdigit() and len(terceiro) == 4:
                try:
                    return date(int(terceiro), int(segundo), int(primeiro))
                except ValueError:
                    pass
            if terceiro and terceiro.isdigit() and len(terceiro) == 2:
                try:
                    return date(2000 + int(terceiro), int(segundo), int(primeiro))
                except ValueError:
                    pass
            try:
                return date(date.today().year, int(segundo), int(primeiro))
            except ValueError:
                continue

    busca_dia = re.search(r"\b(?:no\s+)?dia\s+(\d{1,2})\b", normalizado)
    if busca_dia:
        dia = int(busca_dia.group(1))
        hoje = date.today()
        ano, mes = hoje.year, hoje.month
        if dia < hoje.day:
            mes += 1
            if mes > 12:
                mes, ano = 1, ano + 1
        try:
            return date(ano, mes, dia)
        except ValueError:
            pass

    return date.today()


def _carregar_data(valor, titulo):
    if valor:
        try:
            return date.fromisoformat(valor)
        except ValueError:
            pass
    return parse_data_tarefa(titulo)


class Tarefa:
    def __init__(self, titulo, data=None):
        self.titulo = titulo
        self.concluida = False
        self.data = data or parse_data_tarefa(titulo)

    def concluir(self):
        self.concluida = True


class GerenciadorTarefas:
    def __init__(self, janela=None):
        self.janela = janela
        self.tarefas = []
        self._ultima_lista = []
        for dados in carregar_tarefas():
            titulo = dados.get("titulo") if isinstance(dados, dict) else None
            if not titulo:
                continue
            tarefa = Tarefa(titulo, data=_carregar_data(dados.get("data"), titulo))
            tarefa.concluida = bool(dados.get("concluida", False))
            self.tarefas.append(tarefa)

    def obter_tarefas_do_dia(self, ano, mes, dia):
        data_alvo = date(ano, mes, dia)
        return [tarefa for tarefa in self.tarefas if tarefa.data == data_alvo]

    def processar_mensagem(self, texto_usuario):
        composto = re.match(
            r"^(.+?)\s+e\s+((?:a\s+)?(?:primeira|segunda|terceira|quarta|quinta|\d+)\b.+)$",
            texto_usuario.strip(), re.IGNORECASE,
        )
        if composto and re.search(r"\b(?:marque|marca|conclua|concluir|mude|mova|remarque)\b", composto.group(1), re.IGNORECASE) and re.search(r"\b(?:mude|mova|remarque|marque|conclua)\b", composto.group(2), re.IGNORECASE):
            primeira = self.processar_mensagem(composto.group(1))
            segunda = self.processar_mensagem(composto.group(2))
            return f"{primeira}\n{segunda}"

        texto_normalizado = self._normalizar_texto(texto_usuario)
        if re.search(r"\b(?:o que tem pra fazer|o que tenho pra fazer|tarefas? de|afazeres? de)\b", texto_normalizado) and re.search(r"\bhoje\b", texto_normalizado):
            hoje = date.today()
            tarefas_hoje = self.obter_tarefas_do_dia(hoje.year, hoje.month, hoje.day)
            self._ultima_lista = list(tarefas_hoje)
            if not tarefas_hoje:
                return "Você não tem tarefas para hoje."
            return "\n".join(f"{i}. [{'concluída' if t.concluida else 'pendente'}] {t.titulo}" for i, t in enumerate(tarefas_hoje, 1))

        base = {
            "intencao": "desconhecido", "titulo": None, "numero": None,
            "campo": None, "valor": None, "resposta": "",
        }
        interpretacao = self._interpretar_comando_direto(texto_usuario, base)
        if interpretacao["intencao"] == "desconhecido":
            interpretacao = interpretar_mensagem(texto_usuario)
            interpretacao = self._interpretar_comando_direto(texto_usuario, interpretacao)

        intencao = interpretacao["intencao"]

        if intencao == "criar":
            titulo = interpretacao["titulo"]

            if not titulo or not titulo.strip():
                return "Qual tarefa você quer criar?"

            titulo = titulo.strip()
            data = parse_data_tarefa(texto_usuario)
            if data == date.today():
                data = parse_data_tarefa(titulo)
            self.adicionar_tarefa(titulo, data=data)
            return f"Tarefa criada: {titulo}"

        if intencao == "listar":
            return self.formatar_tarefas()

        if intencao == "concluir":
            numero = interpretacao["numero"]

            if numero is None and isinstance(interpretacao.get("titulo"), str):
                tarefa = self._localizar_tarefa(titulo=interpretacao["titulo"])
                if not isinstance(tarefa, str):
                    numero = self.tarefas.index(tarefa) + 1

            if not isinstance(numero, int) or isinstance(numero, bool) or numero < 1:
                return interpretacao["resposta"] or (
                    "Qual número de tarefa você quer concluir?"
                )

            return self.concluir_tarefa(str(numero))

        if intencao == "excluir":
            if interpretacao.get("campo") == "todas_data":
                return self.excluir_tarefas_na_data(parse_data_tarefa(interpretacao.get("valor") or texto_usuario))
            if interpretacao.get("campo") == "uma_data":
                return self.excluir_uma_tarefa_na_data(parse_data_tarefa(interpretacao.get("valor") or texto_usuario))
            if interpretacao.get("campo") == "todas":
                return self.excluir_tarefas_na_data(None)
            numero = interpretacao["numero"]

            if numero is not None:
                if (
                    not isinstance(numero, int)
                    or isinstance(numero, bool)
                    or numero < 1
                ):
                    return interpretacao["resposta"] or (
                        "Informe um número válido para excluir a tarefa."
                    )

                return self.excluir_tarefa(numero=numero)

            titulo = interpretacao["titulo"]
            if isinstance(titulo, str) and titulo.strip():
                return self.excluir_tarefa(titulo=titulo)

            return interpretacao["resposta"] or (
                "Qual tarefa você quer excluir? Informe o número ou o título."
            )

        if intencao == "editar":
            campo = self._normalizar_texto(interpretacao.get("campo") or "")
            valor = interpretacao.get("valor")
            if campo not in {"titulo", "data"} or not isinstance(valor, str) or not valor.strip():
                return interpretacao["resposta"] or "Informe a tarefa, o campo e o novo valor."
            valor = valor.strip()
            if campo == "data":
                try:
                    date.fromisoformat(valor)
                except ValueError:
                    nova = parse_data_tarefa(valor)
                    if nova == date.today() and "hoje" not in self._normalizar_texto(valor):
                        return "Não entendi a data. Use, por exemplo, 25/11/2026."
                    valor = nova.isoformat()
            return self.editar_tarefa(numero=interpretacao.get("numero"), titulo=interpretacao.get("titulo"), campo=campo, valor=valor)

        if intencao in {"conversa", "esclarecer", "desconhecido"}:
            return interpretacao["resposta"]

        return (
            "Não consegui identificar o pedido. Você pode pedir para "
            "criar, listar, concluir ou excluir uma tarefa?"
        )

    def processar_mensagem_async(self, texto_usuario, callback, on_error=None):
        def _worker():
            try:
                resposta = self.processar_mensagem(texto_usuario)
                callback(resposta)
            except Exception as e:
                if on_error:
                    on_error(e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _interpretar_comando_direto(self, texto, interpretacao):
        if not isinstance(texto, str) or not texto.strip():
            return interpretacao
        normalizado = self._normalizar_texto(texto)
        verbo = r"(?:apagar|apague|delete|deletar|excluir|exclua|remover|remova|destruir|destrua)"

        # Reconhece intenções comuns antes de consultar o modelo local. A forma
        # normalizada permite comparar sem depender de acentos ou maiúsculas.
        somente_comando = re.sub(r"[.!?]+$", "", normalizado).strip()
        if re.fullmatch(r"(?:me diga|diga|me fale|fale)\s+(?:as tarefas?|os afazeres?)(?:\s+de\s+hoje)?", somente_comando):
            return {**interpretacao, "intencao": "listar", "titulo": None,
                    "numero": None, "campo": None, "valor": None}
        comeca_com_acao = re.match(
            r"(?:adicione|adicionar|crie|criar|agende|agendar|inclua|incluir|registre|registrar|"
            r"anote|anotar|marque|marcar|conclua|concluir|apague|apagar|exclua|excluir|delete|"
            r"deletar|remova|remover|mova|mover|mude|remarque|deixe|defina)\b", somente_comando)
        if not comeca_com_acao and re.search(r"^(?:.*\b(?:mostre|mostrar|liste|listar|veja|ver|consultar|consulte)\b.*\b(?:tarefas?|afazeres?)\b|(?:minhas?\s+)?(?:tarefas?|afazeres?)\s*$)", somente_comando):
            return {**interpretacao, "intencao": "listar", "titulo": None,
                    "numero": None, "campo": None, "valor": None}

        # Trate primeiro a exclusão de uma tarefa específica para que
        # "delete a tarefa 2" não caia na regra de exclusão em lote.
        excluir_numero = re.match(
            rf"^{verbo}\s+(?:(?:a|essa|esta)\s+)?(?:tarefa\s+)?(\d+)\s*[.!?]*$",
            normalizado,
        )
        if excluir_numero:
            return {**interpretacao, "intencao": "excluir",
                    "numero": int(excluir_numero.group(1)), "titulo": None,
                    "campo": None, "valor": None}

        excluir_data_unica = re.match(
            rf"^{verbo}\s+(?:a\s+)?tarefa\s+(?:de\s+|para\s+|do\s+|da\s+)?(hoje|amanha|depois de amanha|\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?|\d{{1,2}}\s+de\s+[a-z]+(?:\s+de\s+\d{{4}})?|(?:proxima\s+)?(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?)\s*[.!?]*$",
            normalizado,
        )
        if excluir_data_unica:
            return {**interpretacao, "intencao": "excluir", "numero": None,
                    "titulo": None, "campo": "uma_data",
                    "valor": excluir_data_unica.group(1)}

        # A frase "marque como concluída" é uma ação de conclusão, nunca um
        # título para uma nova tarefa. Se o alvo não vier explícito, pergunte.
        concluir_sem_alvo = re.fullmatch(
            r"(?:marque|marca|deixe|defina)\s+(?:a\s+tarefa\s+)?como\s+(?:concluida|feita|finalizada)",
            somente_comando,
        )
        if concluir_sem_alvo:
            return {**interpretacao, "intencao": "esclarecer", "titulo": None,
                    "numero": None, "resposta": "Qual tarefa você quer marcar como concluída? Informe o número ou o título."}

        marcar_depois = re.fullmatch(
            r"(?:marque|marca|deixe|defina)\s+como\s+(?:concluida|feita|finalizada)\s+(.+)",
            somente_comando,
        )
        if marcar_depois:
            numero_alvo, titulo_alvo = _resolver_alvo(marcar_depois.group(1))
            return {**interpretacao, "intencao": "concluir", "numero": numero_alvo,
                    "titulo": titulo_alvo,
                    "resposta": "Qual tarefa você quer marcar como concluída? Informe o número ou o título."}

        verbo_concluir = r"(?:concluir|conclua|finalizar|finalize|terminar|termine|completar|complete|marcar como feita|marcar como concluida|dar como feita)"
        match_concluir = re.search(rf"\b{verbo_concluir}\b\s+(?:(?:a|a tarefa|tarefa)\s+)?(.+?)\s*[.!?]*$", normalizado)
        if match_concluir:
            alvo = match_concluir.group(1).strip()
            numero_match = re.search(r"\b(\d+)\b", alvo)
            if numero_match:
                return {**interpretacao, "intencao": "concluir", "numero": int(numero_match.group(1)), "titulo": None}
            numero_alvo, titulo_alvo = _resolver_alvo(alvo)
            return {**interpretacao, "intencao": "concluir", "numero": numero_alvo, "titulo": titulo_alvo,
                    "resposta": "Qual tarefa você quer concluir? Informe o número ou o título."}

        # Também entende "tarefa X como concluída" e "marque X como feita".
        marcar_alvo = re.match(
            r"(?:marque|marca|deixe|defina)\s+(?:a\s+tarefa\s+)?(.+?)\s+como\s+(?:concluida|feita|finalizada)",
            somente_comando,
        )
        if marcar_alvo:
            alvo = marcar_alvo.group(1).strip()
            numero_match = re.search(r"\b(\d+)\b", alvo)
            numero_alvo, titulo_alvo = _resolver_alvo(alvo)
            return {**interpretacao, "intencao": "concluir",
                    "numero": int(numero_match.group(1)) if numero_match else numero_alvo,
                    "titulo": None if numero_match else titulo_alvo,
                    "resposta": "Qual tarefa você quer marcar como concluída? Informe o número ou o título."}

        # Criar/agendar pode aparecer no início ou no meio da frase. Trechos
        # entre aspas são o título preferido; datas e conectivos são removidos.
        verbos_criar = r"(?:adicione|adicionar|crie|criar|agende|agendar|inclua|incluir|registre|registrar|anote|anotar|marque|marcar)"
        pedido_criar = re.search(rf"\b{verbos_criar}\b", normalizado)
        if pedido_criar and re.search(r"\bcomo\s+(?:concluid|feit|finalizad)", normalizado):
            pedido_criar = None
        if pedido_criar:
            restante_original = texto[pedido_criar.start():]
            restante_original = re.sub(rf"^\s*{verbos_criar}\b", "", restante_original, count=1, flags=re.IGNORECASE).strip()
            busca_aspas = re.search(r"[\"'“”‘’](.+?)[\"'“”‘’]", restante_original)
            if busca_aspas:
                titulo_novo = busca_aspas.group(1).strip()
            else:
                titulo_novo = re.sub(r"^(?:(?:uma?|a)\s+)?tarefa\s+(?:(?:chamada|intitulada|para)\s+)?", "", restante_original, flags=re.IGNORECASE)
                titulo_novo = re.sub(r"\s+(?:para|pra|em|no|na)\s+(?:hoje|amanh(?:ã|a)|depois de amanh(?:ã|a)|\d{1,2}(?:/\d{1,2})?|(?:próxim[oa]s?\s+)?(?:segunda|terça|quarta|quinta|sexta|sábado|domingo)(?:-feira)?)\b.*$", "", titulo_novo, flags=re.IGNORECASE)
                titulo_novo = re.sub(r"\s+(?:hoje|amanh(?:ã|a)|depois de amanh(?:ã|a))\s*$", "", titulo_novo, flags=re.IGNORECASE)
            titulo_novo = re.sub(r"\s+", " ", titulo_novo).strip(" \t\r\n.,!?;:'\"“”‘’")
            if titulo_novo:
                return {**interpretacao, "intencao": "criar", "titulo": titulo_novo,
                        "numero": None, "campo": None, "valor": None}

        if re.fullmatch(r"(?:liste|listar|mostre|mostrar|ver|consultar)\s*(?:minhas?\s+)?(?:tarefas?|afazeres?)?", somente_comando):
            return {**interpretacao, "intencao": "listar", "titulo": None, "numero": None}

        # Comandos explícitos de criação têm prioridade sobre o classificador.
        criar = re.match(r"^(?:adicione|adicionar|crie|criar|agende|agendar|inclua|incluir)\s+(.+)$", texto.strip(), re.IGNORECASE)
        if criar:
            restante = criar.group(1).strip()
            padrao_data = r"(?:\b(?:no\s+dia|dia|para|pra|em|na|no)\s+)?(?:amanh(?:a|\u00e3)|hoje|pr[o\u00f3]xim[ao]\s+(?:segunda|ter[c\u00e7]a|quarta|quinta|sexta|s[a\u00e1]bado|domingo)(?:-feira)?|(?:segunda|ter[c\u00e7]a|quarta|quinta|sexta|s[a\u00e1]bado|domingo)(?:-feira)?|\d{1,2}(?:\s+de\s+[a-z\u00e1-\u00fa]+(?:\s+de\s+\d{4})?)?|\d{4}-\d{2}-\d{2})"
            busca_aspas = re.search(r"[\"'](.+?)[\"']", restante)
            if busca_aspas:
                titulo_novo = busca_aspas.group(1).strip()
            else:
                titulo_novo = re.sub(r"^(?:(?:uma?|a)\s+)?tarefa\s+(?:(?:chamada|intitulada)\s+)?", "", restante, flags=re.IGNORECASE)
            titulo_novo = re.sub(padrao_data, " ", titulo_novo, flags=re.IGNORECASE)
            titulo_novo = re.sub(r"^(?:para|pra|de)\s+", "", titulo_novo, flags=re.IGNORECASE)
            titulo_novo = titulo_novo.strip(" \t\r\n.,!?;:'\"")
            titulo_novo = re.sub(r"\s+", " ", titulo_novo)
            if titulo_novo:
                return {**interpretacao, "intencao": "criar", "titulo": titulo_novo,
                        "numero": None, "campo": None, "valor": None}

        # Pedidos em lote: todos os itens ou todos os itens de uma data.
        match_lote = re.match(
            rf"^{verbo}\s+((?:todas?|todos?|all|every)\s+)?(?:as?\s+)?tarefas?\b(.*)$",
            normalizado,
        )
        if match_lote:
            complemento = match_lote.group(2).strip(" .,!?")
            if not complemento:
                return {**interpretacao, "intencao": "excluir", "numero": None,
                        "titulo": None, "campo": "todas", "valor": None}
            complemento = re.sub(r"^(?:de|para|no dia)\s+", "", complemento)
            tem_data = (
                re.search(r"\bhoje\b|\b(?:proxima\s+)?(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)", complemento)
                or re.search(r"\b\d{1,2}\s+de\s+[a-z]+\b", complemento)
                or re.search(r"\b\d{4}-\d{2}-\d{2}\b", complemento)
                or re.search(r"\b\d{1,2}[/-]\d{1,2}\b", complemento)
            )
            if tem_data:
                return {**interpretacao, "intencao": "excluir", "numero": None,
                        "titulo": None, "campo": "todas_data", "valor": complemento}
            if match_lote.group(1):
                return {**interpretacao, "intencao": "esclarecer", "numero": None,
                        "titulo": None, "resposta": "Qual data você quer usar para filtrar as tarefas?"}
            # sem "todas": é uma tarefa específica pelo título; segue para a exclusão por título

        mover = re.search(r"\b(?:mova|mover|mude|remarque)\b\s+(?:a\s+tarefa\s+)?(primeira|segunda|terceira|quarta|quinta|\d+).*?\b(?:para|pra)\s+(.+)$|\b(?:a\s+tarefa\s+)?(primeira|segunda|terceira|quarta|quinta|\d+)\s+(?:mude|mova|remarque)\b.*?\b(?:para|pra)\s+(.+)$", texto.strip(), re.IGNORECASE)
        if mover and self.tarefas:
            posicoes = {"primeira": 1, "segunda": 2, "terceira": 3, "quarta": 4, "quinta": 5}
            alvo = mover.group(1) or mover.group(3)
            nova_data = mover.group(2) or mover.group(4)
            numero = posicoes.get(alvo.lower(), int(alvo) if alvo.isdigit() else None)
            return {**interpretacao, "intencao": "editar", "numero": numero,
                    "titulo": None, "campo": "data",
                    "valor": parse_data_tarefa(nova_data).isoformat()}

        # Referências como "essa" retomam a lista exibida imediatamente antes.
        ref = re.match(rf"^{verbo}\s+(?:a\s+)?(?:essa|esta|isso|ela|dela)\s*[.!?]*$", normalizado)
        if ref:
            candidatos = [t for t in self._ultima_lista if t in self.tarefas]
            if len(candidatos) == 1:
                return {**interpretacao, "intencao": "excluir",
                        "numero": self.tarefas.index(candidatos[0]) + 1, "titulo": None}
            return {**interpretacao, "intencao": "esclarecer", "numero": None,
                    "titulo": None, "resposta": "Qual tarefa você quis dizer? Informe o número ou parte do título."}

        match = re.match(rf"^{verbo}\s+(?:(?:a|essa|esta)\s+)?(?:tarefa\s+)?(.+?)\s*[.!?]*$", texto.strip(), re.IGNORECASE)
        if match:
            alvo = match.group(1).strip()
            if alvo.isdigit():
                return {**interpretacao, "intencao": "excluir", "numero": int(alvo), "titulo": None}
            return {**interpretacao, "intencao": "excluir", "numero": None, "titulo": alvo}
        return interpretacao

    @staticmethod
    def _normalizar_texto(texto):
        decomposicao = unicodedata.normalize("NFD", texto.casefold())
        sem_acento = "".join(c for c in decomposicao if unicodedata.category(c) != "Mn")
        return re.sub(r"\s+", " ", sem_acento).strip()

    def excluir_tarefas_na_data(self, data_alvo):
        if data_alvo is None:
            quantidade = len(self.tarefas)
            if not quantidade:
                return "Você não tem tarefas para excluir."
            self.tarefas.clear()
            salvar_tarefas(self.tarefas)
            self._ultima_lista = []
            if quantidade == 1:
                return "Exclu\u00ed a tarefa."
            return f"Excluí todas as {quantidade} tarefas."
        removidas = [t for t in self.tarefas if t.data == data_alvo]
        if not removidas:
            return f"Não há tarefas para {data_alvo.strftime('%d/%m/%Y')}."
        self.tarefas = [t for t in self.tarefas if t.data != data_alvo]
        salvar_tarefas(self.tarefas)
        self._ultima_lista = [t for t in self._ultima_lista if t in self.tarefas]
        return f"Excluí {len(removidas)} tarefa(s) de {data_alvo.strftime('%d/%m/%Y')}."

    def excluir_uma_tarefa_na_data(self, data_alvo):
        candidatas = [tarefa for tarefa in self.tarefas if tarefa.data == data_alvo]
        if not candidatas:
            return f"Não encontrei tarefa para {data_alvo.strftime('%d/%m/%Y')}."
        if len(candidatas) > 1:
            return (
                f"Há {len(candidatas)} tarefas para {data_alvo.strftime('%d/%m/%Y')}. "
                "Informe o número da tarefa que quer excluir."
            )
        return self.excluir_tarefa(numero=self.tarefas.index(candidatas[0]) + 1)

    def adicionar_tarefa(self, titulo, data=None):
        nova_tarefa = Tarefa(titulo, data=data or parse_data_tarefa(titulo))
        self.tarefas.append(nova_tarefa)
        salvar_tarefas(self.tarefas)

    def listar_tarefas(self):
        return self.tarefas

    def formatar_tarefas(self):
        self._ultima_lista = list(self.tarefas)
        if not self.tarefas:
            return "Você ainda não tem tarefas."

        linhas = []
        for numero, tarefa in enumerate(self.tarefas, start=1):
            status = "concluída" if tarefa.concluida else "pendente"
            linhas.append(f"{numero}. [{status}] {tarefa.titulo}")

        return "\n".join(linhas)

    def concluir_tarefa(self, numero):
        try:
            indice = int(numero) - 1
        except ValueError:
            return "Informe o número da tarefa. Exemplo: concluir tarefa 1."

        if indice < 0 or indice >= len(self.tarefas):
            return "Não encontrei uma tarefa com esse número."

        tarefa = self.tarefas[indice]
        tarefa.concluir()
        salvar_tarefas(self.tarefas)
        return f"Tarefa concluída: {tarefa.titulo}"

    def editar_tarefa(self, numero=None, titulo=None, campo="titulo", valor=""):
        tarefa = self._localizar_tarefa(numero, titulo)
        if isinstance(tarefa, str):
            return tarefa
        if campo == "titulo":
            tarefa.titulo = valor
        elif campo == "data":
            try:
                tarefa.data = date.fromisoformat(valor)
            except ValueError:
                return "Informe a data no formato AAAA-MM-DD."
        else:
            return "Posso editar o titulo ou a data da tarefa."
        salvar_tarefas(self.tarefas)
        return f"Tarefa atualizada: {tarefa.titulo}"

    def _localizar_tarefa(self, numero=None, titulo=None):
        if numero is not None:
            if not isinstance(numero, int) or isinstance(numero, bool) or numero < 1 or numero > len(self.tarefas):
                return "Nao encontrei uma tarefa com esse numero."
            return self.tarefas[numero - 1]
        palavras_busca = set(re.findall(r"\w+", self._normalizar_texto(titulo or "")))
        palavras_busca -= {"tarefa", "tarefas", "a", "as", "o", "os", "de", "da", "do", "um", "uma"}
        indices = []
        for i, tarefa in enumerate(self.tarefas):
            palavras_titulo = set(re.findall(r"\w+", self._normalizar_texto(tarefa.titulo)))
            if palavras_busca and palavras_busca.issubset(palavras_titulo):
                indices.append(i)
        if not indices:
            return f"Nao encontrei uma tarefa chamada '{(titulo or '').strip()}'."
        if len(indices) > 1:
            return "Encontrei mais de uma tarefa com esse titulo. Informe o numero da tarefa."
        return self.tarefas[indices[0]]

    def excluir_tarefa(self, numero=None, titulo=None):
        if numero is not None:
            indice = numero - 1
            if indice < 0 or indice >= len(self.tarefas):
                return "Não encontrei uma tarefa com esse número."
        else:
            palavras_busca = set(re.findall(r"\w+", self._normalizar_texto(titulo)))
            palavras_busca -= {"tarefa", "tarefas", "a", "as", "o", "os", "de", "da", "do", "um", "uma"}
            indices = []
            for indice, tarefa in enumerate(self.tarefas):
                palavras_titulo = set(re.findall(r"\w+", self._normalizar_texto(tarefa.titulo)))
                if palavras_busca and palavras_busca.issubset(palavras_titulo):
                    indices.append(indice)
            if not indices:
                return f"Não encontrei uma tarefa chamada '{titulo.strip()}'."
            if len(indices) > 1:
                return (
                    "Encontrei mais de uma tarefa com esse título. "
                    "Informe o número da tarefa que quer excluir."
                )
            indice = indices[0]

        tarefa = self.tarefas.pop(indice)
        salvar_tarefas(self.tarefas)
        return f"Tarefa excluída: {tarefa.titulo}"
