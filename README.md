# ASISTER — Gestor Pessoal de Tarefas com IA Local

Aplicativo de desktop em Python para gerenciar tarefas **conversando em linguagem natural**, com um **calendário mensal** para visualizar o que está marcado em cada dia. A interpretação dos pedidos usa um modelo de IA **local** (Ollama + `llama3.2`), então nada é enviado para a internet.

Projeto acadêmico — Tecnologia em Análise e Desenvolvimento de Sistemas (IF Baiano, Campus Catu).
Autor: Kaio do Nascimento Sacramento.

---

## O que o programa faz

**Chat**
- Entende pedidos escritos do jeito que a pessoa fala e executa a ação:
  - **Criar:** `crie uma tarefa estudar para a prova amanhã`
  - **Listar:** `liste minhas tarefas`, `o que tenho pra fazer hoje?`
  - **Concluir:** `marque a primeira como feita`, `conclua a tarefa pagar conta`
  - **Editar:** `mude o nome da tarefa 3 para Revisar SQL`, `mova a tarefa 1 para sexta`
  - **Excluir:** `apague a tarefa 2`, `apague a tarefa de hoje`, `apague todas as tarefas`
- Aceita datas como `hoje`, `amanhã`, `depois de amanhã`, `sexta`, `20/11/2026`, `20 de novembro`, `2026-11-20`.
- Conversa de forma geral quando o pedido não é sobre tarefas.

**Calendário**
- Grade mensal com as tarefas de cada dia (pendentes e concluídas), destaque para o dia de hoje e navegação entre meses.
- Clicar em um dia abre os detalhes das tarefas daquela data.

**Outros**
- Tema claro e escuro.
- As tarefas ficam salvas em `tarefas.json` e são carregadas ao abrir o app.

### Como o pedido é interpretado

1. Primeiro, **regras locais** (expressões regulares em `model.py`) tratam os comandos mais comuns, de forma rápida e previsível, sem precisar da IA.
2. Se nenhuma regra reconhecer o pedido, ele é enviado ao **Ollama (`llama3.2`)**, que devolve um JSON com a intenção (`criar`, `listar`, `concluir`, `excluir`, `editar`, `conversa`...).
3. O aplicativo **valida** esse JSON e só então executa a ação. A IA apenas interpreta; quem altera as tarefas é o código.

---

## Como executar

### Requisitos
- Python 3.10 ou superior (desenvolvido com Python 3.14)
- [Ollama](https://ollama.com/download) instalado
- Windows, Linux ou macOS (com Tkinter disponível)

### Passo a passo

```bash
# 1. entre na pasta do projeto
cd ASISTER

# 2. (opcional) crie e ative um ambiente virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# 3. instale as dependências
pip install -r requirements.txt

# 4. baixe o modelo da IA (uma vez só) e deixe o Ollama aberto
ollama pull llama3.2

# 5. rode o aplicativo
python main.py
```

> O Ollama precisa estar aberto/rodando (`http://localhost:11434`). Sem ele, os comandos reconhecidos pelas regras locais ainda funcionam, mas os pedidos que dependem da IA mostram uma mensagem avisando que não foi possível falar com o Ollama.

### Testes automatizados

```bash
python -m unittest -v test_funcionalidades
```

Os testes não precisam do Ollama: as respostas da IA são simuladas.

---

## Estrutura do projeto

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Interface gráfica (CustomTkinter): chat, calendário, barra lateral e tema |
| `model.py` | Classes `Tarefa` e `GerenciadorTarefas`; leitura de datas; regras locais de comandos |
| `ia_local.py` | Comunicação com o Ollama e validação do JSON retornado |
| `banco.py` | Persistência em `tarefas.json` (gravação atômica) |
| `test_funcionalidades.py` | Testes automatizados (`unittest`) |
| `tarefas.json` | Dados das tarefas |

### Decisões técnicas
- **Orientação a objetos:** `Tarefa` representa uma tarefa; `GerenciadorTarefas` concentra as regras de negócio; a interface não mexe nos dados diretamente.
- **Multithreading:** a chamada à IA pode demorar, então roda em uma `threading.Thread` separada (`processar_mensagem_async`). Assim a janela não congela enquanto aparece "Digitando...". O resultado volta para a interface com `self.after(0, ...)`, porque o Tkinter só deve ser alterado pela thread principal.
- **Gravação segura:** o `banco.py` grava em um arquivo temporário e depois substitui o original (`os.replace`), evitando corromper o `tarefas.json` se o programa fechar no meio da escrita.
- **IA como interpretador, não como executor:** a saída da IA é restrita a um esquema JSON e validada antes de qualquer ação.

---

## Uso de Inteligência Artificial no desenvolvimento

Este projeto foi desenvolvido por mim, **com o apoio de assistentes de IA atuando como mentores**, e quero deixar isso claro:

- **Mentoria em conceitos e arquitetura:** a IA me ajudou a entender e a aplicar conceitos como **multithreading** (rodar a IA em segundo plano sem travar a interface e atualizar a tela com segurança), gravação atômica de arquivos, validação de saídas de modelos de linguagem e organização do código em camadas.
- **Revisão e correção de erros:** na etapa final, uma IA revisou o código e ajudou a encontrar e corrigir bugs (por exemplo, títulos de tarefas cortados, comandos de concluir/excluir que não funcionavam em certos casos e tratamento de erros quando o Ollama está desligado), além de sugerir testes de regressão.
- **A decisão do que construir, a integração das partes e o entendimento do resultado são meus.** Usei a IA como ferramenta de aprendizado e de apoio, e não como substituta do meu trabalho.

---

## Limitações conhecidas
- A qualidade da interpretação pela IA depende do modelo local (`llama3.2`, de porte pequeno); alguns pedidos muito livres podem ser mal entendidos.
- Algumas mensagens do sistema ainda estão sem acento (ex.: "Nao encontrei..."), pois os testes esperam esse texto.
- O aplicativo não tem sincronização na nuvem nem lembretes/notificações.

## Licença
Veja o arquivo `LICENSE`.
