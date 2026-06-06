"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Tickets Inteligentes com IA                  ║
║  Atendimento 1ª Linha feito pela IA da Lira                 ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from ..constants import logger, EMOJI

TICKETS_FILE = os.path.join("data", "tickets.json")

def _load() -> dict:
    if os.path.exists(TICKETS_FILE):
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_tickets": {}} # channel_id -> user_id

def _save(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(TICKETS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistente

    @discord.ui.button(label="📩 Abrir Ticket", style=discord.ButtonStyle.primary, custom_id="lira_open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        # 1. Checar ou criar categoria de Tickets
        category = discord.utils.get(guild.categories, name="🎫 TICKETS")
        if not category:
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False)
                }
                category = await guild.create_category("🎫 TICKETS", overwrites=overwrites)
            except Exception as e:
                await interaction.response.send_message("❌ Erro ao criar categoria de tickets.", ephemeral=True)
                return

        # 2. Criar o canal privado
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Adicionar Mods na permissão (caso precise)
        # Por padrão, quem tem manage_channels ou admin já vê

        try:
            ticket_channel = await guild.create_text_channel(
                f"ticket-{user.name}",
                category=category,
                overwrites=overwrites
            )
        except Exception as e:
            await interaction.response.send_message("❌ Erro ao criar o canal do ticket.", ephemeral=True)
            return

        # 3. Salvar no banco de dados
        cog = interaction.client.get_cog("Tickets")
        if cog:
            cog._db["active_tickets"][str(ticket_channel.id)] = {
                "user_id": str(user.id),
                "ai_active": True
            }
            _save(cog._db)

        # 4. Enviar mensagem de boas vindas da IA no ticket
        embed = discord.Embed(
            title="🎫 Atendimento Iniciado!",
            description=(
                f"Olá {user.mention}! Eu sou a Lira, a assistente oficial daqui.\n\n"
                f"Você está falando diretamente comigo! Pode me dizer qual é a sua dúvida ou problema, e tentarei resolver.\n\n"
                f"Se eu não souber a resposta, basta clicar no botão abaixo para chamar os Moderadores Humanos."
            ),
            color=0xf5a3c7
        )
        
        view = TicketControlView()
        await ticket_channel.send(content=user.mention, embed=embed, view=view)
        await interaction.response.send_message(f"✅ Ticket criado em {ticket_channel.mention}!", ephemeral=True)
        logger.info(f"[TICKETS] {user.name} abriu o ticket {ticket_channel.name}")

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="👤 Chamar Moderadores", style=discord.ButtonStyle.secondary, custom_id="lira_ticket_staff")
    async def call_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Tickets")
        if not cog:
            return
            
        tid = str(interaction.channel_id)
        ticket_data = cog._db["active_tickets"].get(tid)
        
        if not ticket_data:
            await interaction.response.send_message("❌ Este ticket não está registrado no sistema.", ephemeral=True)
            return

        if not ticket_data.get("ai_active", True):
            await interaction.response.send_message("A staff já foi chamada!", ephemeral=True)
            return

        # Desativa a IA
        ticket_data["ai_active"] = False
        _save(cog._db)

        # Atualiza o botão para ficar desabilitado
        button.disabled = True
        await interaction.response.edit_message(view=self)

        await interaction.channel.send("🔔 **Atenção Moderadores!** O usuário solicitou atendimento humano. A IA foi desligada para este ticket.")
        logger.info(f"[TICKETS] IA desligada e staff chamada no ticket {interaction.channel.name}")

    @discord.ui.button(label="🔒 Fechar Ticket", style=discord.ButtonStyle.danger, custom_id="lira_ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Tickets")
        if cog:
            tid = str(interaction.channel_id)
            if tid in cog._db["active_tickets"]:
                del cog._db["active_tickets"][tid]
                _save(cog._db)
        
        await interaction.response.send_message("🔒 Fechando o ticket em 5 segundos...")
        await __import__('asyncio').sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass


class Tickets(commands.Cog):
    """Sistema de Tickets avançado com inteligência artificial."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._db = _load()
        # Registra a view persistente (para o bot lembrar do botão após reiniciar)
        self.bot.add_view(TicketView())
        self.bot.add_view(TicketControlView())

    @commands.command(name="ticket-setup", description="Envia o painel de Tickets neste canal (Apenas Admins)")
    @commands.has_permissions(administrator=True)
    async def setup_ticket(self, ctx: commands.Context):
        embed = discord.Embed(
            title="💌 Suporte e Atendimento",
            description="Precisa de ajuda com alguma coisa? Clique no botão abaixo para abrir um ticket de suporte.\n\nEu (Lira) vou te atender primeiro e tentar resolver rapidinho! ✨",
            color=0xf5a3c7
        )
        embed.set_footer(text="Não abra tickets sem motivo!")
        
        await ctx.send(embed=embed, view=TicketView())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Verifica se estamos em um canal de ticket ativo
        tid = str(message.channel.id)
        ticket_data = self._db["active_tickets"].get(tid)
        
        if ticket_data and ticket_data.get("ai_active", True):
            # A IA está ativa neste ticket! Devemos responder.
            # Usa o ChatCog para gerar a resposta
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog:
                async with message.channel.typing():
                    try:
                        # Adiciona um prompt contextual para o ticket
                        contexto_ticket = f"[SISTEMA: O usuário está no canal de suporte de ticket. Ele precisa de ajuda oficial. Resolva a dúvida dele da melhor forma possível, sendo educada. Se não souber a resposta exata, avise-o que ele pode clicar em 'Chamar Moderadores'.]\n"
                        resp = await chat_cog._responder(contexto_ticket + message.content, message.author.display_name)
                        
                        import re
                        response_limpa = re.sub(r'\[[^\]]+\]', '', resp)
                        response_limpa = re.sub(r'\{[^\}]+\}', '', response_limpa)
                        response_limpa = re.sub(r'</?[a-zA-Z_][a-zA-Z0-9_-]*(?:\s+[^>]*)?>', '', response_limpa)
                        
                        if not response_limpa.strip():
                            response_limpa = "Hmm..."
                            
                        await message.reply(response_limpa[:2000])
                    except Exception as e:
                        logger.error(f"[TICKETS] Erro ao responder via IA no ticket: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
    logger.info("[DISCORD] ✅ Cog Tickets carregada")
