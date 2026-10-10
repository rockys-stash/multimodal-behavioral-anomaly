import "@fontsource/geist-sans/400.css";
import "@fontsource/geist-sans/500.css";
import "@fontsource/geist-sans/600.css";
import "@fontsource/geist-mono/400.css";
import "@fontsource/geist-mono/500.css";
import "./styles.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Ablation } from "./pages/Ablation";
import { Errors } from "./pages/Errors";
import { Experiments } from "./pages/Experiments";
import { Method } from "./pages/Method";
import { NotFound } from "./pages/NotFound";
import { People } from "./pages/People";
import { Person } from "./pages/Person";

const root = document.getElementById("root");
if (!root) throw new Error("missing #root element");

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/people" replace />} />
          <Route path="people" element={<People />} />
          <Route path="people/:uuid" element={<Person />} />
          <Route path="ablation" element={<Ablation />} />
          <Route path="errors" element={<Errors />} />
          <Route path="experiments" element={<Experiments />} />
          <Route path="experiments/:exp" element={<Experiments />} />
          <Route path="method" element={<Method />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
