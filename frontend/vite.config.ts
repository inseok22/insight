import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// 개발 프록시도 deploy/.env의 BACKEND_PORT를 사용합니다. 브라우저에는 노출하지 않습니다.
// 운영 dist의 /api 요청은 Nginx가 처리하므로 포트 변경만으로 프론트 재빌드는 필요 없습니다.
export default defineConfig(({ mode }) => {
    // npm runs this package's scripts from frontend/.
    const env = loadEnv(mode, '../deploy', 'BACKEND_PORT')
    const port = Number(env.BACKEND_PORT ?? '18000')
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error('BACKEND_PORT must be an integer between 1 and 65535')
    }
    return {
        plugins: [react()],
        server: {
            proxy: {
                '/api': {
                    target: `http://127.0.0.1:${port}`,
                    changeOrigin: true,
                },
            },
        },
    }
})
