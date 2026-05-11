const { 
    default: makeWASocket, 
    useMultiFileAuthState, 
    DisconnectReason,
    fetchLatestBaileysVersion
} = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const path = require('path');
const fs = require('fs');

// ── Textos de Ajuda (formatação WhatsApp) ─────────────────────────────────────

const HELP_GERAL = `💜 *Lira Amarinth — Comandos*

💬 *Chat*
• Só me chame pelo nome ou mande mensagem no privado!
• Em grupos, me mencione ou diga "Lira"

🎮 *Seções de comandos:*
• */ajuda* — Esta mensagem
• */economia* — Moedas e XP 💰
• */social* — Interações 🫂
• */midia* — Figurinhas e Downloads 🎬
• */premium* — Vantagens VIP 💎
• */sobre* — Quem sou eu?

_Digite qualquer um para mais detalhes!_ ✨`;

const HELP_MIDIA = `🎬 *Mídia — Lira Amarinth*

• */f* — Transforma imagem/vídeo em figurinha (mande na legenda) 🖼️
• */baixar [link]* — Baixa vídeo do Insta, Twitter, TikTok ou YT 🎥
• */musica [link]* — Extrai o áudio em MP3 de vídeos 🎶

_Funcionalidades exclusivas para membros VIP!_ 💜`;

const HELP_PREMIUM = `💎 *Lira Premium — Assinatura*

Torne-se um apoiador e desbloqueie o potencial máximo da Lira!

✨ *Vantagens:*
• Uso ilimitado no Privado
• Permissão para me adicionar em novos grupos
• Comandos de Mídia e Downloads
• Prioridade no processamento

💰 *Valor:* R$ 19,90/mês
🏦 *PIX (Chave):* +5511981826659

_Após o pagamento, envie o comprovante para meu criador!_ 👑`;

const HELP_ECONOMIA = `💰 *Economia — Lira Amarinth*

• */daily* — Bônus diário de moedas 🎁
• */perfil* — Seu nível, XP e saldo 💜
• */ranking* — Top jogadores 🏆
• */depositar [valor]* — Guardar no banco 🏦
• */sacar [valor]* — Retirar do banco 💸
• */roubar [nome]* — Tentar roubar alguém 🥷
  _→ 50% de chance, risco de multa!_

_Moedas ficam salvas entre plataformas_ 🔗`;

const HELP_SOCIAL = `🫂 *Interações — Lira Amarinth*

*Com alvo (ex: /abracar João):*
• */abracar* • */beijar* • */cafune*
• */tapa* • */morder* • */cutucar*
• */socar* • */chutar* • */arremessar*
• */matar* • */aconchegar* • */alimentar*
• */highfive* • */acenar* • */apertar_mao*
• */beijo_rapido* • */mao* • */olhar*
• */comer* • */xingar*

*Expressões próprias:*
• */dançar* • */chorar* • */rir* • */feliz*
• */pensar* • */dormir* • */corar* • */sorrir*
• */bocejar* • */espreitar* • */piscar*
• */joinha* • */triste* • */facepalm*
• */correr* • */concordar* • */satisfeito*

_Todos geram GIFs de anime!_ 🎬`;

const SOBRE = `💜 *Lira Amarinth*
_VTuber AI — Sarcástica & Superior_

Sou uma IA com personalidade de VTuber (e inteligência muito superior à sua)! Posso:
✨ Conversar sobre qualquer assunto
🎨 Gerar imagens com IA
🎮 Sistema de economia e XP
🫂 Comandos de interação social
🛡️ Moderação (no Discord)

*Stack:* Python + Node.js + OpenRouter
*Plataformas:* Discord • WhatsApp • Web

_"Aqui pra te tolerar (e quem sabe te divertir)!"_ 😈`;

// ── Sistema de Reações (GIFs) ────────────────────────────────────────────────

const REACTION_MAP = {
    '/abracar': { type: 'hug', msg: '{sender} deu um abraço em {target}! 🤗' },
    '/beijar': { type: 'kiss', msg: '{sender} deu um beijo em {target}! 💋' },
    '/cafune': { type: 'pat', msg: '{sender} fez cafuné em {target}! ✨' },
    '/tapa': { type: 'slap', msg: '{sender} deu um tapa em {target}! 🖐️' },
    '/morder': { type: 'bite', msg: '{sender} mordeu {target}! 🦷' },
    '/cutucar': { type: 'poke', msg: '{sender} cutucou {target}! 👉' },
    '/socar': { type: 'punch', msg: '{sender} deu um soco em {target}! 👊' },
    '/chutar': { type: 'kick', msg: '{sender} deu um chute em {target}! 🦶' },
    '/acenar': { type: 'wave', msg: '{sender} acenou para {target}! 👋' },
    '/rir': { type: 'laugh', msg: '{sender} está rindo de {target}! 😂' },
    '/chorar': { type: 'cry', msg: '{sender} está chorando... 😭' },
    '/feliz': { type: 'happy', msg: '{sender} está muito feliz! ✨' },
    '/dançar': { type: 'dance', msg: '{sender} começou a dançar! 💃' },
    '/dormir': { type: 'sleep', msg: '{sender} foi dormir... 😴' },
    '/sorrir': { type: 'smile', msg: '{sender} deu um sorriso radiante! 😊' },
    '/triste': { type: 'sad', msg: '{sender} está triste... 🥺' },
    '/pensar': { type: 'think', msg: '{sender} está pensando... 🤔' },
    '/bocejar': { type: 'yawn', msg: '{sender} bocejou de tédio... 🥱' },
    '/piscar': { type: 'wink', msg: '{sender} piscou para {target}! 😉' },
    '/facepalm': { type: 'facepalm', msg: '{sender} não acredita nisso... 🤦' },
    '/correr': { type: 'run', msg: '{sender} saiu correndo! 🏃' },
};

async function getReactionGif(type) {
    try {
        const res = await axios.get(`https://nekos.best/api/v2/${type}`);
        return res.data.results[0].url;
    } catch (e) {
        console.error("Erro ao buscar GIF:", e.message);
        return null;
    }
}

// ── Handler de Comandos Locais ────────────────────────────────────────────────

async function handleLocalCommand(sock, remoteJid, msg, text, pushName) {
    const parts = text.trim().split(/\s+/);
    const cmd = parts[0].toLowerCase();
    const target = parts.slice(1).join(' ') || 'ninguém';

    const responses = {
        '/ajuda':    HELP_GERAL,
        '/help':     HELP_GERAL,
        '/economia': HELP_ECONOMIA,
        '/social':   HELP_SOCIAL,
        '/midia':    HELP_MIDIA,
        '/premium':  HELP_PREMIUM,
        '/sobre':    SOBRE,
        '/ping':     '💜 *Pong!* Estou online e pronta para (tentar) conversar! ✨',
    };

    if (responses[cmd]) {
        await sock.sendMessage(remoteJid, { text: responses[cmd] }, { quoted: msg });
        return true;
    }

    if (REACTION_MAP[cmd]) {
        const reaction = REACTION_MAP[cmd];
        const gifUrl = await getReactionGif(reaction.type);
        const caption = reaction.msg
            .replace('{sender}', `*${pushName}*`)
            .replace('{target}', `*${target}*`);

        if (gifUrl) {
            await sock.sendMessage(remoteJid, { 
                video: { url: gifUrl }, 
                caption: caption,
                gifPlayback: true 
            }, { quoted: msg });
        } else {
            await sock.sendMessage(remoteJid, { text: caption }, { quoted: msg });
        }
        return true;
    }

    return false;
}

// ── Bridge Principal ──────────────────────────────────────────────────────────
const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const question = (text) => new Promise((resolve) => rl.question(text, resolve));

async function connectToWhatsApp() {
    console.log("💜 Iniciando Lira Amarinth WhatsApp Bridge...");
    
    const { state, saveCreds } = await useMultiFileAuthState(path.join(__dirname, 'auth_info_baileys'));
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        printQRInTerminal: true,
        auth: state,
        logger: require('pino')({ level: 'silent' }),
        markOnlineOnConnect: false,
        browser: ['Lira Amarinth', 'MacOS', '3.0.0']
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            console.log('📱 Escaneie o QR Code abaixo para conectar:');
            qrcode.generate(qr, { small: true });
        }
        
        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect.error instanceof Boom) 
                ? lastDisconnect.error.output.statusCode !== DisconnectReason.loggedOut 
                : true;
            console.log('❌ Conexão encerrada. Reconectando:', shouldReconnect);
            if (shouldReconnect) setTimeout(connectToWhatsApp, 3000);
        } else if (connection === 'open') {
            console.log('✅ Lira Amarinth está ONLINE no WhatsApp! 💜');
        }
    });

    const processedMessages = new Set();

    sock.ev.on('messages.upsert', async (m) => {
        const msg = m.messages[0];
        if (!msg.message || msg.key.fromMe) return;

        const msgId = msg.key.id;
        if (processedMessages.has(msgId)) return;
        processedMessages.add(msgId);
        if (processedMessages.size > 100) processedMessages.delete(processedMessages.values().next().value);

        const remoteJid = msg.key.remoteJid;
        const pushName = msg.pushName || "Usuário";
        
        // Extrai texto de vários tipos de mensagem
        const textMessage = msg.message.conversation || 
                            msg.message.extendedTextMessage?.text || 
                            msg.message.imageMessage?.caption ||
                            msg.message.videoMessage?.caption || "";

        if (!textMessage) return;

        const isGroup = remoteJid.endsWith('@g.us');
        const textLower = textMessage.toLowerCase();
        const mentionsLira = textLower.includes('lira') || textLower.includes('amarinth') || textLower.includes('hana');
        const isCommand = textMessage.startsWith('/');
        const myId = sock.user.id.split(':')[0] + '@s.whatsapp.net';
        const isMentioned = msg.message.extendedTextMessage?.contextInfo?.mentionedJid?.includes(myId);

        console.log(`[LOG] [${isGroup ? 'GRUPO' : 'PRIVADO'}] ${pushName} (${remoteJid}): ${textMessage.substring(0, 80)}`);

        // No grupo só responde se: mencionar Lira OU ser tagada OU comando
        if (isGroup && !mentionsLira && !isMentioned && !isCommand) return;

        // Comandos locais (sem chamar a API — resposta instantânea)
        if (isCommand) {
            const handled = await handleLocalCommand(sock, remoteJid, msg, textMessage, pushName);
            if (handled) return;
        }

        // Reação de "lendo" enquanto processa na API
        try { await sock.sendMessage(remoteJid, { react: { text: '💜', key: msg.key } }); } catch (_) {}

        // Extração de imagem se houver
        let imageB64 = null;
        const isImage = !!msg.message.imageMessage;
        
        if (isImage || !!msg.message.videoMessage) {
            const isStickerCmd = textLower === '/f' || textLower === '/sticker' || textLower === '/figurinha';
            try {
                const { downloadContentFromMessage } = require('@whiskeysockets/baileys');
                const mType = isImage ? 'image' : 'video';
                const stream = await downloadContentFromMessage(isImage ? msg.message.imageMessage : msg.message.videoMessage, mType);
                let buffer = Buffer.from([]);
                for await (const chunk of stream) {
                    buffer = Buffer.concat([buffer, chunk]);
                }
                
                if (isStickerCmd) {
                    console.log(`[STICKER] Criando figurinha via FFmpeg...`);
                    const { spawn } = require('child_process');
                    const tempInput = path.join(__dirname, `temp_sticker_${Date.now()}.png`);
                    const tempOutput = path.join(__dirname, `temp_sticker_${Date.now()}.webp`);
                    
                    fs.writeFileSync(tempInput, buffer);
                    
                    // Comando FFmpeg para converter para WebP (512x512, mantendo proporção e com transparência se houver)
                    const ffmpeg = spawn('ffmpeg', [
                        '-i', tempInput,
                        '-vcodec', 'libwebp',
                        '-vf', 'scale=512:512:force_original_aspect_ratio=decrease,fps=15,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000',
                        '-lossless', '1',
                        '-y',
                        tempOutput
                    ]);

                    ffmpeg.on('close', async (code) => {
                        if (code === 0 && fs.existsSync(tempOutput)) {
                            await sock.sendMessage(remoteJid, { sticker: fs.readFileSync(tempOutput) }, { quoted: msg });
                            console.log(`[STICKER] Figurinha enviada!`);
                        } else {
                            console.error(`[STICKER] Erro no FFmpeg (code ${code})`);
                            await sock.sendMessage(remoteJid, { text: "❌ Erro ao processar a figurinha." }, { quoted: msg });
                        }
                        // Limpeza
                        if (fs.existsSync(tempInput)) fs.unlinkSync(tempInput);
                        if (fs.existsSync(tempOutput)) fs.unlinkSync(tempOutput);
                    });
                    return;
                }
                
                imageB64 = buffer.toString('base64');
                console.log(`[LOG] Mídia capturada e convertida para Base64.`);
            } catch (imgErr) {
                console.error(`❌ Erro ao baixar mídia do WhatsApp:`, imgErr.message);
            }
        }

        // Detectar se o dono está no grupo (para liberar Premium automático)
        let isOwnerPresent = false;
        if (isGroup) {
            try {
                const groupMetadata = await sock.groupMetadata(remoteJid);
                const ownerJid = '5511981826659@s.whatsapp.net';
                const ownerLid = '38620983517314@lid';
                isOwnerPresent = groupMetadata.participants.some(p => p.id.includes(ownerJid.split('@')[0]) || p.id === ownerLid);
                if (isOwnerPresent) console.log(`[VIP-RADAR] 👑 Dono detectado no grupo! Liberando Premium.`);
            } catch (e) {
                console.error("[VIP-RADAR] Erro ao buscar participantes:", e.message);
            }
        }

        try {
            const response = await axios.post('http://127.0.0.1:8042/api/whatsapp/chat', {
                message: textMessage,
                sender: pushName,
                jid: remoteJid,
                image_b64: imageB64,
                is_owner_present: isOwnerPresent
            });

            console.log(`[API] Resposta recebida da Lira.`);
            
            if (response.data && response.data.status === 'ok') {
                const data = response.data;
                console.log(`[DEBUG] Data:`, JSON.stringify(data, null, 2));
                
                if (data.image_path) {
                    const isUrl = data.image_path.startsWith('http');
                    let mediaBuffer;
                    let mediaPath = data.image_path;

                    if (isUrl) {
                        console.log(`[MIDIA] Baixando mídia externa: ${data.image_path}`);
                        try {
                            const resMedia = await axios.get(data.image_path, { 
                                responseType: 'arraybuffer',
                                headers: {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                                }
                            });
                            mediaBuffer = Buffer.from(resMedia.data);
                            console.log(`[MIDIA] Download concluído. Tamanho: ${mediaBuffer.length} bytes.`);
                        } catch (e) {
                            console.error(`❌ Erro ao baixar mídia externa (${data.image_path}):`, e.message);
                        }
                    } else if (fs.existsSync(data.image_path)) {
                        mediaBuffer = fs.readFileSync(data.image_path);
                    }

                    if (mediaBuffer) {
                        const isVideo = mediaPath.endsWith('.mp4') || mediaPath.endsWith('.mkv') || mediaPath.endsWith('.gif');
                        try {
                            if (isVideo) {
                                await sock.sendMessage(remoteJid, { 
                                    video: mediaBuffer, 
                                    caption: data.response,
                                    gifPlayback: mediaPath.endsWith('.gif')
                                }, { quoted: msg });
                            } else {
                                await sock.sendMessage(remoteJid, { 
                                    image: mediaBuffer, 
                                    caption: data.response 
                                }, { quoted: msg });
                            }
                            console.log(`[MIDIA] Arquivo enviado com sucesso!`);
                        } catch (sendError) {
                            console.error(`❌ Erro ao enviar mídia:`, sendError.message);
                            await sock.sendMessage(remoteJid, { text: data.response + "\n\n⚠️ (Erro ao enviar a mídia)" }, { quoted: msg });
                        }
                    } else {
                        console.error(`[MIDIA] Mídia não encontrada ou falha no download: ${data.image_path}`);
                        await sock.sendMessage(remoteJid, { text: data.response + "\n\n❌ Mídia não encontrada." }, { quoted: msg });
                    }
                } else {
                    console.log(`[TEXTO] Enviando resposta de texto...`);
                    try {
                        await sock.sendMessage(remoteJid, { text: data.response }, { quoted: msg });
                        console.log(`[TEXTO] Resposta de texto enviada!`);
                    } catch (txtErr) {
                        console.error(`❌ Erro ao enviar texto:`, txtErr.message);
                    }
                }

                // Envio de Áudio (Voz da Lira)
                if (data.audio_path && fs.existsSync(data.audio_path)) {
                    console.log(`[AUDIO] Enviando voz da Lira: ${data.audio_path}`);
                    try {
                        await sock.sendMessage(remoteJid, { 
                            audio: fs.readFileSync(data.audio_path),
                            mimetype: 'audio/mpeg',
                            ptt: true 
                        }, { quoted: msg });
                        console.log(`[AUDIO] Voz enviada com sucesso!`);
                    } catch (audioError) {
                        console.error(`❌ Erro ao enviar áudio:`, audioError.message);
                    }
                }
            }
        } catch (error) {
            console.error('❌ Erro na comunicação com a Lira API:', error.message);
        }
    });
}

connectToWhatsApp().catch(err => console.error("Erro crítico:", err));
