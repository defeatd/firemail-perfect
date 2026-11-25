import { ref, onMounted, onUnmounted } from 'vue'

const MOBILE_QUERY = '(max-width: 767.98px)'
const NARROW_QUERY = '(max-width: 1199.98px)'

export function useBreakpoint() {
  const isMobile = ref(
    typeof window !== 'undefined' && Boolean(window.matchMedia?.(MOBILE_QUERY).matches)
  )
  const isNarrow = ref(
    typeof window !== 'undefined' && Boolean(window.matchMedia?.(NARROW_QUERY).matches)
  )

  let mqlMobile = null
  let mqlNarrow = null

  const onMobileChange = (e) => {
    isMobile.value = e.matches
  }
  const onNarrowChange = (e) => {
    isNarrow.value = e.matches
  }

  onMounted(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    mqlMobile = window.matchMedia(MOBILE_QUERY)
    mqlNarrow = window.matchMedia(NARROW_QUERY)
    isMobile.value = mqlMobile.matches
    isNarrow.value = mqlNarrow.matches
    mqlMobile.addEventListener('change', onMobileChange)
    mqlNarrow.addEventListener('change', onNarrowChange)
  })

  onUnmounted(() => {
    mqlMobile?.removeEventListener('change', onMobileChange)
    mqlNarrow?.removeEventListener('change', onNarrowChange)
  })

  return { isMobile, isNarrow }
}
