import discord
from discord import app_commands
from discord.ext import commands
from ..constants import EMOJI
from src.modules.gamification import lira_gamification

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="daily", description="Receba seu bônus diário de moedas 🎁")
    async def daily(self, interaction: discord.Interaction):
        result = lira_gamification.claim_daily(str(interaction.user.id), "discord")
        if result["success"]:
            await interaction.response.send_message(
                f"🎁 **BÔNUS DIÁRIO!**\nVocê recebeu **{result['coins']}** {EMOJI['coin']} e **{result['xp']}** XP!\n"
                f"Volte amanhã para mais! 🌸"
            )
        else:
            await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)

    @app_commands.command(name="perfil", description="Veja seu status, XP e saldo 🌸")
    @app_commands.describe(usuario="O usuário que você quer ver o perfil (deixe vazio para o seu)")
    async def perfil(self, interaction: discord.Interaction, usuario: discord.Member = None):
        target = usuario or interaction.user
        stats = lira_gamification.get_user(str(target.id), "discord", target.display_name)
        
        xp_next = lira_gamification.get_xp_for_level(stats['level'] + 1)
        progress = (stats['xp'] / xp_next) * 100 if xp_next > 0 else 0
        
        embed = discord.Embed(title=f"Perfil de {target.display_name}", color=0xff69b4)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="⭐ Nível", value=f"Lvl {stats['level']}", inline=True)
        embed.add_field(name="✨ XP", value=f"{stats['xp']} / {xp_next}", inline=True)
        embed.add_field(name=f"{EMOJI['coin']} Carteira", value=f"{stats['coins']}", inline=True)
        embed.add_field(name="🏦 Banco", value=f"{stats['bank_coins']}", inline=True)
        
        # Barra de progresso simples
        bar_size = 10
        filled = int(progress / (100/bar_size))
        bar = "🌸" * filled + "⚪" * (bar_size - filled)
        embed.add_field(name="Progresso", value=f"{bar} ({progress:.1f}%)", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="depositar", description="Guarde suas moedas no banco para protegê-las 🏦")
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
    @app_commands.describe(quantidade="Quantidade de moedas para retirar")
    async def sacar(self, interaction: discord.Interaction, quantidade: int):
        if quantidade <= 0: return await interaction.response.send_message("Valor inválido.", ephemeral=True)
        
        result = lira_gamification.bank_action(str(interaction.user.id), "discord", "withdraw", quantidade)
        if result["success"]:
            await interaction.response.send_message(f"💰 Você sacou **{quantidade}** {EMOJI['coin']} do banco!")
        else:
            await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)

    @app_commands.command(name="roubar", description="Tente roubar a carteira de alguém! (Cuidado com a polícia 🚔)")
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
