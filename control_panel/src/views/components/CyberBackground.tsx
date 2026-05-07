import { useEffect, useRef } from 'react';

export function CyberBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let particles: {x: number, y: number, size: number, speedX: number, speedY: number, opacity: number}[] = [];
    
    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    // Inicializa partículas
    for (let i = 0; i < 70; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        size: Math.random() * 2 + 0.5,
        speedX: (Math.random() - 0.5) * 0.5,
        speedY: (Math.random() - 0.5) * 0.5 - 0.2, // Tende a subir
        opacity: Math.random() * 0.5 + 0.1
      });
    }

    const drawGrid = (time: number) => {
      // Pega a cor principal (neon) do CSS variable
      const computedStyle = getComputedStyle(document.documentElement);
      let neonColor = computedStyle.getPropertyValue('--purple-neon').trim() || '#a855f7';
      
      // Converte HEX para RGB se necessário para lidar com opacidade no canvas
      // Por simplicidade, usaremos shadowColor global para o brilho

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // --- 1. Grelha Holográfica ---
      const gridSize = 40;
      const perspectiveOffset = (time / 30) % gridSize;
      
      ctx.lineWidth = 1;
      
      // Desenha linhas horizontais com efeito de perspectiva (fade out no topo)
      for (let y = canvas.height; y > 0; y -= gridSize) {
        const adjustedY = y + perspectiveOffset;
        if (adjustedY > canvas.height) continue;
        
        // Opacidade diminui à medida que sobe (y menor)
        const opacity = Math.max(0.02, (adjustedY / canvas.height) * 0.15);
        ctx.strokeStyle = `rgba(255, 255, 255, ${opacity})`;
        
        ctx.beginPath();
        ctx.moveTo(0, adjustedY);
        ctx.lineTo(canvas.width, adjustedY);
        ctx.stroke();
      }

      // Desenha linhas verticais (efeito tunel a partir do centro superior)
      const centerX = canvas.width / 2;
      for (let i = -20; i <= 20; i++) {
        const xOffset = i * gridSize * 1.5;
        
        // Gradiente para as linhas verticais
        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
        gradient.addColorStop(0, `rgba(255, 255, 255, 0.0)`);
        gradient.addColorStop(1, `rgba(255, 255, 255, 0.1)`);
        
        ctx.strokeStyle = gradient;
        ctx.beginPath();
        // Sai de um ponto comum no topo (vanishing point)
        ctx.moveTo(centerX + (xOffset * 0.2), 0);
        ctx.lineTo(centerX + xOffset, canvas.height);
        ctx.stroke();
      }

      // --- 2. Partículas Flutuantes ---
      ctx.shadowBlur = 10;
      ctx.shadowColor = neonColor;
      ctx.fillStyle = neonColor;

      particles.forEach(p => {
        // Atualiza posição
        p.x += p.speedX;
        p.y += p.speedY;

        // Efeito de cintilação (piscar)
        p.opacity += (Math.random() - 0.5) * 0.05;
        p.opacity = Math.max(0.1, Math.min(0.8, p.opacity));

        // Loop das partículas (reaparecem no fundo ou dos lados)
        if (p.y < -10) p.y = canvas.height + 10;
        if (p.x < -10) p.x = canvas.width + 10;
        if (p.x > canvas.width + 10) p.x = -10;

        ctx.globalAlpha = p.opacity;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });
      
      ctx.globalAlpha = 1.0;
      ctx.shadowBlur = 0;
    };

    const renderLoop = (time: number) => {
      drawGrid(time);
      animationFrameId = requestAnimationFrame(renderLoop);
    };

    animationFrameId = requestAnimationFrame(renderLoop);

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="fixed top-0 left-0 w-full h-full pointer-events-none z-[-1] overflow-hidden bg-[var(--bg-dark)]">
      {/* Imagem de fundo opcional esmaecida (pode ser a foto da Lira) */}
      <div 
        className="absolute inset-0 opacity-[0.03] mix-blend-screen"
        style={{
          backgroundImage: 'url(/lira_foto_01.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          filter: 'blur(8px) grayscale(100%)'
        }}
      />
      
      <canvas 
        ref={canvasRef} 
        className="absolute inset-0"
      />
      
      {/* Vignette effect (bordas mais escuras) */}
      <div className="absolute inset-0 bg-gradient-radial from-transparent to-[var(--bg-dark)] opacity-80" />
    </div>
  );
}
