import { Link } from "react-router-dom";
import { EstadoVacio } from "../components/ui/Estados";

export default function NoEncontrada() {
  return (
    <EstadoVacio titulo="Esta página no existe en KOVA" accion={<Link to="/" className="inline-flex min-h-11 items-center rounded-full bg-bosque px-5 text-sm font-bold text-blanco">Volver al inicio</Link>}>
      La dirección que abriste no corresponde a ninguna sección de la plataforma.
    </EstadoVacio>
  );
}
