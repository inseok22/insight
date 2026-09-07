import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 로컬 개발서버(5173)에서 /api 요청을 백엔드(8000)로 프록시.
// → VITE_API_BASE_URL을 비워(상대경로) 두면 로컬은 vite가, 서버는 nginx가 처리해서 동일하게 동작.
export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
            },
        },
    },
})
