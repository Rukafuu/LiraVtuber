import os
import re
import sys
import asyncio
import logging

try:
    import discord
    from discord import app_commands
    from discord.ext import commands
except ImportError:
    print("A biblioteca 'discord.py' não está instalada. Execute: pip install discord.py")
    sys.exit(1)

from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.config.config_loader import CONFIG
from src.providers.provider_selector import ProviderSelector
from src.memory.memory_manager import LiraMemoryManager
from src.core.prompt_builder import build_gui_system_prompt
from src.modules.gamification import lira_gamification
from src.modules.games import lira_games
from src.modules.automod import lira_automod
from src.modules.vision.image_gen import LiraImageGen
from src.utils.profile_card import generate_profile_card
import random

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("HanaDiscordBot")

THINKING_MSG = "Deixa eu pensar... 🌸"

llm_selector = ProviderSelector()
memory_manager = LiraMemoryManager()
image_gen = LiraImageGen()
active_hangmans = {}


async def _responder(texto_usuario: str, author_name: str) -> str:
    """Lógica central de resposta da Hana para o Discord."""
    prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get("openrouter", {})
    model_id = prov_cfg.get("modelo_chat", "openrouter/owl-alpha")
    temperature = CONFIG.get("LLM_TEMPERATURE", 0.85)

    logger.info(f"[DISCORD] Recebido de {author_name}: {texto_usuario}")

    system_prompt = build_gui_system_prompt(
        task_type="chat_normal",
        memory_context=(
            "Canal: Discord. Use a formatação nativa do Discord nas suas respostas quando fizer sentido:\n"
            "- **negrito** para ênfase\n"
            "- *itálico* para tom suave ou pensativo\n"
            "- ||spoiler|| para revelar algo de forma lúdica\n"
            "> citação para destacar algo importante\n"
            "- `código` ou ```bloco de código``` para trechos técnicos\n"
            "- ~~tachado~~ para humor ou correções\n"
            "Use essas formatações com naturalidade, não em excesso."
        ),
        request_context={"channel": "discord", "response_mode": "long", "markdown_enabled": True},
        attachments_overview="Nenhum anexo na mensagem atual."
    )
    system_prompt += "\nSe o usuário pedir para você desenhar algo, use a tag [GEN_IMAGE: descrição detalhada em inglês] no final da sua resposta."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Mensagem do Discord enviada por {author_name}: {texto_usuario}"}
    ]

    provider = llm_selector.get_provider("openrouter")
    resposta = await asyncio.to_thread(provider._chamar_api, model_id, messages)
    response_text = resposta.choices[0].message.content or ""

    clean = re.sub(r'\[EMOTION:.*?\]', '', response_text, flags=re.IGNORECASE)
    clean = re.sub(r'\[PARAM:.*?\]', '', clean, flags=re.IGNORECASE)
    return clean.strip()


async def _enviar_resposta_longa(resposta_msg, canal, clean: str):
    if len(clean) <= 2000:
        await resposta_msg.edit(content=clean)
    else:
        await resposta_msg.edit(content=clean[:2000])
        for chunk in [clean[i:i+2000] for i in range(2000, len(clean), 2000)]:
            await canal.send(chunk)


async def _responder_com_thinking(destination, text: str, author_name: str, quoted_msg=None):
    """Envia o 'pensando...' e edita com a resposta final, com suporte a imagem."""
    thinking_msg = await destination.send(THINKING_MSG)
    try:
        response = await _responder(text, author_name)

        match_img = re.search(r'\[GEN_IMAGE:\s*(.*?)\]', response, flags=re.IGNORECASE)
        image_file = None
        if match_img:
            prompt_art = match_img.group(1)
            path = await asyncio.to_thread(image_gen.generate, prompt_art)
            if path:
                image_file = discord.File(path, filename="hana_art.png")

        clean_text = re.sub(r'\[EMOTION:.*?\]', '', response, flags=re.IGNORECASE)
        clean_text = re.sub(r'\[GEN_IMAGE:.*?\]', '', clean_text, flags=re.IGNORECASE).strip()

        if len(clean_text) <= 2000:
            await thinking_msg.edit(content=clean_text)
        else:
            await thinking_msg.edit(content=clean_text[:2000])
            for chunk in [clean_text[i:i+2000] for i in range(2000, len(clean_text), 2000)]:
                await destination.send(chunk)

        if image_file:
            await destination.send(file=image_file)
    except Exception as e:
        logger.error(f"[DISCORD] Erro ao responder: {e}")
        await thinking_msg.edit(content="Eita, tive um probleminha técnico... tenta de novo? 😅")


# ── BOT ──────────────────────────────────────────────────────────

class HanaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        synced = await self.tree.sync()
        logger.info(f"[DISCORD] {len(synced)} slash commands sincronizados globalmente.")

    async def on_ready(self):
        logger.info(f'[DISCORD] ✦ Hana Nakamura online como {self.user} ✦')
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="você com carinho 🌸")
        )

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # AutoMod
        if lira_automod.settings["automod"]:
            is_clean, reason = lira_automod.check_message(str(message.author.id), message.content)
            if not is_clean:
                warns = lira_automod.add_warn(str(message.author.id))
                await message.delete()
                if warns >= 3:
                    try:
                        await message.author.ban(reason="Excesso de avisos (AutoMod)")
                        await message.channel.send(f"🚫 {message.author.mention} foi banido por atingir 3 avisos.")
                    except Exception:
                        await message.channel.send(f"⚠️ {message.author.mention} deveria ser banido, mas não tenho permissão!")
                else:
                    await message.channel.send(
                        f"⚠️ {message.author.mention}, mensagem removida (**{reason}**). Aviso {warns}/3.",
                        delete_after=5
                    )
                return

        # XP por mensagem
        if lira_automod.settings.get("economy", True):
            leveled_up = lira_gamification.add_xp(str(message.author.id), "discord", 10)
            if leveled_up:
                user_data = lira_gamification.get_user(str(message.author.id), "discord")
                await message.channel.send(
                    f"🎊 **SUBIU DE NÍVEL!** Parabéns {message.author.mention}, você agora é Nível **{user_data['level']}**! ✨"
                )

        # Responde se for mencionada
        if self.user.mentioned_in(message):
            clean_content = message.content.replace(f'<@!{self.user.id}>', '').replace(f'<@{self.user.id}>', '').strip()
            if clean_content:
                await _responder_com_thinking(message.channel, clean_content, message.author.display_name, message)

        await self.process_commands(message)


bot = HanaBot()


# ── SLASH COMMANDS ──────────────────────────────────────────────

@bot.tree.command(name="chat", description="Fale diretamente com a Hana Nakamura 🌸")
@app_commands.describe(mensagem="O que você quer dizer pra ela?")
async def slash_chat(interaction: discord.Interaction, mensagem: str):
    await interaction.response.defer(thinking=True)
    try:
        clean = await _responder(mensagem, interaction.user.name)
        chunks = [clean[i:i+2000] for i in range(0, len(clean), 2000)]
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)
    except Exception as e:
        logger.error(f"[DISCORD] Erro no /chat: {e}", exc_info=True)
        await interaction.followup.send("Ops... Tive um colapso momentâneo. Tenta de novo? 😅")


@bot.tree.command(name="imaginar", description="Pede para a Hana gerar uma imagem artística 🎨")
@app_commands.describe(prompt="Descreva a imagem que você quer")
async def slash_imaginar(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    try:
        image_path = await asyncio.to_thread(image_gen.generate, prompt)
        if image_path:
            file = discord.File(image_path, filename="hana_art.png")
            await interaction.followup.send(content=f"🎨 Aqui está: *\"{prompt}\"*", file=file)
        else:
            await interaction.followup.send("❌ Não consegui gerar essa imagem agora. Tente um prompt diferente!")
    except Exception as e:
        logger.error(f"[DISCORD] Erro ao imaginar: {e}")
        await interaction.followup.send("🚨 Tive um problema técnico ao tentar desenhar isso.")


@bot.tree.command(name="perfil", description="Veja seu card de perfil com XP e nível 🌸")
async def slash_perfil(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    user_data = lira_gamification.get_user(user_id, "discord", interaction.user.display_name)
    needed_xp = lira_gamification.get_xp_for_level(user_data['level'] + 1)

    card_path = generate_profile_card(
        username=interaction.user.display_name,
        level=user_data['level'],
        xp=user_data['xp'],
        needed_xp=needed_xp,
        avatar_url=str(interaction.user.display_avatar.url)
    )

    file = discord.File(card_path, filename="profile.png")
    embed = discord.Embed(title=f"🌸 Hana Profile — {interaction.user.display_name}", color=0xf472b6)
    embed.add_field(name="🪙 LiraCoins", value=f"{user_data['coins']}", inline=True)
    embed.add_field(name="⭐ Nível", value=f"{user_data['level']}", inline=True)
    embed.add_field(name="✨ XP", value=f"{user_data['xp']}", inline=True)
    embed.set_image(url="attachment://profile.png")
    await interaction.followup.send(file=file, embed=embed)


@bot.tree.command(name="daily", description="Resgata sua recompensa diária 🎁")
async def slash_daily(interaction: discord.Interaction):
    result = lira_gamification.claim_daily(str(interaction.user.id), "discord")
    if result["success"]:
        await interaction.response.send_message(f"🎁 **BÔNUS!** Você recebeu **{result['coins']}** 🪙 e **{result['xp']}** ⭐ XP!")
    else:
        await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)


@bot.tree.command(name="ranking", description="Veja os maiores conversadores 🏆")
async def slash_ranking(interaction: discord.Interaction):
    top = lira_gamification.get_leaderboard(platform="discord", limit=5)
    msg = "🏆 **TOP 5 — HANA DISCORD RANKING** 🏆\n\n"
    for i, u in enumerate(top, 1):
        msg += f"`#{i}` **{u['username']}** - LVL {u['level']} ({u['xp']} XP)\n"
    await interaction.response.send_message(msg)


@bot.tree.command(name="depositar", description="Guarda moedas no banco 🏦")
@app_commands.describe(moedas="Quantidade de moedas a depositar")
async def slash_depositar(interaction: discord.Interaction, moedas: int):
    res = lira_gamification.bank_action(str(interaction.user.id), "discord", "deposit", moedas)
    if res["success"]:
        await interaction.response.send_message(f"🏦 Você depositou **{moedas}** moedas no banco!")
    else:
        await interaction.response.send_message(f"❌ {res['message']}", ephemeral=True)


@bot.tree.command(name="sacar", description="Retira moedas do banco 🏧")
@app_commands.describe(moedas="Quantidade de moedas a sacar")
async def slash_sacar(interaction: discord.Interaction, moedas: int):
    res = lira_gamification.bank_action(str(interaction.user.id), "discord", "withdraw", moedas)
    if res["success"]:
        await interaction.response.send_message(f"🏧 Você sacou **{moedas}** moedas!")
    else:
        await interaction.response.send_message(f"❌ {res['message']}", ephemeral=True)


@bot.tree.command(name="roubar", description="Tenta roubar moedas de outro usuário 😈")
@app_commands.describe(alvo="Quem você quer roubar")
async def slash_roubar(interaction: discord.Interaction, alvo: discord.Member):
    res = lira_gamification.steal(str(interaction.user.id), str(alvo.id), "discord")
    if res["success"]:
        await interaction.response.send_message(f"😈 **SUCESSO!** Você roubou **{res['stolen']}** moedas de **{res['target_name']}**!")
    else:
        await interaction.response.send_message(f"👮 {res['message']}")


@bot.tree.command(name="suporte", description="Informações de suporte e contato 📞")
async def slash_suporte(interaction: discord.Interaction):
    embed = discord.Embed(title="📞 Suporte — Hana Nakamura", color=0xa855f7)
    embed.add_field(name="✉️ E-mail", value="amarinthlira@gmail.com", inline=False)
    embed.add_field(name="💬 Discord", value="Fale com Rukafuu", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="config", description="Ativa ou desativa módulos (Apenas Admins) ⚙️")
@app_commands.describe(modulo="Módulo: games, automod, economy", ativo="True para ativar, False para desativar")
@app_commands.checks.has_permissions(administrator=True)
async def slash_config(interaction: discord.Interaction, modulo: str, ativo: bool):
    success = lira_automod.set_module(modulo.lower(), ativo)
    if success:
        await interaction.response.send_message(f"⚙️ Módulo **{modulo}** agora está {'✅ ATIVO' if ativo else '❌ DESATIVADO'}.")
    else:
        await interaction.response.send_message(f"❌ Módulo '{modulo}' não existe. Opções: `games`, `automod`, `economy`.", ephemeral=True)


@bot.tree.command(name="ajuda", description="Lista todos os comandos disponíveis ✦")
async def slash_ajuda(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✦ Hana Nakamura — Comandos",
        description="Aqui estão as formas de interagir comigo:",
        color=0xa855f7
    )
    embed.add_field(name="💬 `/chat <msg>`", value="Conversa direta comigo.", inline=True)
    embed.add_field(name="🎨 `/imaginar <desc>`", value="Gero uma imagem pra você.", inline=True)
    embed.add_field(name="🌸 `/perfil`", value="Ver seu card de XP e Nível.", inline=True)
    embed.add_field(name="🎁 `/daily`", value="Sua recompensa diária.", inline=True)
    embed.add_field(name="🏆 `/ranking`", value="Top usuários do servidor.", inline=True)
    embed.add_field(name="🏦 `/depositar <n>`", value="Guardar moedas no banco.", inline=True)
    embed.add_field(name="🏧 `/sacar <n>`", value="Retirar moedas do banco.", inline=True)
    embed.add_field(name="😈 `/roubar <@user>`", value="Tentar roubar moedas.", inline=True)
    embed.set_footer(text="Hana Nakamura • Powered by OpenRouter + Pollinations")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── ENTRYPOINT ──────────────────────────────────────────────────

def run_discord_bot():
    token = os.getenv("DISCORD_TOKEN")
    if not token or token in ("sua_chave_aqui", ""):
        logger.error("[DISCORD] DISCORD_TOKEN não configurado no .env!")
        return
    logger.info("[DISCORD] Iniciando Hana Nakamura Discord Bot...")
    bot.run(token)


if __name__ == "__main__":
    run_discord_bot()
