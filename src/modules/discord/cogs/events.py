import discord
from discord.ext import commands
import base64
from ..constants import logger, EMOJI, THINKING_MSG
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
            chat_cog = self.bot.get_cog('ChatCog')
            if chat_cog:
                # Detecta imagem se houver
                image_b64 = None
                if message.attachments:
                    for att in message.attachments:
                        if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                            try:
                                img_bytes = await att.read()
                                image_b64 = base64.b64encode(img_bytes).decode('utf-8')
                                logger.info(f"[DISCORD] Imagem detectada de {message.author.display_name}")
                                break
                            except Exception as e:
                                logger.error(f"[DISCORD] Erro ao ler anexo: {e}")

                # Envia mensagem de pensando
                thinking_msg = await message.channel.send(THINKING_MSG)
                
                async with message.channel.typing():
                    response = await chat_cog._responder(
                        message.content, 
                        message.author.display_name,
                        image_b64=image_b64
                    )
                    
                    # --- GERAÇÃO DE VOZ (TTS) ---
                    audio_file = None
                    from src.modules.voice.tts_selector import get_tts
                    try:
                        tts = get_tts()
                        # Gera o áudio (salva em data/last_response.mp3)
                        success = tts.falar(response, tocar_local=False)
                        if success:
                            audio_file = discord.File("data/last_response.mp3", filename="lira_voice.mp3")
                    except Exception as v_err:
                        logger.error(f"[DISCORD] Erro ao gerar voz: {v_err}")

                    # Deleta a mensagem de pensando e envia a real
                    await thinking_msg.delete()
                    if audio_file:
                        await message.reply(content=response[:2000], file=audio_file)
                    else:
                        await message.reply(response[:2000])

        # XP por mensagem
        lira_gamification.lira_gamification.add_xp(str(message.author.id), "discord", 10)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
