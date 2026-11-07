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
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
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
import { loadCaptureTexture } from './capture.js'

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
  // 正对果园中心，带一定俯视角度，让果树、摄像头、驱鸟器都进画面
  camera.position.set(15, 13.5, 17)
  camera.lookAt(0, 1.8, 0)

  const controls = new OrbitControls(camera, canvas)
  controls.target.set(0, 1.8, 0)
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

  // 后期辉光：检测框 / 声波环 / 指示灯等高亮荧绿元素产生泛光，科技感更强。
  // 阈值 0.78 只让荧绿 #d3e856（亮度≈0.85）级别的高亮泛光，天空与果树不受影响。
  const composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))
  const bloomPass = new UnrealBloomPass(new THREE.Vector2(1440, 900), 0.9, 0.45, 0.78)
  composer.addPass(bloomPass)
  composer.addPass(new OutputPass())

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

  /* ---------- 立体扫描（监测中：扫描幕布 + 扩散圆环） ---------- */
  // 竖直扫描幕布：一面上下起伏的半透明平面，像激光幕墙扫过果园
  const curtainGeo = new THREE.PlaneGeometry(36, 12, 1, 1)
  const curtainMat = new THREE.MeshBasicMaterial({
    color: PALETTE.detect,
    transparent: true,
    opacity: 0,
    side: THREE.DoubleSide,
    depthWrite: false,
  })
  const curtain = new THREE.Mesh(curtainGeo, curtainMat)
  curtain.position.y = 5.4
  scene.add(curtain)

  // 扩散圆环：从果园中心向外扩散的地面圆环，形成立体扫描感
  const rippleGeo = new THREE.RingGeometry(0.96, 1.04, 64)
  const rippleMat = new THREE.MeshBasicMaterial({
    color: PALETTE.detect,
    transparent: true,
    opacity: 0,
    side: THREE.DoubleSide,
    depthWrite: false,
  })
  const ripple = new THREE.Mesh(rippleGeo, rippleMat)
  ripple.rotation.x = -Math.PI / 2
  ripple.position.y = 0.08
  scene.add(ripple)

  // 扫描点阵：果园上方若干荧绿小点，模拟立体采样
  const dots = new THREE.Group()
  for (let i = 0; i < 18; i += 1) {
    const dotGeo = new THREE.SphereGeometry(0.09, 6, 6)
    const dotMat = new THREE.MeshBasicMaterial({ color: PALETTE.detect, transparent: true, opacity: 0 })
    const dot = new THREE.Mesh(dotGeo, dotMat)
    const a = (i / 18) * Math.PI * 2
    dot.position.set(Math.cos(a) * 14, 1.2 + Math.sin(i * 1.7) * 1.6, Math.sin(a) * 14)
    dots.add(dot)
  }
  scene.add(dots)

  /* ---------- 尺寸自适应 ---------- */
  function resize() {
    const parent = canvas.parentElement || canvas
    const w = parent.clientWidth || window.innerWidth
    const h = parent.clientHeight || window.innerHeight
    renderer.setSize(w, h, false)
    composer.setSize(w, h)
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

  /* ---------- 相机控制 ---------- */
  // 视角完全交给用户：不自动推进、不自动拉近，只在用户开启"自动环绕"时缓慢绕转。
  // 用户一旦手动拖拽，立即停止自动环绕，且不会自己恢复。
  let userAutoRotate = true

  function bindUserControl() {
    controls.addEventListener('start', () => {
      // 用户开始拖拽：立刻停掉自动环绕，避免"抢视角"
      controls.autoRotate = false
      userAutoRotate = false
    })
  }
  bindUserControl()

  /* ---------- 居留鸟群（演示核心） ----------
   * 检测结束后鸟不立即飞走，而是留在场景作为"待驱离目标"。
   * 每次驱离成功按概率驱散一部分，可能需要 2~3 次才能清空。
   */
  const occupants = []   // 当前留在场景里的鸟 { species, confidence, bbox, scared, snap }
  let lastDetKey = ''    // 当前采纳的物种签名，识别"新的检测帧"
  let noRespawn = false  // 驱离清空后置位：本轮禁止再从旧检测数据复活鸟群
  let scareBoost = 0     // 驱离瞬间的惊飞强度 0~1，随时间衰减
  let captureCtx = { server: '', ticket: '' }   // 抓拍贴图所需上下文
  let snapTable = {}     // 物种 -> 抓拍文件名，随时可能更新

  /** 从检测结果固化一批「居留鸟」 */
  function adoptDetections(dets, snapshots) {
    if (snapshots) snapTable = snapshots
    occupants.length = 0
    dets.slice(0, MAX_BIRDS).forEach((d, i) => {
      const info = snapTable[d.species] || null
      occupants.push({
        species: d.species || '',
        confidence: d.confidence ?? 0.7,
        bbox: Array.isArray(d.bbox) ? d.bbox.slice() : null,
        scared: false,
        // 抓拍图与该图自己的 bbox 成对使用（后端同帧保存）
        snap: info ? info.name : null,
        snapBbox: info ? info.bbox : null,
      })
    })
  }

  /** 执行一次驱离：按概率驱散部分鸟，返回是否还有剩余 */
  function disperse(force = 0) {
    if (!occupants.length) return 0
    scareBoost = 1
    // 一次驱离散掉约一半（至少 1 只），所以 2~3 次能清空
    const n = occupants.length
    let removeCount = Math.max(1, Math.ceil(n * 0.5))
    // 只剩 1 只时有小概率没驱走（拟真），除非 force
    if (n === 1 && force < 1 && Math.random() < 0.3) removeCount = 0
    removeCount = Math.min(removeCount, n)
    for (let i = 0; i < removeCount; i += 1) occupants.pop()
    // 全部驱离完毕：本轮不允许再从检测数据"复活"，直到新一轮检测
    if (occupants.length === 0) noRespawn = true
    return occupants.length
  }

  function updateBirds(dt, elapsed) {
    // 居留鸟群的采纳统一在 setState 里完成（含驱离后禁止复活的判断），
    // 这里只负责按 occupants 渲染。

    // 惊飞强度衰减
    scareBoost = Math.max(0, scareBoost - dt * 0.55)

    const wantBirds = Math.min(occupants.length, MAX_BIRDS)

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
          // 只隐藏，不丢弃已加载的贴图（避免反复重载导致一直淡入不完）
          b.mesh.userData.sprite.visible = false
          b.mesh.userData.spriteMat.opacity = 0
          b.waitTex = 0
          b.mesh.userData.body.material.opacity = 1
          b.mesh.userData.wings.forEach(({ mesh }) => { mesh.material.opacity = 1 })
        }
      }
      if (!b.active) return

      const occ = occupants[i]
      const det = occ ? { species: occ.species, confidence: occ.confidence, bbox: occ.bbox } : null
      b.species = occ ? occ.species : ''

      // ---- 真实抓拍贴图：按物种懒加载，取到后贴到 billboard 上 ----
      if (occ && occ.snap && !b.textureSettled && !b.texLoading) {
        b.texLoading = true
        if (captureCtx.server && captureCtx.ticket) {
          loadCaptureTexture(captureCtx.server, occ.snap, captureCtx.ticket, occ.snapBbox)
            .then((tex) => {
              b.texLoading = false
              if (!tex) return
              b.textureSettled = true
              b.mesh.userData.spriteMat.map = tex
              b.mesh.userData.spriteMat.needsUpdate = true
              b.waitTex = 0
            })
            .catch(() => { b.texLoading = false })
        } else {
          b.texLoading = false
        }
      }
      // 贴图就绪后淡入并隐藏低模鸟（保留检测框与告警标记）
      const sm = b.mesh.userData.spriteMat
      if (sm.map) {
        // 首帧就接近满不透明，之后快速到 1（保证任何截帧都能看清照片）
        b.waitTex = Math.min(1, Math.max(0.95, b.waitTex || 0) + dt * 8)
        sm.opacity = b.waitTex
        const sp = b.mesh.userData.sprite
        sp.visible = true
        // 尺寸跟随检测框，保证远处也清晰可辨
        const sw = Math.max(2.4, b.detectBox.scale.x * 1.6)
        const sh = Math.max(1.7, b.detectBox.scale.y * 1.5)
        sp.scale.set(sw, sh, 1)
        // 低模鸟整体渐隐（鸟身 + 双翼），让真实照片更清晰
        const bodyMat = b.mesh.userData.body.material
        bodyMat.opacity = Math.max(0, 1 - b.waitTex)
        bodyMat.transparent = true
        b.mesh.userData.wings.forEach(({ mesh }) => {
          mesh.material.opacity = Math.max(0, 1 - b.waitTex)
          mesh.material.transparent = true
        })
      }

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
      // 驱离时：加速盘旋 + 抬升，模拟鸟被声波惊扰
      const panic = scareBoost
      b.angle += b.speed * (1 + panic * 2.6) * dt
      b.bob += dt * (2.2 + panic * 4)
      const x = Math.cos(b.angle) * b.radius * (1 + panic * 0.35) + (b.offsetX || 0)
      const z = Math.sin(b.angle) * b.radius * 0.72 * (1 + panic * 0.35) + (b.offsetZ || 0)
      const y = b.height + Math.sin(b.bob) * 0.55 + panic * 2.2
      b.mesh.position.set(x, y, z)

      // 朝向飞行切线方向
      const nextX = Math.cos(b.angle + 0.08) * b.radius + (b.offsetX || 0)
      const nextZ = Math.sin(b.angle + 0.08) * b.radius * 0.72 + (b.offsetZ || 0)
      b.mesh.lookAt(nextX, y, nextZ)

      // 翅膀扑动（惊飞时更快）
      const flap = Math.sin(elapsed * (9 + panic * 14) + i) * (0.55 + panic * 0.5)
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

    // 立体扫描：监测中扫描幕布扫过 + 圆环扩散 + 点阵呼吸
    if (visual.running) {
      scanProgress = (scanProgress + dt * 0.22) % 1

      // 扫描幕布：沿 z 轴往复扫过果园
      const cz = -16 + scanProgress * 32
      curtain.position.z = cz
      curtainMat.opacity = 0.10 + Math.sin(scanProgress * Math.PI) * 0.06

      // 扩散圆环：从中心向外扩散，循环
      const rippleT = (elapsed * 0.35) % 1
      ripple.scale.setScalar(0.5 + rippleT * 22)
      rippleMat.opacity = (1 - rippleT) * 0.22

      // 点阵呼吸：模拟立体采样点
      dots.children.forEach((dot, i) => {
        dot.material.opacity = 0.25 + Math.sin(elapsed * 2.4 + i * 0.7) * 0.2
        dot.position.y = 1.2 + Math.sin(elapsed * 1.3 + i * 0.9) * 1.6
      })
    } else {
      curtainMat.opacity = 0
      rippleMat.opacity = 0
      dots.children.forEach((dot) => { dot.material.opacity = 0 })
    }
  }

  function loop() {
    if (disposed) return
    rafId = requestAnimationFrame(loop)
    const dt = Math.min(clock.getDelta(), 0.05)
    const elapsed = clock.elapsedTime

    // 不再自动操控相机，视角完全由用户掌握
    controls.update()
    updateBirds(dt, elapsed)
    updateDevices(dt, elapsed)
    composer.render()
  }

  loop()
  if (onReady) onReady({ scene, camera, renderer, controls })

  /* ---------- 对外接口 ---------- */
  return {
    /** 注入最新业务状态 */
    setState({ running, detections, alarms, executing, offline, detTime, snapshots, server, ticket }) {
      visual.running = !!running
      visual.detections = Array.isArray(detections) ? detections : []
      visual.alarms = Array.isArray(alarms) ? alarms : []
      visual.executing = !!executing
      visual.offline = !!offline
      visual.detTime = detTime || 0
      if (server) captureCtx.server = server
      if (ticket) captureCtx.ticket = ticket
      if (snapshots) snapTable = snapshots

      // 同步登记居留鸟群（仅在为空或物种集合变化时重建，避免贴图反复重置）
      // noRespawn：本轮鸟群已被人工驱离清空，不再从旧检测数据复活；
      // 新一轮检测由 clearOccupants() 复位该标志。
      if (visual.detections.length) {
        const sig = visual.detections.map((d) => d.species).join(',')
        const needAdopt = (occupants.length === 0 && !noRespawn) || sig !== lastDetKey
        if (needAdopt) {
          lastDetKey = sig
          noRespawn = false
          adoptDetections(visual.detections, snapshots)
        } else {
          // 已驻留的鸟：补齐可能后到的抓拍图
          for (const o of occupants) {
            const info = snapTable[o.species]
            if (!o.snap && info) {
              o.snap = info.name
              o.snapBbox = info.bbox
            }
          }
        }
      }
    },
    /** 暂停/恢复自动环绕 */
    setAutoRotate(on) {
      userAutoRotate = !!on
      controls.autoRotate = !!on
    },
    /**
     * 执行一次驱离，返回剩余鸟数。
     * force=0：剩最后一只时有 30% 概率抵抗不离开，形成「需多次驱离」的拟真节奏。
     */
    disperse() {
      return disperse(0)
    },
    /** 当前留在场景里的鸟数（待驱离目标） */
    occupantCount() {
      return occupants.length
    },
    /** 清空居留鸟群（重新开始检测时调用） */
    clearOccupants() {
      occupants.length = 0
      lastDetKey = ''
      noRespawn = false
      scareBoost = 0
    },
    /** 当前惊飞强度 0~1（供 HUD 判断是否在驱离中） */
    panicLevel() {
      return scareBoost
    },
    /** 调试：返回贴图加载状态 */
    debugTextureState() {
      return {
        server: captureCtx.server,
        hasTicket: !!captureCtx.ticket,
        ticketLen: (captureCtx.ticket || '').length,
        snapTable,
        occupants: occupants.map((o) => ({ species: o.species, snap: o.snap, bbox: o.bbox })),
        birds: birds.map((b) => ({
          active: b.active,
          settled: !!b.textureSettled,
          loading: !!b.texLoading,
          hasMap: !!b.mesh.userData.spriteMat.map,
          spriteVisible: b.mesh.userData.sprite.visible,
          opacity: b.mesh.userData.spriteMat.opacity,
          scale: b.mesh.userData.sprite.scale.toArray().map((v) => +v.toFixed(2)),
          bodyOpacity: b.mesh.userData.body.material.opacity,
        })),
        captureStats: (typeof window !== 'undefined' && window.__captureStats) || null,
      }
    },
    /** 重置视角（回到俯瞰全景，并恢复自动环绕） */
    resetView() {
      userAutoRotate = true
      controls.autoRotate = true
      camera.position.set(15, 13.5, 17)
      controls.target.set(0, 1.8, 0)
      controls.update()
    },
    resize,
    dispose() {
      disposed = true
      cancelAnimationFrame(rafId)
      ro.disconnect()
      controls.dispose()
      composer.dispose()
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
