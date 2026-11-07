/**
 * 真实抓拍贴图
 * ---------------------------------------------------------------------------
 * 后端在产生告警时会存整帧抓拍图（960x540，带检测框标注）。
 * 这里按 bbox 用 Canvas 裁剪出鸟类特写，作为 3D billboard 的纹理，
 * 让低模鸟身上带有真实鸟类照片，答辩时更有辨识度。
 *
 * 裁剪策略：
 *   1. 有 bbox 且坐标有效 → 按 bbox 外扩 12% 裁剪
 *   2. 无 bbox → 取画面中央 46%×62% 区域（抓拍图里鸟通常在正中）
 */
import * as THREE from 'three'

const cache = new Map()      // snapshot 文件名 -> Promise<THREE.Texture>
const failed = new Set()     // 加载失败的，避免反复重试

/**
 * 从 ImageData 按区域裁剪并输出正方形纹理
 */
function cropToTexture(img, box) {
  const { width: iw, height: ih } = img
  let sx = 0
  let sy = 0
  let sw = iw
  let sh = ih

  // bbox 由后端与抓拍图同帧成对保存（alarms.bbox），直接信任。
  // 内缩 3% 避开画在框线上的绿色标注；无效时回退中央区域。
  let useBox = false
  if (box && box.length === 4) {
    const [x1, y1, x2, y2] = box.map(Number)
    const scaleX = iw / 960
    const scaleY = ih / 540
    const bw = (x2 - x1) * scaleX
    const bh = (y2 - y1) * scaleY
    if (bw > 8 && bh > 8) {
      const insetX = bw * 0.03
      const insetY = bh * 0.03
      sx = Math.max(0, x1 * scaleX + insetX)
      sy = Math.max(0, y1 * scaleY + insetY)
      sw = Math.min(iw - sx, bw - insetX * 2)
      sh = Math.min(ih - sy, bh - insetY * 2)
      if (sw > 8 && sh > 8) useBox = true
    }
  }

  if (!useBox) {
    // 旧数据无 bbox：取中央区域（抓拍图里鸟通常位于画面中部）
    sw = iw * 0.5
    sh = ih * 0.72
    sx = (iw - sw) / 2
    sy = (ih - sh) / 2
  }

  // 输出成正方形画布（避免拉伸变形）
  const OUT = 256
  const canvas = document.createElement('canvas')
  canvas.width = OUT
  canvas.height = OUT
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  // 保持长宽比，居中裁剪到正方形
  const side = Math.min(sw, sh)
  const cx = sx + (sw - side) / 2
  const cy = sy + (sh - side) / 2
  ctx.drawImage(img, cx, cy, side, side, 0, 0, OUT, OUT)

  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.minFilter = THREE.LinearFilter
  tex.magFilter = THREE.LinearFilter
  tex.needsUpdate = true
  return tex
}

/**
 * 加载一张抓拍图并裁剪为纹理。
 * 注意：/api/captures 用的是媒体票据（?ticket=），不是 Bearer token。
 * @param {string} server  服务基址，如 http://127.0.0.1:8008
 * @param {string} name    抓拍文件名，如 T1bc13630fa-15.jpg
 * @param {string} ticket  媒体票据 media_ticket
 * @param {number[]|null} box  可选的 bbox
 */
export function loadCaptureTexture(server, name, ticket, box = null) {
  const key = name + '|' + (box ? box.join(',') : 'center')
  if (failed.has(key)) return Promise.resolve(null)
  const hit = cache.get(key)
  if (hit) return hit

  const p = new Promise((resolve) => {
    const url = `${server}/api/captures/${encodeURIComponent(name)}?ticket=${encodeURIComponent(ticket || '')}`
    const img = new Image()
    img.crossOrigin = 'anonymous'
    fetch(url)
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error('capture ' + r.status))))
      .then((blob) => {
        img.onload = () => {
          try {
            const tex = cropToTexture(img, box)
            if (!tex) { failed.add(key); resolve(null); return }
            // 记录加载成功，便于调试
            if (typeof window !== 'undefined') {
              window.__captureStats = window.__captureStats || { ok: 0, fail: 0, last: '' }
              window.__captureStats.ok += 1
              window.__captureStats.last = name + ' ' + img.width + 'x' + img.height
            }
            resolve(tex)
          } catch (e) {
            failed.add(key)
            if (typeof window !== 'undefined') {
              window.__captureStats = window.__captureStats || { ok: 0, fail: 0, last: '' }
              window.__captureStats.fail += 1
              window.__captureStats.last = name + ' ERR ' + (e && e.message)
            }
            resolve(null)
          }
        }
        img.onerror = () => {
          failed.add(key)
          resolve(null)
        }
        img.src = URL.createObjectURL(blob)
      })
      .catch(() => {
        failed.add(key)
        resolve(null)
      })
  })

  cache.set(key, p)
  return p
}

/** 清空缓存（切换任务时调用，避免内存堆积） */
export function clearCaptureCache() {
  for (const p of cache.values()) {
    Promise.resolve(p).then((tex) => tex && tex.dispose && tex.dispose()).catch(() => {})
  }
  cache.clear()
  failed.clear()
}
