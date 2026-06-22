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
from src.providers.provider_selector import ProviderSelector
from src.memory.memory_manager import LiraMemoryManager
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
        self.llm_selector = ProviderSelector()
        chroma = os.getenv("LIRA_RAG_CHROMA", "0").lower() in ("1", "true", "yes")
        self.memory_manager = LiraMemoryManager(
            enable_chroma=chroma,
            sync_graph_to_rag=False,
            defer_graph_sync=True,
        )
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

    async def _synthesize_and_edit(self, message: discord.Message, payload: _ResponderPayload) -> None:
        if not payload.needs_synthesis or not payload.tool_exec:
            return
        from lira_core.tools.runner_helpers import build_final_answer_after_tools

        synth_timeout = float(os.getenv("CHAT_SYNTHESIS_TIMEOUT", "50"))
        try:
            final = await asyncio.wait_for(
                asyncio.to_thread(
                    build_final_answer_after_tools,
                    payload.llm,
                    user_message=payload.user_message,
                    sistema_prompt=payload.sistema_prompt,
                    tool_exec=payload.tool_exec,
                    request_context=payload.request_context,
                ),
                timeout=synth_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("[DISCORD] Síntese pós-tool timeout (%.0fs)", synth_timeout)
            return
        except Exception as exc:
            logger.error("[DISCORD] Síntese pós-tool falhou: %s", exc)
            return

        if not final or not str(final).strip():
            return
        final_text = self._postprocess_visible(str(final))
        if final_text.strip() == payload.text.strip():
            return
        try:
            await message.edit(content=final_text[:2000])
        except discord.NotFound:
            pass
        except discord.HTTPException as exc:
            logger.warning("[DISCORD] Não foi possível editar mensagem pós-síntese: %s", exc)

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
        if payload.needs_synthesis:
            asyncio.create_task(self._synthesize_and_edit(msg, payload))
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

        if request_context is None:
            request_context = build_request_context(
                channel="discord",
                task_type="chat_normal",
            )
        else:
            request_context = dict(request_context)
            request_context.setdefault("channel", "discord")

        if image_b64 or arquivos_multimidia:
            request_context = apply_vision_request_context(request_context)
            texto_usuario = enrich_media_prompt(texto_usuario, has_image=True)
            logger.info(
                "[DISCORD] Modo visão ativo (b64=%s, arquivos=%s)",
                bool(image_b64),
                len(arquivos_multimidia) if arquivos_multimidia else 0,
            )
            if arquivos_multimidia:
                is_video = any("temp/frames" in f.replace("\\", "/") or "video" in f.lower() for f in arquivos_multimidia)
                if is_video:
                    video_instr = (
                        "\n[INSTRUÇÃO DO SISTEMA: O usuário enviou um vídeo ou GIF animado. "
                        "Os frames sequenciais foram extraídos e anexados a esta mensagem em ordem cronológica. "
                        "Analise as imagens com atenção para entender e descrever a ação/conteúdo do vídeo.]"
                    )
                    texto_usuario = texto_usuario + video_instr

        # Memória (RAG + grafo) — roda em thread para não travar o heartbeat do Discord
        mem_context = ""
        if self.memory_manager:
            try:
                mem_context = await asyncio.to_thread(
                    self.memory_manager.get_context,
                    texto_usuario,
                )
            except Exception as e:
                logger.error("[DISCORD] Erro ao carregar memoria: %s", e)

        # Monta lista de emojis mostrando APENAS a chave curta que o LLM deve usar
        emoji_list_str = "\n".join(
            [f"- :{key}:" for key in EMOJI.keys()]
        )
        
        capabilities_info = (
            "\n[SUAS CAPACIDADES DE ELITE - LIRA V2]:\n"
            "1. IMAGENS: Você pode desenhar e gerar imagens! Se o usuário pedir para desenhar, use <gerar_imagem>prompt em inglês</gerar_imagem>.\n"
            "2. DOWNLOADS: Você baixa vídeos e músicas por link ou NOME com o comando `/baixar` ou `/musica`.\n"
            "3. VOZ: Você fala como Rei Ayanami. Seja superior e use markdown (*negrito*, _itálico_).\n"
        )

        discord_context = (
            "Canal: Discord.\n"
            "Você está conversando no Discord. Responda com deboche, sarcasmo e superioridade. Trate os humanos como seres inferiores e fofos em sua ignorância.\n"
            "REGRA OBRIGATÓRIA DE EMOJIS: NUNCA use emojis padrão do Windows (como 🌸, 😈, 😂).\n"
            "Use os emojis customizados listados abaixo escrevendo-os EXATAMENTE como mostrado, no formato :chave:.\n"
            "NUNCA invente emojis, NUNCA adicione números antes do nome. Use apenas as chaves da lista abaixo.\n"
            "NUNCA use kanji, hiragana ou katakana — só português do Brasil.\n\n"
            f"[EMOJIS DISPONÍVEIS - USE EXATAMENTE ESSES NOMES]:\n{emoji_list_str}\n\n"
            f"Contexto de memoria: {mem_context}"
        )

        from lira_core.tools.mcp_access import McpCallerContext
        from src.core.prompt_builder import build_gui_system_prompt

        mcp_caller = McpCallerContext(
            channel="discord",
            user_id=str(discord_user_id or ""),
            user_name=author_name,
        )

        chat_cfg = CONFIG.get("CHAT", {})
        provider_name = chat_cfg.get("LLM_PROVIDER") or CONFIG.get("LLM_PROVIDER", "openrouter")
        ctx = dict(request_context or {})
        chat_model = chat_cfg.get("LLM_MODEL")
        if chat_model and not ctx.get("override_model") and not image_b64:
            ctx["override_model"] = chat_model

        from src.core.reflex_routing import apply_reflex_routing

        provider_name, ctx = apply_reflex_routing(
            user_message=texto_usuario,
            mcp_caller=mcp_caller,
            provider=provider_name,
            llm_context=ctx,
        )
        if ctx.get("reflex_mode"):
            logger.info(
                "[DISCORD] Reflex → %s / %s",
                provider_name,
                ctx.get("override_model"),
            )

        prompt_request_context = {
            **request_context,
            **{k: v for k, v in ctx.items() if k in ("task_type", "reflex_mode", "override_model")},
            "channel": "discord",
            "response_mode": request_context.get("response_mode", "normal"),
            "markdown_enabled": request_context.get("markdown_enabled", True),
            "mcp_caller": mcp_caller,
        }
        task_type = str(prompt_request_context.get("task_type") or "chat_normal")
        system_prompt = build_gui_system_prompt(
            task_type=task_type,
            memory_context=discord_context,
            request_context=prompt_request_context,
            attachments_overview=(
                "Nenhum anexo."
                if not (image_b64 or arquivos_multimidia)
                else (
                    "Vários frames sequenciais extraídos de um vídeo/GIF enviado pelo usuário."
                    if arquivos_multimidia and any("temp/frames" in f or "video" in f.lower() for f in arquivos_multimidia)
                    else "Imagens/Stickers anexados — ANALISE O CONTEÚDO VISUAL antes de responder."
                )
            ),
        )

        llm = self.llm_selector.get_provider(provider_name)
        if not llm:
            return _ResponderPayload(text="💜 Nenhum provedor LLM disponível. Confere o `.env`.")

        def _call_llm(call_ctx):
            return llm.gerar_resposta(
                chat_history=[],
                sistema_prompt=system_prompt,
                user_message=f"Mensagem de {author_name}: {texto_usuario}",
                image_b64=image_b64,
                arquivos_multimidia=arquivos_multimidia,
                request_context=call_ctx,
            )

        llm_timeout = 90.0 if (image_b64 or arquivos_multimidia) else 55.0
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_call_llm, ctx),
                timeout=llm_timeout,
            )
        except asyncio.TimeoutError:
            logger.error("[DISCORD] LLM timeout (%.0fs)", llm_timeout)
            return _ResponderPayload(
                text="💜 Demorei demais pra pensar (API lenta). Manda de novo em alguns segundos."
            )

        if is_api_error_response(response):
            logger.warning("[DISCORD] Erro API (%s) — retry com Google Gemini", provider_name)
            gemini = self.llm_selector.get_provider("google_cloud")
            if gemini and provider_name != "google_cloud":
                gctx = dict(ctx)
                gctx["override_model"] = CONFIG.get("CHAT", {}).get("LLM_MODEL", "gemini-2.5-flash")
                def _call_gemini():
                    return gemini.gerar_resposta(
                        chat_history=[],
                        sistema_prompt=system_prompt,
                        user_message=f"Mensagem de {author_name}: {texto_usuario}",
                        image_b64=image_b64,
                        arquivos_multimidia=arquivos_multimidia,
                        request_context=gctx,
                    )

                try:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(_call_gemini),
                        timeout=45.0,
                    )
                except asyncio.TimeoutError:
                    return _ResponderPayload(text=sanitize_for_discord(response))
            return _ResponderPayload(text=sanitize_for_discord(response))

        if is_bad_llm_response(response):
            retry_ctx = dict(ctx)
            if provider_name == "openrouter":
                retry_ctx["override_model"] = FALLBACK_MODEL
            logger.warning(
                "[DISCORD] Resposta inválida (%r) — 1 retry",
                (response or "")[:80],
            )
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(_call_llm, retry_ctx),
                    timeout=40.0,
                )
            except asyncio.TimeoutError:
                return _ResponderPayload(text="💜 Retry também estourou o tempo. Tenta de novo.")

        # --- PROCESSAMENTO DE TOOLS (MCP, web, etc.) — igual painel/WhatsApp ---
        from lira_core.tools.runner_helpers import (
            clean_tool_artifacts_from_visible,
            execute_silent_tools,
            quick_interim_after_tools,
        )
        from src.utils.lira_tags import strip_xml_tags
        from lira_core.tools.tool_manager import ToolManager

        user_marked = f"Mensagem de {author_name}: {texto_usuario}"
        tool_timeout = float(os.getenv("DISCORD_TOOL_TIMEOUT", "90"))

        def _run_tools():
            return execute_silent_tools(
                response,
                user_message=texto_usuario,
                tool_manager=ToolManager(self.memory_manager),
                caller_context=mcp_caller,
            )

        try:
            tool_exec = await asyncio.wait_for(asyncio.to_thread(_run_tools), timeout=tool_timeout)
        except asyncio.TimeoutError:
            logger.warning("[DISCORD] Tools timeout (%.0fs)", tool_timeout)
            return _ResponderPayload(
                text=sanitize_for_discord(
                    "💜 A ferramenta (MCP/web) demorou demais. "
                    "Confere se o MCP Gateway :8045 está ON e tenta de novo."
                )
            )

        if tool_exec.report.memory_injections:
            interim = quick_interim_after_tools(
                response or "",
                tool_exec,
                clean_visible=lambda t: clean_tool_artifacts_from_visible(strip_xml_tags(t)),
            )
            interim = self._postprocess_visible(interim)
            logger.info("[DISCORD] Tools OK — interim enviado, síntese em background")
            return _ResponderPayload(
                text=interim,
                needs_synthesis=True,
                tool_exec=tool_exec,
                llm=llm,
                sistema_prompt=system_prompt,
                user_message=user_marked,
                request_context=ctx,
            )

        # --- PROCESSAMENTO DE IMAGEM VIA TAGS XML (Discord Chat) ---
        image_path = None
        from src.utils.lira_tags import extract_xml_actions
        img_actions = extract_xml_actions(response or "", ("gerar_imagem", "gerar_imagem_avancada"))
        
        prompt_avancado = None
        prompt_normal = None
        
        if img_actions.get("gerar_imagem_avancada"):
            prompt_avancado = img_actions["gerar_imagem_avancada"][0]
        elif img_actions.get("gerar_imagem"):
            prompt_normal = img_actions["gerar_imagem"][0]
        else:
            # Fallback para colchetes
            match_img_adv = re.search(r'\[GEN_IMAGE_ADVANCED:\s*(.*?)\]', response or "", flags=re.IGNORECASE)
            match_img = re.search(r'\[GEN_IMAGE:\s*(.*?)\]', response or "", flags=re.IGNORECASE)
            if match_img_adv:
                prompt_avancado = match_img_adv.group(1)
            elif match_img:
                prompt_normal = match_img.group(1)
                
        if prompt_avancado or prompt_normal:
            try:
                if prompt_avancado:
                    logger.info("[DISCORD CHAT] Gerando imagem avançada (Riverflow): %s", prompt_avancado)
                    image_path = await asyncio.to_thread(self.image_gen.generate_advanced, prompt_avancado)
                else:
                    logger.info("[DISCORD CHAT] Gerando imagem normal (Pollinations): %s", prompt_normal)
                    image_path = await asyncio.to_thread(self.image_gen.generate, prompt_normal)
            except Exception as e:
                logger.error("[DISCORD CHAT] Erro ao gerar imagem via tag: %s", e)

        processed = self._postprocess_visible(
            clean_tool_artifacts_from_visible(strip_xml_tags(response or ""))
        )
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
