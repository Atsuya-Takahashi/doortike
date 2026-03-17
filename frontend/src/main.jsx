import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ReactGA from "react-ga4"

const gaId = import.meta.env.VITE_GA_ID;
// 本番環境 かつ IDが設定されている時だけ起動
if (import.meta.env.MODE === "production" && gaId) {
  ReactGA.initialize(gaId);
}

console.log("main.jsx module executing");

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
