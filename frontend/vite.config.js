import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8'))
const port = process.env.VITE_PORT ? parseInt(process.env.VITE_PORT, 10) : 3000

const VUE_CORE_PACKAGES = new Set(['vue', 'vue-demi', 'vue-router', 'pinia'])

/**
 * 从 Rollup 模块 ID 中提取最后一个 /node_modules/ 之后的精确包名，
 * 彻底免疫 pnpm 虚拟存储路径（如 .pnpm/element-plus@2.9.10_vue@3.5.14/node_modules/element-plus/...）干扰。
 */
export function getNodeModulePackageName(id) {
  if (!id) return null
  const normalized = id.replace(/\\/g, '/')
  const marker = '/node_modules/'
  const idx = normalized.lastIndexOf(marker)
  if (idx === -1) return null
  const rest = normalized.slice(idx + marker.length)
  const parts = rest.split('/')
  if (!parts[0]) return null
  if (parts[0].startsWith('@')) {
    return parts[1] ? `${parts[0]}/${parts[1]}` : null
  }
  return parts[0]
}

export function resolveManualChunk(id) {
  const pkgName = getNodeModulePackageName(id)
  if (!pkgName) return undefined
  // 闭合零外部依赖集合：vue / @vue/* / vue-demi / vue-router / pinia 绝不依赖外部包，出度恒为 0
  if (VUE_CORE_PACKAGES.has(pkgName) || pkgName.startsWith('@vue/')) {
    return 'vue-vendor'
  }
  if (pkgName === 'dompurify') {
    return 'dompurify'
  }
  if (
    pkgName === 'element-plus' ||
    pkgName.startsWith('@element-plus/') ||
    pkgName.startsWith('@vueuse/') ||
    pkgName.startsWith('@floating-ui/') ||
    pkgName === '@popperjs/core' ||
    pkgName === '@sxzz/popperjs-es' ||
    pkgName === '@ctrl/tinycolor' ||
    pkgName === 'async-validator' ||
    pkgName === 'lodash-es' ||
    pkgName === 'lodash-unified'
  ) {
    return 'element-plus'
  }
  return undefined
}

function assertNoCircularChunks() {
  return {
    name: 'firemail-assert-no-circular-chunks',
    generateBundle(_options, bundle) {
      const graph = new Map()
      for (const [fileName, item] of Object.entries(bundle)) {
        if (item.type === 'chunk') {
          graph.set(fileName, item.imports || [])
        }
      }
      const visiting = new Set()
      const visited = new Set()
      const stack = []

      const dfs = (node) => {
        visiting.add(node)
        stack.push(node)
        for (const dep of graph.get(node) || []) {
          if (!graph.has(dep)) continue
          if (visiting.has(dep)) {
            const cycle = [...stack.slice(stack.indexOf(dep)), dep].join(' -> ')
            this.error(`检测到致命的前端产物循环分包依赖 (Circular Chunk): ${cycle}`)
          }
          if (!visited.has(dep)) {
            dfs(dep)
          }
        }
        stack.pop()
        visiting.delete(node)
        visited.add(node)
      }

      for (const node of graph.keys()) {
        if (!visited.has(node)) dfs(node)
      }
    }
  }
}

export default defineConfig({
  plugins: [vue(), assertNoCircularChunks()],
  define: {
    __APP_VERSION__: JSON.stringify(process.env.VITE_APP_VERSION || pkg.version || '1.0.0')
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: resolveManualChunk
      }
    }
  },
  server: {
    cors: true,
    port,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://127.0.0.1:8765',
        ws: true
      }
    }
  }
})
