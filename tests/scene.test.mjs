import test from 'node:test'
import assert from 'node:assert/strict'
import { createGround, createTree, mulberry32 } from '../scene/src/lib/orchard.js'
function fingerprint(object) {
  const entries = []
  object.traverse(node => {
    entries.push([...node.position.toArray(), ...node.scale.toArray()])
    if (node.isInstancedMesh) entries.push(Array.from(node.instanceMatrix.array))
  })
  return entries
}
test('procedural geometry is deterministic and finite', () => {
  assert.deepEqual(fingerprint(createTree(mulberry32(42))), fingerprint(createTree(mulberry32(42))))
  for (const root of [createGround(mulberry32(42)), createTree(mulberry32(17), 1.35)]) {
    root.traverse(node => {
      assert.ok([...node.position.toArray(), ...node.scale.toArray()].every(Number.isFinite))
      if (node.geometry) assert.ok(Array.from(node.geometry.attributes.position.array).every(Number.isFinite))
      if (node.isInstancedMesh) {
        assert.ok(Array.from(node.instanceMatrix.array).every(Number.isFinite))
        assert.ok(node.count > 0 && node.count <= 200)
      }
    })
  }
})
test('botanical resources are shared, then renewed after disposal', () => {
  const first = createTree(mulberry32(1))
  const second = createTree(mulberry32(2))
  assert.equal(first.children[0].geometry, second.children[0].geometry)
  assert.equal(first.children[0].material, second.children[0].material)
  const oldMaterial = first.children[0].material
  const oldTexture = oldMaterial.map
  oldTexture.dispose()
  oldMaterial.dispose()
  const next = createTree(mulberry32(1))
  assert.notEqual(next.children[0].material, oldMaterial)
  assert.notEqual(next.children[0].material.map, oldTexture)
  assert.deepEqual(fingerprint(first), fingerprint(next))
})
