import { resolve } from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Two surfaces, two entry points, two bundles. The public page and the
// enforcement console share components but are never served as one app: the
// public bundle must not contain the flag queue or the case files.
//
// SURFACE=public|console builds one surface alone, which is what the
// single-file packaging step wants. Unset builds both.
const ENTRIES = {
  console: resolve(__dirname, 'index.html'),
  public: resolve(__dirname, 'report.html'),
}
const surface = process.env.SURFACE

// The console is served under /console when the API server hosts it, so its
// asset URLs must be prefixed or they resolve against the public mount and 404.
// Irrelevant for the single-file artifact build, where assets are inlined.
const base = surface === 'console' ? '/console/' : '/'

export default defineConfig({
  base,
  plugins: [react()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      input: surface ? { [surface]: ENTRIES[surface] } : ENTRIES,
    },
  },
})
