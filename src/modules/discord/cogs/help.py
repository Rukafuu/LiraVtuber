import discord
from discord import app_commands
from discord.ext import commands
from ..constants import EMOJI


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ajuda", description="Veja todos os comandos da Hana 🌸")
    async def ajuda(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌸 Hana Nakamura — Central de Ajuda",
            description="Aqui estão todos os meus comandos! Use `/` para acessar qualquer um.",
            color=0xff69b4
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        embed.add_field(
            name="💬 Chat & Criatividade",
            value=(
                "`/chat` — Fale comigo diretamente\n"
                "`/imaginar` — Peça para eu gerar uma imagem"
            ),
            inline=False
        )

        embed.add_field(
            name="💰 Economia",
            value=(
                "`/daily` — Bônus diário de moedas\n"
                "`/perfil` — Veja seu nível, XP e saldo\n"
                "`/ranking` — Top 5 do servidor\n"
                "`/depositar` — Guarde moedas no banco\n"
                "`/sacar` — Retire moedas do banco\n"
                "`/roubar` — Tente roubar alguém (50% de chance!)"
            ),
            inline=False
        )

        embed.add_field(
            name="💍 Relacionamentos",
            value=(
                "`/casar` — Peça alguém em casamento\n"
                "`/divorciar` — Termine seu casamento"
            ),
            inline=False
        )

        embed.add_field(
            name="🫂 Interações (com alvo)",
            value=(
                "`/abracar` `/beijar` `/cafune` `/beijo_rapido`\n"
                "`/aconchegar` `/mao` `/apertar_mao` `/highfive`\n"
                "`/cutucar` `/alimentar` `/acenar` `/olhar`\n"
                "`/morder` `/comer` `/xingar` `/tapa`\n"
                "`/socar` `/chutar` `/arremessar` `/matar`"
            ),
            inline=False
        )

        embed.add_field(
            name="😊 Expressões (só você)",
            value=(
                "`/corar` `/feliz` `/sorrir` `/piscar`\n"
                "`/rir` `/dançar` `/pensar` `/concordar`\n"
                "`/joinha` `/satisfeito` `/fazer_bico`\n"
                "`/chorar` `/triste` `/dar_de_ombros`\n"
                "`/entediado` `/facepalm` `/recusar`\n"
                "`/correr` `/dormir` `/bocejar` `/espreitar`"
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ Administração (requer permissão)",
            value=(
                "`/banir` `/expulsar` `/silenciar` `/dessilenciar`\n"
                "`/advertir` `/avisos` `/remover_aviso` `/limpar_avisos`\n"
                "`/limpar` `/trancar` `/destrancar` `/lento`\n"
                "`/anunciar` `/info_usuario`"
            ),
            inline=False
        )

        embed.set_footer(text="Hana Nakamura 🌸 | Todos os GIFs são de anime!")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
