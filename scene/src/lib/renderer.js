/**
 * 果园 3D 场景渲染器
 * ---------------------------------------------------------------------------
 * 职责：
 *   1. 初始化 Three.js 场景、相机、光照、渲染循环
 *   2. 组装低多边形果园（地面 / 果树 / 摄像头 / 驱鸟器）
 *   3. 根据 WebSocket 数据驱动视觉状态：
 *        监测中   -> 摄像头指示灯亮、视野锥显形、扫描动画
 *        有检出   -> 鸟出现 + 检测框跟随
 *        有告警   -> 鸟头顶浮动告警标记
 *        执行中   -> 驱鸟器发光 + 声波环扩散
 */
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  PALETTE,
  createGround,
  createTree,
  createCamera,
  createDeterrent,
  createBirdMesh,
  createDetectBox,
  createAlarmMarker,
  mulberry32,
} from './orchard.js'

const MAX_BIRDS = 6

export function createOrchardScene(canvas, options = {}) {
  const { onReady } = options

  /* ---------- 基础三件套 ---------- */
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap

  const scene = new THREE.Scene()
  scene.background = new THREE.Color(PALETTE.sky)
  scene.fog = new THREE.Fog(PALETTE.fog, 34, 74)

  const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 260)
  camera.position.set(17, 12.5, 19)
  camera.lookAt(0, 2.4, 0)

  const controls = new OrbitControls(camera, canvas)
  controls.target.set(0, 2.2, 0)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.minDistance = 9
  controls.maxDistance = 46
  controls.maxPolarAngle = Math.PI * 0.475
  controls.minPolarAngle = Math.PI * 0.12
  controls.autoRotate = true
  controls.autoRotateSpeed = 0.28
  controls.enablePan = false
  controls.update()

  /* ---------- 光照 ---------- */
  const hemi = new THREE.HemisphereLight(0xdceaf2, 0x4a5535, 1.15)
  scene.add(hemi)

  const sun = new THREE.DirectionalLight(0xfff2d8, 1.75)
  sun.position.set(16, 22, 12)
  sun.castShadow = true
  sun.shadow.mapSize.set(1024, 1024)
  sun.shadow.camera.near = 1
  sun.shadow.camera.far = 70
  sun.shadow.camera.left = -26
  sun.shadow.camera.right = 26
  sun.shadow.camera.top = 26
  sun.shadow.camera.bottom = -26
  sun.shadow.bias = -0.0012
  scene.add(sun)

  const fill = new THREE.DirectionalLight(0xb9d4e0, 0.35)
  fill.position.set(-14, 10, -12)
  scene.add(fill)

  /* ---------- 天地 ---------- */
  const rand = mulberry32(20261105)
  const ground = createGround(rand)
  scene.add(ground)

  // 远景林带（低多边形树环绕，增加纵深）
  const treeGroup = new THREE.Group()
  const placed = []
  const tryPlace = (x, z, minDist) => {
    for (const p of placed) {
      if (Math.hypot(p.x - x, p.z - z) < minDist) return false
    }
    placed.push({ x, z })
    return true
  }

  // 主果园：行列种植
  const rows = 3
  const cols = 4
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const x = (c - (cols - 1) / 2) * 6.4 + (rand() - 0.5) * 1.1
      const z = (r - (rows - 1) / 2) * 6.8 - 4.5 + (rand() - 0.5) * 1.1
      if (!tryPlace(x, z, 3.6)) continue
      const tree = createTree(rand, 1 + rand() * 0.35)
      tree.position.set(x, 0, z)
      tree.rotation.y = rand() * Math.PI * 2
      treeGroup.add(tree)
    }
  }

  // 外围林带
  for (let i = 0; i < 26; i += 1) {
    const angle = (i / 26) * Math.PI * 2 + rand() * 0.2
    const radius = 24 + rand() * 7
    const x = Math.cos(angle) * radius
    const z = Math.sin(angle) * radius
    const tree = createTree(rand, 0.85 + rand() * 0.5)
    tree.position.set(x, 0, z)
    tree.rotation.y = rand() * Math.PI * 2
    treeGroup.add(tree)
  }
  scene.add(treeGroup)

  /* ---------- 设备 ---------- */
  // 摄像头（果园左侧，朝右看）
  const camRig = createCamera()
  camRig.position.set(-11, 0, 6.5)
  camRig.rotation.y = -Math.PI / 3.1
  scene.add(camRig)

  // 驱鸟器（果园右侧）
  const deterrent = createDeterrent()
  deterrent.position.set(11.5, 0, -2)
  scene.add(deterrent)

  // 设备标签锚点（供 HUD 定位，预留）
  const markers = {
    camera: new THREE.Vector3(-10.1, 5.2, 6.2),
    deterrent: new THREE.Vector3(11.5, 3.9, -2),
  }

  /* ---------- 鸟类池 ---------- */
  const birds = []
  for (let i = 0; i < MAX_BIRDS; i += 1) {
    const bird = createBirdMesh()
    bird.visible = false
    const detectBox = createDetectBox()
    detectBox.visible = false
    const alarm = createAlarmMarker()
    alarm.visible = false
    bird.add(detectBox)
    bird.add(alarm)
    scene.add(bird)
    birds.push({
      mesh: bird,
      detectBox,
      alarm,
      // 飞行参数
      radius: 6 + Math.random() * 7,
      angle: Math.random() * Math.PI * 2,
      speed: 0.16 + Math.random() * 0.16,
      height: 5.5 + Math.random() * 4.5,
      bob: Math.random() * Math.PI * 2,
      active: false,
      species: '',
      // bbox 映射的位置偏移（平滑过渡）
      offsetX: 0,
      offsetZ: 0,
    })
  }

  /* ---------- 扫描线（监测中画面横线） ---------- */
  const scanGeo = new THREE.PlaneGeometry(30, 0.12)
  const scanMat = new THREE.MeshBasicMaterial({
    color: PALETTE.detect,
    transparent: true,
    opacity: 0,
    depthWrite: false,
  })
  const scanLine = new THREE.Mesh(scanGeo, scanMat)
  scanLine.rotation.x = -Math.PI / 2
  scanLine.position.y = 0.06
  scene.add(scanLine)

  /* ---------- 尺寸自适应 ---------- */
  function resize() {
    const parent = canvas.parentElement || canvas
    const w = parent.clientWidth || window.innerWidth
    const h = parent.clientHeight || window.innerHeight
    renderer.setSize(w, h, false)
    camera.aspect = w / Math.max(h, 1)
    camera.updateProjectionMatrix()
  }

  const ro = new ResizeObserver(resize)
  ro.observe(canvas.parentElement || canvas)
  resize()

  /* ---------- 动画状态 ---------- */
  const clock = new THREE.Clock()
  let rafId = 0
  let disposed = false
  let scanProgress = 0

  /** 由外部注入的最新状态 */
  const visual = {
    running: false,
    detections: [],
    alarms: [],
    executing: false,
    offline: false,
    detTime: 0,
  }

  function updateBirds(dt, elapsed) {
    // 监测中且有检出：让对应数量的鸟出现在上空
    const wantBirds = visual.running ? Math.min(visual.detections.length, MAX_BIRDS) : 0

    birds.forEach((b, i) => {
      const shouldShow = i < wantBirds
      if (shouldShow !== b.active) {
        b.active = shouldShow
        b.mesh.visible = shouldShow
        if (shouldShow) {
          b.detectBox.visible = true
          b.angle = Math.random() * Math.PI * 2
        } else {
          b.detectBox.visible = false
          b.alarm.visible = false
        }
      }
      if (!b.active) return

      const det = visual.detections[i]
      b.species = det ? det.species : ''

      // ---- 用 bbox 映射鸟在果园中的位置 ----
      // 画面坐标系：x 左→右（0~960），y 上→下（0~540）
      // 映射到果园：bbox 中心 x 决定横向偏移（-14~+14），
      //             bbox 中心 y 决定纵向位置（画面越靠下 = 离摄像头越近）
      if (det && Array.isArray(det.bbox) && det.bbox.length === 4) {
        const [x1, y1, x2, y2] = det.bbox
        const cx = (x1 + x2) / 2 / 960   // 0~1 归一化
        const cy = (y1 + y2) / 2 / 540
        // 横向：画面中心(0.5) → 果园中心(0)，左右各约 ±13
        const offsetX = (cx - 0.5) * 26
        // 纵向：画面越靠下(cy 大) → 越靠果园前侧(z 小)
        const offsetZ = (cy - 0.5) * 14
        // 叠加在圆周运动上，让鸟的位置跟随画面
        b.offsetX += (offsetX - b.offsetX) * Math.min(dt * 3, 1)
        b.offsetZ += (offsetZ - b.offsetZ) * Math.min(dt * 3, 1)
      }

      // 圆周飞行 + 上下浮动（叠加 bbox 偏移）
      b.angle += b.speed * dt
      b.bob += dt * 2.2
      const x = Math.cos(b.angle) * b.radius + (b.offsetX || 0)
      const z = Math.sin(b.angle) * b.radius * 0.72 + (b.offsetZ || 0)
      const y = b.height + Math.sin(b.bob) * 0.55
      b.mesh.position.set(x, y, z)

      // 朝向飞行切线方向
      const nextX = Math.cos(b.angle + 0.08) * b.radius + (b.offsetX || 0)
      const nextZ = Math.sin(b.angle + 0.08) * b.radius * 0.72 + (b.offsetZ || 0)
      b.mesh.lookAt(nextX, y, nextZ)

      // 翅膀扑动
      const flap = Math.sin(elapsed * 9 + i) * 0.55
      b.mesh.userData.wings.forEach(({ mesh, dir }) => {
        mesh.rotation.x = dir * flap
      })

      // ---- 检测框：用 bbox 真实宽高比例映射尺寸 ----
      let bw = 1.5, bh = 1.1
      if (det && Array.isArray(det.bbox) && det.bbox.length === 4) {
        const [x1, y1, x2, y2] = det.bbox
        // bbox 宽高相对画面比例 → 3D 检测框尺寸
        // 画面 960 宽的物体，映射到 3D 约 3 单位宽；540 高映射约 2 单位
        const wRatio = (x2 - x1) / 960
        const hRatio = (y2 - y1) / 540
        bw = 0.9 + wRatio * 3.2
        bh = 0.7 + hRatio * 2.4
      }
      const conf = det ? det.confidence : 0.7
      const confScale = 0.85 + conf * 0.4
      b.detectBox.scale.set(bw * confScale, bh * confScale, bw * confScale)
      b.detectBox.position.set(0, 0, 0)
      b.detectBox.material.opacity = 0.55 + Math.sin(elapsed * 4 + i) * 0.2

      // ---- 告警标记：精确关联到「这一只鸟」 ----
      // 匹配规则：物种相同，且告警的 video_time 接近当前帧时间
      const detTime = visual.detTime ?? 0
      const isAlarm = visual.alarms.some(
        (a) => a.species === b.species && Math.abs((a.video_time ?? 0) - detTime) < 4,
      )
      b.alarm.visible = isAlarm
      if (isAlarm) {
        b.alarm.position.set(0, 1.15, 0)
        b.alarm.userData.ring.scale.setScalar(1 + Math.sin(elapsed * 3.4 + i) * 0.16)
        b.alarm.userData.ringMat.opacity = 0.34 + Math.sin(elapsed * 3.4 + i) * 0.18
        b.alarm.rotation.y += dt * 1.4
      }
    })
  }

  function updateDevices(dt, elapsed) {
    // 摄像头
    const { led, cone, coneMat } = camRig.userData
    if (visual.running) {
      led.material.color.setHex(0xd3e856)
      coneMat.opacity = 0.06 + Math.sin(elapsed * 1.6) * 0.022
    } else if (visual.offline) {
      led.material.color.setHex(0x9c5546)
      coneMat.opacity = 0.02
    } else {
      led.material.color.setHex(0x56753f)
      coneMat.opacity = 0.028
    }
    // 球机缓慢左右巡航
    camRig.rotation.y = -Math.PI / 3.1 + Math.sin(elapsed * 0.24) * 0.16

    // 驱鸟器声波
    const { led: dled, waves } = deterrent.userData
    dled.material.color.setHex(visual.executing ? 0xd3e856 : (visual.offline ? 0x9c5546 : 0x56753f))
    waves.forEach(({ mesh, mat, phase }) => {
      if (!visual.executing) {
        mat.opacity = 0
        return
      }
      const t = (elapsed * 0.85 + phase) % 1
      mesh.scale.setScalar(0.8 + t * 5.2)
      mat.opacity = (1 - t) * 0.55
    })

    // 扫描线：监测中从场景一侧扫到另一侧
    if (visual.running) {
      scanProgress = (scanProgress + dt * 0.32) % 1
      scanLine.position.z = -18 + scanProgress * 36
      scanMat.opacity = 0.16
    } else {
      scanMat.opacity = 0
    }
  }

  function loop() {
    if (disposed) return
    rafId = requestAnimationFrame(loop)
    const dt = Math.min(clock.getDelta(), 0.05)
    const elapsed = clock.elapsedTime

    controls.update()
    updateBirds(dt, elapsed)
    updateDevices(dt, elapsed)
    renderer.render(scene, camera)
  }

  loop()
  if (onReady) onReady({ scene, camera, renderer, controls })

  /* ---------- 对外接口 ---------- */
  return {
    /** 注入最新业务状态 */
    setState({ running, detections, alarms, executing, offline, detTime }) {
      visual.running = !!running
      visual.detections = Array.isArray(detections) ? detections : []
      visual.alarms = Array.isArray(alarms) ? alarms : []
      visual.executing = !!executing
      visual.offline = !!offline
      visual.detTime = detTime || 0
    },
    /** 暂停/恢复自动环绕 */
    setAutoRotate(on) {
      controls.autoRotate = !!on
    },
    /** 重置视角 */
    resetView() {
      camera.position.set(17, 12.5, 19)
      controls.target.set(0, 2.2, 0)
      controls.update()
    },
    resize,
    dispose() {
      disposed = true
      cancelAnimationFrame(rafId)
      ro.disconnect()
      controls.dispose()
      scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose()
        if (obj.material) {
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
          mats.forEach((m) => m.dispose())
        }
      })
      renderer.dispose()
    },
  }
}
