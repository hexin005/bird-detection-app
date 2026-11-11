// 告警提醒(H5):新告警出现时播放双音提示 + 桌面通知 + 标题闪烁;
// 用户进入告警页或待处理清零后由调用方停止闪烁。
// 开关存本地('bird-alert-remind'),默认开;桌面通知权限在用户开启开关时请求。
let flashTimer: ReturnType<typeof setInterval> | null = null
let audioCtx: AudioContext | null = null
let baseTitle = ''
const H5 = typeof window !== 'undefined' && typeof document !== 'undefined'

export function alertRemindEnabled(): boolean {
  try { return uni.getStorageSync('bird-alert-remind') !== 'off' } catch { return true }
}

export function setAlertRemind(on: boolean): void {
  try { uni.setStorageSync('bird-alert-remind', on ? 'on' : 'off') } catch { /* 存储不可用时忽略 */ }
  if (on && H5 && 'Notification' in window && Notification.permission === 'default') {
    void Notification.requestPermission()
  }
  if (!on) stopAlertTitleFlash()
}

function beep(): void {
  if (!H5) return
  try {
    const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) return
    audioCtx = audioCtx || new Ctor()
    if (audioCtx.state === 'suspended') void audioCtx.resume()
    const t0 = audioCtx.currentTime
    ;[0, 0.24].forEach((offset, idx) => {
      const osc = audioCtx!.createOscillator()
      const gain = audioCtx!.createGain()
      osc.type = 'square'
      osc.frequency.value = idx ? 880 : 1245
      gain.gain.setValueAtTime(0.0001, t0 + offset)
      gain.gain.exponentialRampToValueAtTime(0.14, t0 + offset + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + offset + 0.2)
      osc.connect(gain).connect(audioCtx!.destination)
      osc.start(t0 + offset)
      osc.stop(t0 + offset + 0.22)
    })
  } catch { /* 音频不可用时静默 */ }
}

function notifyDesktop(count: number): void {
  if (!H5 || !('Notification' in window) || Notification.permission !== 'granted') return
  try {
    const n = new Notification('鸟情告警', { body: `有 ${count} 条新的待处理告警，请前往告警页确认`, tag: 'bird-alarm' })
    n.onclick = () => { window.focus(); n.close() }
  } catch { /* 通知构造失败时静默 */ }
}

/** 停止标题闪烁(进入告警页 / 待处理清零 / 关闭开关时调用) */
export function stopAlertTitleFlash(): void {
  if (flashTimer) { clearInterval(flashTimer); flashTimer = null }
  if (H5) document.title = baseTitle || document.title
}

/** 新增 N 条待处理告警:提示音 + 桌面通知 + 标题闪烁 */
export function alertNewAlarms(count: number): void {
  if (!H5 || !alertRemindEnabled()) return
  beep()
  notifyDesktop(count)
  if (flashTimer) return
  baseTitle = baseTitle || document.title
  let flashOn = false
  flashTimer = setInterval(() => {
    flashOn = !flashOn
    document.title = flashOn ? `【新告警 ${count} 条】青禾果园守护` : (baseTitle || '青禾果园守护')
  }, 900)
}
