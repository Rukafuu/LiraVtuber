import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re
from ..constants import EMOJI, THINKING_MSG, logger
from src.providers.provider_selector import ProviderSelector
from src.memory.memory_manager import LiraMemoryManager
from src.modules.vision.image_gen import LiraImageGen
from src.config.config_loader import CONFIG
from src.core.request_profiles import build_request_context

class ChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.llm_selector = ProviderSelector()
        self.memory_manager = LiraMemoryManager()
        self.image_gen = LiraImageGen()

    async def _responder(self, texto_usuario, author_name, image_b64=None):
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get("openrouter", {})
        model_id = prov_cfg.get("modelo_chat", "openrouter/owl-alpha")
        
        # Constrói o contexto usando a função correta
        context = build_request_context(
            channel="control_center_chat", # Canal que permite markdown e chat longo
            task_type="chat_normal"
        )
        
        # Sistema de Identidade (Prompt Base)
        from src.core.prompt_builder import load_prompt_assets
        assets = load_prompt_assets()
        
        system_prompt = f"=== [NÚCLEO DE PERSONALIDADE: LIRA AMARINTH] ===\n{assets.personality}\n\n" \
                        f"=== [PROTOCOLO DISCORD] ===\n" \
                        f"Você está no Discord. Responda com deboche, sarcasmo e superioridade.\n" \
                        f"REGRA OBRIGATÓRIA DE EMOJIS: NUNCA use emojis padrão do Windows (como 🌸, 😈, 😂).\n" \
                        f"Use APENAS os emojis customizados do Discord listados abaixo. Coloque-os no final de frases impactantes.\n" \
                        f"Use seu tic de fala ('entendi', 'entende' ou 'entendo') organicamente.\n"
        
        if image_b64:
            system_prompt += "\n[MODO VISÃO ATIVADO]: O usuário enviou uma imagem. Comente sobre ela com seu deboche habitual. Descreva o que vê se for algo ridículo ou fofo (para você, tudo humano é ridículo).\n"
            logger.info(f"[DISCORD] Modo Visão ativado para {author_name}")

        # Injeta emojis
        emoji_instr = "\n[LISTA DE EMOJIS DISCORD PERMITIDOS]:\n"
        for name, code in EMOJI.items():
            if name != "loading": emoji_instr += f"- Use para {name}: {code}\n"
        system_prompt += emoji_instr

        llm = self.llm_selector.get_provider()
        
        # Chama a API em uma thread separada para não travar o loop do Discord
        response = await asyncio.to_thread(
            llm.gerar_resposta,
            chat_history=[], 
            sistema_prompt=system_prompt,
            user_message=f"Mensagem de {author_name}: {texto_usuario}",
            image_b64=image_b64
        )

        # Pós-processamento de tags de emoção e parâmetros
        def get_emoji_code(name):
            name = name.lower().replace(":", "").strip()
            return EMOJI.get(name, None)

        # 1. Limpa PARAMS e tags técnicas do VTS
        processed = re.sub(r'\[+PARAM:.*?\]+', '', response, flags=re.IGNORECASE | re.DOTALL)

        # 2. Normaliza [EMOTION:nome] para :nome: (facilita o processamento)
        processed = re.sub(r'\[+EMOTION:(.*?)\]+', r':\1:', processed, flags=re.IGNORECASE)

        # 3. Agora converte todos os :nome: para o código real do Discord
        # Usamos um regex que garante que não estamos pegando algo que já é um emoji
        def final_emoji_replace(match):
            name = match.group(1).lower().strip()
            code = get_emoji_code(name)
            if code:
                return f" {code} "
            return match.group(0) # Mantém o texto se não for um emoji conhecido

        processed = re.sub(r'(?<!<):([a-zA-Z0-9_]+):', final_emoji_replace, processed)
        
        # 4. Limpa sobras de tags mal formatadas
        processed = re.sub(r'\[+[a-zA-Z0-9_]+:[^\]]*\]+', '', processed)
        
        # 5. Limpa quebras de linha excessivas e espaços duplos
        processed = re.sub(r'\n{3,}', '\n\n', processed)
        processed = re.sub(r' +', ' ', processed)
        
        logger.info(f"[DISCORD DEBUG] Final: {processed[:100]}...")
        
        return processed.strip()

    @app_commands.command(name="chat", description="Fale diretamente com a Lira Amarinth 🌸")
    @app_commands.describe(mensagem="O que você quer dizer para a Lira?")
    async def chat(self, interaction: discord.Interaction, mensagem: str):
        await interaction.response.defer(thinking=True)
        try:
            response = await self._responder(mensagem, interaction.user.display_name)
            await interaction.followup.send(response[:2000])
        except Exception as e:
            logger.error(f"[DISCORD] Erro no chat: {e}")
            await interaction.followup.send(f"{EMOJI['what']} Deu erro aqui!")

    @app_commands.command(name="imaginar", description="Pede para a Lira gerar uma imagem 🎨")
    @app_commands.describe(prompt="Descreva a imagem que você quer que eu desenhe")
    async def imaginar(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer(thinking=True)
        path = await asyncio.to_thread(self.image_gen.generate, prompt)
        if path:
            await interaction.followup.send(file=discord.File(path, filename="lira_art.png"))
        else:
            await interaction.followup.send("Não consegui desenhar isso...")

async def setup(bot):
    await bot.add_cog(ChatCog(bot))
