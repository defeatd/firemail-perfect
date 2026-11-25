// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { getNodeModulePackageName, resolveManualChunk } from '../../../vite.config.js'

describe('vite manualChunks resolution (anti-circular chunk guard)', () => {
  it('extracts exact package name from npm and pnpm virtual store paths', () => {
    expect(
      getNodeModulePackageName('/app/frontend/node_modules/vue-demi/lib/index.mjs')
    ).toBe('vue-demi')

    expect(
      getNodeModulePackageName(
        '/app/frontend/node_modules/.pnpm/element-plus@2.9.10_vue@3.5.14/node_modules/element-plus/es/components/button/index.mjs'
      )
    ).toBe('element-plus')

    expect(
      getNodeModulePackageName(
        '/app/frontend/node_modules/.pnpm/@vueuse+core@11.3.0_vue@3.5.14/node_modules/@vueuse/core/index.mjs'
      )
    ).toBe('@vueuse/core')

    expect(
      getNodeModulePackageName(
        'C:\\repo\\frontend\\node_modules\\.pnpm\\pinia@2.3.1_vue@3.5.14\\node_modules\\pinia\\dist\\pinia.mjs'
      )
    ).toBe('pinia')

    expect(getNodeModulePackageName('/app/frontend/src/views/HomeView.vue')).toBeNull()
  })

  it('places vue, @vue/*, vue-demi, vue-router and pinia in zero-outdegree vue-vendor', () => {
    const vueVendorPaths = [
      '/app/frontend/node_modules/vue/dist/vue.runtime.esm-bundler.js',
      '/app/frontend/node_modules/.pnpm/@vue+reactivity@3.5.14/node_modules/@vue/reactivity/dist/reactivity.esm-bundler.js',
      '/app/frontend/node_modules/.pnpm/vue-demi@0.14.10_vue@3.5.14/node_modules/vue-demi/lib/index.mjs',
      '/app/frontend/node_modules/.pnpm/pinia@2.3.1_vue@3.5.14/node_modules/pinia/dist/pinia.mjs',
      '/app/frontend/node_modules/vue-router/dist/vue-router.mjs'
    ]

    for (const modPath of vueVendorPaths) {
      expect(resolveManualChunk(modPath)).toBe('vue-vendor')
    }
  })

  it('places element-plus and its UI helpers in element-plus without leaking into vue-vendor', () => {
    const epPaths = [
      '/app/frontend/node_modules/.pnpm/element-plus@2.9.10_vue@3.5.14/node_modules/element-plus/es/index.mjs',
      '/app/frontend/node_modules/.pnpm/@element-plus+icons-vue@2.3.1_vue@3.5.14/node_modules/@element-plus/icons-vue/dist/index.js',
      '/app/frontend/node_modules/.pnpm/@vueuse+core@11.3.0_vue@3.5.14/node_modules/@vueuse/core/index.mjs',
      '/app/frontend/node_modules/.pnpm/@floating-ui+dom@1.6.13/node_modules/@floating-ui/dom/dist/floating-ui.dom.mjs',
      '/app/frontend/node_modules/lodash-es/debounce.js'
    ]

    for (const modPath of epPaths) {
      expect(resolveManualChunk(modPath)).toBe('element-plus')
    }
  })

  it('places dompurify in its own chunk and leaves app code / axios default', () => {
    expect(
      resolveManualChunk('/app/frontend/node_modules/dompurify/dist/purify.es.mjs')
    ).toBe('dompurify')
    expect(resolveManualChunk('/app/frontend/node_modules/axios/lib/axios.js')).toBeUndefined()
    expect(resolveManualChunk('/app/frontend/src/main.js')).toBeUndefined()
  })
})
