/**
 * 农场地形扩展:环园道路、支路、田块底色与过渡带(布局图 v1 坐标)。
 * 只做"地形与通路"(阶段 1);作物/农具等细节在阶段 4 由 wheat.js/vegetable.js 追加。
 */
import * as THREE from 'three'
import { surfaceTexture } from './orchard.js'

/* 布局常量(与 docs/scene-farm/layout.html 一致;阶段 2 的路点图同样引用) */
export const FARM = {
  ring: 20.5,          // 环园道路中心线
  roadWidth: 2.4,
  wheat: { x1: -46, x2: -24, z1: -44, z2: -18 },   // 麦田 22×26(西北)
  veg: { x1: 26, x2: 46, z1: -13, z2: 13 },        // 菜地 20×26(东)
}

const flat = (mat) => new THREE.MeshStandardMaterial({
  ...mat, roughness: 1,
  // 远距离深度精度(near=0.5)下避免与地面 z-fighting
  polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
})

export function createTerrain(rand) {
  const group = new THREE.Group()
  const roadTexture = surfaceTexture('soil', 7)

  /* ---- 道路:略高于草面,同土壤色系 ---- */
  const roadMat = flat({ color: 0xcfc2a2, map: roadTexture, bumpMap: roadTexture, bumpScale: .006 })
  const addRoad = (w, l, x, z, rotY = 0) => {
    const road = new THREE.Mesh(new THREE.PlaneGeometry(w, l), roadMat)
    road.rotation.x = -Math.PI / 2
    road.rotation.z = rotY
    road.position.set(x, 0.045, z)
    road.receiveShadow = true
    group.add(road)
  }
  // 环园路四边:平面默认长边沿 z(南北向),东西向条带需面内旋转 90°
  const s = FARM.ring
  const edge = 2 * s + FARM.roadWidth
  addRoad(FARM.roadWidth, edge, -s, 0)                  // 西边(南北向)
  addRoad(FARM.roadWidth, edge, s, 0)                   // 东边(南北向)
  addRoad(FARM.roadWidth, edge, 0, -s, Math.PI / 2)     // 北边(东西向)
  addRoad(FARM.roadWidth, edge, 0, s, Math.PI / 2)      // 南边(东西向)
  // 西北支路:沿北边向西延伸进麦田南缘(x -21.7 → -27,东西向)
  addRoad(5.8, FARM.roadWidth * 0.92, -24.6, -s)
  // 东支路:沿东边向东进菜地西缘(x 21.7 → 27, z 0,东西向)
  addRoad(5.4, FARM.roadWidth * 0.92, 24.3, 0)

  /* ---- 田块底色:麦田金浪 / 菜地深畦(作物阶段 4 再立起来) ---- */
  const wheatTex = surfaceTexture('wheat', 5)
  const wheatMat = flat({ map: wheatTex, bumpMap: wheatTex, bumpScale: .01 })
  const wheat = new THREE.Mesh(new THREE.PlaneGeometry(FARM.wheat.x2 - FARM.wheat.x1 + 2, FARM.wheat.z2 - FARM.wheat.z1 + 2), wheatMat)
  wheat.rotation.x = -Math.PI / 2
  wheat.position.set((FARM.wheat.x1 + FARM.wheat.x2) / 2, 0.03, (FARM.wheat.z1 + FARM.wheat.z2) / 2)
  wheat.receiveShadow = true
  group.add(wheat)

  const bedTex = surfaceTexture('bed', 5)
  const bedMat = flat({ map: bedTex, bumpMap: bedTex, bumpScale: .012 })
  const veg = new THREE.Mesh(new THREE.PlaneGeometry(FARM.veg.x2 - FARM.veg.x1 + 2, FARM.veg.z2 - FARM.veg.z1 + 2), bedMat)
  veg.rotation.x = -Math.PI / 2
  veg.position.set((FARM.veg.x1 + FARM.veg.x2) / 2, 0.03, (FARM.veg.z1 + FARM.veg.z2) / 2)
  veg.receiveShadow = true
  group.add(veg)

  /* ---- 过渡带:田块内侧排水沟(深色湿沟) + 少量杂草 ---- */
  const ditchMat = new THREE.MeshLambertMaterial({ color: 0x4a5a3c, flatShading: true, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 })
  const ditch = (w, l, x, z) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, l), ditchMat)
    m.rotation.x = -Math.PI / 2
    m.position.set(x, 0.028, z)
    m.receiveShadow = true
    group.add(m)
  }
  // 麦田东缘与南缘各一条(朝果园/道路侧)
  ditch(1.1, FARM.wheat.z2 - FARM.wheat.z1, FARM.wheat.x2 + 1.6, (FARM.wheat.z1 + FARM.wheat.z2) / 2)
  ditch(FARM.wheat.x2 - FARM.wheat.x1 + 2, 1.1, (FARM.wheat.x1 + FARM.wheat.x2) / 2, FARM.wheat.z2 + 1.6)
  // 菜地西缘一条
  ditch(1.1, FARM.veg.z2 - FARM.veg.z1, FARM.veg.x1 - 1.6, (FARM.veg.z1 + FARM.veg.z2) / 2)

  const tuftMat = new THREE.MeshLambertMaterial({ color: 0x7a8f55, flatShading: true })
  for (let i = 0; i < 16; i += 1) {
    // 过渡带草丛:贴着田缘与路肩,不进田块中心
    const nearWheat = rand() > 0.5
    const t = rand()
    let x, z
    if (nearWheat) {
      x = FARM.wheat.x2 + 2.6 + rand() * 2.2
      z = FARM.wheat.z1 + t * (FARM.wheat.z2 - FARM.wheat.z1)
    } else {
      x = FARM.veg.x1 - 2.6 - rand() * 2.2
      z = FARM.veg.z1 + t * (FARM.veg.z2 - FARM.veg.z1)
    }
    const tuft = new THREE.Mesh(new THREE.ConeGeometry(0.14 + rand() * 0.12, 0.42 + rand() * 0.24, 4), tuftMat)
    tuft.position.set(x, 0.24, z)
    tuft.rotation.y = rand() * Math.PI
    group.add(tuft)
  }

  group.add(createCrops(rand))

  return group
}

/* ---- 作物:麦束与菜丛(InstancedMesh,各 1 个 draw call;风吹摆动阶段 4 再加) ---- */
export function createCrops(rand) {
  const group = new THREE.Group()
  const F = FARM
  const dummy = new THREE.Object3D()
  const tint = new THREE.Color()

  // 麦束:沿 x 条播(与垄纹同向),缺株 ~8%,株高微差
  const stemGeo = new THREE.ConeGeometry(0.09, 0.62, 5)
  const stemMat = new THREE.MeshLambertMaterial({ color: 0xffffff, flatShading: true })
  const wheatSpots = []
  for (let z = F.wheat.z1 + 1.4; z <= F.wheat.z2 - 1.4; z += 1.15) {
    for (let x = F.wheat.x1 + 1.2; x <= F.wheat.x2 - 1.2; x += 0.72) {
      if (rand() < 0.08) continue
      wheatSpots.push([x + (rand() - 0.5) * 0.3, z + (rand() - 0.5) * 0.3])
    }
  }
  const wheat = new THREE.InstancedMesh(stemGeo, stemMat, wheatSpots.length)
  wheatSpots.forEach(([x, z], i) => {
    const s = 0.85 + rand() * 0.45
    dummy.position.set(x, 0.31 * s, z)
    dummy.scale.setScalar(s)
    dummy.rotation.y = rand() * Math.PI
    dummy.updateMatrix()
    wheat.setMatrixAt(i, dummy.matrix)
    wheat.setColorAt(i, tint.setHSL(0.105 + rand() * 0.025, 0.5 + rand() * 0.14, 0.4 + rand() * 0.12))
  })
  wheat.instanceMatrix.needsUpdate = true
  if (wheat.instanceColor) wheat.instanceColor.needsUpdate = true
  group.add(wheat)

  // 菜丛:沿 z 向的畦沟条植,缺株 ~10%,两种绿 + 尺寸差
  const vegGeo = new THREE.IcosahedronGeometry(0.18, 0)
  const vegMat = new THREE.MeshLambertMaterial({ color: 0xffffff, flatShading: true })
  const vegSpots = []
  for (let x = F.veg.x1 + 1.4; x <= F.veg.x2 - 1.4; x += 1.4) {
    for (let z = F.veg.z1 + 1.2; z <= F.veg.z2 - 1.2; z += 0.92) {
      if (rand() < 0.1) continue
      vegSpots.push([x + (rand() - 0.5) * 0.26, z + (rand() - 0.5) * 0.26])
    }
  }
  const vegs = new THREE.InstancedMesh(vegGeo, vegMat, vegSpots.length)
  vegSpots.forEach(([x, z], i) => {
    const s = 0.75 + rand() * 0.55
    dummy.position.set(x, 0.13 * s, z)
    dummy.scale.set(s, s * 0.8, s)
    dummy.rotation.y = rand() * Math.PI
    dummy.updateMatrix()
    vegs.setMatrixAt(i, dummy.matrix)
    vegs.setColorAt(i, tint.setHSL(0.29 + rand() * 0.05, 0.42 + rand() * 0.16, 0.3 + rand() * 0.12))
  })
  vegs.instanceMatrix.needsUpdate = true
  if (vegs.instanceColor) vegs.instanceColor.needsUpdate = true
  group.add(vegs)

  return group
}
