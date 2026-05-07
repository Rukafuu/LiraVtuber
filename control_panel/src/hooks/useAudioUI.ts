import { useEffect, useRef } from 'react';

/**
 * Hook para gerar efeitos sonoros Sci-Fi utilizando a Web Audio API.
 * Sem dependência de ficheiros externos. Leve e rápido.
 */
export function useAudioUI() {
  const audioCtxRef = useRef<AudioContext | null>(null);

  // Inicializa o AudioContext ao montar
  useEffect(() => {
    // Só tenta criar se o browser suportar
    if (window.AudioContext || (window as any).webkitAudioContext) {
      audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    return () => {
      if (audioCtxRef.current?.state !== 'closed') {
        audioCtxRef.current?.close();
      }
    };
  }, []);

  const playOscillator = (
    type: OscillatorType,
    freqStart: number,
    freqEnd: number,
    durationMs: number,
    volLevel: number = 0.05
  ) => {
    if (!audioCtxRef.current) return;
    
    // Retomar contexto caso esteja suspenso (política do browser)
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }

    const ctx = audioCtxRef.current;
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freqStart, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(freqEnd, ctx.currentTime + durationMs / 1000);

    // Fade out suave para evitar "cliques" no final do som
    gainNode.gain.setValueAtTime(volLevel, ctx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durationMs / 1000);

    osc.connect(gainNode);
    gainNode.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + durationMs / 1000);
  };

  const playHover = () => {
    // Bip curto e agudo
    playOscillator('sine', 800, 1200, 50, 0.02);
  };

  const playClick = () => {
    // Click firme (mecânico/sci-fi)
    playOscillator('square', 150, 50, 80, 0.05);
    // Overlap com um bip agudo rápido
    setTimeout(() => playOscillator('sine', 2000, 3000, 30, 0.03), 10);
  };

  const playToggleOn = () => {
    // Som subindo de tom
    playOscillator('triangle', 300, 800, 150, 0.04);
  };

  const playToggleOff = () => {
    // Som descendo de tom
    playOscillator('triangle', 800, 300, 150, 0.04);
  };

  const playStartup = () => {
    if (!audioCtxRef.current) return;
    const ctx = audioCtxRef.current;
    if (ctx.state === 'suspended') ctx.resume();

    // Acorde futurista varrendo frequências
    const freqs = [220, 330, 440, 550, 880];
    freqs.forEach((freq, i) => {
      setTimeout(() => {
        playOscillator('sine', freq, freq * 1.5, 800, 0.03);
      }, i * 150);
    });
  };

  return {
    playHover,
    playClick,
    playToggleOn,
    playToggleOff,
    playStartup,
  };
}
