import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
import random
from ..constants import EMOJI
from src.modules.gamification import lira_gamification

# Mapeamento categoria nekos.best → termos de busca Giphy/Tenor (fallback)
SEARCH_TERMS = {
    "hug":       "anime hug",
    "kiss":      "anime kiss",
    "pat":       "anime head pat",
    "slap":      "anime slap",
    "bite":      "anime bite",
    "cuddle":    "anime cuddle",
    "feed":      "anime feeding",
    "handhold":  "anime holding hands",
    "highfive":  "anime high five",
    "kick":      "anime kick",
    "peck":      "anime peck kiss",
    "poke":      "anime poke",
    "punch":     "anime punch",
    "tickle":    "anime tickle",
    "wave":      "anime wave",
    "yeet":      "anime yeet throw",
    "baka":      "anime baka",
    "nom":       "anime nom",
    # Próprias (sem alvo)
    "blush":     "anime blush",
    "bored":     "anime bored",
    "cry":       "anime cry",
    "dance":     "anime dance",
    "facepalm":  "anime facepalm",
    "laugh":     "anime laugh",
    "nod":       "anime nod",
    "nope":      "anime no",
    "pout":      "anime pout",
    "run":       "anime running",
    "sad":       "anime sad",
    "shrug":     "anime shrug",
    "sleep":     "anime sleeping",
    "smile":     "anime smile",
    "smug":      "anime smug",
    "stare":     "anime stare",
    "think":     "anime thinking",
    "thumbsup":  "anime thumbs up",
    "wink":      "anime wink",
    "yawn":      "anime yawn",
}


# ── Funções de Fetch com Fallback ─────────────────────────────────────────────

async def _from_nekos(session: aiohttp.ClientSession, category: str) -> str | None:
    try:
        async with session.get(
            f"https://nekos.best/api/v2/{category}",
            timeout=aiohttp.ClientTimeout(total=4)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["results"][0]["url"]
    except Exception:
        pass
    return None


async def _from_giphy(session: aiohttp.ClientSession, category: str) -> str | None:
    api_key = os.getenv("GIPHY_API_KEY", "dc6zaTOxFJmzC")
    query = SEARCH_TERMS.get(category, f"anime {category}")
    try:
        async with session.get(
            "https://api.giphy.com/v1/gifs/search",
            params={"api_key": api_key, "q": query, "limit": 20, "rating": "pg-13"},
            timeout=aiohttp.ClientTimeout(total=4)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("data", [])
                if results:
                    return random.choice(results)["images"]["original"]["url"]
    except Exception:
        pass
    return None


async def _from_tenor(session: aiohttp.ClientSession, category: str) -> str | None:
    api_key = os.getenv("TENOR_API_KEY")
    if not api_key:
        return None
    query = SEARCH_TERMS.get(category, f"anime {category}")
    try:
        async with session.get(
            "https://tenor.googleapis.com/v2/search",
            params={"q": query, "key": api_key, "limit": 20, "media_filter": "gif"},
            timeout=aiohttp.ClientTimeout(total=4)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("results", [])
                if results:
                    item = random.choice(results)
                    return item["media_formats"]["gif"]["url"]
    except Exception:
        pass
    return None


async def fetch_gif(category: str) -> str | None:
    """Busca GIF com fallback: nekos.best → Giphy → Tenor."""
    async with aiohttp.ClientSession() as session:
        return (
            await _from_nekos(session, category)
            or await _from_giphy(session, category)
            or await _from_tenor(session, category)
        )


# ── View de Casamento ─────────────────────────────────────────────────────────

class MarriageView(discord.ui.View):
    def __init__(self, proposer, target):
        super().__init__(timeout=60)
        self.proposer = proposer
        self.target = target

    @discord.ui.button(label="Aceito! ❤️", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target:
            return await interaction.response.send_message("Este pedido não é para você!", ephemeral=True)
        success = lira_gamification.marry(str(self.proposer.id), str(self.target.id), "discord")
        if success:
            gif_url = await fetch_gif("kiss")
            embed = discord.Embed(
                title="💍 NOVO CASAL!",
                description=f"✨ **{self.target.display_name}** aceitou o pedido de **{self.proposer.display_name}**!\nFelicidades ao casal! 🎉",
                color=0xff69b4
            )
            if gif_url:
                embed.set_image(url=gif_url)
            await interaction.response.edit_message(content=None, embed=embed, view=None)
        else:
            await interaction.response.send_message("Um de vocês já está casado! 💔", ephemeral=True)

    @discord.ui.button(label="Recusar 💔", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target:
            return await interaction.response.send_message("Este pedido não é para você!", ephemeral=True)
        await interaction.response.edit_message(
            content=f"💔 **{self.proposer.mention}**, seu pedido foi recusado...",
            embed=None, view=None
        )


# ── Cog ───────────────────────────────────────────────────────────────────────

class SocialCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _react(self, interaction, usuario, category, emoji, texto, color=0xff69b4):
        """Helper: busca GIF e manda embed de reação com alvo."""
        await interaction.response.defer()
        gif_url = await fetch_gif(category)
        embed = discord.Embed(
            description=f"{emoji} **{interaction.user.display_name}** {texto} **{usuario.display_name}**!",
            color=color
        )
        if gif_url:
            embed.set_image(url=gif_url)
        else:
            embed.set_footer(text="(GIF indisponível no momento)")
        await interaction.followup.send(embed=embed)

    async def _react_self(self, interaction, category, emoji, texto, color=0x9b59b6):
        """Helper: reação sem alvo (própria expressão)."""
        await interaction.response.defer()
        gif_url = await fetch_gif(category)
        embed = discord.Embed(
            description=f"{emoji} **{interaction.user.display_name}** {texto}",
            color=color
        )
        if gif_url:
            embed.set_image(url=gif_url)
        else:
            embed.set_footer(text="(GIF indisponível no momento)")
        await interaction.followup.send(embed=embed)

    # ── Casamento ──────────────────────────────────────────────────────────────

    @app_commands.command(name="casar", description="Peça alguém em casamento! 💍")
    @app_commands.describe(usuario="Quem é o amor da sua vida?")
    async def casar(self, interaction: discord.Interaction, usuario: discord.Member):
        if usuario == interaction.user:
            return await interaction.response.send_message("Você não pode casar consigo mesmo!", ephemeral=True)
        if usuario.bot:
            return await interaction.response.send_message("Você não pode casar com um bot!", ephemeral=True)
        if lira_gamification.get_marriage(str(interaction.user.id), "discord"):
            return await interaction.response.send_message("Você já está casado! 💍", ephemeral=True)
        if lira_gamification.get_marriage(str(usuario.id), "discord"):
            return await interaction.response.send_message(f"**{usuario.display_name}** já está casado(a)! 💔", ephemeral=True)
        view = MarriageView(interaction.user, usuario)
        await interaction.response.send_message(
            content=f"💍 {usuario.mention}, **{interaction.user.display_name}** está te pedindo em casamento! Você aceita?",
            view=view
        )

    @app_commands.command(name="divorciar", description="Termine seu casamento atual 💔")
    async def divorciar(self, interaction: discord.Interaction):
        success = lira_gamification.divorce(str(interaction.user.id), "discord")
        if success:
            await interaction.response.send_message("💔 Você agora está solteiro(a)...")
        else:
            await interaction.response.send_message("Você não está casado com ninguém!", ephemeral=True)

    # ── Interações com Alvo ────────────────────────────────────────────────────

    @app_commands.command(name="abracar", description="Dê um abraço apertado 🫂")
    @app_commands.describe(usuario="Quem você quer abraçar?")
    async def abracar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "hug", "🫂", "deu um abraço carinhoso em")

    @app_commands.command(name="beijar", description="Dê um beijo 💋")
    @app_commands.describe(usuario="Quem você quer beijar?")
    async def beijar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "kiss", "💋", "beijou")

    @app_commands.command(name="cafune", description="Faça um cafuné 🌸")
    @app_commands.describe(usuario="Em quem você quer fazer cafuné?")
    async def cafune(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "pat", "🌸", "fez cafuné em")

    @app_commands.command(name="tapa", description="Dê um tapa 🖐️")
    @app_commands.describe(usuario="Quem merece um tapa?")
    async def tapa(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "slap", "🖐️", "deu um tapa em", color=0xff4444)

    @app_commands.command(name="morder", description="Dê uma mordidinha 🦷")
    @app_commands.describe(usuario="Quem você quer morder?")
    async def morder(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "bite", "🦷", "mordeu")

    @app_commands.command(name="aconchegar", description="Aconchegue alguém 🥰")
    @app_commands.describe(usuario="Com quem você quer se aconchegar?")
    async def aconchegar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "cuddle", "🥰", "se aconchegou com")

    @app_commands.command(name="alimentar", description="Alimente alguém 🍱")
    @app_commands.describe(usuario="Quem você quer alimentar?")
    async def alimentar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "feed", "🍱", "alimentou")

    @app_commands.command(name="mao", description="Segure a mão de alguém 🤝")
    @app_commands.describe(usuario="De quem você quer segurar a mão?")
    async def mao(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "handhold", "🤝", "segurou a mão de")

    @app_commands.command(name="highfive", description="Dê um high-five! ✋")
    @app_commands.describe(usuario="Com quem você quer dar um high-five?")
    async def highfive(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "highfive", "✋", "deu um high-five em")

    @app_commands.command(name="chutar", description="Dê um chute 🦵")
    @app_commands.describe(usuario="Quem você quer chutar?")
    async def chutar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "kick", "🦵", "chutou", color=0xff4444)

    @app_commands.command(name="beijo_rapido", description="Dê um beijinho rápido 😘")
    @app_commands.describe(usuario="Quem você quer dar um beijinho?")
    async def beijo_rapido(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "peck", "😘", "deu um beijinho em")

    @app_commands.command(name="cutucar", description="Cutuque alguém 👉")
    @app_commands.describe(usuario="Quem você quer cutucar?")
    async def cutucar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "poke", "👉", "cutucou")

    @app_commands.command(name="socar", description="Dê um soco 🥊")
    @app_commands.describe(usuario="Quem merece um soco?")
    async def socar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "punch", "🥊", "socou", color=0xff4444)

    @app_commands.command(name="cócegas", description="Faça cócegas em alguém 🤣")
    @app_commands.describe(usuario="Quem você quer fazer cócegas?")
    async def cocegas(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "tickle", "🤣", "fez cócegas em")

    @app_commands.command(name="acenar", description="Acene para alguém 👋")
    @app_commands.describe(usuario="Para quem você quer acenar?")
    async def acenar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "wave", "👋", "aceneu para")

    @app_commands.command(name="arremessar", description="Arremesse alguém para longe 🌀")
    @app_commands.describe(usuario="Quem você quer arremessar?")
    async def arremessar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "yeet", "🌀", "arremessou", color=0x3498db)

    @app_commands.command(name="comer", description="Coma alguém 😋")
    @app_commands.describe(usuario="Quem você quer comer?")
    async def comer(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "nom", "😋", "comeu")

    @app_commands.command(name="xingar", description="Chame alguém de baka 😤")
    @app_commands.describe(usuario="Quem é o baka?")
    async def xingar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "baka", "😤", "chamou de baka", color=0xe67e22)

    @app_commands.command(name="olhar", description="Fique encarando alguém 👀")
    @app_commands.describe(usuario="Quem você está encarando?")
    async def olhar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "stare", "👀", "ficou encarando")

    @app_commands.command(name="matar", description="Mate alguém dramaticamente ⚔️")
    @app_commands.describe(usuario="Quem você quer matar?")
    async def matar(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "kill", "⚔️", "matou", color=0x2c2c2c)

    @app_commands.command(name="apertar_mao", description="Aperte a mão de alguém 🤝")
    @app_commands.describe(usuario="Com quem você quer apertar a mão?")
    async def apertar_mao(self, interaction: discord.Interaction, usuario: discord.Member):
        await self._react(interaction, usuario, "handshake", "🤝", "apertou a mão de")

    # ── Reações Próprias (sem alvo) ────────────────────────────────────────────

    @app_commands.command(name="corar", description="Cora de vergonha 😳")
    async def corar(self, interaction: discord.Interaction):
        await self._react_self(interaction, "blush", "😳", "está corando!")

    @app_commands.command(name="entediado", description="Mostre que está entediado 😒")
    async def entediado(self, interaction: discord.Interaction):
        await self._react_self(interaction, "bored", "😒", "está entediado(a)...")

    @app_commands.command(name="chorar", description="Chore 😭")
    async def chorar(self, interaction: discord.Interaction):
        await self._react_self(interaction, "cry", "😭", "está chorando...")

    @app_commands.command(name="dançar", description="Dance! 💃")
    async def dancar(self, interaction: discord.Interaction):
        await self._react_self(interaction, "dance", "💃", "está dançando!")

    @app_commands.command(name="facepalm", description="Facepalm 🤦")
    async def facepalm(self, interaction: discord.Interaction):
        await self._react_self(interaction, "facepalm", "🤦", "não acredita no que aconteceu...")

    @app_commands.command(name="rir", description="Gargalhe 😂")
    async def rir(self, interaction: discord.Interaction):
        await self._react_self(interaction, "laugh", "😂", "está rindo muito!")

    @app_commands.command(name="concordar", description="Concorde com a cabeça 😌")
    async def concordar(self, interaction: discord.Interaction):
        await self._react_self(interaction, "nod", "😌", "está concordando")

    @app_commands.command(name="recusar", description="Recuse com a cabeça 🙅")
    async def recusar_cabeca(self, interaction: discord.Interaction):
        await self._react_self(interaction, "nope", "🙅", "está recusando")

    @app_commands.command(name="fazer_bico", description="Faça bico 😤")
    async def fazer_bico(self, interaction: discord.Interaction):
        await self._react_self(interaction, "pout", "😤", "está fazendo bico")

    @app_commands.command(name="correr", description="Corra! 🏃")
    async def correr(self, interaction: discord.Interaction):
        await self._react_self(interaction, "run", "🏃", "está correndo!")

    @app_commands.command(name="triste", description="Mostre que está triste 😢")
    async def triste(self, interaction: discord.Interaction):
        await self._react_self(interaction, "sad", "😢", "está triste...")

    @app_commands.command(name="dar_de_ombros", description="Dê de ombros 🤷")
    async def dar_de_ombros(self, interaction: discord.Interaction):
        await self._react_self(interaction, "shrug", "🤷", "não sabe o que dizer")

    @app_commands.command(name="dormir", description="Durma! 😴")
    async def dormir(self, interaction: discord.Interaction):
        await self._react_self(interaction, "sleep", "😴", "foi dormir... boa noite!")

    @app_commands.command(name="sorrir", description="Sorria 😊")
    async def sorrir(self, interaction: discord.Interaction):
        await self._react_self(interaction, "smile", "😊", "está sorrindo!")

    @app_commands.command(name="satisfeito", description="Fique satisfeito(a) 😏")
    async def satisfeito(self, interaction: discord.Interaction):
        await self._react_self(interaction, "smug", "😏", "está satisfeito(a)")

    @app_commands.command(name="pensar", description="Pense profundamente 🤔")
    async def pensar(self, interaction: discord.Interaction):
        await self._react_self(interaction, "think", "🤔", "está pensando...")

    @app_commands.command(name="joinha", description="Dê um joinha 👍")
    async def joinha(self, interaction: discord.Interaction):
        await self._react_self(interaction, "thumbsup", "👍", "aprova!")

    @app_commands.command(name="piscar", description="Pisce o olho 😉")
    async def piscar(self, interaction: discord.Interaction):
        await self._react_self(interaction, "wink", "😉", "está piscando!")

    @app_commands.command(name="bocejar", description="Boceje 🥱")
    async def bocejar(self, interaction: discord.Interaction):
        await self._react_self(interaction, "yawn", "🥱", "está com sono...")

    @app_commands.command(name="feliz", description="Mostre que está feliz! 😄")
    async def feliz(self, interaction: discord.Interaction):
        await self._react_self(interaction, "happy", "😄", "está feliz!")

    @app_commands.command(name="espreitar", description="Espreitando por aí 👁️")
    async def espreitar(self, interaction: discord.Interaction):
        await self._react_self(interaction, "lurk", "👁️", "está espiando...")


async def setup(bot):
    await bot.add_cog(SocialCog(bot))
