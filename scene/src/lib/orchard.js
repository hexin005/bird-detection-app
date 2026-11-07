/**
 * 低多边形果园场景构建器
 * ---------------------------------------------------------------------------
 * 全部几何体由代码生成，不依赖外部 GLB/GLTF 资源，保证零下载依赖。
 * 配色取自 designs token：墨绿果园 + 荧绿检测框。
 */
import * as THREE from 'three'

/* ---------- 调色板（与 tokens.css 对应） ---------- */
export const PALETTE = {
  sky: 0x8fa7b8,
  skyTop: 0x6d8ba3,
  fog: 0xb8c4c9,
  ground: 0x6d7f4a,
  groundDark: 0x55663a,
  path: 0x9a9270,
  trunk: 0x5a4a35,
  trunkDark: 0x463a29,
  leafA: 0x4f7d3a,
  leafB: 0x5f8f42,
  leafC: 0x6d9d4c,
  leafD: 0x476f34,
  fruit: 0xc4562f,
  metal: 0x8d9491,
  metalDark: 0x5e6663,
  wood: 0x6b5842,
  detect: 0xd3e856,
  alarm: 0xe0a03a,
  bird: 0x2f3a2a,
}

/* ---------- 低多边形树 ---------- */
/**
 * 生成一棵低多边形果树：锥台树干 + 3~5 个多面体树冠。
 * @param {() => number} rand 伪随机函数，保证同 seed 下形态稳定
 * @param {number} scale 整体缩放
 */
export function createTree(rand, scale = 1) {
  const group = new THREE.Group()

  const height = (2.4 + rand() * 1.4) * scale
  const trunkR = (0.16 + rand() * 0.08) * scale

  // 树干：上细下粗的锥台
  const trunkGeo = new THREE.CylinderGeometry(trunkR * 0.72, trunkR, height, 6, 1)
  const trunkMat = new THREE.MeshLambertMaterial({ color: PALETTE.trunk, flatShading: true })
  const trunk = new THREE.Mesh(trunkGeo, trunkMat)
  trunk.position.y = height / 2
  trunk.castShadow = true
  trunk.receiveShadow = true
  group.add(trunk)

  // 树冠：3~5 个不同大小的二十面体堆叠
  const leafColors = [PALETTE.leafA, PALETTE.leafB, PALETTE.leafC, PALETTE.leafD]
  const crownCount = 3 + Math.floor(rand() * 3)
  for (let i = 0; i < crownCount; i += 1) {
    const radius = (0.85 + rand() * 0.55) * scale
    const geo = new THREE.IcosahedronGeometry(radius, 0)
    const mat = new THREE.MeshLambertMaterial({
      color: leafColors[Math.floor(rand() * leafColors.length)],
      flatShading: true,
    })
    const crown = new THREE.Mesh(geo, mat)
    const angle = rand() * Math.PI * 2
    const spread = rand() * 0.55 * scale
    crown.position.set(
      Math.cos(angle) * spread,
      height + (rand() - 0.3) * 0.7 * scale,
      Math.sin(angle) * spread,
    )
    crown.rotation.set(rand() * Math.PI, rand() * Math.PI, rand() * Math.PI)
    crown.castShadow = true
    crown.receiveShadow = true
    group.add(crown)

    // 少量果实点缀
    if (rand() > 0.45) {
      const fruitGeo = new THREE.IcosahedronGeometry(0.09 * scale, 0)
      const fruitMat = new THREE.MeshLambertMaterial({ color: PALETTE.fruit, flatShading: true })
      const fruit = new THREE.Mesh(fruitGeo, fruitMat)
      fruit.position.set(
        crown.position.x + (rand() - 0.5) * radius * 1.4,
        crown.position.y + (rand() - 0.5) * radius * 1.2,
        crown.position.z + (rand() - 0.5) * radius * 1.4,
      )
      group.add(fruit)
    }
  }

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
    // 边缘抬起，中间平坦（视觉上像一块坡地）
    const lift = Math.pow(Math.min(dist / (size * 0.5), 1), 2.2) * 1.8
    const noise = Math.sin(x * 0.35) * Math.cos(y * 0.31) * 0.18
    pos.setZ(i, lift + noise)
  }
  geo.computeVertexNormals()

  const groundMat = new THREE.MeshLambertMaterial({
    color: PALETTE.ground,
    flatShading: true,
  })
  const ground = new THREE.Mesh(geo, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  group.add(ground)

  // 深色补丁：随机小块，打破单调
  for (let i = 0; i < 14; i += 1) {
    const patchGeo = new THREE.CircleGeometry(1.2 + rand() * 2.2, 6)
    const patchMat = new THREE.MeshLambertMaterial({
      color: PALETTE.groundDark,
      flatShading: true,
    })
    const patch = new THREE.Mesh(patchGeo, patchMat)
    patch.rotation.x = -Math.PI / 2
    patch.position.set((rand() - 0.5) * 34, 0.02, (rand() - 0.5) * 34)
    patch.receiveShadow = true
    group.add(patch)
  }

  // 中央土路
  const roadGeo = new THREE.PlaneGeometry(3.2, 26, 1, 8)
  const roadMat = new THREE.MeshLambertMaterial({ color: PALETTE.path, flatShading: true })
  const road = new THREE.Mesh(roadGeo, roadMat)
  road.rotation.x = -Math.PI / 2
  road.position.set(0, 0.03, 2)
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

  // 球机外壳
  const housingGeo = new THREE.IcosahedronGeometry(0.32, 0)
  const housing = new THREE.Mesh(housingGeo, darkMat)
  housing.position.set(0.86, 5.0, 0)
  housing.castShadow = true
  group.add(housing)

  // 镜头
  const lensGeo = new THREE.CylinderGeometry(0.14, 0.17, 0.22, 10)
  const lensMat = new THREE.MeshLambertMaterial({ color: 0x1a2018 })
  const lens = new THREE.Mesh(lensGeo, lensMat)
  lens.rotation.z = Math.PI / 2
  lens.position.set(1.1, 4.95, 0)
  group.add(lens)

  // 工作指示灯（运行时改色）
  const ledGeo = new THREE.SphereGeometry(0.055, 8, 8)
  const ledMat = new THREE.MeshBasicMaterial({ color: 0x445244 })
  const led = new THREE.Mesh(ledGeo, ledMat)
  led.position.set(1.02, 5.22, 0)
  group.add(led)

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
  cone.position.set(5.2, 4.2, 0)
  group.add(cone)

  group.userData = { led, cone, coneMat }
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

  group.userData = { led, ledMat, waves, metalMat }
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
