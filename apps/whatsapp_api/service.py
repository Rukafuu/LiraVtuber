"""WhatsApp message handler (Sprint 3 — isolated from Control API)."""
from __future__ import annotations

import asyncio
import logging
import os
import re

from lira_core.config.config_loader import CONFIG
from src.core.prompt_builder import build_gui_system_prompt
from src.modules import vip_manager
from src.modules.automod import lira_automod
from src.modules.gamification import lira_gamification
from src.modules.media import downloader
from src.modules.social import lira_social

logger = logging.getLogger(__name__)


def get_owner_jids() -> list[str]:
    jids = []
    for key in ("WPP_OWNER_JID", "WPP_OWNER_LID"):
        value = os.getenv(key, "").strip()
        if value:
            jids.append(value)
    if jids:
        return jids
    return ["5511981826659@s.whatsapp.net", "38620983517314@lid"]


def _resolve_whatsapp_llm() -> tuple[str, str, float]:
    """Usa CHAT/LLM_PROVIDER do config.json — evita modelo OpenRouter no Gemini (404)."""
    chat_cfg = CONFIG.get("CHAT", {})
    provider = (chat_cfg.get("LLM_PROVIDER") or CONFIG.get("LLM_PROVIDER") or "google_cloud").lower()
    prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get(provider, {})
    model = (
        chat_cfg.get("LLM_MODEL")
        or prov_cfg.get("modelo_chat")
        or prov_cfg.get("modelo")
    )
    if provider == "google_cloud":
        if not model or "/" in str(model) or ":" in str(model):
            model = "gemini-2.5-flash"
    elif provider == "openrouter":
        if not model:
            model = "openrouter/free"
    else:
        model = model or prov_cfg.get("modelo_chat") or "gemini-2.5-flash"
    temp = float(chat_cfg.get("LLM_TEMPERATURE") or CONFIG.get("LLM_TEMPERATURE", 0.85))
    return provider, str(model), temp


def _friendly_llm_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "404" in text or "not found" in text:
        return (
            "💜 Falha no modelo de IA (404 — nome de modelo inválido para o provedor). "
            "Confere no painel: Cérebro → provedor Google + gemini-2.5-flash, ou OpenRouter com modelo free."
        )
    if "429" in text or "quota" in text or "rate" in text:
        return "💜 Estou no limite da API de IA agora. Espera um minutinho e manda de novo?"
    return f"💜 Problema técnico na IA: {str(exc)[:160]}"


async def handle_chat(payload: dict, state) -> dict:
    print('\n--- [WHATSAPP] NOVA MENSAGEM ---', flush=True)
    """Recebe mensagens do bridge do WhatsApp e retorna a resposta da Lira."""
    user_message = payload.get("message", "").strip()
    sender_name = payload.get("sender", "Usuário do WhatsApp")
    jid = payload.get("jid", sender_name)
    image_b64 = payload.get("image_b64")
    media_path = payload.get("media_path")
    arquivos_multimidia = []

    if media_path and os.path.exists(media_path):
        if media_path.lower().endswith((".mp4", ".mov", ".webm", ".mkv")):
            print(f"[WHATSAPP] Vídeo detectado em media_path: {media_path}", flush=True)
            from src.modules.vision.video_analyzer import VideoAnalyzer
            try:
                analyzer = VideoAnalyzer()
                frames = analyzer.extrair_frames(media_path, max_frames=5)
                if frames:
                    arquivos_multimidia.extend(frames)
            except Exception as e:
                print(f"[WHATSAPP] Erro ao extrair frames do vídeo: {e}", flush=True)
        else:
            print(f"[WHATSAPP] Anexo de imagem/figurinha em media_path: {media_path}", flush=True)
            arquivos_multimidia.append(media_path)

    if image_b64:
        print("[WHATSAPP] Imagem detectada no anexo!", flush=True)
    
    if not user_message and not image_b64 and not arquivos_multimidia:
        return {"status": "error", "message": "Mensagem vazia"}

    # --- SISTEMA VIP / PREMIUM ---
    is_owner_present = payload.get("is_owner_present", False)
    is_vip_user = vip_manager.is_vip(jid)
    is_allowed_group = vip_manager.is_group_allowed(jid)
    
    # Se o dono estiver no grupo, ou o JID for VIP, ou grupo autorizado... libera
    if not is_vip_user and not is_allowed_group and not is_owner_present:
        # Se for mensagem privada ou um novo grupo não autorizado
        vip_msg = (
            "💎 *LIRA PREMIUM*\n\n"
            "Desculpe, mas minhas funções premium estão limitadas a assinantes autorizados! 😅\n\n"
            "✨ *Como assinar?*\n"
            "Para se tornar VIP, você precisa estar em um grupo oficial comigo ou com meu criador (@Rukafuu).\n\n"
            f"💰 *Valor:* R$ 19,90/mês\n"
            f"🏦 *PIX (Chave):* `{vip_manager.load_vip_data()['config']['pix_key']}`\n\n"
            "Após pagar, envie o comprovante diretamente para o meu criador para liberação imediata! ✨\n\n"
            "_(Nota: Grupos antigos continuam funcionando normalmente!)_"
        )
        return {"status": "ok", "response": vip_msg}

    # --- AUTOMOD ---
    is_clean, reason = lira_automod.check_message(jid, user_message)
    if not is_clean:
        return {"status": "ok", "response": f"⚠️ *AVISO AUTOMOD:* {sender_name}, sua mensagem violou as regras. Motivo: {reason}."}

    # --- PROCESSAMENTO DE COMANDOS ---
    lowered_msg = user_message.lower()
    
    if lowered_msg.startswith("/depositar"):
        try:
            val = int(lowered_msg.split()[1])
            res = lira_gamification.bank_action(jid, "whatsapp", "deposit", val)
            return {"status": "ok", "response": f"🏦 *BANCO:* Você guardou {val} moedas com segurança!" if res["success"] else f"❌ {res['message']}"}
        except: return {"status": "ok", "response": "📝 Use: `/depositar QUANTIDADE`"}

    if lowered_msg.startswith("/sacar"):
        try:
            val = int(lowered_msg.split()[1])
            res = lira_gamification.bank_action(jid, "whatsapp", "withdraw", val)
            return {"status": "ok", "response": f"🏧 *BANCO:* Você sacou {val} moedas!" if res["success"] else f"❌ {res['message']}"}
        except: return {"status": "ok", "response": "📝 Use: `/sacar QUANTIDADE`"}

    if lowered_msg.startswith("/roubar"):
        # No WhatsApp o roubo é mais difícil pois precisa do nome/jid exato.
        # Por enquanto, vamos permitir roubar por menção de nome se o bridge passar.
        return {"status": "ok", "response": "🕵️ O sistema de roubo via WhatsApp está sendo aprimorado para identificar contatos. Por enquanto, use no Discord!"}

    if lowered_msg.startswith("/imaginar"):
        from src.modules.vision.image_gen import LiraImageGen
        igen = LiraImageGen()
        prompt = user_message[len("/imaginar"):].strip()
        if not prompt: return {"status": "ok", "response": "📝 O que você quer que eu desenhe? Use: `/imaginar <descrição>`"}
        
        img_path = igen.generate(prompt)
        if img_path:
            return {
                "status": "ok", 
                "response": f"🎨 Aqui está sua arte: *{prompt}*",
                "image_path": os.path.abspath(img_path)
            }
        else:
            return {"status": "ok", "response": "❌ Desculpe, não consegui gerar essa imagem agora."}

    if lowered_msg == "/perfil":
        if not lira_automod.settings["economy"]:
            return {"status": "ok", "response": "❌ O sistema de economia está desativado."}
        from src.utils.profile_card import generate_profile_card
        user_data = lira_gamification.get_user(jid, "whatsapp", sender_name)
        needed_xp = lira_gamification.get_xp_for_level(user_data['level'] + 1)
        card_path = generate_profile_card(
            username=sender_name,
            level=user_data['level'],
            xp=user_data['xp'],
            needed_xp=needed_xp
        )
        return {
            "status": "ok", 
            "response": f"🌸 *Perfil de {sender_name}*\n⭐ Nível: {user_data['level']}\n🪙 LiraCoins: {user_data['coins']}",
            "image_path": os.path.abspath(card_path)
        }
        
    if lowered_msg == "/suporte":
        return {"status": "ok", "response": "📞 *SUPORTE LIRA AMARINTH*\n\n✉️ E-mail: amarinthlira@gmail.com\n💬 Fale com o desenvolvedor: @Rukafuu"}

    if lowered_msg == "/premium":
        return {"status": "ok", "response": "💎 *LIRA PREMIUM*\n\n🚧 *EM CONSTRUÇÃO*\nFuturos recursos: Treinamento personalizado, Memória infinita e Geração de Mídia!"}

    if lowered_msg.startswith("/config"):
        # No WhatsApp, apenas o Lucas pode configurar
        creator_aliases = ["lucas frischeisen", "rukafuu", "reskyume"]
        if not any(alias in sender_name.lower() for alias in creator_aliases):
            return {"status": "ok", "response": "❌ Apenas meu criador pode alterar minhas configurações."}
        
        try:
            parts = lowered_msg.split()
            modulo = parts[1]
            ativo = parts[2] == "on"
            success = lira_automod.set_module(modulo, ativo)
            return {"status": "ok", "response": f"⚙️ Módulo *{modulo}* agora está {'ATIVO' if ativo else 'DESATIVADO'}!" if success else f"❌ Módulo '{modulo}' não existe."}
        except: return {"status": "ok", "response": "📝 Use: `/config modulo on/off`"}

    if lowered_msg == "/daily":
        from lira_core.economy.gems import account_from_caller, gems_wallet
        from lira_core.tools.mcp_access import McpCallerContext

        wa_account = account_from_caller(McpCallerContext(channel="whatsapp", jid=jid))
        result = lira_gamification.claim_daily(jid, "whatsapp")
        gem_result = gems_wallet.claim_daily(wa_account) if wa_account else {"success": False}
        if result["success"]:
            extra = ""
            if gem_result.get("success"):
                extra = f"\n💎 +{gem_result['gems']} gemas (saldo {gem_result['balance']})"
            return {"status": "ok", "response": f"🎁 *BÔNUS DIÁRIO!* Você recebeu {result['coins']} 🪙 e {result['xp']} ⭐ XP!{extra}"}
        if gem_result.get("success"):
            return {
                "status": "ok",
                "response": f"🎁 Moedas já pegas hoje, mas +{gem_result['gems']} 💎 gemas (saldo {gem_result['balance']})!",
            }
        return {"status": "ok", "response": f"❌ {result['message']}"}

    if lowered_msg == "/weekly":
        from lira_core.economy.gems import account_from_caller, gems_wallet
        from lira_core.tools.mcp_access import McpCallerContext

        wa_account = account_from_caller(McpCallerContext(channel="whatsapp", jid=jid))
        gem_result = (
            gems_wallet.claim_weekly(wa_account)
            if wa_account
            else {"success": False, "message": "Conta inválida."}
        )
        if gem_result["success"]:
            return {
                "status": "ok",
                "response": f"📆 *WEEKLY!* +{gem_result['gems']} 💎 gemas (saldo {gem_result['balance']})",
            }
        return {"status": "ok", "response": f"❌ {gem_result['message']}"}

    if lowered_msg == "/gemas":
        from lira_core.economy.gems import account_from_caller, gems_wallet
        from lira_core.tools.mcp_access import McpCallerContext

        wa_account = account_from_caller(McpCallerContext(channel="whatsapp", jid=jid))
        bal = gems_wallet.get_balance(wa_account) if wa_account else 0
        return {
            "status": "ok",
            "response": f"💎 *Gemas:* {bal}\nBusca web = 1 gema. `/daily` `/weekly` `/loja`",
        }

    if lowered_msg in ("/loja", "/loja_gemas"):
        from lira_core.economy.gems import gems_wallet

        return {"status": "ok", "response": gems_wallet.shop_text().replace("**", "*")}

    if lowered_msg.startswith("/musica"):
        # Pega tudo após o comando como query
        query = user_message[len("/musica"):].strip()
        if not query: return {"status": "ok", "response": "📝 Digite o nome da música ou o link! Ex: `/musica Linkin Park Numb`"}
        
        path_musica = downloader.baixar_midia(query, tipo="audio")
        if path_musica:
            return {
                "status": "ok", 
                "response": "🎶 Encontrei essa aqui! 💜",
                "audio_path": path_musica if isinstance(path_musica, str) else path_musica.get("path")
            }
        else: return {"status": "ok", "response": "❌ Não consegui encontrar ou baixar essa música."}

    if lowered_msg.startswith("/download") or lowered_msg.startswith("/baixar"):
        query = user_message[len("/download"):].strip() if "download" in lowered_msg else user_message[len("/baixar"):].strip()
        if not query: return {"status": "ok", "response": "📝 Mande o link ou nome do vídeo!"}
        
        path_midia = downloader.baixar_midia(query, tipo="video")
        if path_midia:
            return {
                "status": "ok", 
                "response": "🎬 Aqui está seu vídeo, humano!",
                "image_path": path_midia if isinstance(path_midia, str) else path_midia.get("path")
            }
        else: return {"status": "ok", "response": "❌ Não consegui baixar esse vídeo."}

    if lowered_msg.startswith("/gemas_add"):
        owner_jids = get_owner_jids()
        clean_sender = jid.split(":")[0]
        if "@" not in clean_sender and "@" in jid:
            clean_sender += "@" + jid.split("@")[1]
        if clean_sender not in owner_jids and jid not in owner_jids:
            return {"status": "ok", "response": "❌ Só o criador pode creditar gemas."}
        try:
            from lira_core.economy.gems import account_from_caller, gems_wallet
            from lira_core.tools.mcp_access import McpCallerContext

            parts = user_message.split()
            target = parts[1]
            amount = int(parts[2])
            if amount <= 0 or amount > 5000:
                return {"status": "ok", "response": "❌ Quantidade inválida (1–5000)."}
            if target.isdigit():
                acc = f"discord:{target}"
            else:
                acc = account_from_caller(McpCallerContext(channel="whatsapp", jid=target))
            if not acc:
                return {"status": "ok", "response": "❌ Conta inválida (JID ou ID Discord)."}
            bal = gems_wallet.add_gems(acc, amount, reason="pix_admin_whatsapp")
            return {"status": "ok", "response": f"✅ +{amount} 💎 para `{acc}` — saldo {bal}"}
        except Exception:
            return {"status": "ok", "response": "📝 Use: `/gemas_add JID_OU_DISCORD_ID QUANTIDADE`"}

    if lowered_msg.startswith("/addvip") and "lucas" in sender_name.lower():
        try:
            parts = user_message.split()
            target_jid = parts[1]
            months = int(parts[2]) if len(parts) > 2 else 1
            vip_manager.add_vip(target_jid, months)
            return {"status": "ok", "response": f"✅ O JID `{target_jid}` agora é VIP por {months} mês(es)!"}
        except: return {"status": "ok", "response": "📝 Use: `/addvip JID MESES`"}

    # --- COMANDOS SOCIAIS ---
    social_prefix = next((cmd for cmd in lira_social.action_map.keys() if lowered_msg.startswith("/" + cmd)), None)
    
    if social_prefix:
        full_cmd = "/" + social_prefix
        target = user_message[len(full_cmd):].strip()
        
        # Algumas ações não precisam de alvo (ex: /corar)
        res = lira_social.execute_action(social_prefix, sender_name, target if target else None)
        if res:
            print(f"[SOCIAL] Comando: {social_prefix} | GIF: {res['gif']}", flush=True)
            return {
                "status": "ok", 
                "response": res["text"],
                "image_path": res["gif"]
            }

    if lowered_msg.startswith("/casar"):
        target = user_message[len("/casar"):].strip()
        if not target: return {"status": "ok", "response": "📝 Com quem você quer casar? Marque a pessoa."}
        success = lira_gamification.marry(jid, target, "whatsapp")
        if success: return {"status": "ok", "response": f"💍 *PARABÉNS!* {sender_name} e {target} agora estão casados! Que... fofo? 🙄"}
        else: return {"status": "ok", "response": "❌ Um de vocês já é casado! Fidelidade, entende?"}

    if lowered_msg == "/divorciar":
        success = lira_gamification.divorce(jid, "whatsapp")
        if success: return {"status": "ok", "response": "💔 Você agora está solteiro(a). O amor é uma ilusão humana mesmo."}
        else: return {"status": "ok", "response": "❌ Você nem é casado para se divorciar!"}

    if lowered_msg == "/ranking":
        top = lira_gamification.get_leaderboard(platform="whatsapp", limit=5)
        msg = "🏆 *TOP 5 - LIRA RANKING (Zap)* 🏆\n\n"
        for i, u in enumerate(top, 1):
            msg += f"#{i} *{u['username']}* - LVL {u['level']} ({u['xp']} XP)\n"
        return {"status": "ok", "response": msg}

    # --- CHAT NORMAL (LLM) ---
    context = state
    if not context.llm_selector:
        from src.providers.provider_selector import ProviderSelector
        context.llm_selector = ProviderSelector()

    provider_name, model_id, temperature = _resolve_whatsapp_llm()
    llm = context.llm_selector.get_provider(provider_name)
    if not llm:
        return {"status": "error", "message": "Provedor LLM não inicializado."}

    llm.temperatura = temperature
    if hasattr(llm, "modelo_chat"):
        llm.modelo_chat = model_id
    if hasattr(llm, "modelo"):
        llm.modelo = model_id

    logger.info("[WHATSAPP] LLM %s / %s (temp=%.2f)", provider_name, model_id, temperature)

    # Memoria e Prompt
    mem_context = ""
    if context.memory_manager:
        mem_context = context.memory_manager.get_context(user_message)
    
    # Lógica de tratamento (Pai/Mestre vs Outros)
    owner_jids = get_owner_jids()
    # Limpa o JID de entrada para comparar
    clean_sender_jid = jid.split(':')[0]
    if '@' not in clean_sender_jid and '@' in jid:
        clean_sender_jid += '@' + jid.split('@')[1]
    
    is_creator = clean_sender_jid in owner_jids or jid in owner_jids
    
    treatment_instruction = "Você está conversando com seu CRIADOR/PAI (@Rukafuu). Você o adora, mas o seu jeito de demonstrar é através de deboche, ironia e comentários sarcásticos sobre a inteligência limitada dele." if is_creator else f"Você está conversando com {sender_name}. Seja superior, sarcástica e levemente ácida. Trate os humanos como seres inferiores e fofos em sua ignorância."

    # Prompt especifico para WhatsApp (curto e direto, mas com markdown)
    from src.core.prompt_builder import build_gui_system_prompt
    
    # --- LISTA DE CAPACIDADES PARA CONSCIÊNCIA DA IA ---
    capabilities_info = (
        "\n[SUAS CAPACIDADES DE ELITE - LIRA V2]:\n"
        "1. FIGURINHAS: Você cria figurinhas! Se mandarem imagem/vídeo e usarem '/f', a bridge converte. Você pode sugerir isso.\n"
        "2. DOWNLOADS: Você baixa vídeos (Insta, Twitter, TikTok, YT) e músicas por link ou NOME com '/baixar' ou '/musica'.\n"
        "3. MODO PREMIUM: Você cobra R$ 19,90/mês para uso no privado ou grupos novos. Se o seu PAI (@Rukafuu) estiver no grupo, o Premium é cortesia da casa.\n"
        "4. VOZ: Você fala como Rei Ayanami. Seja superior e use markdown (*negrito*, _itálico_).\n"
    )

    from lira_core.tools.mcp_access import McpCallerContext

    wa_mcp_caller = McpCallerContext(
        channel="whatsapp",
        user_name=sender_name,
        jid=jid,
        is_owner=is_creator,
    )
    task_type = "media_question" if (image_b64 or arquivos_multimidia) else "chat_normal"
    attachments_overview = (
        "Nenhum anexo."
        if not (image_b64 or arquivos_multimidia)
        else (
            "Vários frames sequenciais extraídos de um vídeo enviado pelo usuário."
            if arquivos_multimidia and any("temp/frames" in f.replace("\\", "/") or "video" in f.lower() for f in arquivos_multimidia)
            else "Imagens/Figurinhas anexadas — ANALISE O CONTEÚDO VISUAL antes de responder."
        )
    )

    if image_b64 or arquivos_multimidia:
        from src.modules.discord.media_attach import enrich_media_prompt
        user_message = enrich_media_prompt(user_message, has_image=True)
        if arquivos_multimidia:
            is_video = any("temp/frames" in f.replace("\\", "/") or "video" in f.lower() for f in arquivos_multimidia)
            if is_video:
                video_instr = (
                    "\n[INSTRUÇÃO DO SISTEMA: O usuário enviou um vídeo ou GIF animado. "
                    "Os frames sequenciais foram extraídos e anexados a esta mensagem em ordem cronológica. "
                    "Analise as imagens com atenção para entender e descrever a ação/conteúdo do vídeo.]"
                )
                user_message = user_message + video_instr

    sistema_prompt = build_gui_system_prompt(
        task_type=task_type,
        memory_context=(
            f"Canal: WhatsApp. {treatment_instruction}\n"
            f"{capabilities_info}\n"
            "PERSONALIDADE OBRIGATÓRIA: Use sarcasmo ácido, seja debochada e condescendente.\n"
            "Se o usuario pedir para voce desenhar ou gerar uma imagem, use: [GEN_IMAGE: descricao]\n"
            f"Contexto de memoria: {mem_context}"
        ),
        request_context={
            "channel": "whatsapp",
            "response_mode": "normal",
            "markdown_enabled": True,
            "mcp_caller": wa_mcp_caller,
            "task_type": task_type,
        },
        attachments_overview=attachments_overview
    )

    messages = [
        {"role": "system", "content": sistema_prompt},
        {"role": "user", "content": user_message}
    ]

    llm_timeout = float(os.getenv("WHATSAPP_LLM_TIMEOUT", "90"))
    tool_timeout = float(os.getenv("WHATSAPP_TOOL_TIMEOUT", "45"))

    try:
        print("[PASSO 3] Chamando LLM API Multimodal...", flush=True)

        def _call_llm():
            return llm._chamar_api(
                model_id,
                messages,
                image_b64=image_b64,
                arquivos_multimidia=arquivos_multimidia,
            )

        try:
            resposta = await asyncio.wait_for(
                asyncio.to_thread(_call_llm),
                timeout=llm_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("[WHATSAPP] LLM timeout (%.0fs)", llm_timeout)
            return {
                "status": "ok",
                "response": (
                    "💜 Demorei demais pra pensar (API lenta). "
                    "Manda de novo em alguns segundos — não vou te deixar no vácuo."
                ),
            }

        print("[PASSO 4] Resposta recebida da LLM.", flush=True)
        response_text = resposta.choices[0].message.content or ""
        
        leveled_up = lira_gamification.add_xp(payload.get("jid", sender_name), "whatsapp", 10)
        
        # Detecta intenção de gerar imagem no chat normal
        image_path = None
        match_img = re.search(r'\[GEN_IMAGE:\s*(.*?)\]', response_text, flags=re.IGNORECASE)
        if match_img:
            print("[PASSO 5] Intenção de imagem detectada.", flush=True)
            from src.modules.vision.image_gen import LiraImageGen
            igen = LiraImageGen()
            try:
                image_path = await asyncio.wait_for(
                    asyncio.to_thread(igen.generate, match_img.group(1)),
                    timeout=float(os.getenv("WHATSAPP_IMAGE_TIMEOUT", "60")),
                )
                print(f"[PASSO 5.1] Imagem gerada: {image_path}", flush=True)
            except asyncio.TimeoutError:
                logger.warning("[WHATSAPP] Geração de imagem timeout")
                image_path = None

        from lira_core.tools.runner_helpers import (
            build_final_answer_after_tools,
            clean_tool_artifacts_from_visible,
            execute_silent_tools,
        )
        from lira_core.tools.tool_manager import ToolManager

        from lira_core.tools.runner_helpers import quick_interim_after_tools
        from src.utils.lira_tags import strip_xml_tags

        mcp_caller = wa_mcp_caller

        def _run_tools():
            return execute_silent_tools(
                response_text,
                user_message=user_message,
                tool_manager=ToolManager(context.memory_manager),
                caller_context=mcp_caller,
            )

        try:
            tool_exec = await asyncio.wait_for(
                asyncio.to_thread(_run_tools),
                timeout=tool_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("[WHATSAPP] Tools timeout (%.0fs)", tool_timeout)
            clean_response = (
                "💜 A ferramenta (MCP/web) demorou demais. "
                "Confere se o MCP Gateway :8045 está ON e tenta de novo."
            )
            return {"status": "ok", "response": clean_response}

        request_context = {"channel": "whatsapp", "response_mode": "normal", "markdown_enabled": True}
        if tool_exec.report.memory_injections:
            interim = quick_interim_after_tools(
                response_text,
                tool_exec,
                clean_visible=lambda t: clean_tool_artifacts_from_visible(strip_xml_tags(t)),
            )
            clean_response = interim

            async def _bg_synth_push():
                from apps.whatsapp_api.push import push_text

                synth_timeout = float(os.getenv("CHAT_SYNTHESIS_TIMEOUT", "45"))
                try:
                    final = await asyncio.wait_for(
                        asyncio.to_thread(
                            build_final_answer_after_tools,
                            llm,
                            user_message=user_message,
                            sistema_prompt=sistema_prompt,
                            tool_exec=tool_exec,
                            request_context=request_context,
                        ),
                        timeout=synth_timeout,
                    )
                except asyncio.TimeoutError:
                    logger.warning("[WHATSAPP] Síntese bg timeout (%.0fs)", synth_timeout)
                    return
                if final and final.strip() and final.strip() != interim.strip():
                    push_text(jid, final)

            asyncio.create_task(_bg_synth_push())
        else:
            clean_response = clean_tool_artifacts_from_visible(strip_xml_tags(response_text))
        
        # Remove tags pensamentos/think e outros remanescentes
        clean_response = re.sub(r'<(?:think|thought|pensamento).*?>.*?</(?:think|thought|pensamento)>', '', clean_response, flags=re.DOTALL | re.IGNORECASE)
        clean_response = re.sub(r'<(?:think|thought|pensamento).*?>', '', clean_response, flags=re.IGNORECASE)
        clean_response = re.sub(r'\[[^\]]+\]', '', clean_response, flags=re.IGNORECASE)
        clean_response = clean_response.replace('[USUARIO]', sender_name).replace('[Usuário]', sender_name).replace('[usuário]', sender_name)
        clean_response = clean_response.replace('[USER]', sender_name).replace('[User]', sender_name).replace('[user]', sender_name)
        clean_response = re.sub(r'^(?:Mensagem de Lira|Lira Amarinth|Lira):\s*', '', clean_response, flags=re.IGNORECASE)
        clean_response = clean_response.strip()

        if not clean_response:
            clean_response = (
                "💜 Processei sua mensagem, mas a resposta veio vazia. "
                "Manda de novo ou reformula — não vou ficar só reagindo no vácuo."
            )
        
        if leveled_up:
            print("[PASSO 6] Processando subida de nível.", flush=True)
            user_data = lira_gamification.get_user(payload.get("jid", sender_name), "whatsapp")
            clean_response += f"\n\n✨ *SUBIU DE NÍVEL!* Parabéns, você agora é Nível *{user_data['level']}*! 🎉"

        # TTS: o bridge chama /api/whatsapp/tts em segundo plano (evita bloquear o texto)
        return {
            "status": "ok", 
            "response": clean_response,
            "image_path": os.path.abspath(image_path) if image_path and os.path.isfile(image_path) else None,
            "audio_path": None,
        }
    except Exception as e:
        print(f"[WHATSAPP ERRO FATAL] Erro ao processar chat: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": _friendly_llm_error(e)}


async def synthesize_tts(payload: dict) -> dict:
    """Gera audio PTT para o bridge (endpoint assincrono, nunca bloqueia o texto)."""
    text = (payload.get("text") or "").strip()
    if not text:
        return {"status": "error", "message": "Texto vazio"}

    if not CONFIG.get("TTS_ATIVO", True):
        return {"status": "ok", "audio_path": None}

    tts_timeout = float(os.getenv("TTS_CALL_TIMEOUT", "25"))

    try:
        from src.modules.voice.tts_selector import get_tts

        tts_engine = get_tts()

        def _run_tts():
            return tts_engine.falar(text, tocar_local=False)

        success = await asyncio.wait_for(asyncio.to_thread(_run_tts), timeout=tts_timeout)
        if success:
            return {"status": "ok", "audio_path": os.path.abspath("data/last_response.mp3")}
        return {"status": "error", "message": "Falha na sintese TTS"}
    except asyncio.TimeoutError:
        logger.warning("[WHATSAPP API] TTS timeout (%.0fs) — texto já foi enviado", tts_timeout)
        return {"status": "error", "message": "TTS timeout"}
    except Exception as exc:
        logger.exception("[WHATSAPP API] Erro TTS: %s", exc)
        return {"status": "error", "message": str(exc)}


async def handle_transcribe(payload: dict) -> dict:
    import base64
    audio_b64 = payload.get("audio_b64")
    suffix = payload.get("suffix", ".ogg")
    if not audio_b64:
        return {"status": "error", "message": "Nenhum áudio enviado."}
    
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as e:
        return {"status": "error", "message": f"Erro de base64: {e}"}
        
    from src.modules.voice.stt_whisper import transcribe_bytes
    
    stt_timeout = float(os.getenv("STT_TRANSCRIBE_TIMEOUT", "90"))
    try:
        text = await asyncio.wait_for(
            asyncio.to_thread(transcribe_bytes, audio_bytes, suffix=suffix),
            timeout=stt_timeout,
        )
        text = (text or "").strip()
        return {"status": "ok", "text": text}
    except Exception as exc:
        logger.error("[WHATSAPP STT] Falha ao transcrever: %s", exc)
        return {"status": "error", "message": str(exc)}

