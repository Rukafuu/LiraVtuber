import discord
from discord.ext import commands
from ..constants import logger, EMOJI
import src.modules.gamification as lira_gamification

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Resposta automática em DM ou Menção
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.bot.user.mentioned_in(message)
        
        if is_dm or is_mentioned:
            # Aqui chamamos o cog de chat para responder
            chat_cog = self.bot.get_cog('ChatCog')
            if chat_cog:
                async with message.channel.typing():
                    response = await chat_cog._responder(message.content, message.author.display_name)
                    await message.channel.send(response[:2000])

        # XP por mensagem
        lira_gamification.add_xp(str(message.author.id), "discord", 10)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
