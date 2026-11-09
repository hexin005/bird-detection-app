/**
 * 程序化自然果园场景构建器
 * ---------------------------------------------------------------------------
 * 全部几何体由代码生成，不依赖外部 GLB/GLTF 资源，保证零下载依赖。
 * 自然材质与实例化植被，保留墨绿果园 + 荧绿检测框的识别色。
 */
import * as THREE from 'three'

/* ---------- 调色板（与 tokens.css 对应） ---------- */
export const PALETTE = {
  sky: 0xc3d9d4,
  skyTop: 0x9fbeb8,
  fog: 0xd7dfcf,
  ground: 0x849765,
  groundDark: 0x6c8050,
  path: 0xb49b73,
  trunk: 0x6b5138,
  trunkDark: 0x4c3c2b,
  leafA: 0x587542,
  leafB: 0x718d4c,
  leafC: 0x8da457,
  leafD: 0x496b3c,
  fruit: 0xd27641,
  metal: 0x9ca79e,
  metalDark: 0x4d5b52,
  wood: 0x786047,
  detect: 0xd3e856,
  alarm: 0xe0a03a,
  bird: 0x2f3a2a,
}

/* Procedural surfaces: deterministic, tiled, no network or image dependencies. */
function surfaceTexture(kind, repeats = 1) {
  const size = 128
  const data = new Uint8Array(size * size * 4)
  const random = mulberry32(kind === 'bark' ? 421 : kind === 'soil' ? 933 : 711)
  const noiseGrid = Array.from({ length: 64 }, () => random() - .5)
  const smoothNoise = (x, y) => {
    const gx = x / 16, gy = y / 16
    const ix = Math.floor(gx), iy = Math.floor(gy)
    const u = gx - ix, v = gy - iy
    const sx = u * u * (3 - 2 * u), sy = v * v * (3 - 2 * v)
    const at = (a, b) => noiseGrid[(b % 8) * 8 + a % 8]
    const top = at(ix, iy) * (1 - sx) + at(ix + 1, iy) * sx
    const bottom = at(ix, iy + 1) * (1 - sx) + at(ix + 1, iy + 1) * sx
    return top * (1 - sy) + bottom * sy
  }
  const base = kind === 'bark' ? [111, 91, 69] : kind === 'soil' ? [152, 130, 99] : [112, 133, 77]
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const grain = (random() - .5) * 22
      const broad = smoothNoise(x, y) * 12
      const furrow = kind === 'bark' ? -Math.pow(.5 + .5 * Math.sin(x * Math.PI / 8 + Math.sin(y * Math.PI / 64)), 12) * 43 : 0
      const i = (y * size + x) * 4
      for (let c = 0; c < 3; c++) data[i + c] = Math.max(0, Math.min(255, base[c] + grain + broad + furrow))
      data[i + 3] = 255
    }
  }
  const texture = new THREE.DataTexture(data, size, size, THREE.RGBAFormat)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping
  texture.magFilter = THREE.LinearFilter
  texture.minFilter = THREE.LinearMipmapLinearFilter
  texture.generateMipmaps = true
  texture.repeat.set(repeats, repeats)
  texture.needsUpdate = true
  return texture
}

// Shared geometry and materials keep the extra botanical detail inexpensive.
let botanicalResources
function botanics() {
  if (botanicalResources) return botanicalResources
  const bark = surfaceTexture('bark')
  botanicalResources = {
    trunk: new THREE.CylinderGeometry(.65, 1, 1, 9, 3),
    branch: new THREE.CylinderGeometry(.3, 1, 1, 7),
    leaf: new THREE.SphereGeometry(1, 5, 3),
    fruit: new THREE.SphereGeometry(1, 8, 6),
    bark: new THREE.MeshStandardMaterial({ map: bark, roughness: .96, bumpMap: bark, bumpScale: .055 }),
    foliage: new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: .84 }),
    fruitMat: new THREE.MeshStandardMaterial({ color: 0xc47735, roughness: .64 }),
  }
  const resources = botanicalResources
  resources.bark.addEventListener('dispose', () => {
    if (botanicalResources === resources) botanicalResources = undefined
  })
  return resources
}

export function createTree(rand, scale = 1) {
  const group = new THREE.Group()
  const res = botanics()
  const height = (2.4 + rand() * 1.4) * scale
  const trunkR = (.16 + rand() * .08) * scale
  const trunk = new THREE.Mesh(res.trunk, res.bark)
  trunk.scale.set(trunkR, height, trunkR)
  trunk.position.y = height / 2
  trunk.castShadow = trunk.receiveShadow = true
  group.add(trunk)

  const crowns = []
  for (let i = 0; i < 5; i++) {
    const angle = i * Math.PI * 2 / 5 + rand() * .4
    const radius = (.7 + rand() * .4) * scale
    const center = new THREE.Vector3(Math.cos(angle) * .64 * scale, height + (rand() - .25) * scale, Math.sin(angle) * .64 * scale)
    crowns.push({ center, radius })
    const start = new THREE.Vector3(0, height * .65, 0)
    const delta = center.clone().sub(start)
    const branch = new THREE.Mesh(res.branch, res.bark)
    branch.position.copy(start).addScaledVector(delta, .5)
    branch.scale.set(trunkR * .48, delta.length(), trunkR * .48)
    branch.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), delta.normalize())
    branch.castShadow = true
    group.add(branch)
  }
  // Small overlapping foliage clusters produce a broken, organic silhouette.
  const count = 190
  const leaves = new THREE.InstancedMesh(res.leaf, res.foliage, count)
  const dummy = new THREE.Object3D()
  const color = new THREE.Color()
  for (let i = 0; i < count; i++) {
    const crown = crowns[i % crowns.length]
    const theta = rand() * Math.PI * 2
    const vertical = rand() * 2 - 1
    const r = Math.cbrt(rand()) * crown.radius
    const horizontal = Math.sqrt(1 - vertical * vertical)
    dummy.position.copy(crown.center).add(new THREE.Vector3(Math.cos(theta) * horizontal * r, vertical * r * .85, Math.sin(theta) * horizontal * r))
    dummy.rotation.set(rand() * 2, rand() * 6, rand() * 2)
    const leafSize = (.15 + rand() * .13) * scale
    dummy.scale.set(leafSize * 1.5, leafSize * .6, leafSize)
    dummy.updateMatrix()
    leaves.setMatrixAt(i, dummy.matrix)
    color.setHSL(.23 + rand() * .045, .34 + rand() * .17, .19 + rand() * .13)
    leaves.setColorAt(i, color)
  }
  leaves.castShadow = leaves.receiveShadow = true
  group.add(leaves)
  const fruits = new THREE.InstancedMesh(res.fruit, res.fruitMat, 9)
  for (let i = 0; i < 9; i++) {
    const c = crowns[i % crowns.length]
    dummy.position.copy(c.center).add(new THREE.Vector3((rand() - .5) * c.radius, -.35 * scale, (rand() - .5) * c.radius))
    dummy.scale.setScalar(.08 * scale)
    dummy.updateMatrix()
    fruits.setMatrixAt(i, dummy.matrix)
  }
  group.add(fruits)
  return group
}

/* ---------- 地面 ---------- */
export function createGround(rand) {
  const group = new THREE.Group()

  // 主地面：细分平面 + 顶点扰动，做出起伏
  const size = 60
  const seg = 40
  const geo = new THREE.PlaneGeometry(size, size, seg, seg)
  const pos = geo.attributes.position
  for (let i = 0; i < pos.count; i += 1) {
    const x = pos.getX(i)
    const y = pos.getY(i)
    const dist = Math.sqrt(x * x + y * y)
    // 围栏内保持平整，地形起伏从果园外缘开始，避免角柱被地面吞没。
    const lift = Math.pow(Math.min(Math.max((dist - 21.5) / 8.5, 0), 1), 2.2) * 1.8
    const noise = Math.sin(x * 0.35) * Math.cos(y * 0.31) * (dist < 21.5 ? 0.008 : 0.12)
    pos.setZ(i, lift + noise)
  }
  geo.computeVertexNormals()

  const grassTexture = surfaceTexture('grass', 24)
  const groundMat = new THREE.MeshStandardMaterial({ map: grassTexture, roughness: 1, bumpMap: grassTexture, bumpScale: .008 })
  const ground = new THREE.Mesh(geo, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  group.add(ground)

  // 果树下的耕作带让种植行列可读，草地与土壤形成柔和层次。
  const soilTexture = surfaceTexture('soil', 8)
  const bedMat = new THREE.MeshStandardMaterial({ map: soilTexture, roughness: 1, bumpMap: soilTexture, bumpScale: .012 })
  const irrigationMat = new THREE.MeshLambertMaterial({ color: 0x52694b, flatShading: true })
  for (const z of [-11.4, -5.6, 0.2, 6.0]) {
    const bed = new THREE.Mesh(new THREE.PlaneGeometry(27.5, 3.5), bedMat)
    bed.rotation.x = -Math.PI / 2
    bed.position.set(0, 0.024, z)
    bed.receiveShadow = true
    group.add(bed)

    // 细滴灌管沿树行铺设，作为果园场景的真实设施细节。
    const pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 27, 6), irrigationMat)
    pipe.rotation.z = Math.PI / 2
    pipe.position.set(0, 0.075, z + 1.18)
    group.add(pipe)
  }

  // 少量草丛集中在空地边缘，避免装饰遮住树木、设备和鸟类目标。
  const grassMat = new THREE.MeshLambertMaterial({ color: 0x718951, flatShading: true })
  for (let i = 0; i < 18; i += 1) {
    const x = (rand() - 0.5) * 34
    const z = (rand() - 0.5) * 34
    if ([-11.4, -5.6, 0.2, 6.0].some((rowZ) => Math.abs(z - rowZ) < 2.2) || Math.abs(x) < 2.8) continue
    const tuft = new THREE.Mesh(new THREE.ConeGeometry(0.16 + rand() * 0.12, 0.48 + rand() * 0.26, 4), grassMat)
    tuft.position.set(x, 0.27, z)
    tuft.rotation.y = rand() * Math.PI
    tuft.castShadow = true
    group.add(tuft)
  }

  // 中央土路
  const roadGeo = new THREE.PlaneGeometry(3.8, 34, 1, 8)
  const roadTexture = surfaceTexture('soil', 9)
  const roadMat = new THREE.MeshStandardMaterial({ color: 0xe0cfac, map: roadTexture, roughness: 1, bumpMap: roadTexture, bumpScale: .008 })
  const road = new THREE.Mesh(roadGeo, roadMat)
  road.rotation.x = -Math.PI / 2
  road.position.set(0, 0.035, 2)
  road.receiveShadow = true
  group.add(road)

  return group
}

/* ---------- 监控摄像头 ---------- */
export function createCamera() {
  const group = new THREE.Group()

  const metalMat = new THREE.MeshLambertMaterial({ color: PALETTE.metal, flatShading: true })
  const darkMat = new THREE.MeshLambertMaterial({ color: PALETTE.metalDark, flatShading: true })

  // 立柱
  const poleGeo = new THREE.CylinderGeometry(0.1, 0.13, 5.2, 8)
  const pole = new THREE.Mesh(poleGeo, metalMat)
  pole.position.y = 2.6
  pole.castShadow = true
  group.add(pole)

  // 底座
  const baseGeo = new THREE.CylinderGeometry(0.42, 0.5, 0.24, 8)
  const base = new THREE.Mesh(baseGeo, darkMat)
  base.position.y = 0.12
  base.castShadow = true
  group.add(base)

  // 横臂
  const armGeo = new THREE.CylinderGeometry(0.06, 0.06, 0.9, 6)
  const arm = new THREE.Mesh(armGeo, metalMat)
  arm.rotation.z = Math.PI / 2
  arm.position.set(0.42, 5.1, 0)
  arm.castShadow = true
  group.add(arm)

  // 云台组：球机/镜头/指示灯/视野锥挂在云台上，可独立旋转反复扫掠果园
  const head = new THREE.Group()
  head.position.set(0.86, 5.0, 0)

  // 球机外壳
  const housingGeo = new THREE.IcosahedronGeometry(0.32, 0)
  const housing = new THREE.Mesh(housingGeo, darkMat)
  housing.castShadow = true
  head.add(housing)

  // 镜头
  const lensGeo = new THREE.CylinderGeometry(0.14, 0.17, 0.22, 10)
  const lensMat = new THREE.MeshLambertMaterial({ color: 0x1a2018 })
  const lens = new THREE.Mesh(lensGeo, lensMat)
  lens.rotation.z = Math.PI / 2
  lens.position.set(0.24, -0.05, 0)
  head.add(lens)

  // 工作指示灯（运行时改色）
  const ledGeo = new THREE.SphereGeometry(0.055, 8, 8)
  const ledMat = new THREE.MeshBasicMaterial({ color: 0x445244 })
  const led = new THREE.Mesh(ledGeo, ledMat)
  led.position.set(0.16, 0.22, 0)
  head.add(led)

  // 视野锥（检测范围可视化，平时低透明度）
  const coneGeo = new THREE.ConeGeometry(4.2, 9, 16, 1, true)
  const coneMat = new THREE.MeshBasicMaterial({
    color: PALETTE.detect,
    transparent: true,
    opacity: 0.045,
    side: THREE.DoubleSide,
    depthWrite: false,
  })
  const cone = new THREE.Mesh(coneGeo, coneMat)
  cone.rotation.z = Math.PI / 2
  cone.position.set(4.34, -0.8, 0)
  head.add(cone)

  group.add(head)

  group.userData = { led, cone, coneMat, head }
  return group
}

/* ---------- 声学驱鸟器 ---------- */
export function createDeterrent() {
  const group = new THREE.Group()

  const woodMat = new THREE.MeshLambertMaterial({ color: PALETTE.wood, flatShading: true })
  const metalMat = new THREE.MeshLambertMaterial({ color: PALETTE.metal, flatShading: true })
  const darkMat = new THREE.MeshLambertMaterial({ color: PALETTE.metalDark, flatShading: true })

  // 立柱
  const poleGeo = new THREE.CylinderGeometry(0.11, 0.14, 3.6, 8)
  const pole = new THREE.Mesh(poleGeo, woodMat)
  pole.position.y = 1.8
  pole.castShadow = true
  group.add(pole)

  // 底座
  const baseGeo = new THREE.CylinderGeometry(0.46, 0.54, 0.22, 8)
  const base = new THREE.Mesh(baseGeo, darkMat)
  base.position.y = 0.11
  base.castShadow = true
  group.add(base)

  // 主机箱
  const boxGeo = new THREE.BoxGeometry(0.52, 0.68, 0.4)
  const box = new THREE.Mesh(boxGeo, darkMat)
  box.position.y = 3.5
  box.castShadow = true
  group.add(box)

  // 设备底部加实体控制面板，果农到位后会在这里执行触控操作。
  const controlHousing = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.48, 0.24), darkMat)
  controlHousing.position.set(0.18, 1.3, 0)
  controlHousing.castShadow = true
  group.add(controlHousing)
  const controlScreen = new THREE.Mesh(
    new THREE.BoxGeometry(0.035, 0.24, 0.16),
    new THREE.MeshBasicMaterial({ color: 0x35534b }),
  )
  controlScreen.position.set(0.35, 1.32, 0)
  group.add(controlScreen)

  // 喇叭 ×2（左右各一）
  const hornMat = new THREE.MeshLambertMaterial({ color: PALETTE.metal, flatShading: true })
  for (const dir of [-1, 1]) {
    const hornGeo = new THREE.ConeGeometry(0.3, 0.62, 10, 1, true)
    const horn = new THREE.Mesh(hornGeo, hornMat)
    horn.rotation.z = dir * Math.PI / 2
    horn.position.set(dir * 0.52, 3.66, 0)
    horn.castShadow = true
    group.add(horn)
  }

  // 顶部指示灯
  const ledGeo = new THREE.SphereGeometry(0.075, 8, 8)
  const ledMat = new THREE.MeshBasicMaterial({ color: 0x56753f })
  const led = new THREE.Mesh(ledGeo, ledMat)
  led.position.y = 3.94
  group.add(led)

  // 声波环（执行时显示，用 3 个同心圆环 Pool）
  const waves = []
  for (let i = 0; i < 3; i += 1) {
    const ringGeo = new THREE.RingGeometry(0.3, 0.42, 32)
    const ringMat = new THREE.MeshBasicMaterial({
      color: PALETTE.detect,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
    const ring = new THREE.Mesh(ringGeo, ringMat)
    ring.position.set(0, 3.66, 0)
    ring.rotation.x = -Math.PI / 2
    group.add(ring)
    waves.push({ mesh: ring, mat: ringMat, phase: i / 3 })
  }

  group.userData = { led, ledMat, waves, metalMat, controlScreen }
  return group
}

/* ---------- 鸟类（billboard 精灵 + 简单羽翼） ---------- */
export function createBirdMesh() {
  const group = new THREE.Group()

  const bodyMat = new THREE.MeshLambertMaterial({ color: PALETTE.bird, flatShading: true })
  const bodyGeo = new THREE.IcosahedronGeometry(0.16, 0)
  const body = new THREE.Mesh(bodyGeo, bodyMat)
  body.scale.set(1.5, 1, 0.9)
  group.add(body)

  // 真实抓拍 billboard：有贴图时显示，覆盖在低模鸟之上
  const spriteMat = new THREE.SpriteMaterial({
    color: 0xffffff,
    transparent: true,
    depthWrite: false,
    opacity: 0,
  })
  const sprite = new THREE.Sprite(spriteMat)
  sprite.scale.set(1.1, 0.72, 1)   // 16:10 左右的卡片比例
  sprite.visible = false
  group.add(sprite)

  // 双翼：薄三角片，播动时旋转
  const wingMat = new THREE.MeshLambertMaterial({
    color: 0x3d4a35,
    flatShading: true,
    side: THREE.DoubleSide,
  })
  const wingGeo = new THREE.ConeGeometry(0.22, 0.52, 3)
  const wings = []
  for (const dir of [-1, 1]) {
    const wing = new THREE.Mesh(wingGeo, wingMat)
    wing.rotation.z = dir * Math.PI / 2
    wing.position.set(0, 0.02, dir * 0.2)
    group.add(wing)
    wings.push({ mesh: wing, dir })
  }

  group.userData = { wings, body, sprite, spriteMat }
  return group
}

/* ---------- 检测框（3D 线框） ---------- */
export function createDetectBox() {
  const geo = new THREE.BoxGeometry(1, 1, 1)
  const edges = new THREE.EdgesGeometry(geo)
  const mat = new THREE.LineBasicMaterial({ color: PALETTE.detect, transparent: true, opacity: 0.9 })
  const box = new THREE.LineSegments(edges, mat)
  return box
}

/* ---------- 告警标记（头顶浮标） ---------- */
export function createAlarmMarker() {
  const group = new THREE.Group()

  const mat = new THREE.MeshBasicMaterial({ color: PALETTE.alarm, transparent: true, opacity: 0.95 })

  // 倒锥形指针
  const coneGeo = new THREE.ConeGeometry(0.16, 0.34, 4)
  const cone = new THREE.Mesh(coneGeo, mat)
  cone.rotation.x = Math.PI
  group.add(cone)

  const ringGeo = new THREE.RingGeometry(0.22, 0.3, 16)
  const ringMat = new THREE.MeshBasicMaterial({
    color: PALETTE.alarm,
    transparent: true,
    opacity: 0.55,
    side: THREE.DoubleSide,
    depthWrite: false,
  })
  const ring = new THREE.Mesh(ringGeo, ringMat)
  ring.rotation.x = -Math.PI / 2
  ring.position.y = -0.2
  group.add(ring)

  group.userData = { ring, ringMat }
  return group
}

/* ---------- 种子随机 ---------- */
export function mulberry32(seed) {
  let a = seed
  return function rand() {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/* ---------- 栅栏（围网，南侧留大门缺口） ---------- */
export function createFence() {
  const g = new THREE.Group()
  const postMat = new THREE.MeshLambertMaterial({ color: PALETTE.trunk, flatShading: true })
  const railMat = new THREE.MeshLambertMaterial({ color: 0x8a7458, flatShading: true })
  const R = 16
  const step = 2.9
  const fenceTop = 2.15
  const postGeo = new THREE.CylinderGeometry(0.055, 0.075, fenceTop, 6)

  const addPost = (x, z) => {
    const p = new THREE.Mesh(postGeo, postMat)
    p.position.set(x, fenceTop / 2, z)
    p.castShadow = true
    g.add(p)
  }
  const addRail = (x, z, len, along) => {
    for (const y of [0.55, 1.45]) {
      const r = new THREE.Mesh(
        new THREE.BoxGeometry(along === 'x' ? len : 0.05, 0.06, along === 'x' ? 0.05 : len),
        railMat,
      )
      r.position.set(x, y, z)
      r.castShadow = true
      g.add(r)
    }
  }

  for (let x = -R; x <= R + 0.01; x += step) {
    addPost(x, -R)
    if (Math.abs(x) > 2.2) addPost(x, R)   // 南侧留大门缺口
  }
  for (let z = -R + step; z <= R - step + 0.01; z += step) {
    addPost(-R, z)
    addPost(R, z)
  }
  addRail(0, -R, 2 * R, 'x')
  addRail(-9.1, R, 13.8, 'x')   // 南侧只留 4.4 单位宽的正门
  addRail(9.1, R, 13.8, 'x')
  addRail(-R, 0, 2 * R, 'z')
  addRail(R, 0, 2 * R, 'z')
  return g
}

/* ---------- 大门（门柱 + 果园招牌） ---------- */
function makeSignTexture(text) {
  const c = document.createElement('canvas')
  c.width = 512
  c.height = 72
  const x = c.getContext('2d')
  x.fillStyle = '#2c4429'
  x.fillRect(0, 0, 512, 72)
  x.fillStyle = '#d3e856'
  x.fillRect(20, 22, 10, 10)
  x.fillRect(482, 22, 10, 10)
  x.fillStyle = '#f5f7ec'
  x.font = 'bold 40px "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif'
  x.textAlign = 'center'
  x.textBaseline = 'middle'
  x.fillText(text, 256, 40)
  const t = new THREE.CanvasTexture(c)
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

export function createGate() {
  const g = new THREE.Group()
  const pillarMat = new THREE.MeshLambertMaterial({ color: 0x54503f, flatShading: true })
  for (const x of [-2.4, 2.4]) {
    const p = new THREE.Mesh(new THREE.BoxGeometry(0.55, 1.7, 0.55), pillarMat)
    p.position.set(x, 0.85, 0)
    p.castShadow = true
    g.add(p)
    const cap = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.14, 0.78), pillarMat)
    cap.position.set(x, 1.77, 0)
    g.add(cap)
  }
  const board = new THREE.Mesh(
    new THREE.BoxGeometry(4.4, 0.74, 0.12),
    new THREE.MeshLambertMaterial({ color: 0x34502f, flatShading: true }),
  )
  board.position.set(0, 1.66, 0)
  board.castShadow = true
  g.add(board)
  const signMat = new THREE.MeshBasicMaterial({ map: makeSignTexture('青禾示范果园') })
  for (const side of [1, -1]) {
    const sign = new THREE.Mesh(new THREE.PlaneGeometry(4.15, 0.58), signMat)
    sign.position.set(0, 1.66, side * 0.065)
    if (side < 0) sign.rotation.y = Math.PI
    g.add(sign)
  }
  return g
}

/* ---------- 农户房子（门柱旁的住户） ---------- */
export function createHouse() {
  const g = new THREE.Group()
  const wallMat = new THREE.MeshLambertMaterial({ color: 0xece5d2, flatShading: true })
  const roofMat = new THREE.MeshLambertMaterial({ color: 0x8a5a3e, flatShading: true })
  const woodMat = new THREE.MeshLambertMaterial({ color: PALETTE.trunk, flatShading: true })
  const glassMat = new THREE.MeshLambertMaterial({ color: 0xb9d2e2, flatShading: true })
  const pathMat = new THREE.MeshLambertMaterial({ color: PALETTE.path, flatShading: true })

  const wall = (width, height, depth, x, y, z) => {
    const panel = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), wallMat)
    panel.position.set(x, y, z)
    panel.castShadow = true
    panel.receiveShadow = true
    g.add(panel)
  }
  // 分片墙体给正门留出真实开口，果农可以从室内走出来。
  wall(0.18, 2.5, 3.4, -2.11, 1.25, 0)
  wall(0.18, 2.5, 3.4, 2.11, 1.25, 0)
  wall(4.4, 2.5, 0.18, 0, 1.25, -1.61)
  wall(0.825, 2.5, 0.18, -1.7875, 1.25, 1.61)
  wall(2.625, 2.5, 0.18, 0.8875, 1.25, 1.61)
  wall(0.95, 0.85, 0.18, -0.9, 2.075, 1.61)

  const roof = new THREE.Mesh(new THREE.ConeGeometry(2.75, 1.55, 4), roofMat)
  roof.rotation.y = Math.PI / 4
  roof.position.y = 3.28
  roof.castShadow = true
  g.add(roof)

  const lintel = new THREE.Mesh(new THREE.BoxGeometry(1.18, 0.16, 0.16), woodMat)
  lintel.position.set(-0.9, 1.72, 1.76)
  g.add(lintel)
  for (const x of [-1.43, -0.37]) {
    const jamb = new THREE.Mesh(new THREE.BoxGeometry(0.1, 1.72, 0.16), woodMat)
    jamb.position.set(x, 0.86, 1.76)
    g.add(jamb)
  }

  for (const wx of [0.95, 1.95]) {
    const win = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.68, 0.035), glassMat)
    win.position.set(wx, 1.5, 1.72)
    g.add(win)
    for (const y of [1.08, 1.92]) {
      const rail = new THREE.Mesh(new THREE.BoxGeometry(0.86, 0.08, 0.08), woodMat)
      rail.position.set(wx, y, 1.77)
      g.add(rail)
    }
    for (const x of [wx - 0.42, wx + 0.42]) {
      const stile = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.84, 0.08), woodMat)
      stile.position.set(x, 1.5, 1.77)
      g.add(stile)
    }
    const mullion = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.68, 0.08), woodMat)
    mullion.position.set(wx, 1.5, 1.77)
    g.add(mullion)
  }

  const chim = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.95, 0.42), roofMat)
  chim.position.set(1.2, 3.5, -0.7)
  g.add(chim)

  const step = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.16, 0.9), pathMat)
  step.position.set(-0.9, 0.08, 2.35)
  g.add(step)

  // 门前短廊与台阶共轴，房屋转向时入口仍保持明确。
  const porch = new THREE.Mesh(new THREE.BoxGeometry(1.85, 0.12, 1.25), pathMat)
  porch.position.set(-0.9, 0.025, 2.9)
  g.add(porch)

  return g
}

/* ---------- 红外驱鸟器（脉冲束流，与声学联动） ---------- */
export function createInfrared() {
  const g = new THREE.Group()
  const metalMat = new THREE.MeshLambertMaterial({ color: PALETTE.metal, flatShading: true })
  const darkMat = new THREE.MeshLambertMaterial({ color: PALETTE.metalDark, flatShading: true })

  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.11, 3.1, 8), metalMat)
  pole.position.y = 1.55
  pole.castShadow = true
  g.add(pole)

  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.44, 0.2, 8), darkMat)
  base.position.y = 0.1
  base.castShadow = true
  g.add(base)

  const controlBox = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.5, 0.18), darkMat)
  controlBox.position.set(0, 1.25, -0.28)
  controlBox.castShadow = true
  g.add(controlBox)
  const controlScreen = new THREE.Mesh(
    new THREE.BoxGeometry(0.2, 0.26, 0.035),
    new THREE.MeshBasicMaterial({ color: 0x3e4a46 }),
  )
  controlScreen.position.set(0, 1.28, -0.39)
  g.add(controlScreen)

  const head = new THREE.Group()
  head.position.y = 3.0

  const body = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.52, 0.36), darkMat)
  body.castShadow = true
  head.add(body)

  // 红外发射环（红色，与直线束流同色）
  const lens = new THREE.Mesh(
    new THREE.TorusGeometry(0.13, 0.035, 8, 16),
    new THREE.MeshBasicMaterial({ color: 0xf04438 }),
  )
  lens.rotation.y = Math.PI / 2
  lens.position.set(0.2, 0, 0)
  head.add(lens)

  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.06, 8, 8),
    new THREE.MeshBasicMaterial({ color: 0xff756b }),
  )
  core.position.set(0.22, 0, 0)
  head.add(core)

  const led = new THREE.Mesh(
    new THREE.SphereGeometry(0.05, 8, 8),
    new THREE.MeshBasicMaterial({ color: 0x56753f }),
  )
  led.position.set(0, 0.34, 0)
  head.add(led)

  // 直线红外束由渲染器逐帧瞄准当前鸟类目标。
  const beam = new THREE.Mesh(
    new THREE.CylinderGeometry(0.035, 0.035, 1, 8),
    new THREE.MeshBasicMaterial({
      color: 0xf04438,
      transparent: true,
      opacity: 0,
      depthWrite: false,
    }),
  )
  beam.position.set(0, -10, 0)
  head.add(beam)

  g.add(head)

  g.userData = { led, beam, beamMat: beam.material, head, controlScreen }
  return g
}

/* ---------- 果农角色：低多边形人物，供检测/驱离流程驱动 ---------- */
export function createFarmer({ shirt = 0x5d8050, hat = 0xc7a76c } = {}) {
  const g = new THREE.Group()
  const skin = new THREE.MeshLambertMaterial({ color: 0xc98d67, flatShading: true })
  const shirtMat = new THREE.MeshLambertMaterial({ color: shirt, flatShading: true })
  const pantsMat = new THREE.MeshLambertMaterial({ color: 0x42566a, flatShading: true })
  const hatMat = new THREE.MeshLambertMaterial({ color: hat, flatShading: true })
  const bootMat = new THREE.MeshLambertMaterial({ color: 0x493c2e, flatShading: true })

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.27, 0.62, 7), shirtMat)
  torso.position.y = 1.08
  torso.castShadow = true
  g.add(torso)

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.19, 8, 6), skin)
  head.position.set(0, 1.57, 0.02)
  head.castShadow = true
  g.add(head)

  const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.31, 0.31, 0.055, 10), hatMat)
  brim.position.y = 1.76
  g.add(brim)
  const crown = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.21, 0.2, 8), hatMat)
  crown.position.y = 1.88
  g.add(crown)

  const arms = []
  const legs = []
  for (const side of [-1, 1]) {
    const arm = new THREE.Group()
    arm.position.set(side * 0.23, 1.31, 0)
    const sleeve = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.09, 0.48, 6), shirtMat)
    sleeve.position.y = -0.22
    sleeve.rotation.z = side * -0.12
    sleeve.castShadow = true
    arm.add(sleeve)
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.075, 6, 5), skin)
    hand.position.set(side * -0.025, -0.48, 0.015)
    arm.add(hand)
    g.add(arm)
    arms.push(arm)

    const leg = new THREE.Group()
    leg.position.set(side * 0.11, 0.78, 0)
    const trouser = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.075, 0.46, 6), pantsMat)
    trouser.position.y = -0.22
    leg.add(trouser)
    const boot = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.1, 0.26), bootMat)
    boot.position.set(0, -0.48, 0.045)
    leg.add(boot)
    g.add(leg)
    legs.push(leg)
  }

  const exclamation = new THREE.Group()
  const red = new THREE.MeshBasicMaterial({ color: 0xe8453c })
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.25, 8), red)
  stem.position.y = 0.15
  exclamation.add(stem)
  const dot = new THREE.Mesh(new THREE.SphereGeometry(0.055, 8, 6), red)
  dot.position.y = -0.04
  exclamation.add(dot)
  exclamation.position.y = 2.42
  exclamation.visible = false
  g.add(exclamation)

  g.userData = { arms, legs, exclamation }
  return g
}
