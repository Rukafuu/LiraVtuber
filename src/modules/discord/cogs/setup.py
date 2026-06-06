"""
╔══════════════════════════════════════════════════════════════╗
║  LiraVT · Cog: Setup de Servidor (Template)                 ║
║  Recria a estrutura profissional do servidor do zero        ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands
import asyncio
from ..constants import logger, EMOJI

class SetupServer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setup-servidor", description="Cria a estrutura RPG completa do servidor (cargos e canais).")
    @commands.has_permissions(administrator=True)
    async def setup_servidor(self, ctx: commands.Context, apagar_tudo: bool = False):
        guild = ctx.guild
        
        await ctx.send(
            f"{EMOJI.get('loading', '⏳')} Forjando a nova guilda! Isso vai levar um minuto...\n"
            f"*(Apagar canais e cargos antigos: {'Sim ⚠️' if apagar_tudo else 'Não ✅'})*"
        )

        try:
            # Canais protegidos da foice (Mudae Rolls e Karuta Drop)
            CANAIS_PROTEGIDOS = {1497846216858271824, 1502719153352474724}

            # 1. Apagar canais e cargos se solicitado
            if apagar_tudo:
                # Apagar canais
                for channel in guild.channels:
                    if channel.id not in CANAIS_PROTEGIDOS and channel.id != ctx.channel.id:
                        try:
                            await channel.delete(reason="Setup RPG do servidor (Nuke)")
                        except discord.Forbidden:
                            pass
                        except Exception as e:
                            logger.warning(f"[SETUP] Erro ao deletar canal {channel.name}: {e}")
                
                # Apagar cargos velhos (ignorando roles do bot e @everyone)
                for role in guild.roles:
                    if role.name != "@everyone" and not role.managed:
                        if role < guild.me.top_role:
                            try:
                                await role.delete(reason="Setup RPG (Nuke cargos)")
                                logger.info(f"[SETUP] Cargo {role.name} apagado.")
                            except discord.Forbidden:
                                logger.warning(f"[SETUP] Sem permissão para apagar cargo {role.name} (Forbidden).")
                        else:
                            logger.warning(f"[SETUP] Cargo {role.name} é maior ou igual ao top_role do bot ({guild.me.top_role.name}), ignorando.")

            # 2. Criar Cargos (Temática RPG / Medieval)
            roles_to_create = [
                {"name": "Game Master Reskyume", "color": discord.Color.dark_red(), "hoist": True, "permissions": discord.Permissions(administrator=True)},
                {"name": "Deusa Lira", "color": discord.Color.from_rgb(255, 105, 180), "hoist": True, "permissions": discord.Permissions(administrator=True)},
                {"name": "Princesa Alice", "color": discord.Color.gold(), "hoist": True, "permissions": discord.Permissions(administrator=True)},
                {"name": "Paladino", "color": discord.Color.dark_blue(), "hoist": True, "permissions": discord.Permissions(administrator=True)},
                {"name": "Druida", "color": discord.Color.dark_green(), "hoist": True, "permissions": discord.Permissions(manage_messages=True, kick_members=True, ban_members=True, manage_roles=True)},
                {"name": "Guerreiro", "color": discord.Color.orange(), "hoist": True, "permissions": discord.Permissions(manage_messages=True)},
                {"name": "Maçom", "color": discord.Color.dark_grey(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Vtuber", "color": discord.Color.purple(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Patronos", "color": discord.Color.gold(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Mercador", "color": discord.Color.magenta(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Bardo", "color": discord.Color.teal(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Inscrito", "color": discord.Color.red(), "hoist": False, "permissions": discord.Permissions.none()},
                {"name": "Cozinheiro", "color": discord.Color.light_grey(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Waifu Hunter", "color": discord.Color.from_rgb(255, 192, 203), "hoist": False, "permissions": discord.Permissions.none()},
                {"name": "Cartomante", "color": discord.Color.dark_magenta(), "hoist": False, "permissions": discord.Permissions.none()},
                {"name": "Maestros", "color": discord.Color.from_rgb(200, 200, 255), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Clérigos", "color": discord.Color.blurple(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Vassalo", "color": discord.Color.dark_orange(), "hoist": False, "permissions": discord.Permissions.none()},
                {"name": "Bobo da Corte", "color": discord.Color.darker_grey(), "hoist": False, "permissions": discord.Permissions.none()},
            ]

            created_roles = {}
            active_roles = await guild.fetch_roles()
            for role_data in roles_to_create:
                existing = discord.utils.get(active_roles, name=role_data["name"])
                if existing:
                    created_roles[role_data["name"]] = existing
                else:
                    try:
                        new_role = await guild.create_role(
                            name=role_data["name"],
                            color=role_data["color"],
                            hoist=role_data["hoist"],
                            permissions=role_data["permissions"],
                            reason="Setup RPG do servidor"
                        )
                        created_roles[role_data["name"]] = new_role
                    except discord.Forbidden:
                        pass

            # Distribuir os cargos específicos para os usuários devidos!
            try:
                # GM Reskyume para o autor do comando
                if created_roles.get("Game Master Reskyume"):
                    await ctx.author.add_roles(created_roles["Game Master Reskyume"])
                
                # Deusa Lira para o bot
                if created_roles.get("Deusa Lira"):
                    await guild.me.add_roles(created_roles["Deusa Lira"])

                # Princesa Alice
                princesa = guild.get_member(1286993561732124733)
                if princesa and created_roles.get("Princesa Alice"):
                    await princesa.add_roles(created_roles["Princesa Alice"])
                
                # Clérigos para os Bots, Maestros para membros normais
                role_clerigos = created_roles.get("Clérigos")
                role_maestros = created_roles.get("Maestros")
                
                for member in guild.members:
                    if member.bot and role_clerigos:
                        await member.add_roles(role_clerigos)
                    elif not member.bot and role_maestros:
                        await member.add_roles(role_maestros)
            except Exception as e:
                logger.warning(f"Erro ao distribuir cargos: {e}")

            # Permissões Mute (Bobo da Corte)
            role_bobo = created_roles.get("Bobo da Corte")
            bobo_overwrites = discord.PermissionOverwrite(send_messages=False, add_reactions=False, speak=False)

            # Permissões base
            default_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            if role_bobo:
                default_overwrites[role_bobo] = bobo_overwrites

            readonly_overwrites = dict(default_overwrites)
            readonly_overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
            
            staff_overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False)
            }
            for staff_role_name in ["Game Master Reskyume", "Deusa Lira", "Paladino", "Druida", "Guerreiro"]:
                if created_roles.get(staff_role_name):
                    staff_overwrites[created_roles[staff_role_name]] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            # Identificando bots conhecidos
            spam_bots = [m for m in guild.members if m.bot and any(name in m.name.lower() for name in ["karuta", "mudae", "tatsu", "carl", "zerotwo", "mee6"])]
            com_overwrites = dict(default_overwrites)
            for bot_member in spam_bots:
                com_overwrites[bot_member] = discord.PermissionOverwrite(send_messages=False)
            
            nsfw_overwrites = dict(com_overwrites)
            nsfw_overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False) 

            # 3. Criar Categorias e Canais
            info_cat = await guild.create_category("🏰 O REINO", overwrites=readonly_overwrites, reason="Setup RPG")
            await guild.create_text_channel("📜-regras", category=info_cat)
            await guild.create_text_channel("📯-anuncios", category=info_cat)
            avisos_ch = await guild.create_text_channel("⚠️-avisos", category=info_cat)
            await guild.create_text_channel("👋-boas-vindas", category=info_cat)
            await guild.create_text_channel("📅-eventos", category=info_cat)
            
            comunidade_cat = await guild.create_category("🏘️ A VILA", overwrites=com_overwrites, reason="Setup RPG")
            await guild.create_text_channel("💬-chat-geral", category=comunidade_cat)
            await guild.create_text_channel("🤥-taverna-das-mentiras", category=comunidade_cat, topic="Pode mentir à vontade!")
            await guild.create_text_channel("⛪-confessionario", category=comunidade_cat)
            await guild.create_text_channel("🖼️-midias-sfw", category=comunidade_cat)
            await guild.create_text_channel("🎨-fanarts-sfw", category=comunidade_cat)
            nsfw_ch = await guild.create_text_channel("🔞-beco-escuro-nsfw", category=comunidade_cat, nsfw=True)

            bots_cat = await guild.create_category("🎲 GUILDA DOS BOTS", overwrites=default_overwrites, reason="Setup RPG")
            await guild.create_text_channel("🤖-comandos-gerais", category=bots_cat)
            
            spam_overwrites = dict(default_overwrites)
            for bot_member in spam_bots:
                spam_overwrites[bot_member] = discord.PermissionOverwrite(send_messages=True)
            await guild.create_text_channel("🎴-cartas-e-waifus", category=bots_cat, overwrites=spam_overwrites, topic="Spam de Karuta, Mudae, etc.")

            for ch_id in CANAIS_PROTEGIDOS:
                protected_ch = guild.get_channel(ch_id)
                if protected_ch:
                    try:
                        await protected_ch.edit(category=bots_cat, reason="Movendo canal protegido para Guilda dos Bots")
                    except Exception:
                        pass

            voz_cat = await guild.create_category("🗣️ PRAÇA DE CONVIVÊNCIA", reason="Setup RPG")
            await guild.create_voice_channel("🔊 Voz Infinito", category=voz_cat)
            await guild.create_voice_channel("🎮 Jogatina", category=voz_cat)
            afk_channel = await guild.create_voice_channel("💤 Fosso (AFK)", category=voz_cat)
            try:
                await guild.edit(afk_channel=afk_channel, afk_timeout=300, reason="Setup AFK")
            except Exception:
                pass

            staff_cat = await guild.create_category("⚔️ SALA DO TRONO", overwrites=staff_overwrites, reason="Setup RPG")
            await guild.create_text_channel("🛡️-staff-chat", category=staff_cat)
            await guild.create_text_channel("📜-logs-usuarios", category=staff_cat)
            await guild.create_text_channel("🤖-logs-bots", category=staff_cat)
            await guild.create_voice_channel("🤫 Voz Secreta", category=staff_cat)

            embed = discord.Embed(
                title="✨ O Reino foi Forjado com Sucesso!",
                description="Sua nova guilda RPG está pronta!",
                color=0xf5a3c7
            )
            embed.add_field(name="🛡️ Cargos", value="Cargos criados e **distribuídos aos membros automaticamente**!", inline=False)
            embed.add_field(name="🗺️ Categorias", value="O Reino, A Vila, Guilda dos Bots, Praça de Convivência e Sala do Trono.", inline=False)
            
            if spam_bots:
                bots_names = ", ".join([b.name for b in spam_bots])
                embed.add_field(
                    name="⚠️ Clérigos Mecânicos (Bots)", 
                    value=f"Proibi bots como **{bots_names}** de falarem na Vila.", 
                    inline=False
                )

            await ctx.send(content=ctx.author.mention, embed=embed)
            
            if avisos_ch:
                await avisos_ch.send(
                    f"@everyone 🎇 **A Deusa Lira sorri para vocês! O Reino foi completamente forjado!**\n\n"
                    f"Sejam todos bem-vindos à nova estrutura do servidor."
                )
            
            logger.info(f"[SETUP] Reino RPG {guild.name} forjado por {ctx.author}.")

        except Exception as e:
            logger.error(f"[SETUP] Erro na reestruturação do servidor {guild.name}: {e}")
            await ctx.send(f"❌ Ocorreu um erro ao tentar recriar o servidor: {e}")

    @setup_servidor.error
    async def setup_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Você precisa ser um Administrador para usar este comando!")

    @commands.command(name="setup-cargos", description="Recria apenas os cargos RPG do servidor.")
    @commands.has_permissions(administrator=True)
    async def setup_cargos(self, ctx: commands.Context, apagar_antigos: bool = False):
        guild = ctx.guild
        
        await ctx.send(
            f"{EMOJI.get('loading', '⏳')} Forjando a hierarquia do Reino!...\n"
            f"*(Apagar antigos: {'Sim ⚠️' if apagar_antigos else 'Não ✅'})*"
        )

        try:
            if apagar_antigos:
                for role in guild.roles:
                    if role.name != "@everyone" and not role.managed:
                        if role < guild.me.top_role:
                            try:
                                await role.delete(reason="Setup de Cargos RPG (Reset)")
                                logger.info(f"[SETUP] Cargo {role.name} apagado.")
                            except discord.Forbidden:
                                logger.warning(f"[SETUP] Sem permissão para apagar cargo {role.name} (Forbidden).")
                        else:
                            logger.warning(f"[SETUP] Cargo {role.name} é maior ou igual ao top_role do bot ({guild.me.top_role.name}), ignorando.")

            roles_to_create = [
                {"name": "Game Master Reskyume", "color": discord.Color.dark_red(), "hoist": True, "permissions": discord.Permissions(administrator=True)},
                {"name": "Deusa Lira", "color": discord.Color.fromrgb(255, 105, 180), "hoist": True, "permissions": discord.Permissions(administrator=True)},
                {"name": "Princesa Alice", "color": discord.Color.gold(), "hoist": True, "permissions": discord.Permissions(administrator=True)},
                {"name": "Paladino", "color": discord.Color.dark_blue(), "hoist": True, "permissions": discord.Permissions(administrator=True)},
                {"name": "Druida", "color": discord.Color.dark_green(), "hoist": True, "permissions": discord.Permissions(manage_messages=True, kick_members=True, ban_members=True, manage_roles=True)},
                {"name": "Guerreiro", "color": discord.Color.orange(), "hoist": True, "permissions": discord.Permissions(manage_messages=True)},
                {"name": "Maçom", "color": discord.Color.dark_grey(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Vtuber", "color": discord.Color.purple(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Patronos", "color": discord.Color.gold(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Mercador", "color": discord.Color.magenta(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Bardo", "color": discord.Color.teal(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Inscrito", "color": discord.Color.red(), "hoist": False, "permissions": discord.Permissions.none()},
                {"name": "Cozinheiro", "color": discord.Color.light_grey(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Waifu Hunter", "color": discord.Color.from_rgb(255, 192, 203), "hoist": False, "permissions": discord.Permissions.none()},
                {"name": "Cartomante", "color": discord.Color.dark_magenta(), "hoist": False, "permissions": discord.Permissions.none()},
                {"name": "Maestros", "color": discord.Color.from_rgb(200, 200, 255), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Clérigos", "color": discord.Color.blurple(), "hoist": True, "permissions": discord.Permissions.none()},
                {"name": "Vassalo", "color": discord.Color.dark_orange(), "hoist": False, "permissions": discord.Permissions.none()},
                {"name": "Bobo da Corte", "color": discord.Color.darker_grey(), "hoist": False, "permissions": discord.Permissions.none()},
            ]

            created_roles = {}
            active_roles = await guild.fetch_roles()
            for role_data in roles_to_create:
                existing = discord.utils.get(active_roles, name=role_data["name"])
                if existing:
                    created_roles[role_data["name"]] = existing
                else:
                    try:
                        new_role = await guild.create_role(
                            name=role_data["name"],
                            color=role_data["color"],
                            hoist=role_data["hoist"],
                            permissions=role_data["permissions"],
                            reason="Setup de Cargos RPG"
                        )
                        created_roles[role_data["name"]] = new_role
                    except discord.Forbidden:
                        pass
            
            # Distribuir os cargos específicos para os usuários devidos!
            try:
                if created_roles.get("Game Master Reskyume"):
                    await ctx.author.add_roles(created_roles["Game Master Reskyume"])
                
                if created_roles.get("Deusa Lira"):
                    await guild.me.add_roles(created_roles["Deusa Lira"])

                princesa = guild.get_member(1286993561732124733)
                if princesa and created_roles.get("Princesa Alice"):
                    await princesa.add_roles(created_roles["Princesa Alice"])
                
                role_clerigos = created_roles.get("Clérigos")
                role_maestros = created_roles.get("Maestros")
                
                for member in guild.members:
                    if member.bot and role_clerigos:
                        await member.add_roles(role_clerigos)
                    elif not member.bot and role_maestros:
                        await member.add_roles(role_maestros)
            except Exception as e:
                logger.warning(f"Erro ao distribuir cargos: {e}")

            await ctx.send(f"✨ **Hierarquia Pronta!** Criei os cargos e designei os usuários.")

        except Exception as e:
            logger.error(f"[SETUP] Erro na reestruturação de cargos do servidor {guild.name}: {e}")
            await ctx.send(f"❌ Ocorreu um erro ao tentar recriar os cargos: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupServer(bot))
    logger.info("[DISCORD] ✅ Cog SetupServer carregada")
