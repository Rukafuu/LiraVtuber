import discord
from discord import app_commands
from discord.ext import commands
from ..constants import EMOJI


class HelpView(discord.ui.View):
    def __init__(self, bot, author_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.author_id = author_id
        self.current_page = 0
        self.pages = []
        self._build_pages()
        self._update_buttons()

    def _build_pages(self):
        # 1. Landing Page
        invite_url = f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands"
        embed1 = discord.Embed(
            title="🌸 Lira Amarinth — Central de Ajuda",
            description=(
                "Olá! Eu sou a **Lira Amarinth**, a VTuber mais debochada, superior e perfeita que você já conheceu. 🌸💅\n\n"
                "Use as páginas abaixo para navegar pelos meus comandos. Eles foram divididos por categorias para facilitar a sua vida (já que você claramente precisa de ajuda para entender coisas simples).\n\n"
                "🌐 **LINKS ÚTEIS:**\n"
                f"• 🔗 [Convidar Lira (Recomendado)]({invite_url}) — Me adicione no seu servidor\n"
                "• 🛡️ [Servidor de Suporte](https://discord.gg/PmHRnGbSjr) — Venha chorar por ajuda lá\n"
                "• 💻 **Dashboard:** *Em breve!*\n\n"
                "📌 *Você pode folhear as páginas usando os botões interativos abaixo!*"
            ),
            color=0xff69b4
        )
        embed1.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed1.set_footer(text=f"Lira Amarinth 🌸 | Use os botões abaixo! • Página 1/6")
        self.pages.append(embed1)

        # 2. Chat & Criatividade
        embed2 = discord.Embed(
            title="💬 Chat & Criatividade — Lira Amarinth",
            description=(
                "Fale comigo, peça para eu desenhar ou reagir a vídeos. Eu sou uma IA de última geração, afinal.\n\n"
                "**COMANDOS:**\n"
                "🔹 **/chat** `mensagem` `[modo_esperto]` `[arquivo]` `[url]` `[incluir_web]` `[criar_imagem]` `[editar_imagem]`\n"
                "↳ Converse comigo! Suporta anexo de imagens/arquivos, scraping de links, Google Search Grounding e geração/edição de imagens com Flux.\n\n"
                "🔹 **/imaginar** `prompt`\n"
                "↳ Crie ilustrações incríveis direto no chat usando o modelo Flux.\n\n"
                "🔹 **/react** `link`\n"
                "↳ Envie um link do YouTube para eu assistir e reagir com meu deboche habitual.\n\n"
                "🔹 **/ping**\n"
                "↳ Verifique minha latência e receba uma resposta espirituosa sobre sua conexão lenta."
            ),
            color=0xff69b4
        )
        embed2.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed2.set_footer(text=f"Lira Amarinth 🌸 | Todos os GIFs são de anime! • Página 2/6")
        self.pages.append(embed2)

        # 3. Economia & RPG
        embed3 = discord.Embed(
            title="💰 Economia & RPG — Lira Amarinth",
            description=(
                "Meu sistema completo de moedas, XP e apostas para movimentar o chat.\n\n"
                "**COMANDOS:**\n"
                "🔹 **/daily**\n"
                "↳ Resgate seu bônus diário de Lunadóros para acumular riqueza.\n\n"
                "🔹 **/perfil** `[usuario]`\n"
                "↳ Veja seu nível atual, XP acumulado, saldo da carteira e conta bancária.\n\n"
                "🔹 **/ranking**\n"
                "↳ Veja o ranking global dos 5 usuários mais ricos do servidor.\n\n"
                "🔹 **/depositar** `quantia`\n"
                "↳ Guarde seus Lunadóros no banco para protegê-los de ladrões.\n\n"
                "🔹 **/sacar** `quantia`\n"
                "↳ Saque moedas do seu banco para a carteira.\n\n"
                "🔹 **/roubar** `usuario`\n"
                "↳ Tente roubar moedas da carteira de outro usuário (50% de chance de sucesso, mas cuidado para não ser multado!)."
            ),
            color=0xff69b4
        )
        embed3.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed3.set_footer(text=f"Lira Amarinth 🌸 | Todos os GIFs são de anime! • Página 3/6")
        self.pages.append(embed3)

        # 4. Ações & Social
        embed4 = discord.Embed(
            title="🎭 Ações & Social — Lira Amarinth",
            description=(
                "Comandos de interações dinâmicas, casamentos e o cálculo semanal de compatibilidade.\n\n"
                "**COMANDOS:**\n"
                "🔹 **/act** `acao` `[usuario]` `[mensagem]`\n"
                "↳ Hub principal de ações com GIF: abraçar, beijar, carinho, socar, tapa, dançar, chorar, rir, raiva, amar, morder, cutucar, aconchegar (+ mensagem opcional).\n\n"
                "🔹 **/ship** `[user1]` `[user1_id]` `[nome1]` `[user2]` `[user2_id]` `[nome2]` `[modo]`\n"
                "↳ Calcula o ship determinístico da semana entre dois alvos (membros, IDs ou texto) com barra de progresso e humor selecionável (Normal, Debochado ou Amoroso).\n\n"
                "🔹 **/casar** `usuario`\n"
                "↳ Peça o amor da sua vida em casamento! Cria um vínculo formal de casal no banco de dados.\n\n"
                "🔹 **/divorciar**\n"
                "↳ Termine seu relacionamento atual e volte a ficar solteiro (com a devida taxa dramática)."
            ),
            color=0xff69b4
        )
        embed4.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed4.set_footer(text=f"Lira Amarinth 🌸 | Todos os GIFs são de anime! • Página 4/6")
        self.pages.append(embed4)

        # 5. /act (único comando de GIF social)
        embed5 = discord.Embed(
            title="🎭 /act — Lira Amarinth",
            description=(
                "Ação com GIF anime (com ou sem alvo). Os grupos antigos `/interacao` e `/expressao` foram removidos.\n\n"
                "**Parâmetros:**\n"
                "• `acao` — abraçar, beijar, dançar, chorar, tapa, etc.\n"
                "• `usuario` — menção @ (opcional)\n"
                "• `usuario_nome` — nome se não estiver no servidor\n"
                "• `mensagem` — frase extra\n\n"
                "Sem `usuario`, vira expressão só sua (ex.: dançar sozinho)."
            ),
            color=0xff69b4
        )
        embed5.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed5.set_footer(text=f"Lira Amarinth 🌸 | Todos os GIFs são de anime! • Página 5/6")
        self.pages.append(embed5)

        # 6. Moderação & Admin
        embed7 = discord.Embed(
            title="🛡️ Moderação & Admin — Lira Amarinth",
            description=(
                "Comandos poderosos para gerenciar o servidor. Requerem as devidas permissões de moderador!\n\n"
                "**COMANDOS:**\n"
                "🔹 **/banir** `usuario` `[motivo]` | **/expulsar** `usuario` `[motivo]`\n"
                "↳ Bani ou expulsa um membro infrator do servidor.\n\n"
                "🔹 **/silenciar** `usuario` `tempo` `[motivo]` | **/dessilenciar** `usuario`\n"
                "↳ Silencia temporariamente um usuário para acalmar os ânimos.\n\n"
                "🔹 **/advertir** `usuario` `[motivo]` | **/avisos** `[usuario]`\n"
                "↳ Aplica uma advertência formal ou lista os avisos aplicados.\n\n"
                "🔹 **/remover_aviso** `usuario` `id_aviso` | **/limpar_avisos** `usuario`\n"
                "↳ Gerencia a remoção de advertências de um usuário.\n\n"
                "🔹 **/limpar** `quantidade`\n"
                "↳ Apaga rapidamente uma quantidade de mensagens recentes no canal.\n\n"
                "🔹 **/trancar** | **/destrancar**\n"
                "↳ Bloqueia ou desbloqueia o envio de mensagens no canal atual.\n\n"
                "🔹 **/lento** `segundos`\n"
                "↳ Configura o modo lento (slowmode) no canal para acalmar o chat.\n\n"
                "🔹 **/anunciar** `canal` `titulo` `mensagem`\n"
                "↳ Cria um anúncio oficial bonito em Embed no canal especificado.\n\n"
                "🔹 **/info_usuario** `[usuario]`\n"
                "↳ Exibe informações detalhadas de conta, cargos e histórico de um membro."
            ),
            color=0xff69b4
        )
        embed7.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed7.set_footer(text=f"Lira Amarinth 🌸 | Requer permissões adequadas • Página 6/6")
        self.pages.append(embed7)

    def _update_buttons(self):
        self.children[0].disabled = (self.current_page == 0)
        self.children[1].disabled = (self.current_page == 0)
        self.children[2].label = f"{self.current_page + 1}/{len(self.pages)}"
        self.children[3].disabled = (self.current_page == len(self.pages) - 1)
        self.children[4].disabled = (self.current_page == len(self.pages) - 1)

    @discord.ui.button(label="FIRST", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Você não pode interagir com este menu de ajuda! Use `/ajuda` você mesmo.", ephemeral=True)
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="PREVIOUS", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Você não pode interagir com este menu de ajuda! Use `/ajuda` você mesmo.", ephemeral=True)
        if self.current_page > 0:
            self.current_page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="1/7", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="NEXT", style=discord.ButtonStyle.success)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Você não pode interagir com este menu de ajuda! Use `/ajuda` você mesmo.", ephemeral=True)
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="LAST", style=discord.ButtonStyle.success)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Você não pode interagir com este menu de ajuda! Use `/ajuda` você mesmo.", ephemeral=True)
        self.current_page = len(self.pages) - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            if hasattr(self, "message") and self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ajuda", description="Veja todos os comandos da Lira 🌸")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ajuda(self, interaction: discord.Interaction):
        view = HelpView(self.bot, interaction.user.id)
        embed = view.pages[0]
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="help", description="See all Lira Amarinth's commands 🌸")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def help_cmd(self, interaction: discord.Interaction):
        await self.ajuda(interaction)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
