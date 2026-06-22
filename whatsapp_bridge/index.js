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
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const WHATSAPP_API_BASE = (process.env.WHATSAPP_API_URL || 'http://127.0.0.1:8043').replace(/\/$/, '');

// IDs do dono lidos do .env
const OWNER_JID = process.env.WPP_OWNER_JID || '5511981826659@s.whatsapp.net';
const OWNER_LID = process.env.WPP_OWNER_LID || '38620983517314@lid';
const WPP_LINK_MODE = (process.env.WPP_LINK_MODE || 'qr').toLowerCase();
const WPP_PHONE = (process.env.WPP_PHONE || OWNER_JID.split('@')[0]).replace(/\D/g, '');
const WPP_PUSH_PORT = parseInt(process.env.WPP_PUSH_PORT || '8044', 10);
const AUTH_DIR = path.join(__dirname, 'auth_info_baileys');
const STATUS_FILE = path.join(__dirname, 'bridge_status.json');

let activeSocket = null;
let connectInFlight = false;
let reconnectTimer = null;
let pushServerStarted = false;

function writeBridgeStatus(data) {
    try {
        fs.writeFileSync(
            STATUS_FILE,
            JSON.stringify({ ...data, updated_at: new Date().toISOString() }, null, 2),
            'utf8'
        );
    } catch (e) {
        console.error('[STATUS] Erro ao gravar bridge_status.json:', e.message);
    }
}

function formatPairingCode(code) {
    const c = String(code || '').replace(/\W/g, '').toUpperCase();
    if (c.length === 8) return `${c.slice(0, 4)}-${c.slice(4)}`;
    return String(code || '').toUpperCase();
}

function persistPairingCode(code) {
    const formatted = formatPairingCode(code);
    fs.writeFileSync(path.join(__dirname, 'pairing_code.txt'), formatted, 'utf8');
    writeBridgeStatus({ state: 'pairing', pairing_code: formatted, link_mode: 'pairing' });
    console.log('\n======================================================');
    console.log(`[PAIRING] Código: ${formatted}`);
    console.log('[PAIRING] No celular: WhatsApp → Aparelhos conectados → Conectar com número de telefone');
    console.log(`[PAIRING] Número (somente dígitos): ${WPP_PHONE}`);
    console.log('======================================================\n');
    return formatted;
}

function persistQr(qr) {
    const revision = Date.now();
    fs.writeFileSync(path.join(__dirname, 'qr.txt'), qr, 'utf8');
    fs.writeFileSync(
        path.join(__dirname, 'qr_meta.json'),
        JSON.stringify({ revision, updated_at: new Date().toISOString() }),
        'utf8'
    );
    writeBridgeStatus({ state: 'qr', link_mode: 'qr', qr_revision: revision });
    console.log('[QR] Novo código salvo (revision', revision + '). Escaneie em até ~60s.');
}

function clearSessionArtifacts() {
    for (const f of ['qr.txt', 'qr_meta.json', 'pairing_code.txt']) {
        const p = path.join(__dirname, f);
        try { if (fs.existsSync(p)) fs.unlinkSync(p); } catch (_) { /* ignore */ }
    }
}

function resetAuthDir() {
    if (fs.existsSync(AUTH_DIR)) {
        fs.rmSync(AUTH_DIR, { recursive: true, force: true });
        console.log('[AUTH] Sessão apagada (auth_info_baileys).');
    }
    clearSessionArtifacts();
    writeBridgeStatus({ state: 'reset', message: 'Sessão limpa. Inicie o bridge novamente.' });
}

if (process.env.WPP_RESET_SESSION === '1') {
    resetAuthDir();
}

// ── Utilitários ────────────────────────────────────────────────────────────────
function formatWhatsAppMessage(text) {
    if (!text) return "";
    return text
        .replace(/\*\*\*(.*?)\*\*\*/g, '*_$1_*') // Bold + Italic
        .replace(/\*\*(.*?)\*\*/g, '*$1*')     // Bold
        .replace(/__(.*?)__/g, '*$1*')         // Bold alternative
        .replace(/\*([^\s\*][^*]*?[^\s\*])\*/g, '_$1_') // Italic (não pega balas de lista)
        .replace(/~~(.*?)~~/g, '~$1~');        // Strikethrough
}

async function sendLiraReply(sock, remoteJid, msg, data) {
    const rawText = (data?.response || data?.message || '').trim();
    const textBody = formatWhatsAppMessage(rawText) || rawText;

    if (data?.image_path) {
        const isUrl = data.image_path.startsWith('http');
        let mediaBuffer;
        const mediaPath = data.image_path;

        if (isUrl) {
            try {
                const resMedia = await axios.get(data.image_path, {
                    responseType: 'arraybuffer',
                    timeout: 60000,
                    headers: {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    },
                });
                mediaBuffer = Buffer.from(resMedia.data);
            } catch (e) {
                console.error(`❌ Erro ao baixar mídia (${data.image_path}):`, e.message);
            }
        } else if (fs.existsSync(data.image_path)) {
            mediaBuffer = fs.readFileSync(data.image_path);
        }

        if (mediaBuffer) {
            const isVideo = /\.(mp4|mkv|gif)$/i.test(mediaPath);
            try {
                if (isVideo) {
                    let jpegThumbnail;
                    try {
                        const { execSync } = require('child_process');
                        const thumbPath = mediaPath + '_thumb.jpg';
                        execSync(
                            `ffmpeg -y -i "${mediaPath}" -ss 00:00:00.000 -vframes 1 -vf "scale=320:-1" -q:v 5 "${thumbPath}"`,
                            { stdio: 'pipe', timeout: 15000 }
                        );
                        if (fs.existsSync(thumbPath)) {
                            jpegThumbnail = fs.readFileSync(thumbPath);
                            fs.unlinkSync(thumbPath);
                        }
                    } catch (_) { /* ignore */ }

                    await sock.sendMessage(remoteJid, {
                        video: mediaBuffer,
                        caption: textBody || undefined,
                        mimetype: 'video/mp4',
                        gifPlayback: mediaPath.endsWith('.gif'),
                        ...(jpegThumbnail ? { jpegThumbnail } : {}),
                    }, { quoted: msg });
                } else {
                    await sock.sendMessage(remoteJid, {
                        image: mediaBuffer,
                        caption: textBody || undefined,
                    }, { quoted: msg });
                }
                console.log('[MIDIA] Arquivo enviado.');
                if (rawText && CONFIG_TTS_ENABLED()) {
                    axios.post(`${WHATSAPP_API_BASE}/api/whatsapp/tts`, { text: rawText }, { timeout: 120000 })
                        .then(async (ttsRes) => {
                            const audioPath = ttsRes.data?.audio_path;
                            if (ttsRes.data?.status === 'ok' && audioPath && fs.existsSync(audioPath)) {
                                await sock.sendMessage(remoteJid, {
                                    audio: fs.readFileSync(audioPath),
                                    mimetype: 'audio/mpeg',
                                    ptt: true,
                                }, { quoted: msg });
                            }
                        })
                        .catch((ttsErr) => console.error('❌ Erro TTS:', ttsErr.message));
                }
                return;
            } catch (sendError) {
                console.error('❌ Erro ao enviar mídia:', sendError.message);
            }
        }
    }

    if (textBody) {
        await sock.sendMessage(remoteJid, { text: textBody }, { quoted: msg });
        console.log('[TEXTO] Resposta enviada.');
    } else {
        await sock.sendMessage(
            remoteJid,
            { text: '💜 Tive um problema ao montar a resposta. Tenta de novo?' },
            { quoted: msg }
        );
    }

    if (data?.audio_path && fs.existsSync(data.audio_path)) {
        try {
            await sock.sendMessage(remoteJid, {
                audio: fs.readFileSync(data.audio_path),
                mimetype: 'audio/mpeg',
                ptt: false,
            }, { quoted: msg });
        } catch (audioErr) {
            console.error('❌ Erro ao enviar áudio:', audioErr.message);
        }
    }

    if (rawText && CONFIG_TTS_ENABLED()) {
        axios.post(`${WHATSAPP_API_BASE}/api/whatsapp/tts`, { text: rawText }, { timeout: 120000 })
            .then(async (ttsRes) => {
                const audioPath = ttsRes.data?.audio_path;
                if (ttsRes.data?.status === 'ok' && audioPath && fs.existsSync(audioPath)) {
                    await sock.sendMessage(remoteJid, {
                        audio: fs.readFileSync(audioPath),
                        mimetype: 'audio/mpeg',
                        ptt: true,
                    }, { quoted: msg });
                }
            })
            .catch((ttsErr) => console.error('❌ Erro TTS:', ttsErr.message));
    }
}

function CONFIG_TTS_ENABLED() {
    return process.env.TTS_ATIVO !== '0' && process.env.TTS_ATIVO !== 'false';
}

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
            console.log(`[GIF REACTION] Baixando GIF de reação: ${gifUrl}`);
            try {
                const axios = require('axios');
                const fs = require('fs');
                const path = require('path');
                const { exec } = require('child_process');

                const resMedia = await axios.get(gifUrl, { responseType: 'arraybuffer' });
                const gifBuffer = Buffer.from(resMedia.data);

                const tempGifInput = path.join(__dirname, `temp_gif_in_${Date.now()}.gif`);
                const tempMp4Output = path.join(__dirname, `temp_gif_out_${Date.now()}.mp4`);

                fs.writeFileSync(tempGifInput, gifBuffer);

                // Executa o FFmpeg para converter GIF em MP4 animado
                // -vf scale garante dimensões divisíveis por 2 (requisito do h264 no WhatsApp)
                const ffmpegCmd = `ffmpeg -i "${tempGifInput}" -movflags faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -y "${tempMp4Output}"`;

                exec(ffmpegCmd, async (error) => {
                    try {
                        if (!error && fs.existsSync(tempMp4Output)) {
                            console.log(`[GIF REACTION] GIF convertido para MP4 com sucesso. Enviando...`);
                            await sock.sendMessage(remoteJid, { 
                                video: fs.readFileSync(tempMp4Output), 
                                caption: caption,
                                gifPlayback: true 
                            }, { quoted: msg });
                        } else {
                            console.error(`[GIF REACTION] Erro ao converter GIF para MP4 via FFmpeg:`, error);
                            // Fallback: Envia apenas o texto de ação se o FFmpeg falhar
                            await sock.sendMessage(remoteJid, { text: caption }, { quoted: msg });
                        }
                    } catch (sendErr) {
                        console.error(`[GIF REACTION] Erro ao enviar mensagem de vídeo/texto:`, sendErr.message);
                    } finally {
                        // Limpeza de arquivos temporários
                        if (fs.existsSync(tempGifInput)) try { fs.unlinkSync(tempGifInput); } catch(_) {}
                        if (fs.existsSync(tempMp4Output)) try { fs.unlinkSync(tempMp4Output); } catch(_) {}
                    }
                });
            } catch (gifErr) {
                console.error(`[GIF REACTION] Erro geral no processamento do GIF:`, gifErr.message);
                // Fallback imediato se o download falhar
                await sock.sendMessage(remoteJid, { text: caption }, { quoted: msg });
            }
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
    if (connectInFlight) {
        console.log('[BRIDGE] Conexão já em andamento, ignorando duplicata.');
        return;
    }
    connectInFlight = true;
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    console.log(`💜 Iniciando Lira WhatsApp Bridge (modo: ${WPP_LINK_MODE})...`);
    writeBridgeStatus({ state: 'connecting', link_mode: WPP_LINK_MODE });

    try {
        const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
        const { version } = await fetchLatestBaileysVersion();

        const sock = makeWASocket({
            version,
            printQRInTerminal: WPP_LINK_MODE === 'qr',
            auth: state,
            logger: require('pino')({ level: 'silent' }),
            markOnlineOnConnect: true,
            syncFullHistory: false,
            shouldSyncHistoryMessage: () => false,
            browser: ['Lira Control Center', 'Chrome', '120.0.0'],
            connectTimeoutMs: 120000,
            qrTimeout: 120000,
        });

        activeSocket = sock;

        sock.ev.on('creds.update', saveCreds);

        let pairingRequested = false;

        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;

            if (qr && WPP_LINK_MODE === 'qr') {
                console.log('📱 Escaneie o QR (WhatsApp → Aparelhos conectados → Conectar):');
                qrcode.generate(qr, { small: true });
                try {
                    persistQr(qr);
                } catch (e) {
                    console.error('Erro ao salvar QR:', e.message);
                }
            }

            if (
                qr &&
                WPP_LINK_MODE === 'pairing' &&
                !pairingRequested &&
                !sock.authState?.creds?.registered
            ) {
                pairingRequested = true;
                try {
                    console.log(`[PAIRING] Gerando código para ${WPP_PHONE}...`);
                    const code = await sock.requestPairingCode(WPP_PHONE);
                    persistPairingCode(code);
                } catch (err) {
                    console.error('[PAIRING] Erro:', err.message);
                    writeBridgeStatus({ state: 'pairing_failed', error: err.message, link_mode: 'pairing' });
                }
            }

            if (connection === 'close') {
                const statusCode = lastDisconnect?.error?.output?.statusCode;
                const loggedOut = statusCode === DisconnectReason.loggedOut;
                const badSession = statusCode === DisconnectReason.badSession;
                const restartRequired = statusCode === DisconnectReason.restartRequired;
                const connectionReplaced = statusCode === DisconnectReason.connectionReplaced;
                const sessionInvalid = loggedOut || badSession;
                const shouldReconnect =
                    lastDisconnect?.error instanceof Boom
                        ? !sessionInvalid
                        : true;

                const errMsg = lastDisconnect?.error?.message || 'desconhecido';
                const delayMs = restartRequired ? 2000 : connectionReplaced ? 15000 : 8000;
                console.log(
                    `❌ Conexão encerrada (code=${statusCode}). Reconectar: ${shouldReconnect}${restartRequired ? ' (pós-login)' : ''}`
                );

                writeBridgeStatus({
                    state: restartRequired ? 'restarting' : 'disconnected',
                    disconnect_code: statusCode,
                    error: errMsg,
                    link_mode: WPP_LINK_MODE,
                    hint: sessionInvalid
                        ? 'Sessão inválida: use Limpar sessão no painel e escaneie um QR novo.'
                        : restartRequired
                          ? 'Login aceito — reconectando automaticamente…'
                          : connectionReplaced
                            ? 'Outro WhatsApp Web/sessão aberta. Feche outras sessões e aguarde.'
                            : 'Aguardando reconexão ou novo QR.',
                });

                activeSocket = null;

                if (sessionInvalid) {
                    console.log('[AUTH] Sessão inválida (loggedOut). Limpe a sessão e inicie de novo.');
                    return;
                }

                if (shouldReconnect) {
                    reconnectTimer = setTimeout(() => {
                        connectInFlight = false;
                        connectToWhatsApp();
                    }, delayMs);
                }
            } else if (connection === 'open') {
                console.log('✅ Lira Amarinth está ONLINE no WhatsApp! 💜');
                clearSessionArtifacts();
                writeBridgeStatus({ state: 'connected', link_mode: WPP_LINK_MODE });
                startPushServer(sock);
            } else if (connection === 'connecting') {
                writeBridgeStatus({ state: 'connecting', link_mode: WPP_LINK_MODE });
            }
        });

        const processedMessages = new Set();

        sock.ev.on('messages.upsert', async (m) => {
        console.log('[DEBUG UPSERT] Event type:', m.type, 'messages count:', m.messages?.length);
        // Ignora sincronização de histórico e foca apenas em mensagens novas em tempo real
        if (m.type !== 'notify') return;

        const msg = m.messages[0];
        if (!msg.message) return;
        console.log('[DEBUG msg] fromMe:', msg.key.fromMe, 'timestamp:', msg.messageTimestamp, 'id:', msg.key.id);
        if (msg.key.fromMe) return;

        // Ignora mensagens enviadas há mais de 2 minutos (evita responder mensagens antigas offline)
        let msgTime = msg.messageTimestamp;
        if (msgTime && typeof msgTime === 'object' && typeof msgTime.toNumber === 'function') {
            msgTime = msgTime.toNumber();
        } else if (msgTime) {
            msgTime = Number(msgTime);
        }

        if (msgTime && (Math.floor(Date.now() / 1000) - msgTime > 120)) {
            console.log('[DEBUG msg] Ignorando mensagem antiga:', msgTime);
            return;
        }

        const msgId = msg.key.id;
        if (processedMessages.has(msgId)) return;
        processedMessages.add(msgId);
        if (processedMessages.size > 100) processedMessages.delete(processedMessages.values().next().value);

        const remoteJid = msg.key.remoteJid;
        const participantJid = msg.key.participant || msg.key.remoteJid;
        const pushName = msg.pushName || "Usuário";
        
        const isImage = !!msg.message.imageMessage;
        const isAudio = !!msg.message.audioMessage;
        const isVideo = !!msg.message.videoMessage;
        const isSticker = !!msg.message.stickerMessage;

        // Extrai texto de vários tipos de mensagem
        let textMessage = msg.message.conversation || 
                            msg.message.extendedTextMessage?.text || 
                            msg.message.imageMessage?.caption ||
                            msg.message.videoMessage?.caption || "";

        if (!textMessage && (isImage || isVideo || isSticker)) {
            textMessage = isVideo ? "Analise o vídeo" : isSticker ? "Analise a figurinha" : "Analise a imagem";
        }

        if (!textMessage && !isAudio) return;

        const isGroup = remoteJid.endsWith('@g.us');
        const mentionsLira = /\b(lira|liras|amarinth|hana)\b/i.test(textMessage);
        const isCommand = textMessage.startsWith('/');
        
        // Suporte robusto para menções (incluindo JID padrão, LID e JID bruto com porta)
        const myJidClean = sock.user.id.split(':')[0];
        const myNumber = myJidClean.split('@')[0];
        const myIdNet = myNumber + '@s.whatsapp.net';
        const myIdLid = myNumber + '@lid';
        
        const isMentioned = msg.message.extendedTextMessage?.contextInfo?.mentionedJid?.includes(myIdNet) || 
                            msg.message.extendedTextMessage?.contextInfo?.mentionedJid?.includes(myIdLid) ||
                            msg.message.extendedTextMessage?.contextInfo?.mentionedJid?.includes(sock.user.id) ||
                            msg.message.extendedTextMessage?.contextInfo?.mentionedJid?.includes(myJidClean);

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

        // Extração de imagem, áudio ou outro anexo se houver
        let imageB64 = null;
        let mediaPath = null;
        const tempMediaDir = path.join(__dirname, '..', 'temp', 'incoming_media');

        if (isAudio) {
            console.log(`[AUDIO] Mensagem de voz recebida de ${pushName}. Transcrevendo...`);
            try {
                const { downloadContentFromMessage } = require('@whiskeysockets/baileys');
                const stream = await downloadContentFromMessage(msg.message.audioMessage, 'audio');
                let buffer = Buffer.from([]);
                for await (const chunk of stream) {
                    buffer = Buffer.concat([buffer, chunk]);
                }

                const transcribeRes = await axios.post(
                    `${WHATSAPP_API_BASE}/api/whatsapp/transcribe`,
                    { audio_b64: buffer.toString('base64'), suffix: '.ogg' },
                    { timeout: parseInt(process.env.WPP_STT_TIMEOUT_MS || '90000', 10) }
                );

                if (transcribeRes.data?.status === 'ok' && transcribeRes.data.text) {
                    textMessage = transcribeRes.data.text;
                    console.log(`[AUDIO] Transcrição: "${textMessage.substring(0, 120)}"`);
                } else {
                    const sttErr = transcribeRes.data?.message || 'Não consegui entender o áudio.';
                    await sock.sendMessage(
                        remoteJid,
                        { text: `💜 ${sttErr}` },
                        { quoted: msg }
                    );
                    return;
                }
            } catch (audErr) {
                const detail = audErr.response?.data?.message || audErr.message;
                console.error(`❌ Erro ao processar áudio do WhatsApp:`, detail);
                try {
                    await sock.sendMessage(
                        remoteJid,
                        { text: `💜 Não consegui transcrever o áudio (${detail}).` },
                        { quoted: msg }
                    );
                } catch (_) { /* ignore */ }
                return;
            }
        }

        if (isImage || isVideo || isSticker) {
            try {
                if (!fs.existsSync(tempMediaDir)) {
                    fs.mkdirSync(tempMediaDir, { recursive: true });
                }

                const { downloadContentFromMessage } = require('@whiskeysockets/baileys');
                
                if (isImage) {
                    const textLower = textMessage.toLowerCase();
                    const isStickerCmd = textLower === '/f' || textLower === '/sticker' || textLower === '/figurinha';
                    
                    const stream = await downloadContentFromMessage(msg.message.imageMessage, 'image');
                    let buffer = Buffer.from([]);
                    for await (const chunk of stream) {
                        buffer = Buffer.concat([buffer, chunk]);
                    }

                    if (isStickerCmd) {
                        console.log(`[STICKER] Criando figurinha via FFmpeg...`);
                        const { spawn } = require('child_process');
                        const tempInput = path.join(__dirname, `temp_sticker_in_${Date.now()}.png`);
                        const tempOutput = path.join(__dirname, `temp_sticker_out_${Date.now()}.webp`);
                        
                        fs.writeFileSync(tempInput, buffer);
                        
                        const ffmpegArgs = [
                            '-i', tempInput,
                            '-vcodec', 'libwebp',
                            '-vf', 'scale=512:512:force_original_aspect_ratio=decrease,fps=15,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000',
                            '-qscale', '75',
                            '-preset', 'default',
                            '-loop', '0',
                            '-an',
                            '-vsync', '0',
                            '-y',
                            tempOutput
                        ];

                        const ffmpeg = spawn('ffmpeg', ffmpegArgs);

                        ffmpeg.on('close', async (code) => {
                            if (code === 0 && fs.existsSync(tempOutput)) {
                                const stickerBuffer = fs.readFileSync(tempOutput);
                                await sock.sendMessage(remoteJid, { 
                                    sticker: stickerBuffer,
                                    mimetype: 'image/webp'
                                }, { quoted: msg });
                                console.log(`[STICKER] Figurinha enviada! Tamanho: ${stickerBuffer.length} bytes`);
                            } else {
                                console.error(`[STICKER] Erro no FFmpeg (code ${code})`);
                                await sock.sendMessage(remoteJid, { text: "❌ Erro ao processar a figurinha." }, { quoted: msg });
                            }
                            if (fs.existsSync(tempInput)) try { fs.unlinkSync(tempInput); } catch(e) {}
                            if (fs.existsSync(tempOutput)) try { fs.unlinkSync(tempOutput); } catch(e) {}
                        });
                        return;
                    }

                    imageB64 = buffer.toString('base64');
                    console.log(`[LOG] Mídia capturada e convertida para Base64.`);
                }
                else if (isVideo) {
                    const textLower = textMessage.toLowerCase();
                    const isStickerCmd = textLower === '/f' || textLower === '/sticker' || textLower === '/figurinha';
                    
                    const stream = await downloadContentFromMessage(msg.message.videoMessage, 'video');
                    let buffer = Buffer.from([]);
                    for await (const chunk of stream) {
                        buffer = Buffer.concat([buffer, chunk]);
                    }

                    if (isStickerCmd) {
                        console.log(`[STICKER] Criando figurinha via FFmpeg...`);
                        const { spawn } = require('child_process');
                        const tempInput = path.join(__dirname, `temp_sticker_in_${Date.now()}.mp4`);
                        const tempOutput = path.join(__dirname, `temp_sticker_out_${Date.now()}.webp`);
                        
                        fs.writeFileSync(tempInput, buffer);
                        
                        const ffmpegArgs = [
                            '-t', '5',
                            '-i', tempInput,
                            '-vcodec', 'libwebp',
                            '-vf', 'scale=512:512:force_original_aspect_ratio=decrease,fps=15,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000',
                            '-qscale', '75',
                            '-preset', 'default',
                            '-loop', '0',
                            '-an',
                            '-vsync', '0',
                            '-y',
                            tempOutput
                        ];

                        const ffmpeg = spawn('ffmpeg', ffmpegArgs);

                        ffmpeg.on('close', async (code) => {
                            if (code === 0 && fs.existsSync(tempOutput)) {
                                const stickerBuffer = fs.readFileSync(tempOutput);
                                await sock.sendMessage(remoteJid, { 
                                    sticker: stickerBuffer,
                                    mimetype: 'image/webp'
                                }, { quoted: msg });
                                console.log(`[STICKER] Figurinha enviada! Tamanho: ${stickerBuffer.length} bytes`);
                            } else {
                                console.error(`[STICKER] Erro no FFmpeg (code ${code})`);
                                await sock.sendMessage(remoteJid, { text: "❌ Erro ao processar a figurinha." }, { quoted: msg });
                            }
                            if (fs.existsSync(tempInput)) try { fs.unlinkSync(tempInput); } catch(e) {}
                            if (fs.existsSync(tempOutput)) try { fs.unlinkSync(tempOutput); } catch(e) {}
                        });
                        return;
                    }

                    const videoFilePath = path.join(tempMediaDir, `video_${msgId}.mp4`);
                    fs.writeFileSync(videoFilePath, buffer);
                    mediaPath = videoFilePath;
                    console.log(`[LOG] Vídeo salvo em: ${mediaPath}`);
                }
                else if (isSticker) {
                    console.log(`[LOG] Figurinha recebida. Baixando...`);
                    const stream = await downloadContentFromMessage(msg.message.stickerMessage, 'sticker');
                    let buffer = Buffer.from([]);
                    for await (const chunk of stream) {
                        buffer = Buffer.concat([buffer, chunk]);
                    }

                    const tempInput = path.join(tempMediaDir, `sticker_in_${msgId}.webp`);
                    fs.writeFileSync(tempInput, buffer);
                    mediaPath = tempInput;
                    console.log(`[LOG] Sticker salvo em WebP: ${mediaPath}`);
                }
            } catch (imgErr) {
                console.error(`❌ Erro ao baixar mídia do WhatsApp:`, imgErr.message);
            }
        }

        // Detectar se o dono está no grupo (para liberar Premium automático)
        let isOwnerPresent = false;
        if (isGroup) {
            try {
                const groupMetadata = await sock.groupMetadata(remoteJid);
                const ownerJid = OWNER_JID;
                const ownerLid = OWNER_LID;
                isOwnerPresent = groupMetadata.participants.some(p => p.id.includes(ownerJid.split('@')[0]) || p.id === ownerLid);
                if (isOwnerPresent) console.log(`[VIP-RADAR] 👑 Dono detectado no grupo! Liberando Premium.`);
            } catch (e) {
                console.error("[VIP-RADAR] Erro ao buscar participantes:", e.message);
            }
        }

        try {
            const response = await axios.post(
                `${WHATSAPP_API_BASE}/api/whatsapp/chat`,
                {
                    message: textMessage,
                    sender: pushName,
                    jid: remoteJid,
                    participant: participantJid,
                    image_b64: imageB64,
                    media_path: mediaPath,
                    is_owner_present: isOwnerPresent,
                },
                { timeout: parseInt(process.env.WPP_CHAT_TIMEOUT_MS || '150000', 10) }
            );

            console.log('[API] Resposta recebida da Lira.');
            const data = response.data;

            if (data?.status === 'ok') {
                await sendLiraReply(sock, remoteJid, msg, data);
            } else {
                const errText = data?.message || data?.response || 'Erro desconhecido na API.';
                await sock.sendMessage(
                    remoteJid,
                    { text: `💜 Ops, falhei ao processar: ${errText}` },
                    { quoted: msg }
                );
            }
        } catch (error) {
            const detail = error.response?.data?.message || error.message;
            console.error('❌ Erro na comunicação com a Lira API:', detail);
            try {
                await sock.sendMessage(
                    remoteJid,
                    { text: `💜 Não consegui falar com a API agora (${detail}). A WhatsApp API está rodando na porta 8043?` },
                    { quoted: msg }
                );
            } catch (_) { /* ignore */ }
        }
    });

    } catch (err) {
        console.error('❌ Erro ao iniciar bridge:', err.message);
        writeBridgeStatus({ state: 'error', error: err.message });
        activeSocket = null;
    } finally {
        connectInFlight = false;
    }
}
// ── Servidor HTTP interno para push da API Python ─────────────────────────────
// POST http://127.0.0.1:8044/send (não usar 8043 — reservado para WhatsApp API)
// para mandar mensagens de sistema (startup, shutdown, etc.)

const http = require('http');

let _sockGlobal = null; // referência ao socket ativo

function startPushServer(sock) {
    if (pushServerStarted) {
        _sockGlobal = sock;
        return;
    }
    _sockGlobal = sock;

    const server = http.createServer(async (req, res) => {
        if (req.method !== 'POST' || req.url !== '/send') {
            res.writeHead(404); res.end('Not found'); return;
        }
        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
            try {
                const { jid, text } = JSON.parse(body);
                if (!jid || !text || !_sockGlobal) {
                    res.writeHead(400); res.end(JSON.stringify({ ok: false })); return;
                }
                await _sockGlobal.sendMessage(jid, { text });
                console.log(`[PUSH] Mensagem enviada para ${jid}: ${text.substring(0, 60)}`);
                res.writeHead(200); res.end(JSON.stringify({ ok: true }));
            } catch (e) {
                console.error('[PUSH] Erro:', e.message);
                res.writeHead(500); res.end(JSON.stringify({ ok: false, error: e.message }));
            }
        });
    });

    server.on('error', (e) => {
        if (e.code === 'EADDRINUSE') {
            console.warn(`[PUSH] Porta ${WPP_PUSH_PORT} em uso — push interno desativado (API WhatsApp segue na 8043).`);
        } else {
            console.error('[PUSH] Erro no servidor:', e.message);
        }
    });

    server.listen(WPP_PUSH_PORT, '127.0.0.1', () => {
        pushServerStarted = true;
        console.log(`🔌 [PUSH] Servidor interno em 127.0.0.1:${WPP_PUSH_PORT}`);
    });
}

connectToWhatsApp().catch(err => console.error("Erro crítico:", err));
