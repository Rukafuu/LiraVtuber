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

const HELP_GERAL = `🌸 *Hana Nakamura — Comandos*

💬 *Chat*
• Só me chame pelo nome ou mande mensagem no privado!
• Em grupos, me mencione ou diga "Hana"

🎮 *Seções de comandos:*
• */ajuda* — Esta mensagem
• */economia* — Comandos de moedas e XP
• */social* — Interações e reações
• */sobre* — Quem sou eu?
• */ping* — Verificar se estou online

_Digite qualquer um para mais detalhes!_ ✨`;

const HELP_ECONOMIA = `💰 *Economia — Hana Nakamura*

• */daily* — Bônus diário de moedas 🎁
• */perfil* — Seu nível, XP e saldo 🌸
• */ranking* — Top jogadores 🏆
• */depositar [valor]* — Guardar no banco 🏦
• */sacar [valor]* — Retirar do banco 💸
• */roubar [nome]* — Tentar roubar alguém 🥷
  _→ 50% de chance, risco de multa!_

_Moedas ficam salvas entre plataformas_ 🔗`;

const HELP_SOCIAL = `🫂 *Interações — Hana Nakamura*

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

const SOBRE = `🌸 *Hana Nakamura*
_VTuber AI — Sua companheira digital_

Sou uma IA com personalidade de VTuber! Posso:
✨ Conversar sobre qualquer assunto
🎨 Gerar imagens com IA
🎮 Sistema de economia e XP
🫂 Comandos de interação social
🛡️ Moderação (no Discord)

*Stack:* Python + Node.js + OpenRouter
*Plataformas:* Discord • WhatsApp • Web

_"Aqui pra te fazer companhia!"_ 💙`;

// ── Handler de Comandos Locais ────────────────────────────────────────────────

async function handleLocalCommand(sock, remoteJid, msg, text) {
    const cmd = text.trim().toLowerCase().split(/\s+/)[0];

    const responses = {
        '/ajuda':    HELP_GERAL,
        '/help':     HELP_GERAL,
        '/economia': HELP_ECONOMIA,
        '/social':   HELP_SOCIAL,
        '/sobre':    SOBRE,
        '/ping':     '🌸 *Pong!* Estou online e pronta para conversar! ✨',
    };

    if (responses[cmd]) {
        await sock.sendMessage(remoteJid, { text: responses[cmd] }, { quoted: msg });
        return true; // tratado localmente, não chama a API
    }

    return false; // passa pra API
}

// ── Bridge Principal ──────────────────────────────────────────────────────────

async function connectToWhatsApp() {
    console.log("🌸 Iniciando Hana Nakamura WhatsApp Bridge...");
    
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
            console.log('✅ Hana Nakamura está ONLINE no WhatsApp! 🌸');
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
        const mentionsHana = textLower.includes('hana') || textLower.includes('lira') || textLower.includes('amarinth');
        const isCommand = textMessage.startsWith('/');
        const myId = sock.user.id.split(':')[0] + '@s.whatsapp.net';
        const isMentioned = msg.message.extendedTextMessage?.contextInfo?.mentionedJid?.includes(myId);

        console.log(`[LOG] [${isGroup ? 'GRUPO' : 'PRIVADO'}] ${pushName}: ${textMessage.substring(0, 80)}`);

        // No grupo só responde se: mencionar Hana OU ser tagada OU comando
        if (isGroup && !mentionsHana && !isMentioned && !isCommand) return;

        // Comandos locais (sem chamar a API — resposta instantânea)
        if (isCommand) {
            const handled = await handleLocalCommand(sock, remoteJid, msg, textMessage);
            if (handled) return;
        }

        // Reação de "lendo" enquanto processa na API
        try { await sock.sendMessage(remoteJid, { react: { text: '🌸', key: msg.key } }); } catch (_) {}

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
            console.error('❌ Erro na comunicação com a Hana API:', error.message);
        }
    });
}

connectToWhatsApp().catch(err => console.error("Erro crítico:", err));
