import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], base: '/factory/exchange/', build: { sourcemap: false }, server: { proxy: { '/factory/exchange-snapshot': 'http://127.0.0.1:9089' } } });
