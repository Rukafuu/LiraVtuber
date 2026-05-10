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
        const mentionsHana = textLower.includes('hana') || textLower.includes('nakamura');
        const isCommand = textMessage.startsWith('/');
        const myId = sock.user.id.split(':')[0] + '@s.whatsapp.net';
        const isMentioned = msg.message.extendedTextMessage?.contextInfo?.mentionedJid?.includes(myId);

        console.log(`[LOG] [${isGroup ? 'GRUPO' : 'PRIVADO'}] ${pushName}: ${textMessage.substring(0, 80)}`);

        // No grupo só responde se: mencionar Hana OU ser tagada OU comando
        if (isGroup && !mentionsHana && !isMentioned && !isCommand) {
            return;
        }

        // Reação de "lendo" enquanto processa
        try { await sock.sendMessage(remoteJid, { react: { text: '🌸', key: msg.key } }); } catch (_) {}

        try {
            const response = await axios.post('http://127.0.0.1:8042/api/whatsapp/chat', {
                message: textMessage,
                sender: pushName,
                jid: remoteJid
            });

            if (response.data && response.data.status === 'ok') {
                const data = response.data;
                
                // Se a API mandou uma imagem (ex: Perfil, Gerador de Arte)
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
                            console.error(`❌ Erro ao enviar imagem via WhatsApp:`, sendError.message);
                            await sock.sendMessage(remoteJid, { text: data.response + "\n\n⚠️ (Erro ao enviar a imagem anexa)" }, { quoted: msg });
                        }
                    } else {
                        console.warn(`⚠️ Arquivo de imagem não encontrado: ${data.image_path}`);
                        await sock.sendMessage(remoteJid, { text: data.response + "\n\n❌ Imagem não encontrada no servidor." }, { quoted: msg });
                    }
                } else {
                    // Resposta normal em texto
                    await sock.sendMessage(remoteJid, { text: data.response }, { quoted: msg });
                }
            }
        } catch (error) {
            console.error('❌ Erro na comunicação com a Lira API:', error.message);
        }
    });
}

connectToWhatsApp().catch(err => console.error("Erro crítico:", err));
