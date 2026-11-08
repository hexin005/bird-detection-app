// 主题系统:职责分离 —— applyTheme 只改界面;loadUserTheme 登录后读账号偏好;
// saveUserTheme 用户主动选择时保存。三职责互不调用,避免状态同步风暴。
export type ThemeId = 'b1bit' | 'tower' | 'signal' | 'pixel'

export interface ThemeMeta { id: ThemeId; label: string; tag: string; desc: string }

export const THEMES: ThemeMeta[] = [
  { id: 'tower', label: 'A · 果园塔台', tag: 'AMBER', desc: '1970s 机场翻牌航显板 — 鸟情即航班，驱离即放行许可。监控主页已按主题复刻。' },
  { id: 'b1bit', label: 'B · 果园守护 1.0', tag: '1-BIT', desc: '1984 首代 Macintosh — 纯黑白 1-bit、条纹窗口、硬偏移阴影。' },
  { id: 'signal', label: 'C · 鸟情信号站', tag: 'SIGNAL', desc: '公共预警信号台 — 信号牌按待处理等级升降，跑马灯播报。监控主页已复刻。' },
  { id: 'pixel', label: 'D · 像素果园', tag: '16-BIT', desc: '16-bit 掌机牧场 — 告警是"野生鸟类出现!"对话框，驱离道具即用即走。监控主页已复刻。' },
]

const GLOBAL_KEY = 'bird-theme'
const THEME_IDS = THEMES.map(t => t.id)

export function normalizeTheme(value: unknown): ThemeId {
  return THEME_IDS.includes(value as ThemeId) ? (value as ThemeId) : 'b1bit'
}

/** 只改界面 + 全局缓存(登出后登录页延续上次主题)。 */
export function applyTheme(id: ThemeId) {
  // #ifdef H5
  document.documentElement.setAttribute('data-theme', id)
  // #endif
  uni.setStorageSync(GLOBAL_KEY, id)
}

export function startupTheme(): ThemeId {
  return normalizeTheme(uni.getStorageSync(GLOBAL_KEY))
}

/** 用户级缓存:按「服务地址+用户」区分,避免切换账号串主题。 */
export function userThemeKey(server: string, userId: number | string) {
  return `${GLOBAL_KEY}:${server}:${userId}`
}

export function cachedUserTheme(server: string, userId: number | string): ThemeId {
  return normalizeTheme(uni.getStorageSync(userThemeKey(server, userId)))
}

export function rememberUserTheme(server: string, userId: number | string, id: ThemeId) {
  uni.setStorageSync(userThemeKey(server, userId), id)
}
