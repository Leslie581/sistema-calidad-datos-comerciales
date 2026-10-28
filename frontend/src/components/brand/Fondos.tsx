/**
 * Fondos decorativos propios de KOVA, uno por sección (todos aria-hidden, sin interacción):
 *  - FondoCanales   · Inicio/Panel: dos haces de curvas (físico y online) que convergen en un nodo.
 *  - FondoTrayectos · Centro ETL: trayectorias que atraviesan siete marcas verticales (las fases).
 *  - FondoOrden     · Calidad: retícula de puntos que se alinea de un lado (depuración).
 *  - FondoAislamiento · Cuarentena: bloques modulares con piezas desprendidas, en ámbar.
 *  - FondoEditorial · Reportes/Historial: líneas finas y arcos concéntricos, más sobrio.
 *  - FondoCatalogo  · Catálogo: mosaico de módulos redondeados.
 * Nunca se colocan detrás de tablas densas: solo en cabeceras (hero) y estados vacíos.
 */
type P = { className?: string; oscuro?: boolean };
const base = "pointer-events-none absolute inset-0 h-full w-full";

export function FondoCanales({ className = "", oscuro = true }: P) {
  const c1 = oscuro ? "#B8E8CE" : "#215548";
  const c2 = oscuro ? "#D99B45" : "#D99B45";
  const haz = (y0: number, y1: number, n: number) =>
    Array.from({ length: n }, (_, i) => {
      const t = i / (n - 1);
      const y = y0 + (y1 - y0) * t;
      return `M-20 ${y} C 260 ${y - 70 + t * 30}, 420 ${380 - 40 * t}, 640 ${300 + 10 * t} S 960 ${300 + 10 * t}, 1240 ${300 + 6 * t}`;
    });
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 1200 600" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      {haz(40, 220, 9).map((d, i) => <path key={`a${i}`} d={d} fill="none" stroke={c1} strokeOpacity={0.1 + i * 0.012} strokeWidth="1.3" />)}
      {haz(560, 380, 9).map((d, i) => <path key={`b${i}`} d={d} fill="none" stroke={c2} strokeOpacity={0.1 + i * 0.012} strokeWidth="1.3" />)}
      {Array.from({ length: 6 }, (_, r) => Array.from({ length: 8 }, (_, k) => (
        <circle key={`${r}-${k}`} cx={820 + k * 46} cy={60 + r * 46} r="1.8" fill={c1} fillOpacity={0.18} />
      )))}
      <circle cx="640" cy="300" r="46" fill="none" stroke={c1} strokeOpacity="0.18" />
      <circle cx="640" cy="300" r="82" fill="none" stroke={c1} strokeOpacity="0.1" />
      <circle cx="640" cy="300" r="7" fill={c2} fillOpacity="0.9" />
    </svg>
  );
}

export function FondoTrayectos({ className = "", oscuro = true }: P) {
  const c = oscuro ? "#B8E8CE" : "#215548";
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 1200 400" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      {Array.from({ length: 7 }, (_, i) => (
        <g key={i}>
          <line x1={110 + i * 165} y1="0" x2={110 + i * 165} y2="400" stroke={c} strokeOpacity="0.1" strokeDasharray="2 7" />
          <circle cx={110 + i * 165} cy={200 + Math.sin(i * 1.2) * 60} r="3.2" fill="#D99B45" fillOpacity="0.8" />
        </g>
      ))}
      {Array.from({ length: 7 }, (_, k) => (
        <path key={k} fill="none" stroke={c} strokeOpacity={0.09 + k * 0.012} strokeWidth="1.2"
          d={`M-20 ${40 + k * 52} C 200 ${20 + k * 52}, 360 ${380 - k * 40}, 600 ${200 + (k - 3) * 14} S 1000 ${60 + k * 50}, 1240 ${200 + (k - 3) * 22}`} />
      ))}
    </svg>
  );
}

export function FondoOrden({ className = "", oscuro = false }: P) {
  const c = oscuro ? "#B8E8CE" : "#215548";
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 1200 360" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
      {Array.from({ length: 9 }, (_, r) => Array.from({ length: 26 }, (_, k) => {
        const desorden = Math.max(0, 1 - k / 15);
        const dx = Math.sin((r + 1) * (k + 3) * 1.7) * 11 * desorden;
        const dy = Math.cos((r + 2) * (k + 1) * 1.3) * 11 * desorden;
        return <circle key={`${r}-${k}`} cx={30 + k * 44 + dx} cy={26 + r * 38 + dy} r={k > 15 ? 2.4 : 1.8} fill={c} fillOpacity={k > 15 ? 0.3 : 0.16} />;
      }))}
      {Array.from({ length: 9 }, (_, r) => <line key={r} x1="700" x2="1200" y1={26 + r * 38} y2={26 + r * 38} stroke={c} strokeOpacity="0.1" />)}
    </svg>
  );
}

export function FondoAislamiento({ className = "" }: P) {
  const bloques: [number, number, number][] = [[60, 40, 1], [150, 40, 1], [240, 40, 0], [60, 130, 1], [330, 130, 1], [150, 220, 1], [240, 220, 1], [420, 40, 1], [510, 130, 0]];
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 1200 360" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
      <g transform="translate(560 10)">
        {bloques.map(([x, y, ok], i) => (
          <rect key={i} x={x + 120} y={y} width="72" height="72" rx="18" fill={ok ? "#215548" : "#D99B45"}
            fillOpacity={ok ? 0.1 : 0.28} transform={ok ? undefined : `translate(${14 + i} ${-10 - i})`} />
        ))}
        <path d="M660 40 L660 320" stroke="#D99B45" strokeOpacity="0.4" strokeDasharray="3 8" />
      </g>
      <defs>
        <pattern id="hatch" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="14" stroke="#D99B45" strokeOpacity="0.16" strokeWidth="2" />
        </pattern>
      </defs>
      <rect x="1010" y="0" width="190" height="360" fill="url(#hatch)" />
    </svg>
  );
}

export function FondoEditorial({ className = "", oscuro = false }: P) {
  const c = oscuro ? "#B8E8CE" : "#17352D";
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 1200 300" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
      {Array.from({ length: 8 }, (_, i) => <circle key={i} cx="1080" cy="320" r={60 + i * 42} fill="none" stroke={c} strokeOpacity={0.09 - i * 0.006} />)}
      {Array.from({ length: 5 }, (_, i) => <line key={i} x1="0" x2="1200" y1={60 + i * 52} y2={60 + i * 52} stroke={c} strokeOpacity="0.05" />)}
    </svg>
  );
}

export function FondoCatalogo({ className = "" }: P) {
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 1200 300" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
      {Array.from({ length: 4 }, (_, r) => Array.from({ length: 10 }, (_, k) => {
        const forma = (r + k) % 3;
        const x = 520 + k * 68, y = 20 + r * 68;
        return forma === 0 ? <circle key={`${r}${k}`} cx={x + 28} cy={y + 28} r="26" fill="#215548" fillOpacity="0.08" />
          : forma === 1 ? <rect key={`${r}${k}`} x={x} y={y} width="56" height="56" rx="16" fill="#D99B45" fillOpacity="0.16" />
          : <path key={`${r}${k}`} d={`M${x} ${y + 56}V${y + 20}a20 20 0 0 1 20-20h36v36a20 20 0 0 1-20 20z`} fill="#B8E8CE" fillOpacity="0.5" />;
      }))}
    </svg>
  );
}

/** Pulso comercial: curvas ascendentes y descendentes (ritmo de ventas), con retícula de referencia y un punto ámbar de «hoy». */
export function FondoPulso({ className = "", oscuro = true }: P) {
  const c = oscuro ? "#B8E8CE" : "#215548";
  const curva = (k: number) => {
    const y = 250 - k * 26;
    return `M-20 ${y + 60} C 120 ${y + 20 - k * 4}, 200 ${y + 90}, 330 ${y + 30} S 520 ${y - 40 + k * 6}, 650 ${y - 10} S 900 ${y + 70}, 1030 ${y - 30 - k * 5} S 1160 ${y - 70}, 1240 ${y - 40}`;
  };
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 1200 400" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      {Array.from({ length: 6 }, (_, i) => <line key={i} x1="0" x2="1200" y1={60 + i * 62} y2={60 + i * 62} stroke={c} strokeOpacity="0.07" />)}
      {Array.from({ length: 12 }, (_, i) => <line key={i} y1="0" y2="400" x1={50 + i * 100} x2={50 + i * 100} stroke={c} strokeOpacity="0.05" strokeDasharray="2 8" />)}
      {Array.from({ length: 6 }, (_, k) => <path key={k} d={curva(k)} fill="none" stroke={k === 2 ? "#D99B45" : c} strokeOpacity={k === 2 ? 0.55 : 0.1 + k * 0.02} strokeWidth={k === 2 ? 2 : 1.2} />)}
      <circle cx="1030" cy={250 - 2 * 26 - 30 - 10} r="5" fill="#D99B45" />
      <circle cx="1030" cy={250 - 2 * 26 - 30 - 10} r="14" fill="none" stroke="#D99B45" strokeOpacity="0.4" />
    </svg>
  );
}
