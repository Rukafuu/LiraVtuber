import os

import discord
from discord import app_commands
from discord.ext import commands
from lira_core.economy.gems import gems_wallet

from ..constants import EMOJI
from src.modules.gamification import lira_gamification
from src.utils.profile_card_generator import load_profile_customs, save_profile_customs


def _discord_account(user_id: int | str) -> str:
    return f"discord:{user_id}"


def _is_gem_admin(user_id: int) -> bool:
    owner = os.getenv("DISCORD_OWNER_ID", "").strip()
    return owner and str(user_id) == owner


class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="daily", description="Receba seu bônus diário de moedas 🎁")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def daily(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        result = lira_gamification.claim_daily(uid, "discord")
        gem_result = gems_wallet.claim_daily(_discord_account(uid))
        if result["success"]:
            gem_line = ""
            if gem_result.get("success"):
                gem_line = f"\n💎 **+{gem_result['gems']} gemas** (saldo: {gem_result['balance']}) — busca web usa gemas!"
            await interaction.response.send_message(
                f"🎁 **BÔNUS DIÁRIO!**\nVocê recebeu **{result['coins']}** {EMOJI['coin']} e **{result['xp']}** XP!{gem_line}\n"
                f"Volte amanhã para mais! 🌸"
            )
        else:
            if gem_result.get("success"):
                await interaction.response.send_message(
                    f"🎁 Moedas já coletadas hoje, mas você ganhou **{gem_result['gems']}** 💎 gemas "
                    f"(saldo: {gem_result['balance']})!",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)

    @app_commands.command(name="weekly", description="Bônus semanal de gemas para busca na web 💎")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def weekly(self, interaction: discord.Interaction):
        result = gems_wallet.claim_weekly(_discord_account(interaction.user.id))
        if result["success"]:
            await interaction.response.send_message(
                f"📆 **WEEKLY!** +**{result['gems']}** 💎 gemas (saldo: **{result['balance']}**).\n"
                "Use no `/chat` quando a Lira pesquisar na web. 🌸"
            )
        else:
            await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)

    @app_commands.command(name="gemas", description="Veja seu saldo de gemas para busca na web 💎")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def gemas(self, interaction: discord.Interaction):
        balance = gems_wallet.get_balance(_discord_account(interaction.user.id))
        await interaction.response.send_message(
            f"💎 **Gemas:** **{balance}**\n"
            "Cada busca Tavily no chat gasta **1** gema.\n"
            "Ganhe com `/daily` e `/weekly`, ou `/loja_gemas` (PIX).",
            ephemeral=True,
        )

    @app_commands.command(name="loja_gemas", description="Pacotes de gemas via PIX 💳")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def loja_gemas(self, interaction: discord.Interaction):
        await interaction.response.send_message(gems_wallet.shop_text())

    @app_commands.command(name="gemas_dar", description="[DONO] Creditar gemas após comprovante PIX")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(usuario="Quem recebe", quantidade="Quantidade de gemas")
    async def gemas_dar(self, interaction: discord.Interaction, usuario: discord.User, quantidade: int):
        if not _is_gem_admin(interaction.user.id):
            return await interaction.response.send_message("❌ Só o criador pode usar isso.", ephemeral=True)
        if quantidade <= 0 or quantidade > 5000:
            return await interaction.response.send_message("❌ Quantidade inválida (1–5000).", ephemeral=True)
        account = _discord_account(usuario.id)
        new_bal = gems_wallet.add_gems(account, quantidade, reason=f"pix_admin:{interaction.user.id}")
        await interaction.response.send_message(
            f"✅ **{quantidade}** 💎 para {usuario.mention} — saldo: **{new_bal}**",
            ephemeral=True,
        )

    @app_commands.command(name="perfil", description="Veja seu status, XP e saldo em um card gráfico premium! 🌸")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(usuario="O usuário que você quer ver o perfil (deixe vazio para o seu)")
    async def perfil(self, interaction: discord.Interaction, usuario: discord.Member = None):
        await interaction.response.defer(thinking=True)
        try:
            target = usuario or interaction.user
            stats = lira_gamification.get_user(str(target.id), "discord", target.display_name)
            
            xp_next = lira_gamification.get_xp_for_level(stats['level'] + 1)
            
            # Puxar customização
            customs = load_profile_customs()
            user_cfg = customs.get(str(target.id), {})
            
            theme = user_cfg.get("theme_color", "pink")
            bio = user_cfg.get("sobre_mim", None)
            bg_url = user_cfg.get("banner_url", None)
            
            # Buscar casamento se houver
            marriage = lira_gamification.get_marriage(str(target.id), "discord")
            partner_name = None
            if marriage:
                partner_id = marriage["user_id_2"] if marriage["user_id_1"] == str(target.id) else marriage["user_id_1"]
                partner_member = interaction.guild.get_member(int(partner_id)) if interaction.guild else None
                partner_name = partner_member.display_name if partner_member else f"ID: {partner_id}"

            avatar_url = target.display_avatar.url if target.display_avatar else None

            # Gerar o card de perfil dinâmico em Pillow
            from src.utils.profile_card_generator import generate_profile_card
            
            card_path = await generate_profile_card(
                username=target.display_name,
                level=stats['level'],
                xp=stats['xp'],
                xp_next=xp_next,
                wallet_coins=stats['coins'],
                bank_coins=stats['bank_coins'],
                avatar_url=avatar_url,
                custom_bg_url=bg_url,
                theme_name=theme,
                bio=bio,
                marriage_partner=partner_name
            )

            await interaction.followup.send(file=discord.File(card_path, filename="lira_profile.png"))
        except Exception as e:
            from ..constants import logger
            logger.error(f"[DISCORD] Erro ao carregar card de perfil: {e}")
            await interaction.followup.send("Não consegui gerar seu card de perfil hoje! Verifique se seu avatar é público.")

    @app_commands.command(name="personalizar_perfil", description="Personalize o seu card de perfil gráfico da Lira! 🎨")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        sobre_mim="Sua mensagem de bio (max 80 caracteres)",
        cor_tema="Escolha a cor da barra de XP e detalhes",
        url_fundo="URL pública de uma imagem PNG/JPG para o fundo do seu card"
    )
    @app_commands.choices(cor_tema=[
        app_commands.Choice(name="Rosa Lira 🌸", value="pink"),
        app_commands.Choice(name="Roxo Sombrio 🔮", value="purple"),
        app_commands.Choice(name="Azul Celeste 💎", value="blue"),
        app_commands.Choice(name="Verde Neon 💚", value="green"),
    ])
    async def personalizar_perfil(
        self,
        interaction: discord.Interaction,
        sobre_mim: str = None,
        cor_tema: str = None,
        url_fundo: str = None
    ):
        customs = load_profile_customs()
        user_id = str(interaction.user.id)
        
        if user_id not in customs:
            customs[user_id] = {}
            
        if sobre_mim is not None:
            if len(sobre_mim) > 80:
                return await interaction.response.send_message("❌ Sua biografia não pode passar de 80 caracteres!", ephemeral=True)
            customs[user_id]["sobre_mim"] = sobre_mim
            
        if cor_tema is not None:
            customs[user_id]["theme_color"] = cor_tema
            
        if url_fundo is not None:
            low_url = url_fundo.lower().strip()
            if not (low_url.startswith("http://") or low_url.startswith("https://")):
                return await interaction.response.send_message("❌ A URL de fundo precisa começar com http:// ou https://!", ephemeral=True)
            customs[user_id]["banner_url"] = url_fundo.strip()

        save_profile_customs(customs)
        await interaction.response.send_message("✨ **Perfil personalizado com sucesso!** Use `/perfil` para ver como ficou seu novo card! 🌸💅")

    @app_commands.command(name="depositar", description="Guarde suas moedas no banco para protegê-las 🏦")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(quantidade="Quantidade de moedas para guardar (ou 'tudo')")
    async def depositar(self, interaction: discord.Interaction, quantidade: str):
        stats = lira_gamification.get_user(str(interaction.user.id), "discord")
        
        if quantidade.lower() == "tudo":
            valor = stats['coins']
        else:
            try:
                valor = int(quantidade)
            except:
                return await interaction.response.send_message("Digite um número válido ou 'tudo'.", ephemeral=True)
        
        if valor <= 0: return await interaction.response.send_message("Valor inválido.", ephemeral=True)
        
        result = lira_gamification.bank_action(str(interaction.user.id), "discord", "deposit", valor)
        if result["success"]:
            await interaction.response.send_message(f"🏦 Você depositou **{valor}** {EMOJI['coin']} no banco!")
        else:
            await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)

    @app_commands.command(name="sacar", description="Retire moedas do banco 💰")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(quantidade="Quantidade de moedas para retirar")
    async def sacar(self, interaction: discord.Interaction, quantidade: int):
        if quantidade <= 0: return await interaction.response.send_message("Valor inválido.", ephemeral=True)
        
        result = lira_gamification.bank_action(str(interaction.user.id), "discord", "withdraw", quantidade)
        if result["success"]:
            await interaction.response.send_message(f"💰 Você sacou **{quantidade}** {EMOJI['coin']} do banco!")
        else:
            await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)

    @app_commands.command(name="roubar", description="Tente roubar a carteira de alguém! (Cuidado com a polícia 🚔)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(usuario="De quem você quer tentar roubar?")
    async def roubar(self, interaction: discord.Interaction, usuario: discord.Member):
        if usuario.bot: return await interaction.response.send_message("Você não pode roubar um bot!", ephemeral=True)
        
        result = lira_gamification.steal(str(interaction.user.id), str(usuario.id), "discord")
        if result["success"]:
            await interaction.response.send_message(
                f"🥷 **SUCESSO!** Você roubou **{result['stolen']}** {EMOJI['coin']} de **{result['target_name']}**!"
            )
        else:
            await interaction.response.send_message(result["message"])

    @app_commands.command(name="ranking", description="Veja quem são os maiores do servidor 🏆")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ranking(self, interaction: discord.Interaction):
        top = lira_gamification.get_leaderboard("discord", limit=5)
        
        description = ""
        for i, user in enumerate(top):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🔹"
            description += f"{medal} **{user['username']}** - Lvl {user['level']} ({user['xp']} XP)\n"
            
        embed = discord.Embed(title="🏆 Ranking de Experiência", description=description, color=0xffd700)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
