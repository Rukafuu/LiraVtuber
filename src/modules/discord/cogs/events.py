import asyncio
import os

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
                    payload = await chat_cog._responder(
                        message.content,
                        message.author.display_name,
                        image_b64=image_b64,
                        discord_user_id=message.author.id,
                    )

                    await thinking_msg.delete()
                    reply_msg = await chat_cog._deliver_payload(
                        payload,
                        lambda text: message.reply(text[:2000]),
                    )

                    if os.getenv("TTS_ATIVO", "1").lower() not in ("0", "false", "no"):

                        async def _tts_attach():
                            from src.modules.voice.tts_selector import get_tts

                            try:
                                tts = get_tts()
                                success = await asyncio.wait_for(
                                    asyncio.to_thread(
                                        tts.falar,
                                        payload.text,
                                        tocar_local=False,
                                    ),
                                    timeout=float(os.getenv("TTS_CALL_TIMEOUT", "25")),
                                )
                                if success:
                                    audio_file = discord.File(
                                        "data/last_response.mp3",
                                        filename="lira_voice.mp3",
                                    )
                                    await reply_msg.reply(file=audio_file)
                            except asyncio.TimeoutError:
                                logger.warning("[DISCORD] TTS timeout — resposta só em texto")
                            except Exception as v_err:
                                logger.error("[DISCORD] Erro ao gerar voz: %s", v_err)

                        asyncio.create_task(_tts_attach())

        # XP por mensagem
        lira_gamification.lira_gamification.add_xp(str(message.author.id), "discord", 10)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
