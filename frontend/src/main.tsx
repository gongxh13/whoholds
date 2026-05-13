import { App } from "@/App";
import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";

const root = document.getElementById("root");
if (!root) throw new Error("missing #root in index.html");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
