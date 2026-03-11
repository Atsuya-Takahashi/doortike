import { initializeApp, getApps } from "firebase/app";
import { getAuth, GoogleAuthProvider, OAuthProvider } from "firebase/auth";
import { getAnalytics, isSupported } from "firebase/analytics";
import { getFirestore } from "firebase/firestore";

console.log("firebase.js module executing");

const firebaseConfig = {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
    measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID
};

let app, auth, db, googleProvider, appleProvider, analytics;

try {
    if (firebaseConfig.apiKey) {
        app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
        auth = getAuth(app);
        db = getFirestore(app);
        googleProvider = new GoogleAuthProvider();
        appleProvider = new OAuthProvider('apple.com');

        // アナリティクスの初期化 (ブラウザがサポートしている場合のみ)
        isSupported().then((supported) => {
            if (supported) {
                analytics = getAnalytics(app);
            }
        });
    } else {
        console.warn("Firebase config is missing. Please create .env.local with VITE_FIREBASE_API_KEY.");
    }
} catch (e) {
    console.error("Firebase initialization failed:", e);
}

export { auth, db, googleProvider, appleProvider, analytics };
