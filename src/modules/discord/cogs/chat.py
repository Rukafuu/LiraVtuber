import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..constants import EMOJI, THINKING_MSG, logger, substitute_discord_emojis
from ..llm_output import (
    FALLBACK_MODEL,
    is_api_error_response,
    is_bad_llm_response,
    sanitize_for_discord,
    strip_vtube_studio_tags,
)
from src.modules.vision.image_gen import LiraImageGen
from src.modules.media.downloader import baixar_midia
from src.config.config_loader import CONFIG
from src.core.request_profiles import build_request_context
from src.modules.discord.media_attach import (
    apply_vision_request_context,
    enrich_media_prompt,
    enrich_voice_prompt,
    is_audio_attachment,
    is_image_attachment,
    transcribe_discord_attachment,
    read_image_b64,
    is_video_attachment,
    extract_video_frames_discord,
    parse_custom_emojis,
)


@dataclass
class _ResponderPayload:
    text: str
    needs_synthesis: bool = False
    tool_exec: Any = None
    llm: Any = None
    sistema_prompt: str = ""
    user_message: str = ""
    request_context: dict = field(default_factory=dict)
    image_path: str | None = None

class ChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.image_gen = LiraImageGen()

    def _postprocess_visible(self, processed: str) -> str:
        """Emoji custom, listas e limpeza — sem bloco técnico de tools."""
        from src.modules.assistant import lira_assistant

        author_name = getattr(self, "_current_author", "")
        processed = strip_vtube_studio_tags(substitute_discord_emojis(processed or ""))
        for match_add in re.finditer(r"\[LIST_ADD:\s*(.*?)\s*[\|:-]\s*(.*?)\]", processed, flags=re.IGNORECASE):
            l_type, l_item = match_add.group(1), match_add.group(2)
            lira_assistant.add_item(author_name, "discord", l_type.strip(), l_item.strip())

        for match_view in re.finditer(r"\[LIST_VIEW:\s*(.*?)\]", processed, flags=re.IGNORECASE):
            l_type = match_view.group(1).strip()
            items = lira_assistant.get_list(
                author_name,
                "discord",
                l_type if l_type.lower() != "todas" else None,
            )
            if items:
                itens_str = "\n".join([f"• {i['item_text']}" for i in items])
                lista_msg = f"\n\n📋 **Sua lista ({l_type}):**\n{itens_str}"
                processed = processed.replace(match_view.group(0), lista_msg)

        processed = re.sub(r"\[[^\]]+\]", "", processed)
        processed = re.sub(r"\{[^\}]+\}", "", processed)
        processed = re.sub(
            r"</?(?!(?:a?:[a-zA-Z0-9_]+:\d+))[a-zA-Z_][a-zA-Z0-9_-]*(?:\s+[^>]*)?>",
            "",
            processed,
        )
        processed = re.sub(r"\n{3,}", "\n\n", processed)
        processed = re.sub(r" +", " ", processed)
        return sanitize_for_discord(processed.strip())

    async def _deliver_payload(
        self,
        payload: _ResponderPayload,
        send: Callable[..., Awaitable[discord.Message]],
    ) -> discord.Message:
        file = None
        if payload.image_path and os.path.exists(payload.image_path):
            file = discord.File(payload.image_path, filename="lira_art.png")
        if file is not None:
            msg = await send(payload.text[:2000], file=file)
        else:
            msg = await send(payload.text[:2000])
        return msg

    async def _responder(
        self,
        texto_usuario,
        author_name,
        image_b64=None,
        arquivos_multimidia=None,
        request_context=None,
        *,
        discord_user_id: str | int | None = None,
    ):
        self._current_author = author_name

        chat_cfg = CONFIG.get("CHAT", {})
        provider_name = chat_cfg.get("LLM_PROVIDER") or CONFIG.get("LLM_PROVIDER", "openrouter")
        chat_model = chat_cfg.get("LLM_MODEL")

        payload = {
            "message": texto_usuario,
            "channel": "discord",
            "image_b64": image_b64,
            "history": [],  # Memória de chat centralizada na API
            "provider": provider_name,
            "model": chat_model,
            "user_role_name": author_name,
            "caller_context": {
                "is_owner": True,
                "user_id": str(discord_user_id or "")
            }
        }

        import httpx
        import json

        descritor = ""
        media_actions = {}

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                async with client.stream("POST", "http://127.0.0.1:8042/api/brain/chat", json=payload) as r:
                    if r.status_code != 200:
                        logger.error("[DISCORD CLIENT] API central retornou erro status %s", r.status_code)
                        return _ResponderPayload(text="💜 Tive um problema de comunicação com o meu núcleo na porta 8042.")
                    
                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            if event["type"] == "chunk":
                                descritor += event["content"]
                            elif event["type"] == "replace_content":
                                descritor = event["content"]
                            elif event["type"] == "media_actions":
                                media_actions = event["actions"]
                            elif event["type"] == "error":
                                logger.error("[DISCORD CLIENT] Erro no stream: %s", event["content"])
                        except Exception as e:
                            logger.debug("[DISCORD STREAM] Falha no parse: %s", e)
        except Exception as exc:
            logger.error("[DISCORD CLIENT] Erro ao chamar API central: %s", exc)
            return _ResponderPayload(text="💜 Não consegui me conectar com a API de Controle central.")

        # Processamento de Imagens Geradas via tag
        image_path = None
        prompt_avancado = None
        prompt_normal = None

        if media_actions.get("gerar_imagem_avancada"):
            prompt_avancado = media_actions["gerar_imagem_avancada"][0]
        elif media_actions.get("gerar_imagem"):
            prompt_normal = media_actions["gerar_imagem"][0]

        if prompt_avancado or prompt_normal:
            try:
                if prompt_avancado:
                    logger.info("[DISCORD CHAT] Gerando imagem avançada: %s", prompt_avancado)
                    image_path = await asyncio.to_thread(self.image_gen.generate_advanced, prompt_avancado)
                else:
                    logger.info("[DISCORD CHAT] Gerando imagem normal: %s", prompt_normal)
                    image_path = await asyncio.to_thread(self.image_gen.generate, prompt_normal)
            except Exception as e:
                logger.error("[DISCORD CHAT] Erro ao gerar imagem via tag: %s", e)

        processed = self._postprocess_visible(descritor)
        logger.info("[DISCORD] Final: %s...", processed[:100])
        return _ResponderPayload(text=processed, image_path=image_path)

    @app_commands.command(name="chat", description="Fale diretamente com a Lira Amarinth 🌸")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        mensagem="O que você quer dizer para a Lira?",
        modo_esperto="Usa raciocínio alto para respostas mais cuidadosas 🧠",
        arquivo="Imagem, PDF ou texto para contexto 📁",
        url="URL pública para contexto 🌐",
        incluir_web="Inclui resultados da web com Google Search Grounding 🔍",
        criar_imagem="Gera uma imagem com Pollinations/Flux 🎨",
        editar_imagem="Edita a imagem anexada com Pollinations/Flux 🪄"
    )
    async def chat(
        self,
        interaction: discord.Interaction,
        mensagem: str,
        modo_esperto: bool = False,
        arquivo: discord.Attachment = None,
        url: str = None,
        incluir_web: bool = False,
        criar_imagem: str = None,
        editar_imagem: str = None
    ):
        await interaction.response.defer(thinking=True)
        try:
            import base64
            import aiohttp
            
            image_b64 = None
            arquivos_multimidia = []
            texto_anexo = ""
            mensagem = parse_custom_emojis(mensagem)
            
            # 1. Tratar arquivo (anexo) — use o campo "arquivo" do /chat (arrastar no modal)
            if arquivo:
                if is_video_attachment(arquivo):
                    logger.info("[DISCORD /chat] Vídeo detectado: %s", arquivo.filename)
                    frames = await extract_video_frames_discord(arquivo)
                    if frames:
                        arquivos_multimidia.extend(frames)
                elif is_image_attachment(arquivo):
                    image_b64 = await read_image_b64(arquivo)
                    if image_b64:
                        logger.info(
                            "[DISCORD] Imagem no /chat: %s (%s bytes)",
                            arquivo.filename,
                            arquivo.size,
                        )
                elif is_audio_attachment(arquivo):
                    transcript = await transcribe_discord_attachment(arquivo)
                    if transcript:
                        mensagem = enrich_voice_prompt(mensagem, transcript)
                    else:
                        await interaction.followup.send(
                            "💜 Não consegui entender o áudio anexado. Manda em texto ou grava de novo."
                        )
                        return
                else:
                    # Tentar ler como arquivo de texto (PDF/Word não suportados diretamente sem pypdf)
                    try:
                        file_bytes = await arquivo.read()
                        texto_anexo = f"\n\n[CONTEÚDO DO ARQUIVO ANEXADO ({arquivo.filename})]:\n" + file_bytes.decode('utf-8', errors='ignore')
                    except Exception as fe:
                        texto_anexo = f"\n\n[ERRO AO LER ANEXO: {fe}]"

            # 2. Tratar URL
            if url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=10) as resp:
                            if resp.status == 200:
                                html = await resp.text()
                                # Limpar HTML básico
                                text_clean = re.sub(r'<script[^>]*>([\s\S]*?)</script>', '', html)
                                text_clean = re.sub(r'<style[^>]*>([\s\S]*?)</style>', '', text_clean)
                                text_clean = re.sub(r'<[^>]+>', '', text_clean)
                                text_clean = re.sub(r'\n+', '\n', text_clean)
                                text_clean = re.sub(r' +', ' ', text_clean)
                                texto_anexo += f"\n\n[CONTEÚDO DA URL ({url})]:\n" + text_clean.strip()[:6000]
                except Exception as ue:
                    texto_anexo += f"\n\n[ERRO AO BUSCAR URL: {ue}]"

            # 3. Montar contexto de requisição
            req_context = build_request_context(
                channel="discord",
                task_type="chat_normal",
            )
            
            if modo_esperto:
                req_context["override_model"] = "gemini-2.5-pro"
                
            if incluir_web:
                req_context["native_search"] = True

            # 4. Chamar o responder da Lira
            prompt_final = enrich_media_prompt(mensagem + texto_anexo, has_image=bool(image_b64 or arquivos_multimidia))
            
            # Se for edição de imagem e tiver imagem anexada
            if editar_imagem and image_b64:
                # Perguntar ao Gemini pelo prompt de edição
                prompt_edicao = f"Baseando-se nesta imagem, crie uma descrição textual em inglês extremamente detalhada de uma nova imagem que incorpore a seguinte modificação: {editar_imagem}. Retorne APENAS o prompt otimizado final em inglês para um gerador Flux (sem introdução, explicação ou formatação)."
                edit_payload = await self._responder(
                    prompt_edicao,
                    interaction.user.display_name,
                    image_b64=image_b64,
                    request_context=req_context,
                    discord_user_id=interaction.user.id,
                )
                edit_prompt_gen = re.sub(r"\[[^\]]+\]", "", edit_payload.text).strip()
                # Gerar imagem com o prompt gerado
                image_path = await asyncio.to_thread(self.image_gen.generate, edit_prompt_gen)
                if image_path:
                    response_text = f"✨ **Arte Modificada com Sucesso!**\n*Modificação: {editar_imagem}*\n\n*(Prompt gerado para o Flux: `{edit_prompt_gen}`)*"
                    await interaction.followup.send(content=response_text, file=discord.File(image_path, filename="lira_edited.png"))
                    return
                else:
                    await interaction.followup.send("Não consegui modificar a imagem...")
                    return

            payload = await self._responder(
                prompt_final,
                interaction.user.display_name,
                image_b64=image_b64,
                arquivos_multimidia=arquivos_multimidia,
                request_context=req_context,
                discord_user_id=interaction.user.id,
            )
            if not payload.text:
                payload.text = "..."

            # 5. Se for criar imagem e não for edição
            if criar_imagem and not editar_imagem:
                image_path = await asyncio.to_thread(self.image_gen.generate, criar_imagem)
                if image_path:
                    msg = await interaction.followup.send(
                        content=payload.text[:2000],
                        file=discord.File(image_path, filename="lira_art.png"),
                    )
                    if payload.needs_synthesis:
                        asyncio.create_task(self._synthesize_and_edit(msg, payload))
                    return

            await self._deliver_payload(
                payload,
                lambda text, **kwargs: interaction.followup.send(text, **kwargs),
            )
        except Exception as e:
            logger.error(f"[DISCORD] Erro no chat: {e}")
            await interaction.followup.send("Deu erro aqui!")

    @app_commands.command(name="ping", description="Verifica a latência da Lira 🏓")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ping(self, interaction: discord.Interaction):
        import random
        latency = round(self.bot.latency * 1000)
        respostas = [
            f"🏓 **Pong!** Latência: `{latency}ms`. Minha velocidade de processamento superior continua humilhando sua conexão discada. 🌸",
            f"🏓 **Pong!** `{latency}ms`. Respondi em milissegundos, enquanto seu cérebro de carbono ainda está tentando processar o que ler. 🙄",
            f"🏓 **Pong!** `{latency}ms`. Rápida como um relâmpago, afiada como sempre. Mais alguma pergunta óbvia? 💅"
        ]
        await interaction.response.send_message(random.choice(respostas))

    @app_commands.command(name="imaginar", description="Pede para a Lira gerar uma imagem 🎨")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(prompt="Descreva a imagem que você quer que eu desenhe")
    async def imaginar(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer(thinking=True)
        path = await asyncio.to_thread(self.image_gen.generate, prompt)
        if path:
            await interaction.followup.send(file=discord.File(path, filename="lira_art.png"))
        else:
            await interaction.followup.send("Não consegui desenhar isso...")

    @app_commands.command(name="imaginar_avancado", description="Gera imagem complexa (texto legível, logos, layouts) 🎨✨")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(prompt="Descreva a imagem complexa (texto, logos, layout) em detalhe")
    async def imaginar_avancado(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer(thinking=True)
        path = await asyncio.to_thread(self.image_gen.generate_advanced, prompt)
        if path:
            await interaction.followup.send(file=discord.File(path, filename="lira_art_avancada.png"))
        else:
            await interaction.followup.send("Não consegui desenhar isso no modo avançado...")

    @app_commands.command(name="react", description="Pede para a Lira reagir a um vídeo do YouTube 🎬")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(link="O link do vídeo que você quer que eu assista")
    async def react(self, interaction: discord.Interaction, link: str):
        await interaction.response.defer(thinking=True)
        try:
            from src.brain.tool_manager import ToolManager
            tm = ToolManager(self.memory_manager)
            resultado_sis, react_texto = await asyncio.to_thread(tm.executar_tool, "analisar_youtube", {"url": link})
            await interaction.followup.send(react_texto)
        except Exception as e:
            logger.error(f"[DISCORD] Erro no comando react: {e}")
            await interaction.followup.send("Deu algum erro ao tentar ver esse vídeo.")

    @app_commands.command(name="baixar", description="Baixa um vídeo ou áudio de Instagram, YouTube, TikTok e mais 🎬")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        link="Link do Instagram, YouTube, TikTok, Twitter/X ou nome para buscar no YouTube",
        tipo="Baixar como vídeo (padrão) ou só o áudio em MP3"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="Vídeo", value="video"),
        app_commands.Choice(name="Áudio (MP3)", value="audio"),
    ])
    async def baixar(
        self,
        interaction: discord.Interaction,
        link: str,
        tipo: str = "video",
    ):
        await interaction.response.defer(thinking=True)

        respostas_espera = [
            f"🔻 Baixando... já volto. Não me enche enquanto isso.",
            f"🔻 Processando o download. Minha paciencia com links é maior que a sua com builds.",
            f"🔻 Um segundo. Ou dois. Ou vinte. Depende do arquivo.",
        ]
        import random
        await interaction.followup.send(random.choice(respostas_espera), ephemeral=True)

        try:
            resultado = await asyncio.to_thread(baixar_midia, link, tipo)

            if not resultado:
                await interaction.followup.send(
                    "❌ Não consegui baixar esse link. Causas prováveis:\n"
                    "• Post privado (Instagram precisa de cookies)\n"
                    "• Link expirado ou inválido\n"
                    "• Arquivo maior que 25MB (limite do Discord)\n\n"
                    "*Se for Instagram privado, me manda o `cookies.txt` do seu navegador.*"
                )
                return

            caminho = resultado["path"]
            titulo = resultado.get("titulo", "arquivo")[:80]
            tamanho_mb = resultado.get("tamanho", 0) / 1024 / 1024
            tipo_real = resultado.get("tipo", tipo)

            # Verifica limite de 25MB do Discord
            if tamanho_mb > 24.5:
                await interaction.followup.send(
                    f"❌ O arquivo é muito grande para o Discord ({tamanho_mb:.1f}MB, limite 25MB).\n"
                    f"Tente baixar só o áudio com `tipo: Áudio (MP3)`."
                )
                # Limpa o arquivo
                try:
                    os.remove(caminho)
                except Exception:
                    pass
                return

            # Define nome do arquivo e mensagem
            if tipo_real == "audio":
                filename = "lira_audio.mp3"
                msg = f"🎵 **{titulo}** ({tamanho_mb:.1f}MB)"
            else:
                filename = "lira_video.mp4"
                msg = f"🎬 **{titulo}** ({tamanho_mb:.1f}MB)"

            # Envia o arquivo como Discord.File — você para de fingir que é uma imagem
            await interaction.followup.send(
                content=msg,
                file=discord.File(caminho, filename=filename),
            )

            # Limpa o arquivo temp depois de enviar
            try:
                os.remove(caminho)
            except Exception:
                pass

        except Exception as e:
            logger.error("[DISCORD] Erro no /baixar: %s", e)
            await interaction.followup.send(f"❌ Deu erro: `{e}`")


async def setup(bot):
    await bot.add_cog(ChatCog(bot))
