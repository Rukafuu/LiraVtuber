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

    async def _responder(self, texto_usuario, author_name):
        prov_cfg = CONFIG.get("LLM_PROVIDERS", {}).get("openrouter", {})
        model_id = prov_cfg.get("modelo_chat", "openrouter/owl-alpha")
        
        # Constrói o contexto usando a função correta
        context = build_request_context(
            channel="control_center_chat", # Canal que permite markdown e chat longo
            task_type="chat_normal"
        )
        
        # Sistema de Identidade (Prompt Base)
        system_prompt = f"Você é a Lira Amarinth, uma VTuber sarcástica e inteligente. " \
                        f"Responda de forma natural e use o contexto do Discord."
        
        # Injeta emojis
        emoji_instr = "\n[EMOJIS DISPONÍVEIS]:\n"
        for name, code in EMOJI.items():
            if name != "loading": emoji_instr += f"- {name}: {code}\n"
        system_prompt += emoji_instr

        llm = self.llm_selector.get_provider()
        return await llm.gerar_resposta(
            chat_history=[], 
            sistema_prompt=system_prompt,
            user_message=f"Mensagem de {author_name}: {texto_usuario}"
        )

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
