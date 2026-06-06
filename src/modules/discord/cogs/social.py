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
    "kill":      "anime defeat",
    "love":      "anime love",
    "happy":     "anime happy",
    "lurk":      "anime peek",
    "handshake": "anime handshake",
}


# Catálogo único (/act) — máx. 25 opções (limite Discord)
ACT_CATALOG: dict[str, dict] = {
    "abracar": {"label": "🤗 abraçar", "category": "hug", "emoji": "🤗", "texto_com": "deu um abraço apertado em", "texto_sem": "está carente e quer um abraço!"},
    "beijar": {"label": "😘 beijar", "category": "kiss", "emoji": "😘", "texto_com": "deu um beijo em", "texto_sem": "mandou um beijo carinhoso no ar!"},
    "fazer_carinho": {"label": "👋 carinho", "category": "pat", "emoji": "👋", "texto_com": "fez um carinho fofo na cabeça de", "texto_sem": "está fazendo carinho em si mesmo... fofo!"},
    "socar": {"label": "👊 socar", "category": "punch", "emoji": "👊", "texto_com": "deu um soco certeiro em", "texto_sem": "está dando socos no ar para treinar!"},
    "dar_tapa": {"label": "👏 tapa", "category": "slap", "emoji": "👏", "texto_com": "deu um tapa estalado em", "texto_sem": "deu um tapa na própria testa! Que vacilo..."},
    "aconchegar": {"label": "💜 aconchegar", "category": "cuddle", "emoji": "💜", "texto_com": "se aconchegou quentinho em", "texto_sem": "se encolheu debaixo das cobertas!"},
    "morder": {"label": "🦷 morder", "category": "bite", "emoji": "🦷", "texto_com": "deu uma mordidinha em", "texto_sem": "está se mordendo de raiva e ciúmes!"},
    "cutucar": {"label": "👉 cutucar", "category": "poke", "emoji": "👉", "texto_com": "cutucou chativamente", "texto_sem": "está cutucando o próprio dedo por tédio..."},
    "alimentar": {"label": "🍱 alimentar", "category": "feed", "emoji": "🍱", "texto_com": "alimentou", "texto_sem": "está com fome..."},
    "highfive": {"label": "✋ high-five", "category": "highfive", "emoji": "✋", "texto_com": "deu um high-five em", "texto_sem": "levantou a mão pro alto!"},
    "chutar": {"label": "🦵 chutar", "category": "kick", "emoji": "🦵", "texto_com": "chutou", "texto_sem": "está chutando o ar!"},
    "cocegas": {"label": "🤣 cócegas", "category": "tickle", "emoji": "🤣", "texto_com": "fez cócegas em", "texto_sem": "está se coçando..."},
    "acenar": {"label": "👋 acenar", "category": "wave", "emoji": "👋", "texto_com": "acenou para", "texto_sem": "acenou para ninguém em particular."},
    "arremessar": {"label": "🌀 arremessar", "category": "yeet", "emoji": "🌀", "texto_com": "arremessou", "texto_sem": "se jogou no sofá."},
    "xingar": {"label": "😤 baka", "category": "baka", "emoji": "😤", "texto_com": "chamou de baka", "texto_sem": "está xingando o vento."},
    "olhar": {"label": "👀 encarar", "category": "stare", "emoji": "👀", "texto_com": "ficou encarando", "texto_sem": "está encarando a parede."},
    "dancar": {"label": "💃 dançar", "category": "dance", "emoji": "💃", "texto_com": "está dançando com", "texto_sem": "está dançando e comemorando a vida!"},
    "chorar": {"label": "😭 chorar", "category": "cry", "emoji": "😭", "texto_com": "está chorando no ombro de", "texto_sem": "desabou a chorar dramaticamente... 😭"},
    "rir": {"label": "😂 rir", "category": "laugh", "emoji": "😂", "texto_com": "está rindo da cara de", "texto_sem": "começou a gargalhar do nada!"},
    "ficar_com_raiva": {"label": "😠 raiva", "category": "pout", "emoji": "😠", "texto_com": "está bufando de raiva de", "texto_sem": "está com raiva e fazendo bico! 😤"},
    "amar": {"label": "💕 amar", "category": "love", "emoji": "💕", "texto_com": "declarou todo o seu amor por", "texto_sem": "está com o coração transbordando de amor!"},
    "corar": {"label": "😳 corar", "category": "blush", "emoji": "😳", "texto_com": "fez corar", "texto_sem": "está corando de vergonha!"},
    "facepalm": {"label": "🤦 facepalm", "category": "facepalm", "emoji": "🤦", "texto_com": "deu facepalm por causa de", "texto_sem": "não acredita no que aconteceu..."},
    "pensar": {"label": "🤔 pensar", "category": "think", "emoji": "🤔", "texto_com": "está pensando em", "texto_sem": "está pensando profundamente..."},
    "dormir": {"label": "😴 dormir", "category": "sleep", "emoji": "😴", "texto_com": "mandou dormir", "texto_sem": "foi dormir... boa noite!"},
}


def _act_choice_list() -> list[app_commands.Choice[str]]:
    return [app_commands.Choice(name=m["label"], value=k) for k, m in ACT_CATALOG.items()]


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


from ..slash_meta import USER_APP_CONTEXT, USER_APP_INSTALL

_SOCIAL_INSTALL = USER_APP_INSTALL
_SOCIAL_CONTEXT = USER_APP_CONTEXT


def _display_name(user: discord.abc.User | None, fallback: str | None = None) -> str | None:
    if user:
        return getattr(user, "display_name", None) or getattr(user, "name", None) or str(user)
    if fallback and fallback.strip():
        return fallback.strip()
    return None


# ── Cog ───────────────────────────────────────────────────────────────────────

class SocialCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Casamento ──────────────────────────────────────────────────────────────

    @app_commands.command(name="casar", description="Peça alguém em casamento! 💍")
    @_SOCIAL_CONTEXT
    @_SOCIAL_INSTALL
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
    @_SOCIAL_CONTEXT
    @_SOCIAL_INSTALL
    async def divorciar(self, interaction: discord.Interaction):
        success = lira_gamification.divorce(str(interaction.user.id), "discord")
        if success:
            await interaction.response.send_message("💔 Você agora está solteiro(a)...")
        else:
            await interaction.response.send_message("Você não está casado com ninguém!", ephemeral=True)


    @app_commands.command(name="act", description="Realize uma ação dramática ou expresse um sentimento! 🎭")
    @app_commands.describe(
        acao="Escolha o tipo de ação",
        usuario="Membro do servidor (escolha na lista @menção)",
        usuario_nome="Ou digite o apelido, se não achar na lista",
        mensagem="Mensagem personalizada para acompanhar a ação (opcional)",
    )
    @app_commands.choices(acao=_act_choice_list())
    @_SOCIAL_CONTEXT
    @_SOCIAL_INSTALL
    async def act(
        self,
        interaction: discord.Interaction,
        acao: str,
        usuario: discord.User = None,
        usuario_nome: str = None,
        mensagem: str = None,
    ):
        info = ACT_CATALOG.get(acao)
        if not info:
            return await interaction.response.send_message("Ação inválida!", ephemeral=True)

        alvo = _display_name(usuario, usuario_nome)
        if usuario_nome and not usuario and not alvo:
            return await interaction.response.send_message(
                "❌ Não entendi o nome. Tenta de novo ou escolhe o usuário na lista @menção.",
                ephemeral=True,
            )

        category = info["category"]
        emoji = info["emoji"]

        await interaction.response.defer()
        gif_url = await fetch_gif(category)

        if alvo:
            texto_final = f"{emoji} **{interaction.user.display_name}** {info['texto_com']} **{alvo}**!"
        else:
            # Reação própria
            texto_final = f"{emoji} **{interaction.user.display_name}** {info['texto_sem']}"
            
        if mensagem:
            # Sanitiza a mensagem para evitar menções e formatações quebradas
            msg_clean = discord.utils.escape_markdown(mensagem)
            texto_final += f"\n\n*\" {msg_clean} \"*"
            
        embed = discord.Embed(description=texto_final, color=0xff69b4)
        if gif_url:
            embed.set_image(url=gif_url)
        else:
            embed.set_footer(text="(GIF indisponível no momento)")
            
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ship", description="Calcula o ship semanal entre usuários, IDs ou nomes ❤️")
    @app_commands.describe(
        user1="Primeiro usuário do ship (opcional)",
        user1_id="ID Discord manual do primeiro lado (opcional)",
        nome1="Nome manual do primeiro lado (opcional)",
        user2="Segundo usuário do ship (opcional)",
        user2_id="ID Discord manual do segundo lado (opcional)",
        nome2="Nome manual do segundo lado (opcional)",
        modo="Estilo textual do resultado (opcional)"
    )
    @app_commands.choices(modo=[
        app_commands.Choice(name="Normal 😐", value="normal"),
        app_commands.Choice(name="Debochado 😏", value="debochado"),
        app_commands.Choice(name="Amoroso 💕", value="amoroso"),
    ])
    @_SOCIAL_CONTEXT
    @_SOCIAL_INSTALL
    async def ship(
        self,
        interaction: discord.Interaction,
        user1: discord.Member = None,
        user1_id: str = None,
        nome1: str = None,
        user2: discord.Member = None,
        user2_id: str = None,
        nome2: str = None,
        modo: str = "debochado"
    ):
        # Resolver Lado 1
        if user1:
            name1 = user1.display_name
            id1 = str(user1.id)
        elif user1_id:
            name1 = f"<@{user1_id}>"
            id1 = user1_id
        elif nome1:
            name1 = nome1
            id1 = nome1.lower()
        else:
            name1 = interaction.user.display_name
            id1 = str(interaction.user.id)

        # Resolver Lado 2
        if user2:
            name2 = user2.display_name
            id2 = str(user2.id)
        elif user2_id:
            name2 = f"<@{user2_id}>"
            id2 = user2_id
        elif nome2:
            name2 = nome2
            id2 = nome2.lower()
        else:
            return await interaction.response.send_message("❌ Você precisa preencher o segundo lado do ship! Especifique um usuário, ID ou nome.", ephemeral=True)

        if id1 == id2:
            return await interaction.response.send_message("❌ Shippar a si mesmo ou a mesma entidade? Um pouco de amor próprio é bom, mas vamos manter o senso!", ephemeral=True)

        await interaction.response.defer()

        # Cálculo determinístico semanal
        import datetime
        import hashlib
        year, week_num, _ = datetime.date.today().isocalendar()
        week_id = f"{year}-{week_num}"
        sorted_ids = sorted([id1, id2])
        combined = f"{sorted_ids[0]}:{sorted_ids[1]}:{week_id}"
        hash_val = hashlib.sha256(combined.encode('utf-8')).hexdigest()
        percentage = int(hash_val, 16) % 101

        # Barra de progresso customizada
        filled = round(percentage / 10)
        bar = "❤️" * filled + "🖤" * (10 - filled)

        # Comentários por categoria
        COMENTARIOS = {
            "debochado": [
                (20, "Horrível. Recomendo distância imediata de pelo menos 5 quilômetros antes que vire caso de polícia. 🤮"),
                (40, "Amizade (e olhe lá). Um querendo a alma do outro, mas sem coragem ou inteligência para admitir. 😒"),
                (60, "Morno. Talvez depois de 5 copos de suco de uva e um empurrãozinho de um cupido bêbado dê alguma coisa. 🥴"),
                (80, "Fofinho. Lira quase sente um vestígio de simpatia humana por vocês. Quase. 🌸"),
                (100, "Casal Perfeito! Prontos para assinar o divórcio amigável daqui a 3 meses. Mentira, muito amor! 💍💕")
            ],
            "amoroso": [
                (20, "Um começo difícil, mas com paciência e carinho, todo amor pode florescer! 🌱"),
                (40, "A amizade de vocês é linda! Quem sabe um dia não se transforma em algo ainda maior? ✨"),
                (60, "Vocês têm uma conexão super gostosa! O destino está de olho em vocês dois... 👀💖"),
                (80, "Muito amor envolvido! Vocês se complementam de uma forma linda e aconchegante! 🌸"),
                (100, "Almas Gêmeas! O universo inteiro conspira a favor da felicidade desse casal lindo! 💍💕")
            ],
            "normal": [
                (20, "Compatibilidade baixa. O santo de vocês simplesmente não bateu. ❌"),
                (40, "Uma relação neutra. Funcionam muito bem como amigos ou colegas de trabalho. 👍"),
                (60, "Compatibilidade razoável. Existe potencial se ambos estiverem dispostos a investir. ⚖️"),
                (80, "Compatibilidade alta! Uma ótima dupla com excelente entrosamento no dia a dia. 🎉"),
                (100, "Compatibilidade excelente! Uma conexão rara e extremamente harmônica. 🏆")
            ]
        }

        # Obter comentário correto
        comentario_lista = COMENTARIOS.get(modo, COMENTARIOS["debochado"])
        comentario_final = ""
        for limite, texto in comentario_lista:
            if percentage <= limite:
                comentario_final = texto
                break

        embed = discord.Embed(
            title="❤️ CÁLCULO DE SHIP SEMANAL ❤️",
            description=f"Calculando a afinidade cósmica para esta semana...\n\n**{name1}** & **{name2}**\n\n`{bar}` **{percentage}%**\n\n**Opinião da Lira:**\n*{comentario_final}*",
            color=0xff69b4 if percentage >= 50 else 0x95a5a6
        )
        embed.set_footer(text=f"Afinidade calculada para a semana {week_num} de {year} 🌸")
        
        # Opcional: Adicionar um GIF romântico se der match alto, ou triste se der match baixo!
        if percentage >= 70:
            gif_url = await fetch_gif("cuddle")
            if gif_url:
                embed.set_image(url=gif_url)
        elif percentage <= 20:
            gif_url = await fetch_gif("cry")
            if gif_url:
                embed.set_image(url=gif_url)

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(SocialCog(bot))
