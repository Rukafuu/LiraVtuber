import asyncio
import os

import discord
from discord.ext import commands
from ..constants import logger, EMOJI, THINKING_MSG
from ..media_attach import (
    enrich_media_prompt,
    enrich_voice_prompt,
    is_audio_attachment,
    read_image_b64,
    transcribe_discord_attachment,
    is_video_attachment,
    extract_video_frames_discord,
    download_discord_sticker,
    parse_custom_emojis,
    is_image_attachment,
)
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
                image_b64 = None
                voice_transcript = None
                arquivos_multimidia = []
                user_text = parse_custom_emojis(message.content)

                if message.stickers:
                    for sticker in message.stickers:
                        desc = f"[Sticker: {sticker.name}]"
                        if sticker.description:
                            desc = f"[Sticker: {sticker.name} ({sticker.description})]"
                        user_text = f"{user_text}\n\n{desc}" if user_text else desc
                        st_path = await download_discord_sticker(sticker)
                        if st_path:
                            arquivos_multimidia.append(st_path)

                if message.attachments:
                    for att in message.attachments:
                        if is_video_attachment(att):
                            logger.info("[DISCORD] Vídeo detectado em menção/DM: %s", att.filename)
                            frames = await extract_video_frames_discord(att)
                            if frames:
                                arquivos_multimidia.extend(frames)
                        elif is_image_attachment(att):
                            if not arquivos_multimidia and not image_b64:
                                image_b64 = await read_image_b64(att)
                                if image_b64:
                                    logger.info(
                                        "[DISCORD] Imagem em menção/DM de %s: %s",
                                        message.author.display_name,
                                        att.filename,
                                    )
                            else:
                                temp_dir = os.path.abspath("temp/incoming_media")
                                os.makedirs(temp_dir, exist_ok=True)
                                temp_path = os.path.join(temp_dir, f"discord_img_{att.id}_{att.filename}")
                                try:
                                    await att.save(temp_path)
                                    arquivos_multimidia.append(temp_path)
                                except Exception as e:
                                    logger.error("[DISCORD] Erro ao salvar imagem: %s", e)
                        elif is_audio_attachment(att) and not voice_transcript:
                            voice_transcript = await transcribe_discord_attachment(att)

                if voice_transcript:
                    user_text = enrich_voice_prompt(user_text, voice_transcript)
                else:
                    user_text = enrich_media_prompt(user_text, has_image=bool(image_b64 or arquivos_multimidia))

                if not user_text.strip() and not image_b64 and not arquivos_multimidia:
                    if message.attachments and any(
                        is_audio_attachment(a) for a in message.attachments
                    ):
                        await message.reply(
                            "💜 Não consegui entender o áudio. Tenta gravar de novo ou manda em texto."
                        )
                    return

                # Envia mensagem de pensando
                thinking_msg = await message.channel.send(THINKING_MSG)
                
                async with message.channel.typing():
                    payload = await chat_cog._responder(
                        user_text,
                        message.author.display_name,
                        image_b64=image_b64,
                        arquivos_multimidia=arquivos_multimidia,
                        discord_user_id=message.author.id,
                    )

                    await thinking_msg.delete()
                    reply_msg = await chat_cog._deliver_payload(
                        payload,
                        lambda text, **kwargs: message.reply(text[:2000], **kwargs),
                    )

                    if os.getenv("TTS_ATIVO", "1").lower() not in ("0", "false", "no"):

                        async def _tts_attach():
                            from src.modules.voice.tts_selector import get_tts

                            try:
                                # Edge é gratuito e evita cascata de erro nos outros TTS
                                tts = get_tts(os.getenv("DISCORD_TTS_PROVIDER", "edge"))
                                result = await asyncio.wait_for(
                                    asyncio.to_thread(
                                        tts.falar,
                                        payload.text,
                                        tocar_local=False,
                                    ),
                                    timeout=float(os.getenv("TTS_CALL_TIMEOUT", "25")),
                                )
                                audio_path = None
                                if isinstance(result, str) and os.path.isfile(result):
                                    audio_path = result
                                elif result and os.path.isfile("data/last_response.mp3"):
                                    audio_path = "data/last_response.mp3"
                                if audio_path:
                                    await reply_msg.reply(
                                        file=discord.File(audio_path, filename="lira_voice.mp3"),
                                    )
                            except asyncio.TimeoutError:
                                logger.warning("[DISCORD] TTS timeout — resposta só em texto")
                            except OSError as v_err:
                                logger.warning("[DISCORD] Áudio não anexado: %s", v_err)
                            except Exception as v_err:
                                logger.warning("[DISCORD] TTS falhou (texto já enviado): %s", v_err)

                        asyncio.create_task(_tts_attach())

        # XP por mensagem
        lira_gamification.lira_gamification.add_xp(str(message.author.id), "discord", 10)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
