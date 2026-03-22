// frontend/src/composables/useResponsive.js
import { ref } from 'vue'

const MOBILE_BREAKPOINT = '(max-width: 768px)'
const mediaQuery = window.matchMedia(MOBILE_BREAKPOINT)
const isMobile = ref(mediaQuery.matches)

mediaQuery.addEventListener('change', (e) => {
  isMobile.value = e.matches
})

export function useResponsive() {
  return { isMobile }
}
