/**
 * 安全的浏览器存储封装：在严格隐私策略（SecurityError / QuotaExceededError）或 SSR 环境下绝不抛出未捕获异常。
 */
export function safeGetStorage(key, fallback = null) {
  try {
    if (typeof localStorage === 'undefined') return fallback
    const val = localStorage.getItem(key)
    return val === null ? fallback : val
  } catch (_e) {
    return fallback
  }
}

export function safeSetStorage(key, value) {
  try {
    if (typeof localStorage === 'undefined') return false
    localStorage.setItem(key, value)
    return true
  } catch (_e) {
    return false
  }
}

export function safeRemoveStorage(key) {
  try {
    if (typeof localStorage === 'undefined') return false
    localStorage.removeItem(key)
    return true
  } catch (_e) {
    return false
  }
}

export function safeGetSession(key, fallback = null) {
  try {
    if (typeof sessionStorage === 'undefined') return fallback
    const val = sessionStorage.getItem(key)
    return val === null ? fallback : val
  } catch (_e) {
    return fallback
  }
}

export function safeSetSession(key, value) {
  try {
    if (typeof sessionStorage === 'undefined') return false
    sessionStorage.setItem(key, value)
    return true
  } catch (_e) {
    return false
  }
}
