import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import QRCode from "qrcode";
import { ApiController } from "../../controllers/api";
import type { ServiceStatus, WhatsAppSession } from "../../models/types";
import { Loader2, Smartphone } from "lucide-react";

interface Props {
  bridge: ServiceStatus | undefined;
}

export function WhatsAppSessionPanel({ bridge }: Props) {
  const { t } = useTranslation();
  const [session, setSession] = useState<WhatsAppSession | null>(null);
  const [qrImage, setQrImage] = useState<string | null>(null);
  const [qrLoading, setQrLoading] = useState(false);

  const watchSession = useMemo(() => {
    if (!bridge) return false;
    if (bridge.state === "stopped") return false;
    if (bridge.connection === "connected") return false;
    return true;
  }, [bridge]);

  useEffect(() => {
    if (!watchSession) {
      setSession(null);
      return;
    }
    let cancelled = false;
    const poll = async () => {
      const data = await ApiController.getWhatsAppSession();
      if (!cancelled) setSession(data);
    };
    poll();
    const id = setInterval(poll, 1500);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [watchSession, bridge?.state, bridge?.connection]);

  const qrKey = session?.qr?.available
    ? `${session.qr.revision}:${session.qr.fingerprint ?? ""}`
    : null;

  useEffect(() => {
    if (!session?.qr?.available || !session.qr.payload) {
      setQrImage(null);
      setQrLoading(false);
      return;
    }
    let cancelled = false;
    setQrLoading(true);
    QRCode.toDataURL(session.qr.payload, {
      width: 280,
      margin: 2,
      errorCorrectionLevel: "M",
      color: { dark: "#1a0a2e", light: "#ffffff" },
    })
      .then((url) => {
        if (!cancelled) setQrImage(url);
      })
      .catch(() => {
        if (!cancelled) setQrImage(null);
      })
      .finally(() => {
        if (!cancelled) setQrLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [qrKey, session?.qr?.payload]);

  if (!watchSession) return null;

  const statusHint = session?.status_message;
  const showQr = session?.qr?.available && qrImage;
  const showPairing = !!session?.pairing_code;

  if (!showQr && !showPairing && !qrLoading) {
    return (
      <div className="glass-panel rounded-2xl p-5 border border-amber-500/30 flex flex-col gap-2 text-amber-200/90 text-sm">
        <div className="flex items-center gap-3">
          <Loader2 size={18} className="animate-spin shrink-0" />
          {t("servicos.qr_waiting")}
        </div>
        {statusHint && <p className="text-xs pl-8">{statusHint}</p>}
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-2xl p-5 border border-[var(--cyan-neon)]/30 flex flex-col md:flex-row gap-6 items-center md:items-start">
      <div className="flex items-center gap-2 text-white shrink-0">
        <Smartphone className="text-[var(--cyan-neon)]" size={22} />
        <div>
          <h3 className="font-bold text-lg">{t("servicos.qr_title")}</h3>
          <p className="text-xs text-[var(--text-secondary)]">{t("servicos.qr_hint")}</p>
          {statusHint && (
            <p className="text-xs text-amber-200/90 mt-1">{statusHint}</p>
          )}
        </div>
      </div>

      {showQr && (
        <div className="flex flex-col items-center gap-2">
          <div
            key={qrKey ?? "qr"}
            className="p-3 bg-white rounded-xl shadow-[0_0_24px_rgba(34,211,238,0.25)] animate-fade-in"
          >
            {qrLoading ? (
              <div className="w-[280px] h-[280px] flex items-center justify-center">
                <Loader2 className="animate-spin text-[var(--purple-neon)]" size={32} />
              </div>
            ) : (
              <img
                src={qrImage!}
                alt={t("servicos.qr_alt")}
                width={280}
                height={280}
                className="block"
              />
            )}
          </div>
          {session?.qr?.updated_at && (
            <span className="text-[10px] font-mono text-[var(--text-muted)]">
              {t("servicos.qr_updated")}: {session.qr.updated_at}
            </span>
          )}
        </div>
      )}

      {showPairing && (
        <div className="flex flex-col gap-2 md:ml-auto">
          <span className="text-xs uppercase tracking-widest text-[var(--text-muted)]">
            {t("servicos.pairing_label")}
          </span>
          <span className="text-3xl font-mono font-bold text-[var(--cyan-neon)] tracking-widest">
            {session!.pairing_code}
          </span>
        </div>
      )}
    </div>
  );
}