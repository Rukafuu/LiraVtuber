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
• */economia* — Comandos de moedas e XP
• */social* — Interações e reações
• */sobre* — Quem sou eu?
• */ping* — Verificar se estou online

_Digite qualquer um para mais detalhes!_ ✨`;

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

async function connectToWhatsApp() {
    console.log("💜 Iniciando Lira Amarinth WhatsApp Bridge...");
    
    const { state, saveCreds } = await useMultiFileAuthState(path.join(__dirname, 'auth_info_baileys'));
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        printQRInTerminal: true,
        auth: state,
        logger: require('pino')({ level: 'silent' }),
        markOnlineOnConnect: false
    });

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        if (qr) qrcode.generate(qr, { small: true });
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

    sock.ev.on('creds.update', saveCreds);

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

        console.log(`[LOG] [${isGroup ? 'GRUPO' : 'PRIVADO'}] ${pushName}: ${textMessage.substring(0, 80)}`);

        // No grupo só responde se: mencionar Lira OU ser tagada OU comando
        if (isGroup && !mentionsLira && !isMentioned && !isCommand) return;

        // Comandos locais (sem chamar a API — resposta instantânea)
        if (isCommand) {
            const handled = await handleLocalCommand(sock, remoteJid, msg, textMessage, pushName);
            if (handled) return;
        }

        // Reação de "lendo" enquanto processa na API
        try { await sock.sendMessage(remoteJid, { react: { text: '💜', key: msg.key } }); } catch (_) {}

        try {
            const response = await axios.post('http://127.0.0.1:8042/api/whatsapp/chat', {
                message: textMessage,
                sender: pushName,
                jid: remoteJid
            });

            if (response.data && response.data.status === 'ok') {
                const data = response.data;
                
                if (data.image_path) {
                    console.log(`[IMG] Tentando enviar imagem: ${data.image_path}`);
                    if (fs.existsSync(data.image_path)) {
                        try {
                            await sock.sendMessage(remoteJid, { 
                                image: fs.readFileSync(data.image_path), 
                                caption: data.response 
                            }, { quoted: msg });
                            console.log(`[IMG] Imagem enviada com sucesso!`);
                        } catch (sendError) {
                            console.error(`❌ Erro ao enviar imagem:`, sendError.message);
                            await sock.sendMessage(remoteJid, { text: data.response + "\n\n⚠️ (Erro ao enviar a imagem)" }, { quoted: msg });
                        }
                    } else {
                        await sock.sendMessage(remoteJid, { text: data.response + "\n\n❌ Imagem não encontrada." }, { quoted: msg });
                    }
                } else {
                    await sock.sendMessage(remoteJid, { text: data.response }, { quoted: msg });
                }
            }
        } catch (error) {
            console.error('❌ Erro na comunicação com a Lira API:', error.message);
        }
    });
}

connectToWhatsApp().catch(err => console.error("Erro crítico:", err));
