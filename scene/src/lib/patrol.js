/**
 * 巡逻路点图(布局图 v1 坐标,与 terrain.js 的 FARM 常量一致)。
 * 三层:果园内环(o*)、环园路(r*)、麦田环(w*)、菜地环(v*),经大门与两条支路连通。
 * 巡逻 = 各自区域内随机走相邻点;响应 = BFS 最短路经环园路 → 大门 → 集结点。
 */

export const NODES = {
  // 果园内环(围栏 ±16 内侧,贴耕作带边缘)
  o1: { x: -12, z: -8, r: 'orchard' },
  o2: { x: 0, z: -10.5, r: 'orchard' },
  o3: { x: 12, z: -8, r: 'orchard' },
  o4: { x: 12.5, z: 4, r: 'orchard' },
  o5: { x: 7, z: 11, r: 'orchard' },
  o6: { x: 0, z: 13.2, r: 'orchard' },
  o7: { x: -7, z: 11, r: 'orchard' },
  o8: { x: -12.5, z: 4, r: 'orchard' },
  gate: { x: 0, z: 15.6, r: 'orchard' },
  // 大门外 + 环园路(±20.5)
  gOut: { x: 0, z: 18.4, r: 'road' },
  rS: { x: 0, z: 20.5, r: 'road' },
  rSW: { x: -20.5, z: 20.5, r: 'road' },
  rW: { x: -20.5, z: 0, r: 'road' },
  rNW: { x: -20.5, z: -20.5, r: 'road' },
  rN: { x: 0, z: -20.5, r: 'road' },
  rNE: { x: 20.5, z: -20.5, r: 'road' },
  rE: { x: 20.5, z: 0, r: 'road' },
  rSE: { x: 20.5, z: 20.5, r: 'road' },
  // 麦田环(田埂,南缘接西北支路)
  wIn: { x: -24.6, z: -20.5, r: 'road' },
  w1: { x: -27, z: -20.8, r: 'wheat' },
  w2: { x: -35, z: -20.8, r: 'wheat' },
  w3: { x: -43.5, z: -21.5, r: 'wheat' },
  w4: { x: -43.5, z: -42, r: 'wheat' },
  w5: { x: -35, z: -43, r: 'wheat' },
  w6: { x: -26.5, z: -42, r: 'wheat' },
  w7: { x: -25.5, z: -31, r: 'wheat' },
  // 菜地环(畦沟,西缘接东支路)
  vIn: { x: 24.3, z: 0, r: 'road' },
  v1: { x: 27.5, z: 0, r: 'veg' },
  v2: { x: 27.5, z: -10.5, r: 'veg' },
  v3: { x: 36, z: -12, r: 'veg' },
  v4: { x: 44.5, z: -10.5, r: 'veg' },
  v5: { x: 44.5, z: 10.5, r: 'veg' },
  v6: { x: 36, z: 12, r: 'veg' },
  v7: { x: 27.5, z: 10.5, r: 'veg' },
}

export const LINKS = [
  ['o1', 'o2'], ['o2', 'o3'], ['o3', 'o4'], ['o4', 'o5'], ['o5', 'o6'], ['o6', 'o7'], ['o7', 'o8'], ['o8', 'o1'],
  ['o6', 'gate'], ['gate', 'gOut'], ['gOut', 'rS'],
  ['rS', 'rSE'], ['rSE', 'rE'], ['rE', 'rNE'], ['rNE', 'rN'], ['rN', 'rNW'], ['rNW', 'rW'], ['rW', 'rSW'], ['rSW', 'rS'],
  ['rNW', 'wIn'], ['wIn', 'w1'], ['w1', 'w2'], ['w2', 'w3'], ['w3', 'w4'], ['w4', 'w5'], ['w5', 'w6'], ['w6', 'w7'], ['w7', 'w1'],
  ['rE', 'vIn'], ['vIn', 'v1'], ['v1', 'v2'], ['v2', 'v3'], ['v3', 'v4'], ['v4', 'v5'], ['v5', 'v6'], ['v6', 'v7'], ['v7', 'v1'],
]

/* 邻接表 */
const ADJ = {}
for (const id of Object.keys(NODES)) ADJ[id] = []
for (const [a, b] of LINKS) {
  ADJ[a].push(b)
  ADJ[b].push(a)
}

/* 三人驻点:甲(巡园)=果园 乙(红外)=麦田 丙(声波)=菜地 */
export const STATIONS = { inspect: 'o3', infrared: 'w2', acoustic: 'v1' }
export const STATION_LABEL = { orchard: '果园', wheat: '麦田', veg: '菜地' }

/** 离 (x,z) 最近的节点 id(可限定区域) */
export function nearestNode(x, z, region) {
  let best = null, bd = Infinity
  for (const [id, n] of Object.entries(NODES)) {
    if (region && n.r !== region) continue
    const d = (n.x - x) ** 2 + (n.z - z) ** 2
    if (d < bd) { bd = d; best = id }
  }
  return best
}

/** BFS 最短路(hops;图边短且均匀,跳数≈距离) */
export function bfsPath(fromId, toId) {
  if (fromId === toId) return [fromId]
  const prev = { [fromId]: null }
  const queue = [fromId]
  while (queue.length) {
    const cur = queue.shift()
    for (const next of ADJ[cur]) {
      if (next in prev) continue
      prev[next] = cur
      if (next === toId) {
        const path = [toId]
        let p = cur
        while (p !== null) { path.unshift(p); p = prev[p] }
        return path
      }
      queue.push(next)
    }
  }
  return [fromId]
}

/** 节点路径 → 世界坐标点列 */
export function nodePoints(ids) {
  return ids.map((id) => {
    const n = NODES[id]
    return { x: n.x, z: n.z }
  })
}

/** 某节点的相邻点(可排除来路,避免巡逻来回抖动) */
export function neighborsOf(id, exclude) {
  const list = ADJ[id].filter((n) => n !== exclude)
  return list.length ? list : [exclude]
}
