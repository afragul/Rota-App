import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// Üretim derlemesine (yalnızca build, dev'de değil) bir CSP meta tag'i ekler.
// Dev'de eklenmiyor: @vitejs/plugin-react'in Fast Refresh preamble'ı index.html'e
// satır içi (inline) bir <script> enjekte ediyor — script-src'de 'unsafe-inline'
// olmadan bu HMR'ı kırardı. Build çıktısında böyle bir inline script yok (her şey
// dışarıdan yüklenen, derlenmiş dosyalarda), o yüzden script-src strict kalabiliyor.
function cspPlugin(): Plugin {
  const csp = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://*.tile.openstreetmap.org",
    "connect-src 'self' https://*.supabase.co",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    // frame-ancestors bir meta tag'de desteklenmiyor (spec: yalnızca HTTP
    // header üzerinden); gerçek web sunucusu kurulunca (ROADMAP.md "Yayın
    // mimarisi kararı") X-Frame-Options/CSP header'ı olarak eklenmeli.
  ].join('; ')

  return {
    name: 'rota-csp',
    apply: 'build',
    transformIndexHtml(html) {
      return html.replace(
        '</title>',
        `</title>\n    <meta http-equiv="Content-Security-Policy" content="${csp}" />`,
      )
    },
  }
}

// Dev'de /api/* istekleri FastAPI'ye (8000) yönlenir; CORS ayarı gerekmez.
export default defineConfig({
  plugins: [react(), cspPlugin()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
