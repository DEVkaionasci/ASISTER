import calendar
import json
from datetime import date
from urllib.error import URLError

import customtkinter as ctk
from PIL import Image, ImageDraw

from model import GerenciadorTarefas

# =====================================================================
# Constantes e paleta de cores
# =====================================================================

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

AZUL = "#1963b8"
AZUL_HOVER = "#154f94"
VERDE = "#3fa764"

# Tuplas (claro, escuro) para cores adaptáveis ao tema
COR_PENDENTE = ("#dbeafe", "#1e3a5f")
COR_FEITA = ("#d1fae5", "#1a3a2a")
COR_SIDEBAR = ("#f4f4f5", "#18181b")
COR_HOVER = ("#e4e4e7", "#27272a")
COR_ATIVO = ("#dbeafe", "#1e3a5f")
COR_TEXTO = ("#18181b", "#f4f4f5")
COR_TEXTO_SUAVE = ("#71717a", "#a1a1aa")
COR_BORDA = ("#e4e4e7", "#27272a")

COR_CELULA = ("white", "#1c1c1e")
COR_CELULA_FORA = ("#f4f4f5", "#161618")
COR_CELULA_HOJE = ("#dbeafe", "#1a2f4e")

COR_BARRA_INF = ("#f4f4f5", "#0f0f11")
COR_PILL = ("white", "#262628")
COR_BALAO_IA = ("#e4e4e7", "#333336")

MAX_CHIPS = 2
LARGURA_MAX_BALAO = 560


# =====================================================================
# Aplicação principal
# =====================================================================

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gestor Pessoal")
        self.geometry("1000x650")
        self.minsize(760, 520)
        ctk.set_appearance_mode("Dark")

        self.barra_lateral_visivel = False
        self.balao_digitando = None
        self.boas_vindas_ativa = True

        self.criar_barra_lateral()
        self.criar_paginas()
        self.criar_barra_chat()
        self.criar_area_mensagens()
        self.gerenciador_tarefas = GerenciadorTarefas(self)
        self.criar_calendario()
        self.criar_botao_menu_flutuante()
        self.mostrar_pagina("chat")

    # ------------------------------------------------------------------
    # Páginas (chat / calendário)
    # ------------------------------------------------------------------
    def criar_paginas(self):
        self.conteudo = ctk.CTkFrame(master=self, fg_color="transparent")
        self.conteudo.pack(fill="both", expand=True)

        self.pagina_chat = ctk.CTkFrame(
            master=self.conteudo, fg_color="transparent")
        self.pagina_calendario = ctk.CTkFrame(
            master=self.conteudo, fg_color="transparent")

    def mostrar_pagina(self, nome):
        self.pagina_chat.pack_forget()
        self.pagina_calendario.pack_forget()
        if nome == "calendario":
            self.desenhar_mes()
            self.pagina_calendario.pack(fill="both", expand=True)
        else:
            self.pagina_chat.pack(fill="both", expand=True)

        for chave, botao in self.botoes_nav.items():
            botao.configure(
                fg_color=COR_ATIVO if chave == nome else "transparent")

    # ------------------------------------------------------------------
    # Ícones desenhados com PIL
    # ------------------------------------------------------------------
    def criar_icone(self, tipo, tamanho=20):
        """Cria um CTkImage a partir de um desenho PIL, com versões clara
        e escura para se adaptar automaticamente ao tema."""

        def desenhar(cor):
            img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            if tipo == "menu":
                for y in (12, 19, 26):
                    d.rounded_rectangle((8, y, 32, y + 3), radius=2, fill=cor)
            elif tipo == "enviar":
                # seta simples apontando à direita
                d.polygon([(12, 10), (30, 20), (12, 30)], fill=cor)
            elif tipo == "fechar":
                d.line([(10, 10), (30, 30)], fill=cor, width=3, joint="curve")
                d.line([(30, 10), (10, 30)], fill=cor, width=3, joint="curve")
            return img

        return ctk.CTkImage(
            light_image=desenhar((40, 40, 40, 255)),
            dark_image=desenhar((235, 235, 235, 255)),
            size=(tamanho, tamanho))

    # ------------------------------------------------------------------
    # Barra lateral
    # ------------------------------------------------------------------
    def criar_barra_lateral(self):
        self.barra_lateral = ctk.CTkFrame(
            master=self, width=240, corner_radius=0, fg_color=COR_SIDEBAR)
        self.barra_lateral.pack_propagate(False)

        cabecalho = ctk.CTkFrame(self.barra_lateral, fg_color="transparent")
        cabecalho.pack(fill="x", padx=12, pady=(14, 10))

        self.icone_menu = self.criar_icone("menu")
        self.btn_menu_lateral = ctk.CTkButton(
            cabecalho, fg_color="transparent", hover_color=COR_HOVER,
            image=self.icone_menu, text="", width=36, height=36, corner_radius=8,
            command=self.toggle_barra_lateral)
        self.btn_menu_lateral.pack(side="left")

        ctk.CTkLabel(
            cabecalho, text="Gestor Pessoal",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COR_TEXTO).pack(side="left", padx=10)

        ctk.CTkLabel(
            self.barra_lateral, text="NAVEGAÇÃO", anchor="w",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COR_TEXTO_SUAVE).pack(fill="x", padx=22, pady=(16, 6))

        self.botoes_nav = {}
        itens = (("chat", "💬   Chat"), ("calendario", "📅   Calendário"))
        for chave, rotulo in itens:
            botao = ctk.CTkButton(
                self.barra_lateral, text=rotulo, anchor="w", height=42,
                corner_radius=8, fg_color="transparent",
                text_color=COR_TEXTO, hover_color=COR_HOVER,
                font=ctk.CTkFont(size=14),
                command=lambda c=chave: self.mostrar_pagina(c))
            botao.pack(fill="x", padx=12, pady=2)
            self.botoes_nav[chave] = botao

        # rodapé
        ctk.CTkFrame(
            self.barra_lateral, height=1, fg_color=COR_BORDA).pack(
            side="bottom", fill="x", padx=16)

        self.switch_tema = ctk.CTkSwitch(
            master=self.barra_lateral, text="Modo Escuro",
            command=self.alternar_tema, progress_color=AZUL,
            button_color="white", button_hover_color="#e0e0e0")
        self.switch_tema.select()
        self.switch_tema.pack(side="bottom", anchor="w", padx=22, pady=(10, 20))

    def alternar_tema(self):
        if self.switch_tema.get() == 1:
            ctk.set_appearance_mode("Dark")
            self.switch_tema.configure(text="Modo Escuro")
        else:
            ctk.set_appearance_mode("Light")
            self.switch_tema.configure(text="Modo Claro")

    def toggle_barra_lateral(self):
        if not self.barra_lateral_visivel:
            self.barra_lateral.pack(before=self.conteudo, side="left", fill="y")
            self.btn_menu.pack_forget()
        else:
            self.barra_lateral.pack_forget()
            self.btn_menu.pack(before=self.conteudo, side="top", anchor="nw",
                               padx=10, pady=10)
        self.barra_lateral_visivel = not self.barra_lateral_visivel

    def criar_botao_menu_flutuante(self):
        self.btn_menu = ctk.CTkButton(
            master=self, fg_color="transparent", hover_color=COR_HOVER,
            image=self.icone_menu, text="", width=36, height=36, corner_radius=8,
            command=self.toggle_barra_lateral)
        self.btn_menu.pack(before=self.conteudo, side="top", anchor="nw",
                           padx=10, pady=10)

    # ------------------------------------------------------------------
    # Calendário
    # ------------------------------------------------------------------
    def criar_calendario(self):
        hoje = date.today()
        self.ano, self.mes = hoje.year, hoje.month

        topo = ctk.CTkFrame(master=self.pagina_calendario, fg_color="transparent")
        topo.pack(fill="x", padx=20, pady=(14, 8))

        # título à esquerda
        ctk.CTkLabel(
            topo, text="Calendário",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COR_TEXTO).pack(side="left", padx=(4, 0))

        # controles à direita
        ctk.CTkButton(
            topo, text="Hoje", width=70, height=34, corner_radius=17,
            fg_color="transparent", border_width=1, border_color=COR_BORDA,
            text_color=COR_TEXTO, hover_color=COR_HOVER,
            font=ctk.CTkFont(size=13),
            command=self.ir_para_hoje).pack(side="right")
        ctk.CTkButton(
            topo, text="›", width=36, height=34, corner_radius=17,
            fg_color="transparent", text_color=COR_TEXTO, hover_color=COR_HOVER,
            font=ctk.CTkFont(size=20),
            command=lambda: self.mudar_mes(1)).pack(side="right", padx=(0, 4))
        ctk.CTkButton(
            topo, text="‹", width=36, height=34, corner_radius=17,
            fg_color="transparent", text_color=COR_TEXTO, hover_color=COR_HOVER,
            font=ctk.CTkFont(size=20),
            command=lambda: self.mudar_mes(-1)).pack(side="right")
        self.lbl_mes = ctk.CTkLabel(
            topo, text="", font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COR_TEXTO)
        self.lbl_mes.pack(side="right", padx=(0, 16))

        self.grade = ctk.CTkFrame(
            master=self.pagina_calendario, fg_color="transparent")
        self.grade.pack(fill="both", expand=True, padx=20, pady=(4, 16))
        for c in range(7):
            self.grade.grid_columnconfigure(c, weight=1, uniform="dia")

        self.desenhar_mes()

    def ir_para_hoje(self):
        hoje = date.today()
        self.ano, self.mes = hoje.year, hoje.month
        self.desenhar_mes()

    def mudar_mes(self, delta):
        self.mes += delta
        if self.mes < 1:
            self.mes, self.ano = 12, self.ano - 1
        elif self.mes > 12:
            self.mes, self.ano = 1, self.ano + 1
        self.desenhar_mes()

    def desenhar_mes(self):
        for w in self.grade.winfo_children():
            w.destroy()
        self.lbl_mes.configure(text=f"{MESES[self.mes - 1]} {self.ano}")
        hoje = date.today()

        # cabeçalho dos dias da semana
        for c, nome in enumerate(DIAS_SEMANA):
            ctk.CTkLabel(
                self.grade, text=nome.upper(),
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COR_TEXTO_SUAVE).grid(
                row=0, column=c, pady=(0, 8), sticky="w", padx=6)

        semanas = calendar.Calendar(firstweekday=6).monthdatescalendar(
            self.ano, self.mes)

        # CORREÇÃO: apenas as linhas que contêm semanas recebem peso e
        # uniformidade; as demais ficam com peso 0 e sem uniform, para não
        # roubar espaço e deixar um buraco no fundo da grade.
        for r in range(1, 7):
            self.grade.grid_rowconfigure(r, weight=0, uniform="")
        for r in range(1, len(semanas) + 1):
            self.grade.grid_rowconfigure(r, weight=1, uniform="semana")

        for r, semana in enumerate(semanas, start=1):
            for c, data in enumerate(semana):
                fora = data.month != self.mes
                eh_hoje = data == hoje

                if eh_hoje:
                    cor_celula = COR_CELULA_HOJE
                elif fora:
                    cor_celula = COR_CELULA_FORA
                else:
                    cor_celula = COR_CELULA

                celula = ctk.CTkFrame(
                    self.grade, corner_radius=10, fg_color=cor_celula,
                    border_width=2 if eh_hoje else 1,
                    border_color=AZUL if eh_hoje else COR_BORDA)
                celula.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)

                abrir = lambda _e=None, d=data: self.mostrar_detalhes_dia(
                    d.year, d.month, d.day)
                celula.bind("<Button-1>", abrir)

                # botão do número do dia
                if eh_hoje:
                    cor_num = ("white", "white")
                    fg_btn = AZUL
                    hover_btn = AZUL_HOVER
                elif fora:
                    cor_num = ("#a1a1aa", "#52525b")
                    fg_btn = "transparent"
                    hover_btn = ("#e4e4e7", "#2a2a2a")
                else:
                    cor_num = COR_TEXTO
                    fg_btn = "transparent"
                    hover_btn = ("#e4e4e7", "#2a2a2a")

                btn_dia = ctk.CTkButton(
                    celula, text=str(data.day), width=28, height=24,
                    corner_radius=12,
                    font=ctk.CTkFont(
                        size=11, weight="bold" if eh_hoje else "normal"),
                    fg_color=fg_btn, hover_color=hover_btn,
                    text_color=cor_num, command=abrir)
                btn_dia.pack(anchor="nw", padx=4, pady=(3, 1))

                # chips de tarefas
                tarefas = self.gerenciador_tarefas.obter_tarefas_do_dia(
                    data.year, data.month, data.day)

                container_chips = ctk.CTkFrame(celula, fg_color="transparent")
                container_chips.pack(fill="x", padx=3, pady=(0, 3))

                for tarefa in tarefas[:MAX_CHIPS]:
                    texto = tarefa.titulo
                    if len(texto) > 12:
                        texto = texto[:11] + "…"
                    prefixo = "✓ " if tarefa.concluida else "• "
                    chip = ctk.CTkLabel(
                        container_chips, text=prefixo + texto, anchor="w",
                        height=16, corner_radius=4, padx=4,
                        font=ctk.CTkFont(size=9),
                        fg_color=COR_FEITA if tarefa.concluida else COR_PENDENTE,
                        text_color=("gray15", "gray95"))
                    chip.pack(anchor="w", pady=1)
                    chip.bind("<Button-1>", abrir)

                restantes = len(tarefas) - MAX_CHIPS
                if restantes > 0:
                    mais = ctk.CTkLabel(
                        container_chips, text=f"+{restantes} mais", anchor="w",
                        height=13,
                        font=ctk.CTkFont(size=8),
                        text_color=COR_TEXTO_SUAVE)
                    mais.pack(anchor="w", padx=2, pady=(0, 0))
                    mais.bind("<Button-1>", abrir)

    def mostrar_detalhes_dia(self, ano, mes, dia):
        janela = ctk.CTkToplevel(self)
        janela.title(f"{dia} de {MESES[mes - 1]} de {ano}")
        janela.geometry("460x520")
        janela.transient(self)
        janela.grab_set()
        janela.after(100, janela.focus)

        # cabeçalho com botão de fechar
        cabecalho = ctk.CTkFrame(janela, fg_color="transparent")
        cabecalho.pack(fill="x", padx=20, pady=(18, 4))

        ctk.CTkLabel(
            cabecalho, text=f"{dia} de {MESES[mes - 1]} de {ano}",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COR_TEXTO).pack(side="left")

        self.icone_fechar = self.criar_icone("fechar", tamanho=16)
        ctk.CTkButton(
            cabecalho, text="", image=self.icone_fechar,
            width=30, height=30, corner_radius=15,
            fg_color="transparent", hover_color=COR_HOVER,
            command=janela.destroy).pack(side="right")

        ctk.CTkFrame(janela, height=1, fg_color=COR_BORDA).pack(
            fill="x", padx=20, pady=(8, 8))

        tarefas = self.gerenciador_tarefas.obter_tarefas_do_dia(ano, mes, dia)
        if not tarefas:
            ctk.CTkLabel(
                janela, text="Nenhuma tarefa para esta data.", anchor="w",
                text_color=COR_TEXTO_SUAVE,
                font=ctk.CTkFont(size=13)).pack(fill="x", padx=20, pady=20)
            return

        lista = ctk.CTkScrollableFrame(janela, fg_color="transparent")
        lista.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for tarefa in tarefas:
            item = ctk.CTkFrame(
                lista, corner_radius=10, height=58,
                fg_color=("white", "#1e1e20"),
                border_width=1, border_color=COR_BORDA)
            item.pack(fill="x", padx=6, pady=3)
            item.pack_propagate(False)

            # faixa lateral colorida
            ctk.CTkFrame(
                item, width=4, corner_radius=2,
                fg_color=VERDE if tarefa.concluida else AZUL).pack(
                side="left", fill="y", padx=(6, 0), pady=10)

            corpo = ctk.CTkFrame(item, fg_color="transparent")
            corpo.pack(side="left", fill="both", expand=True,
                       padx=(8, 10), pady=8)

            linha_titulo = ctk.CTkFrame(corpo, fg_color="transparent")
            linha_titulo.pack(fill="x", expand=True)

            icone = "✓" if tarefa.concluida else "○"
            cor_icone = VERDE if tarefa.concluida else AZUL
            ctk.CTkLabel(
                linha_titulo, text=icone, width=20,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=cor_icone).pack(side="left", padx=(0, 6))

            ctk.CTkLabel(
                linha_titulo, text=tarefa.titulo, anchor="w", justify="left",
                wraplength=320,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COR_TEXTO).pack(
                side="left", fill="x", expand=True)

            ctk.CTkLabel(
                corpo, text="Concluída" if tarefa.concluida else "Pendente",
                anchor="w", text_color=COR_TEXTO_SUAVE,
                font=ctk.CTkFont(size=11)).pack(
                fill="x", padx=26, pady=(0, 0))

    # ------------------------------------------------------------------
    # Chat — barra inferior baseada em frames (sem PIL)
    # ------------------------------------------------------------------
    def criar_barra_chat(self):
        """Cria e empacota a barra inferior do chat.
        Usa frames CTk nativos em vez de imagens PIL: é mais rápido,
        adaptável ao tema e sem regeneração a cada redimensionamento."""
        self.barra_inferior = ctk.CTkFrame(
            master=self.pagina_chat, fg_color=COR_BARRA_INF, height=74,
            corner_radius=0, border_width=1, border_color=COR_BORDA)
        self.barra_inferior.pack(side="bottom", fill="x")
        self.barra_inferior.pack_propagate(False)

        # pílula arredondada que contém o campo e o botão
        self.pill = ctk.CTkFrame(
            master=self.barra_inferior, fg_color=COR_PILL, height=50,
            corner_radius=25, border_width=1, border_color=COR_BORDA)
        self.pill.pack(fill="x", expand=True, padx=20, pady=(10, 14))
        self.pill.pack_propagate(False)

        self.chat = ctk.CTkEntry(
            master=self.pill, height=36, corner_radius=18,
            fg_color="transparent", border_width=0,
            placeholder_text="Digite uma mensagem...",
            font=ctk.CTkFont(size=14), text_color=COR_TEXTO)
        self.chat.pack(side="left", fill="x", expand=True,
                       padx=(18, 6), pady=7)
        self.chat.bind("<Return>", self.enviar_mensagem)

        self.icone_enviar = self.criar_icone("enviar", tamanho=18)
        self.btn_enviar = ctk.CTkButton(
            master=self.pill, text="", image=self.icone_enviar,
            width=36, height=36, corner_radius=18,
            fg_color=AZUL, hover_color=AZUL_HOVER,
            command=self.enviar_mensagem)
        self.btn_enviar.pack(side="right", padx=(6, 7), pady=7)

    def criar_area_mensagens(self):
        self.area_mensagens = ctk.CTkScrollableFrame(
            master=self.pagina_chat, fg_color="transparent",
            scrollbar_button_color=("gray80", "gray30"),
            scrollbar_button_hover_color=("gray65", "gray45"))
        self.area_mensagens.pack(fill="both", expand=True)

        self._mostrar_boas_vindas()

    def _mostrar_boas_vindas(self):
        """Exibe uma mensagem de boas-vindas centralizada na área de chat
        quando não há mensagens. Usa place() para centralizar verticalmente."""
        self.frame_boas_vindas = ctk.CTkFrame(
            master=self.pagina_chat, fg_color="transparent")
        self.frame_boas_vindas.place(relx=0.5, rely=0.38, anchor="center",
                                     relwidth=0.92)
        self.frame_boas_vindas.lift()

        ctk.CTkLabel(
            self.frame_boas_vindas, text="💬",
            font=ctk.CTkFont(size=48)).pack(pady=(0, 10))

        ctk.CTkLabel(
            self.frame_boas_vindas, text="Bem-vindo ao Gestor Pessoal",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COR_TEXTO).pack(pady=(0, 8))

        ctk.CTkLabel(
            self.frame_boas_vindas,
            text="Digite uma mensagem para criar tarefas ou tirar dúvidas.\n"
                 "Use o calendário para visualizar suas tarefas por data.",
            font=ctk.CTkFont(size=13),
            text_color=COR_TEXTO_SUAVE, justify="center").pack(pady=(0, 10))

        # dica visual
        ctk.CTkLabel(
            self.frame_boas_vindas,
            text="Pressione Enter ou clique no botão azul para enviar",
            font=ctk.CTkFont(size=11),
            text_color=COR_TEXTO_SUAVE).pack(pady=(6, 0))

    def adicionar_balao(self, texto, remetente="usuario"):
        # remove a tela de boas-vindas na primeira mensagem
        if self.boas_vindas_ativa and hasattr(self, "frame_boas_vindas"):
            if self.frame_boas_vindas.winfo_exists():
                self.frame_boas_vindas.destroy()
            self.boas_vindas_ativa = False

        if remetente == "usuario":
            cor_fundo = (AZUL, AZUL)
            cor_texto = ("white", "white")
            lado = "right"
        else:
            cor_fundo = COR_BALAO_IA
            cor_texto = COR_TEXTO
            lado = "left"

        # largura do balão com limites mínimo e máximo
        w = self.area_mensagens.winfo_width()
        if w > 1:
            largura_balao = min(max(200, w - 60), LARGURA_MAX_BALAO)
        else:
            largura_balao = 420

        linha = ctk.CTkFrame(
            master=self.area_mensagens, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=5)

        balao = ctk.CTkFrame(
            master=linha, fg_color=cor_fundo, corner_radius=16)
        balao.pack(side=lado)

        ctk.CTkLabel(
            master=balao, text=texto, wraplength=largura_balao,
            justify="left", text_color=cor_texto,
            font=ctk.CTkFont(size=13)).pack(padx=14, pady=8)
        return linha

    def enviar_mensagem(self, event=None):
        texto = self.chat.get().strip()
        if not texto:
            return

        self.adicionar_balao(texto, remetente="usuario")
        self.chat.delete(0, "end")
        self.chat.configure(state="disabled")
        self.btn_enviar.configure(state="disabled")
        self.balao_digitando = self.adicionar_balao(
            "Digitando...", remetente="ia")

        self.gerenciador_tarefas.processar_mensagem_async(
            texto,
            callback=self._agendar_resposta,
            on_error=lambda e: self._agendar_resposta(self._mensagem_erro(e)))

    def _finalizar_resposta(self, resposta):
        if getattr(self, "balao_digitando", None) is not None:
            self.balao_digitando.destroy()
            self.balao_digitando = None
        self.chat.configure(state="normal")
        self.btn_enviar.configure(state="normal")
        self.chat.focus_set()
        self.adicionar_balao(resposta, remetente="ia")
        # rola até o fim (depois de o Tk desenhar o novo balão)
        self.after(50, self._rolar_para_o_fim)

    def _rolar_para_o_fim(self):
        try:
            self.area_mensagens._parent_canvas.yview_moveto(1.0)
        except AttributeError:
            pass

    @staticmethod
    def _mensagem_erro(erro):
        if isinstance(erro, (URLError, TimeoutError, ConnectionError)):
            return ("Não consegui falar com o Ollama. Verifique se ele está aberto "
                    "e se o modelo llama3.2 está instalado.")
        if isinstance(erro, json.JSONDecodeError):
            return "A IA devolveu uma resposta inválida. Tente de novo."
        return f"Erro: {erro}"

    def _agendar_resposta(self, resposta):
        """Agenda atualizações da interface na thread principal do Tk."""
        self.after(0, self._finalizar_resposta, resposta)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
