"""Testes automatizados do gerenciador, persistência e interpretador local.

Execute com: python -m unittest -v test_funcionalidades
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import banco
import ia_local
import model
from model import GerenciadorTarefas, Tarefa, parse_data_tarefa


class RespostaHTTP:
    """Resposta mínima compatível com o contexto usado por urlopen."""

    def __init__(self, conteudo):
        self.conteudo = conteudo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.conteudo


class TestBanco(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.arquivo = Path(self.temp.name) / "tarefas.json"
        self.patch_arquivo = patch.object(banco, "ARQUIVO_TAREFAS", self.arquivo)
        self.patch_arquivo.start()
        self.addCleanup(self.patch_arquivo.stop)
        self.addCleanup(self.temp.cleanup)

    def test_arquivo_ausente_ou_vazio_retorna_lista(self):
        self.assertEqual(banco.carregar_tarefas(), [])
        self.arquivo.write_text("  ", encoding="utf-8")
        self.assertEqual(banco.carregar_tarefas(), [])

    def test_carrega_lista_json_e_rejeita_estrutura_invalida(self):
        self.arquivo.write_text('[{"titulo":"Ler", "concluida":false}]', encoding="utf-8")
        self.assertEqual(banco.carregar_tarefas()[0]["titulo"], "Ler")
        self.arquivo.write_text('{"titulo":"Ler"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lista"):
            banco.carregar_tarefas()

    def test_salva_e_recarrega_tarefa_com_data_e_status(self):
        tarefa = Tarefa("Revisar", date(2026, 11, 20))
        tarefa.concluir()
        banco.salvar_tarefas([tarefa])
        self.assertEqual(banco.carregar_tarefas(), [{
            "titulo": "Revisar", "concluida": True, "data": "2026-11-20"
        }])
        self.assertEqual(list(Path(self.temp.name).glob("tmp*")), [])


class TestParseData(unittest.TestCase):
    def test_datas_iso_br_e_mes_por_extenso(self):
        self.assertEqual(parse_data_tarefa("2026-11-20"), date(2026, 11, 20))
        self.assertEqual(parse_data_tarefa("20/11/2026"), date(2026, 11, 20))
        self.assertEqual(parse_data_tarefa("20 de novembro de 2026"), date(2026, 11, 20))

    def test_data_invalida_e_texto_sem_data_usam_hoje(self):
        hoje = date.today()
        self.assertEqual(parse_data_tarefa("31/02/2026"), hoje)
        self.assertEqual(parse_data_tarefa("qualquer tarefa"), hoje)
        self.assertEqual(parse_data_tarefa(None), hoje)

    def test_datas_relativas(self):
        hoje = date.today()
        self.assertEqual(parse_data_tarefa("hoje"), hoje)
        self.assertEqual(parse_data_tarefa("amanhã"), date.fromordinal(hoje.toordinal() + 1))
        self.assertEqual(parse_data_tarefa("depois de amanhã"), date.fromordinal(hoje.toordinal() + 2))


class TestGerenciador(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.arquivo = Path(self.temp.name) / "tarefas.json"
        self.patch_arquivo = patch.object(banco, "ARQUIVO_TAREFAS", self.arquivo)
        self.patch_arquivo.start()
        self.addCleanup(self.patch_arquivo.stop)
        self.addCleanup(self.temp.cleanup)
        self.g = GerenciadorTarefas()

    def adicionar_duas(self):
        self.g.adicionar_tarefa("Estudar Python", date(2026, 11, 20))
        self.g.adicionar_tarefa("Pagar conta", date(2026, 11, 21))

    def test_criar_listar_e_persistir(self):
        resposta = self.g.processar_mensagem("crie uma tarefa chamada estudar testes para 20/11/2026")
        self.assertIn("Tarefa criada", resposta)
        self.assertEqual(len(self.g.listar_tarefas()), 1)
        self.assertEqual(self.g.tarefas[0].data, date(2026, 11, 20))
        recarregado = GerenciadorTarefas()
        self.assertEqual(recarregado.tarefas[0].titulo, self.g.tarefas[0].titulo)

    def test_formatar_lista_vazia_pendente_concluida_e_referencia(self):
        self.assertIn("tarefas", self.g.formatar_tarefas())
        self.adicionar_duas()
        self.g.concluir_tarefa("1")
        resultado = self.g.formatar_tarefas()
        self.assertIn("Estudar Python", resultado)
        self.assertTrue(self.g.tarefas[0].concluida)
        self.assertIn("2. [pendente] Pagar conta", resultado)
        self.assertEqual(self.g._ultima_lista, self.g.tarefas)

    def test_concluir_valida_numero_e_salva(self):
        self.adicionar_duas()
        self.assertIn("tarefa", self.g.concluir_tarefa("0").lower())
        self.assertIn("Informe", self.g.concluir_tarefa("abc"))
        self.g.concluir_tarefa("2")
        self.assertTrue(self.g.tarefas[1].concluida)
        self.assertTrue(banco.carregar_tarefas()[1]["concluida"])

    def test_editar_titulo_data_e_erros(self):
        self.adicionar_duas()
        self.g.editar_tarefa(numero=1, campo="titulo", valor="Estudar pytest")
        self.assertEqual(self.g.tarefas[0].titulo, "Estudar pytest")
        self.g.editar_tarefa(titulo="pagar conta", campo="data", valor="2026-11-25")
        self.assertEqual(self.g.tarefas[1].data, date(2026, 11, 25))
        self.assertIn("formato", self.g.editar_tarefa(numero=1, campo="data", valor="25/11/2026"))
        self.assertIn("titulo ou a data", self.g.editar_tarefa(numero=1, campo="outro", valor="x"))

    def test_busca_por_titulo_ignora_acento_e_detecta_ambiguidades(self):
        self.g.adicionar_tarefa("Reunião com João", date(2026, 11, 20))
        self.g.adicionar_tarefa("Reunião com Maria", date(2026, 11, 21))
        self.assertEqual(self.g._localizar_tarefa(titulo="reuniao joao").titulo, "Reunião com João")
        self.assertIn("mais de uma", self.g._localizar_tarefa(titulo="reunião"))
        self.assertIn("Nao encontrei", self.g._localizar_tarefa(titulo="inexistente"))
        self.assertIn("numero", self.g._localizar_tarefa(numero=True))

    def test_excluir_por_numero_titulo_data_e_todas(self):
        self.adicionar_duas()
        self.g.excluir_tarefa(titulo="estudar python")
        self.assertEqual(len(self.g.tarefas), 1)
        self.g.adicionar_tarefa("Outra", date(2026, 11, 20))
        self.assertIn("tarefa(s)", self.g.excluir_tarefas_na_data(date(2026, 11, 20)))
        self.assertEqual(len(self.g.tarefas), 1)
        self.g.excluir_tarefas_na_data(None)
        self.assertEqual(self.g.tarefas, [])
        self.assertIn("tarefas", self.g.excluir_tarefas_na_data(None))

    def test_excluir_unica_data_ou_pedir_especificacao_se_ambiguo(self):
        dia = date(2026, 11, 20)
        self.g.adicionar_tarefa("Um", dia)
        self.g.excluir_uma_tarefa_na_data(dia)
        self.g.adicionar_tarefa("Dois", dia)
        self.g.adicionar_tarefa("Três", dia)
        self.assertIn("Informe", self.g.excluir_uma_tarefa_na_data(dia))
        self.assertIn("tarefa", self.g.excluir_uma_tarefa_na_data(date(2026, 12, 1)))

    def test_tarefas_do_dia_e_comandos_diretos_sem_ollama(self):
        self.adicionar_duas()
        self.assertEqual(len(self.g.obter_tarefas_do_dia(2026, 11, 20)), 1)
        self.assertIn("Estudar Python", self.g.processar_mensagem("liste minhas tarefas"))
        self.g.processar_mensagem("marque a tarefa 1 como feita")
        self.assertTrue(self.g.tarefas[0].concluida)
        interpretacao_edicao = {
            "intencao": "editar", "numero": 2, "titulo": None,
            "campo": "titulo", "valor": "Revisar contas", "resposta": "",
        }
        with patch.object(model, "interpretar_mensagem", return_value=interpretacao_edicao):
            self.g.processar_mensagem("altere o título da tarefa 2")
        self.assertEqual(self.g.tarefas[1].titulo, "Revisar contas")
        self.g.processar_mensagem("delete a tarefa 2")
        self.assertEqual(len(self.g.tarefas), 1)

    def test_regressoes_titulo_conclusao_e_exclusao_por_titulo(self):
        self.adicionar_duas()
        # título não pode perder letras t/r/n nas pontas
        self.g.processar_mensagem("crie tarefa estudar python")
        self.assertEqual(self.g.tarefas[-1].titulo, "estudar python")
        # "marque como concluída ..." não cria tarefa e aceita ordinal
        total = len(self.g.tarefas)
        self.g.processar_mensagem("marque como concluída a tarefa 2")
        self.g.processar_mensagem("marque a primeira como feita")
        self.assertEqual(len(self.g.tarefas), total)
        self.assertTrue(self.g.tarefas[0].concluida and self.g.tarefas[1].concluida)
        # criar com "ver tarefas" no título não vira listagem
        self.g.processar_mensagem("crie a tarefa ver tarefas da faculdade")
        self.assertEqual(self.g.tarefas[-1].titulo, "ver tarefas da faculdade")
        # excluir pelo título
        self.g.processar_mensagem("apague a tarefa pagar conta")
        self.assertNotIn("Pagar conta", [t.titulo for t in self.g.tarefas])

    def test_editar_data_vinda_da_ia_em_formato_brasileiro(self):
        self.adicionar_duas()
        edicao = {"intencao": "editar", "numero": 1, "titulo": None,
                  "campo": "data", "valor": "25/11/2026", "resposta": ""}
        with patch.object(model, "interpretar_mensagem", return_value=edicao):
            self.g.processar_mensagem("altera a data da tarefa 1 para 25/11/2026")
        self.assertEqual(self.g.tarefas[0].data, date(2026, 11, 25))

    def test_async_chama_callback_ou_callback_de_erro(self):
        recebido = []
        evento = __import__("threading").Event()
        self.g.processar_mensagem = lambda _: "ok"
        self.g.processar_mensagem_async("oi", lambda valor: (recebido.append(valor), evento.set()))
        self.assertTrue(evento.wait(2))
        self.assertEqual(recebido, ["ok"])

        erros = []
        evento.clear()
        def falhar(_):
            raise RuntimeError("falha")
        self.g.processar_mensagem = falhar
        self.g.processar_mensagem_async("oi", lambda _: None,
                                        lambda erro: (erros.append(erro), evento.set()))
        self.assertTrue(evento.wait(2))
        self.assertIsInstance(erros[0], RuntimeError)


class TestInterpretadorLocal(unittest.TestCase):
    def resposta_fake(self, interpretacao):
        corpo = json.dumps({"message": {"content": json.dumps(interpretacao)}}).encode("utf-8")
        return RespostaHTTP(corpo)

    def test_mensagem_vazia_nao_consulta_modelo(self):
        with patch.object(ia_local, "urlopen") as urlopen:
            resultado = ia_local.interpretar_mensagem("  ")
        urlopen.assert_not_called()
        self.assertEqual(resultado["intencao"], "esclarecer")

    def test_interpretacao_valida_normaliza_campos_e_monta_requisicao(self):
        bruto = {"intencao": "criar", "titulo": "  Comprar café ", "numero": True,
                 "campo": "campo_invalido", "valor": " null ", "resposta": " Criando "}
        with patch.object(ia_local, "urlopen", return_value=self.resposta_fake(bruto)) as urlopen:
            resultado = ia_local.interpretar_mensagem("  crie uma tarefa  ")
        requisicao = urlopen.call_args.args[0]
        enviado = json.loads(requisicao.data.decode("utf-8"))
        self.assertEqual(resultado, {"intencao": "criar", "titulo": "Comprar café", "numero": None,
                                     "campo": None, "valor": None, "resposta": "Criando"})
        self.assertEqual(requisicao.method, "POST")
        self.assertEqual(enviado["messages"][-1]["content"], "crie uma tarefa")

    def test_intencao_invalida_e_json_malformado_propagam_erro(self):
        bruto = {"intencao": "inventada", "resposta": "x"}
        with patch.object(ia_local, "urlopen", return_value=self.resposta_fake(bruto)):
            with self.assertRaises(ValueError):
                ia_local.interpretar_mensagem("oi")
        resposta = RespostaHTTP(b"nao e json")
        with patch.object(ia_local, "urlopen", return_value=resposta):
            with self.assertRaises(json.JSONDecodeError):
                ia_local.interpretar_mensagem("oi")


if __name__ == "__main__":
    unittest.main()
