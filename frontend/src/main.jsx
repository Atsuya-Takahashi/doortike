import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ReactGA from "react-ga4"

const gaId = import.meta.env.VITE_GA_ID;
// IDが設定されている時だけ起動（開発環境でもテスト可能にする）
if (gaId) {
  ReactGA.initialize(gaId, {
    gaOptions: {
      debug_mode: true
    }
  });
  console.log("GA4 Initialized with ID:", gaId);
}

console.log("main.jsx module executing");

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
