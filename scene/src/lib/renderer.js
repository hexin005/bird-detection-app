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
  createInfrared,
  createFence,
  createGate,
  createHouse,
  createFarmer,
  createBirdMesh,
  createDetectBox,
  createAlarmMarker,
  mulberry32,
} from './orchard.js'
import { loadCaptureTexture } from './capture.js'

const MAX_BIRDS = 6

export function createOrchardScene(canvas, options = {}) {
  const { onReady, onCrewAlertReady, onCrewArrived } = options

  /* ---------- 基础三件套 ---------- */
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.08
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap

  const scene = new THREE.Scene()
  scene.background = new THREE.Color(PALETTE.sky)
  scene.fog = new THREE.Fog(PALETTE.fog, 44, 96)

  const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 260)
  // 正对果园中心，带一定俯视角度，让果树、摄像头、驱鸟器都进画面
  camera.position.set(26, 24, 37)
  camera.lookAt(0, 1.45, 0)

  const controls = new OrbitControls(camera, canvas)
  controls.target.set(0, 1.45, 0)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.minDistance = 9
  controls.maxDistance = 58
  controls.maxPolarAngle = Math.PI * 0.475
  controls.minPolarAngle = Math.PI * 0.12
  controls.autoRotate = true
  controls.autoRotateSpeed = 0.18
  controls.enablePan = false
  controls.update()

  // 克制的辉光只托起检测框和驱鸟设备指示灯，保留果园材质与鸟体细节。
  const composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))
  const bloomPass = new UnrealBloomPass(new THREE.Vector2(1440, 900), 0.32, 0.32, 0.9)
  composer.addPass(bloomPass)
  composer.addPass(new OutputPass())

  /* ---------- 光照 ---------- */
  const hemi = new THREE.HemisphereLight(0xeaf3df, 0x64704d, 1.35)
  scene.add(hemi)

  const sun = new THREE.DirectionalLight(0xffdfae, 2.15)
  sun.position.set(-18, 26, 16)
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

  const fill = new THREE.DirectionalLight(0xd8e9dc, 0.48)
  fill.position.set(14, 12, -16)
  scene.add(fill)

  /* ---------- 昼夜光照:按小时在关键帧间插值(0~24) ---------- */
  const DAYLIGHT_KEYS = [
    { h: 0,    sky: 0x0d1420, fog: 0x0d1420, sunC: 0x9db8dd, sunI: 0.26, hemiI: 0.34, fillI: 0.10, px: -14, py: 20, pz: -12, night: 1 },
    { h: 5.4,  sky: 0x1a2430, fog: 0x1a2430, sunC: 0xc9a06a, sunI: 0.55, hemiI: 0.52, fillI: 0.18, px: -22, py: 7,  pz: 16,  night: 1 },
    { h: 7,    sky: 0x9ec4de, fog: 0xa9c8d8, sunC: 0xffc27a, sunI: 1.75, hemiI: 1.02, fillI: 0.34, px: -26, py: 9,  pz: 19,  night: 0 },
    { h: 12,   sky: PALETTE.sky, fog: PALETTE.fog, sunC: 0xfff2d8, sunI: 2.3, hemiI: 1.35, fillI: 0.48, px: -12, py: 30, pz: 10, night: 0 },
    { h: 17.6, sky: 0xe6c096, fog: 0xd6ae86, sunC: 0xff9a4d, sunI: 1.9,  hemiI: 0.96, fillI: 0.30, px: 20,  py: 12, pz: 20,  night: 0 },
    { h: 19.4, sky: 0x272c40, fog: 0x252a3c, sunC: 0x8fb0d8, sunI: 0.32, hemiI: 0.46, fillI: 0.14, px: 18,  py: 9,  pz: -12, night: 1 },
    { h: 24,   sky: 0x0d1420, fog: 0x0d1420, sunC: 0x9db8dd, sunI: 0.26, hemiI: 0.34, fillI: 0.10, px: -14, py: 20, pz: -12, night: 1 },
  ]
  function applyDaylightHour(h) {
    const hh = ((h % 24) + 24) % 24
    let a = DAYLIGHT_KEYS[0]
    let b = DAYLIGHT_KEYS[DAYLIGHT_KEYS.length - 1]
    for (let i = 0; i < DAYLIGHT_KEYS.length - 1; i += 1) {
      if (hh >= DAYLIGHT_KEYS[i].h && hh <= DAYLIGHT_KEYS[i + 1].h) {
        a = DAYLIGHT_KEYS[i]
        b = DAYLIGHT_KEYS[i + 1]
        break
      }
    }
    const t = THREE.MathUtils.clamp((hh - a.h) / (b.h - a.h || 1), 0, 1)
    sun.color.set(a.sunC).lerp(new THREE.Color(b.sunC), t)
    sun.intensity = a.sunI + (b.sunI - a.sunI) * t
    sun.position.set(a.px + (b.px - a.px) * t, a.py + (b.py - a.py) * t, a.pz + (b.pz - a.pz) * t)
    hemi.intensity = a.hemiI + (b.hemiI - a.hemiI) * t
    fill.intensity = a.fillI + (b.fillI - a.fillI) * t
    scene.background.copy(new THREE.Color(a.sky).lerp(new THREE.Color(b.sky), t))
    scene.fog.color.set(a.fog).lerp(new THREE.Color(b.fog), t)
    // 夜间标志:设备灯/红外束在暗景中增强(见 updateDevices)
    visual.night = Math.round(a.night + (b.night - a.night) * t) === 1
  }

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
  const rows = 4
  const cols = 4
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const x = (c - (cols - 1) / 2) * 6.1 + (rand() - 0.5) * 0.8
      const z = (r - (rows - 1) / 2) * 5.8 - 2.7 + (rand() - 0.5) * 0.8
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

  // 红外驱鸟器（东南角，与声学联动）
  const infrared = createInfrared()
  infrared.position.set(8.6, 0, 8.6)
  infrared.rotation.y = Math.PI * 3 / 4   // 束流朝果园中心
  scene.add(infrared)

  /* ---------- 围栏与门户 ---------- */
  scene.add(createFence())

  // 大门（南侧正对土路）
  const gate = createGate()
  gate.position.set(0, 0, 16)
  scene.add(gate)

  // 农户房子（大门旁）
  const house = createHouse()
  house.position.set(-4, 0, 20.6)
  let houseHeading = Math.PI * 0.8
  for (let i = 0; i < 8; i += 1) {
    house.rotation.y = houseHeading
    house.updateMatrixWorld(true)
    const entry = house.localToWorld(new THREE.Vector3(-0.9, 0, 1.76))
    houseHeading = Math.atan2(gate.position.x - entry.x, gate.position.z - entry.z)
  }
  house.rotation.y = houseHeading // 让门口正对果园大门中心
  scene.add(house)
  house.updateMatrixWorld(true)
  const houseInterior = (x) => house.localToWorld(new THREE.Vector3(x, 0, 0.25)).toArray()
  const houseDoorInside = house.localToWorld(new THREE.Vector3(-0.9, 0, 1.42))
  const houseDoorOutside = house.localToWorld(new THREE.Vector3(-0.9, 0, 2.2))

  /* ---------- 果农协作组：待命在房屋内，发现鸟后经大门进入果园 ---------- */
  const crew = [
    { name: '巡园果农', role: 'inspect', home: houseInterior(-0.45), muster: [-0.82, 0, 14.15], task: [-6.1, 0, -2.3], lookAt: [-4.2, 0, -2.3], shirt: 0x668452, hat: 0xc6a66d },
    { name: '红外设备员', role: 'infrared', home: houseInterior(0.15), muster: [0, 0, 14.15], task: [8.0, 0, 9.2], lookAt: [8.35, 0, 8.85], shirt: 0x4f7e86, hat: 0xb58e59 },
    { name: '声波设备员', role: 'acoustic', home: houseInterior(0.75), muster: [0.82, 0, 14.15], task: [11.15, 0, -2], lookAt: [11.8, 0, -2], shirt: 0xa56b48, hat: 0xd1b171 },
  ]
  crew.forEach((person) => {
    person.mesh = createFarmer({ shirt: person.shirt, hat: person.hat })
    person.mesh.position.set(...person.home)
    person.mesh.visible = false
    scene.add(person.mesh)
    person.trail = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineDashedMaterial({
        color: 0x59decf,
        transparent: true,
        opacity: 0.76,
        dashSize: 0.48,
        gapSize: 0.26,
        depthWrite: false,
      }),
    )
    person.trail.visible = false
    person.trail.renderOrder = 2
    person.trail.frustumCulled = false
    scene.add(person.trail)
  })

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

  /* ---------- 逃散鸟池:被驱离的鸟从盘旋位置起飞离场(独立于驻留池) ---------- */
  const fleeBirds = []
  for (let i = 0; i < MAX_BIRDS; i += 1) {
    const mesh = createBirdMesh()
    mesh.visible = false
    scene.add(mesh)
    fleeBirds.push({ mesh, active: false, t: 0, dur: 2.1 + Math.random() * 0.6, from: new THREE.Vector3(), dir: new THREE.Vector3() })
  }
  function spawnFlee(fromPos) {
    const f = fleeBirds.find((b) => !b.active)
    if (!f) return
    f.active = true
    f.t = 0
    f.from.copy(fromPos)
    f.from.y = Math.max(1.4, fromPos.y)
    const a = Math.random() * Math.PI * 2
    f.dir.set(Math.cos(a), 0, Math.sin(a))
    f.mesh.visible = true
    if (f.mesh.userData.sprite) f.mesh.userData.sprite.visible = false
  }
  function updateFleeBirds(dt) {
    fleeBirds.forEach((f) => {
      if (!f.active) return
      f.t += dt / f.dur
      if (f.t >= 1) {
        f.active = false
        f.mesh.visible = false
        return
      }
      const dist = f.t * 24
      // 先快速爬升脱离树冠，再缓升远去
      const lift = Math.sin(Math.min(1, f.t * 1.8) * Math.PI * 0.55) * 5.5 + f.t * 2.5
      f.mesh.position.set(f.from.x + f.dir.x * dist, f.from.y + lift, f.from.z + f.dir.z * dist)
      f.mesh.lookAt(f.from.x + f.dir.x * (dist + 2), f.mesh.position.y, f.from.z + f.dir.z * (dist + 2))
      const flap = Math.sin(f.t * 55) * 0.72
      f.mesh.userData.wings.forEach(({ mesh, dir }) => {
        mesh.rotation.x = dir * flap
      })
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
    repelMode: 'both',   // acoustic | infrared | both：驱离方式，决定点亮哪些设备动效
    crewPhase: 'home',
    night: false,        // 昼夜光照的夜间标志:设备灯/束流在暗景中增强
  }

  const crewMotion = { phase: '', started: 0, duration: 0, paths: [], alertReadySent: false, arrivalSent: false }
  const worldUp = new THREE.Vector3(0, 1, 0)

  function makeCrewRoute(person, phase) {
    const start = person.mesh.position.clone()
    if (phase === 'alert') {
      if (!person.mesh.visible) start.set(...person.home)
      return [
        start,
        houseDoorInside.clone(),
        houseDoorOutside.clone(), // 从正门离开房屋
        new THREE.Vector3(3.4, 0, 18.35), // 沿围栏外侧走向大门
        new THREE.Vector3(0, 0, 18.35),
        new THREE.Vector3(person.muster[0], 0, 16.05), // 从唯一大门进入
        new THREE.Vector3(...person.muster),
      ]
    }
    if (phase === 'working') {
      const enabled = person.role === 'inspect'
        || person.role === 'infrared' && visual.repelMode !== 'acoustic'
        || person.role === 'acoustic' && visual.repelMode !== 'infrared'
      if (!enabled) return [start]
      const lane = person.role === 'inspect'
        ? [new THREE.Vector3(-1.5, 0, 10.5), new THREE.Vector3(-3.8, 0, 5.6)]
        : person.role === 'infrared'
          ? [new THREE.Vector3(2.3, 0, 11.4), new THREE.Vector3(5.1, 0, 9.1)]
          : [new THREE.Vector3(3.1, 0, 12.2), new THREE.Vector3(8.5, 0, 7.1)]
      return [start, ...lane, new THREE.Vector3(...person.task)]
    }
    if (phase === 'returning') {
      return [
        start,
        new THREE.Vector3(...person.muster),
        new THREE.Vector3(person.muster[0], 0, 16.05),
        new THREE.Vector3(0, 0, 18.35),
        new THREE.Vector3(3.4, 0, 18.35),
        houseDoorOutside.clone(),
        houseDoorInside.clone(),
        new THREE.Vector3(...person.home),
      ]
    }
    return [start]
  }

  function routePoint(points, progress) {
    if (!points || points.length < 2) return points?.[0]?.clone() || new THREE.Vector3()
    const lengths = []
    let total = 0
    for (let i = 1; i < points.length; i += 1) {
      const length = points[i - 1].distanceTo(points[i])
      lengths.push(length)
      total += length
    }
    let remaining = total * progress
    for (let i = 0; i < lengths.length; i += 1) {
      if (remaining <= lengths[i] || i === lengths.length - 1) {
        return points[i].clone().lerp(points[i + 1], lengths[i] ? Math.min(remaining / lengths[i], 1) : 1)
      }
      remaining -= lengths[i]
    }
    return points[points.length - 1].clone()
  }

  function beginCrewPhase(phase, elapsed) {
    crewMotion.phase = phase
    crewMotion.started = elapsed
    crewMotion.duration = phase === 'alert' ? 4.2 : phase === 'working' ? 3.4 : phase === 'returning' ? 5.4 : 0
    crewMotion.paths = []
    crewMotion.alertReadySent = false
    crewMotion.arrivalSent = false
    crew.forEach((person) => {
      const isHome = phase === 'home'
      person.mesh.visible = !isHome
      person.mesh.userData.exclamation.visible = phase === 'alert'
      if (phase === 'alert' && !person.mesh.visible) person.mesh.position.set(...person.home)
      const path = makeCrewRoute(person, phase)
      crewMotion.paths.push(path)
      if (phase === 'working' && path.length > 1) {
        person.trail.geometry.dispose()
        person.trail.geometry = new THREE.BufferGeometry().setFromPoints(path.map((point) => point.clone().setY(0.12)))
        person.trail.computeLineDistances()
      }
      person.trail.visible = ['working', 'positioned', 'actuating', 'waiting'].includes(phase)
    })
  }

  function updateCrew(elapsed) {
    if (crewMotion.phase !== visual.crewPhase) beginCrewPhase(visual.crewPhase, elapsed)
    const moving = crewMotion.duration > 0 && elapsed - crewMotion.started < crewMotion.duration
    const raw = crewMotion.duration ? Math.min((elapsed - crewMotion.started) / crewMotion.duration, 1) : 1
    const progress = raw * raw * (3 - 2 * raw)
    crew.forEach((person, index) => {
      const mesh = person.mesh
      if (!mesh.visible) return
      const path = crewMotion.paths[index]
      const previous = mesh.position.clone()
      if (moving && path?.length > 1) mesh.position.copy(routePoint(path, progress))
      if (moving && path?.length > 1) {
        const dx = mesh.position.x - previous.x
        const dz = mesh.position.z - previous.z
        if (Math.abs(dx) + Math.abs(dz) > 0.0001) mesh.rotation.y = Math.atan2(dx, dz)
      }
      const walk = moving && path?.length > 1
      const gait = Math.sin(elapsed * 10 + index * 1.7)
      mesh.position.y = (walk ? Math.abs(gait) * 0.055 : 0)
      person.trail.material.dashOffset = -elapsed * 0.2
      if (visual.crewPhase === 'working' && !moving && person.lookAt) {
        mesh.rotation.y = Math.atan2(person.lookAt[0] - mesh.position.x, person.lookAt[2] - mesh.position.z)
      }
      mesh.userData.legs.forEach((leg, legIndex) => {
        leg.rotation.x = walk ? (legIndex === 0 ? 1 : -1) * gait * 0.48 : 0
      })
      mesh.userData.arms.forEach((arm, armIndex) => {
        if (walk) {
          arm.rotation.x = (armIndex === 0 ? -1 : 1) * gait * 0.32
          arm.rotation.z = 0
        } else if (visual.crewPhase === 'actuating') {
          const inspectorMotion = person.role === 'inspect' && armIndex === 0
          arm.rotation.x = inspectorMotion ? -0.45 - Math.sin(elapsed * 3.4) * 0.2 : armIndex === 1 ? -1.18 - Math.sin(elapsed * 4) * 0.08 : 0.08
          arm.rotation.z = inspectorMotion ? 0.18 : armIndex === 1 ? -0.14 : 0.08
        } else {
          arm.rotation.x = 0
          arm.rotation.z = 0
        }
      })
      const marker = mesh.userData.exclamation
      if (marker.visible) marker.position.y = 2.42 + Math.sin(elapsed * 4.5 + index) * 0.08
      if (visual.crewPhase === 'returning' && !moving) mesh.visible = false
    })
    if (visual.crewPhase === 'alert' && !moving && !crewMotion.alertReadySent) {
      crewMotion.alertReadySent = true
      if (onCrewAlertReady) onCrewAlertReady()
    }
    if (visual.crewPhase === 'working' && !moving && !crewMotion.arrivalSent) {
      crewMotion.arrivalSent = true
      if (onCrewArrived) onCrewArrived()
    }
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

  /** 执行一次驱离:被移除的鸟播放逃散动画,剩余鸟进入惊飞状态;返回是否还有剩余 */
  function disperse(force = 0) {
    if (!occupants.length) return 0
    scareBoost = 1
    const n = occupants.length
    let removeCount = Math.max(1, Math.ceil(n * 0.5))
    // 只剩 1 只时有小概率没驱走(拟真),除非 force
    if (n === 1 && force < 1 && Math.random() < 0.3) removeCount = 0
    removeCount = Math.min(removeCount, n)
    // 逃散动画:被移除的鸟从各自当前盘旋位置起飞(槽位 i ↔ occupants[i] 一一对应)
    const firstIdx = n - removeCount
    for (let k = 0; k < removeCount; k += 1) {
      const slot = birds[firstIdx + k]
      if (slot && slot.mesh.visible) spawnFlee(slot.mesh.position.clone())
      else spawnFlee(new THREE.Vector3((Math.random() - 0.5) * 14, 5.5 + Math.random() * 3, (Math.random() - 0.5) * 9))
    }
    occupants.length = firstIdx
    // 全部驱离完毕:本轮不允许再从检测数据"复活",直到新一轮检测
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
          loadCaptureTexture(
            captureCtx.server,
            occ.snap,
            captureCtx.ticket,
            occ.snapBbox,
            { title: occ.species, sub: Math.round((occ.confidence || 0) * 100) + '%' },
          )
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
    // 云台反复扫掠果园（巡逻式监测），底座朝向固定
    camRig.rotation.y = -Math.PI / 3.1
    camRig.userData.head.rotation.y = Math.sin(elapsed * 0.22) * 1.05

    // 驱鸟器声波：方式含声学（acoustic/both）时才点亮;夜间波纹更亮更远
    const { led: dled, waves, controlScreen: acousticScreen } = deterrent.userData
    const wavesOn = visual.executing && visual.repelMode !== 'infrared'
    dled.material.color.setHex(wavesOn ? 0xd3e856 : (visual.offline ? 0x9c5546 : 0x56753f))
    acousticScreen.material.color.setHex(wavesOn ? 0x66f5c7 : 0x35534b)
    waves.forEach(({ mesh, mat, phase }) => {
      if (!wavesOn) {
        mat.opacity = 0
        return
      }
      const t = (elapsed * 0.85 + phase) % 1
      mesh.scale.setScalar(0.8 + t * (visual.night ? 6.4 : 5.2))
      mat.opacity = Math.min(1, (1 - t) * (visual.night ? 0.8 : 0.55))
    })

    // 红外驱鸟器：方式含红外（infrared/both）时才点亮束流;夜间束流增强
    const ir = infrared.userData
    ir.controlScreen.material.color.setHex(visual.executing && visual.repelMode !== 'acoustic' ? 0xff524f : 0x3e4a46)
    const targetBird = birds.find((bird) => bird.active)
    const beamOn = visual.executing && !visual.offline && visual.repelMode !== 'acoustic' && !!targetBird
    ir.led.material.color.setHex(beamOn ? 0xffb066 : (visual.offline ? 0x9c5546 : 0x56753f))
    if (beamOn) {
      ir.head.updateWorldMatrix(true, false)
      const origin = new THREE.Vector3(0.22, 0, 0)
      const target = ir.head.worldToLocal(targetBird.mesh.position.clone())
      const direction = target.sub(origin)
      const distance = direction.length()
      ir.beam.position.copy(origin).addScaledVector(direction, 0.5)
      ir.beam.quaternion.setFromUnitVectors(worldUp, direction.normalize())
      ir.beam.scale.set(1, distance, 1)
      ir.beam.visible = true
      ir.beamMat.opacity = (visual.night ? 0.95 : 0.82) + Math.sin(elapsed * 5.5) * 0.1
    } else {
      ir.beam.visible = false
      ir.beamMat.opacity = 0
    }

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
    updateFleeBirds(dt)
    updateCrew(elapsed)
    updateDevices(dt, elapsed)
    composer.render()
  }

  loop()
  if (onReady) onReady({ scene, camera, renderer, controls })

  /* ---------- 对外接口 ---------- */
  return {
    /** 注入最新业务状态 */
    setState({ running, detections, alarms, executing, offline, detTime, snapshots, server, ticket, repelMode, crewPhase }) {
      visual.running = !!running
      visual.detections = Array.isArray(detections) ? detections : []
      visual.alarms = Array.isArray(alarms) ? alarms : []
      visual.executing = !!executing
      visual.offline = !!offline
      visual.detTime = detTime || 0
      if (repelMode) visual.repelMode = repelMode
      if (crewPhase) visual.crewPhase = crewPhase
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
    /** 昼夜光照:传入 0~24 小时(真实本地时间或光照演示滑杆) */
    setDaylight(hour) {
      applyDaylightHour(hour)
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
    /** 供开发验证读取果农演示状态，不参与业务数据持久化。 */
    crewState() {
      return { phase: crewMotion.phase, people: crew.map((person) => ({ name: person.name, visible: person.mesh.visible, position: person.mesh.position.toArray(), alert: person.mesh.userData.exclamation.visible })) }
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
      camera.position.set(26, 24, 37)
      controls.target.set(0, 1.8, 0)
      controls.update()
    },
    /** 聚焦某个点（演示用：聚焦大门 / 设备等） */
    /** 定位到某条检测记录(按 bbox 映射场景坐标,与 updateBirds 同一公式) */
    focusDetection(bbox) {
      if (!Array.isArray(bbox) || bbox.length !== 4) return
      const cx = ((bbox[0] + bbox[2]) / 2) / 960
      const cy = ((bbox[1] + bbox[3]) / 2) / 540
      const x = (cx - 0.5) * 26
      const z = (cy - 0.5) * 14
      controls.autoRotate = false
      camera.position.set(x, 8.5, z + 15)
      controls.target.set(x, 3.2, z)
      controls.update()
    },
    focusPoint(x, y, z, dist = 12) {
      controls.autoRotate = false
      camera.position.set(x, y + dist * 0.55, z + dist * 0.82)
      controls.target.set(x, y, z)
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
