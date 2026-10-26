import { lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { SistemaProvider } from "./layouts/SistemaProvider";
import Inicio from "./pages/Inicio";
import NoEncontrada from "./pages/NoEncontrada";

const Panel = lazy(() => import("./pages/Panel"));
const CentroETL = lazy(() => import("./pages/CentroETL"));
const Calidad = lazy(() => import("./pages/Calidad"));
const Transacciones = lazy(() => import("./pages/Transacciones"));
const Cuarentena = lazy(() => import("./pages/Cuarentena"));
const Catalogo = lazy(() => import("./pages/Catalogo"));
const Historial = lazy(() => import("./pages/Historial"));

export default function App() {
  return (
    <SistemaProvider>
      <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<Inicio />} />
            <Route path="panel" element={<Panel />} />
            <Route path="etl" element={<CentroETL />} />
            <Route path="calidad" element={<Calidad />} />
            <Route path="transacciones/:id?" element={<Transacciones />} />
            <Route path="cuarentena/:id?" element={<Cuarentena />} />
            <Route path="catalogo" element={<Catalogo />} />
            <Route path="historial" element={<Historial />} />
            <Route path="*" element={<NoEncontrada />} />
          </Route>
      </Routes>
    </SistemaProvider>
  );
}
