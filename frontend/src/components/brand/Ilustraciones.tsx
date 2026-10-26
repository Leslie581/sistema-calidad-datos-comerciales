import type { ReactElement } from "react";
import { fEntero } from "../../lib/format";

/**
 * Convergencia de canales: dos fuentes (CSV físico y JSON online) se unen en el núcleo KOVA y se bifurcan en
 * transacciones limpias y cuarentena. Los números, cuando existen, vienen de la última carga real.
 */
export function IlustracionConvergencia({ fisica, online, limpias, cuarentena, className = "" }: {
  fisica?: number; online?: number; limpias?: number; cuarentena?: number; className?: string;
}) {
  const num = (n?: number) => (n == null ? "" : fEntero(n));
  return (
    <svg viewBox="0 0 620 440" className={className} role="img"
      aria-label={`Ilustración: dos canales de venta convergen en KOVA y se separan en transacciones limpias y cuarentena${limpias != null ? `: ${limpias} limpias, ${cuarentena} en cuarentena` : ""}`}>
      <defs>
        <linearGradient id="ic-v" x1="0" x2="1"><stop offset="0" stopColor="#B8E8CE" stopOpacity="0.9" /><stop offset="1" stopColor="#B8E8CE" stopOpacity="0.3" /></linearGradient>
        <linearGradient id="ic-a" x1="0" x2="1"><stop offset="0" stopColor="#D99B45" stopOpacity="0.9" /><stop offset="1" stopColor="#D99B45" stopOpacity="0.3" /></linearGradient>
      </defs>
      {/* conexiones */}
      <g fill="none" strokeWidth="2.2" strokeLinecap="round">
        <path d="M150 112 C 250 112, 250 210, 322 214" stroke="url(#ic-v)" className="flujo-animado" />
        <path d="M150 328 C 250 328, 250 232, 322 226" stroke="url(#ic-a)" className="flujo-animado" />
        <path d="M398 214 C 460 214, 466 120, 520 112" stroke="#B8E8CE" strokeOpacity="0.8" className="flujo-animado" />
        <path d="M398 228 C 460 228, 466 322, 520 328" stroke="#D99B45" strokeOpacity="0.85" className="flujo-animado" />
      </g>
      {/* fuentes */}
      <g>
        <rect x="26" y="68" width="124" height="88" rx="22" fill="#FDFCFA" fillOpacity="0.12" stroke="#B8E8CE" strokeOpacity="0.45" />
        {[0, 1, 2].map((i) => <rect key={i} x="44" y={86 + i * 14} width={i === 0 ? 70 : 88} height="6" rx="3" fill="#B8E8CE" fillOpacity={0.75 - i * 0.2} />)}
        <text x="44" y="144" fill="#FDFCFA" fontSize="14" fontWeight="700" fontFamily="inherit">Tienda física</text>
        <text x="136" y="144" fill="#B8E8CE" fontSize="11" fontWeight="700" textAnchor="end" fontFamily="inherit">CSV</text>
        <text x="26" y="56" fill="#B8E8CE" fontSize="13" fontWeight="700" className="num" fontFamily="inherit">{num(fisica)}</text>
      </g>
      <g>
        <rect x="26" y="284" width="124" height="88" rx="22" fill="#FDFCFA" fillOpacity="0.12" stroke="#D99B45" strokeOpacity="0.55" />
        <text x="44" y="322" fill="#D99B45" fontSize="26" fontWeight="800" fontFamily="inherit">{"{ }"}</text>
        <text x="44" y="360" fill="#FDFCFA" fontSize="14" fontWeight="700" fontFamily="inherit">Tienda online</text>
        <text x="136" y="360" fill="#D99B45" fontSize="11" fontWeight="700" textAnchor="end" fontFamily="inherit">JSON</text>
        <text x="26" y="272" fill="#D99B45" fontSize="13" fontWeight="700" className="num" fontFamily="inherit">{num(online)}</text>
      </g>
      {/* núcleo: isotipo ampliado */}
      <g transform="translate(300 142) scale(1.55)">
        <path d="M14 30V22a8 8 0 0 1 8-8h8v14a2 2 0 0 1-2 2H14z" fill="#B8E8CE" />
        <path d="M34 14h8a8 8 0 0 1 8 8v8H36a2 2 0 0 1-2-2V14z" fill="#FDFCFA" />
        <path d="M14 34h14a2 2 0 0 1 2 2v14h-8a8 8 0 0 1-8-8v-8z" fill="#FDFCFA" fillOpacity=".62" />
        <path d="M34 36a2 2 0 0 1 2-2h14v8a8 8 0 0 1-8 8h-8V36z" fill="#B8E8CE" fillOpacity=".62" />
        <circle cx="32" cy="32" r="4.4" fill="#D99B45" stroke="#17352D" strokeWidth="2.6" />
      </g>
      {/* salidas */}
      <g>
        <rect x="520" y="68" width="82" height="88" rx="22" fill="#B8E8CE" fillOpacity="0.92" />
        <path d="M545 104l10 10 20-22" fill="none" stroke="#17352D" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        <text x="561" y="146" fill="#17352D" fontSize="12" fontWeight="800" textAnchor="middle" fontFamily="inherit">Limpias</text>
        <text x="561" y="58" fill="#B8E8CE" fontSize="15" fontWeight="800" textAnchor="middle" className="num" fontFamily="inherit">{num(limpias)}</text>
      </g>
      <g>
        <rect x="520" y="284" width="82" height="88" rx="22" fill="#D99B45" fillOpacity="0.95" />
        <path d="M561 306v28M561 346v.5" stroke="#17352D" strokeWidth="5.5" strokeLinecap="round" />
        <text x="561" y="364" fill="#17352D" fontSize="11.5" fontWeight="800" textAnchor="middle" fontFamily="inherit">Cuarentena</text>
        <text x="561" y="272" fill="#D99B45" fontSize="15" fontWeight="800" textAnchor="middle" className="num" fontFamily="inherit">{num(cuarentena)}</text>
      </g>
    </svg>
  );
}

/** Isotipo por categoría comercial (representación gráfica, NO fotografía de producto). */
export function IconoCategoria({ categoria, tam = 56 }: { categoria: string; tam?: number }) {
  const c = categoria.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const paleta: Record<string, [string, string]> = {
    alimentos: ["#E3F3EA", "#2B7A57"], deportes: ["#E6EEF0", "#215548"], electronica: ["#FBF0DC", "#85570F"],
    hogar: ["#EEF1E4", "#4C6B3C"], jugueteria: ["#F9E5E1", "#A2443A"], ropa: ["#EAE6F2", "#5B4B8A"],
  };
  const [fondo, trazo] = paleta[c] ?? ["#F0EFE6", "#215548"];
  const glifo: Record<string, ReactElement> = {
    alimentos: <path d="M32 18c8 0 14 7 14 15 0 9-6 15-14 15s-14-6-14-15c0-8 6-15 14-15zm0-6c0 4 3 6 6 6" />,
    deportes: <><circle cx="32" cy="32" r="15" /><path d="M17 32h30M32 17c6 8 6 22 0 30M32 17c-6 8-6 22 0 30" /></>,
    electronica: <><rect x="16" y="19" width="32" height="22" rx="4" /><path d="M24 48h16M32 41v7" /></>,
    hogar: <path d="M16 32L32 17l16 15M21 29v18h22V29M29 47V37h6v10" />,
    jugueteria: <><rect x="18" y="26" width="28" height="22" rx="4" /><path d="M32 26v22M18 36h28M32 26c-3-8-11-8-11-3s8 3 11 3zm0 0c3-8 11-8 11-3s-8 3-11 3z" /></>,
    ropa: <path d="M24 17l-10 8 6 6 4-3v20h16V28l4 3 6-6-10-8c-1 4-4 6-8 6s-7-2-8-6z" />,
  };
  return (
    <svg width={tam} height={tam} viewBox="0 0 64 64" role="img" aria-label={`Categoría ${categoria}`}>
      <rect width="64" height="64" rx="20" fill={fondo} />
      <g fill="none" stroke={trazo} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">{glifo[c] ?? <circle cx="32" cy="32" r="12" />}</g>
    </svg>
  );
}
