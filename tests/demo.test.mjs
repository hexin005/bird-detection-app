import test from 'node:test';
import assert from 'node:assert/strict';
import { seed, transition, restore } from '../demo/state.js';
const now = 10000000;
const apply = (s, action, at = now) => transition(s, action, at).state;
test('alarm → command → completion keeps related records consistent', () => {
  const start = apply(seed(now), { type: 'start', alarmId: 'A103', duration: 3 });
  assert.equal(start.alarms[0].status, 'processing');
  assert.equal(start.commands[0].alarmId, 'A103');
  const early = apply(start, { type: 'finish' }, now + 2000);
  assert.equal(early.activeId, start.activeId);
  const end = apply(start, { type: 'finish', id: start.activeId }, now + 3000);
  assert.equal(end.alarms[0].status, 'handled');
  assert.equal(end.commands[0].status, 'completed');
  assert.equal(end.activeId, null);
});
test('repeated clicks never create concurrent commands', () => {
  const start = apply(seed(now), { type: 'start', duration: 3 });
  const result = transition(start, { type: 'start', duration: 3 }, now);
  assert.equal(result.state.commands.length, start.commands.length);
  assert.ok(result.message);
});
test('offline refuses commands and reconnect never replays them', () => {
  let s = apply(seed(now), { type: 'scenario', value: 'offline' });
  s = apply(s, { type: 'start', alarmId: 'A103', duration: 3 });
  assert.equal(s.commands.length, 1);
  s = apply(s, { type: 'scenario', value: 'normal' });
  assert.equal(s.activeId, null);
  assert.equal(s.commands.length, 1);
});
test('timeout returns the alarm to pending and does not claim success', () => {
  let s = apply(seed(now), { type: 'scenario', value: 'timeout' });
  s = apply(s, { type: 'start', alarmId: 'A103', duration: 3 });
  s = apply(s, { type: 'finish' }, now + 4000);
  assert.equal(s.commands[0].status, 'failed');
  assert.equal(s.alarms[0].status, 'new');
});
test('stop is terminal; a stale timer cannot complete the cancelled command', () => {
  let s = apply(seed(now), { type: 'start', alarmId: 'A103', duration: 3 });
  const oldId = s.activeId;
  s = apply(s, { type: 'stop' });
  s = apply(s, { type: 'start', alarmId: 'A102', duration: 3 }, now + 1000);
  s = apply(s, { type: 'finish', id: oldId }, now + 10000);
  assert.equal(s.commands[1].status, 'cancelled');
  assert.equal(s.commands[0].status, 'running');
});
test('continuous detections merge, while paused monitoring creates no alerts', () => {
  let s = apply(seed(now), { type: 'alarm' });
  s = apply(s, { type: 'alarm' }, now + 1000);
  assert.equal(s.alarms.length, 4);
  assert.equal(s.alarms[0].hits, 2);
  s = apply(s, { type: 'monitor' });
  s = apply(s, { type: 'alarm' }, now + 90000);
  assert.equal(s.alarms.length, 4);
});
test('refresh interrupts an active simulation without inventing completion', () => {
  const s = apply(seed(now), { type: 'start', alarmId: 'A103', duration: 3 });
  const recovered = restore(s);
  assert.equal(recovered.commands[0].status, 'unknown');
  assert.equal(recovered.activeId, null);
  assert.equal(recovered.alarms[0].status, 'new');
  assert.equal(restore(null).version, 1);
});
test('ignored alarms cannot start a command; scenario cannot change mid-command', () => {
  let s = apply(seed(now), { type: 'ignore', id: 'A103' });
  assert.ok(transition(s, { type: 'start', alarmId: 'A103', duration: 3 }).message);
  s = apply(s, { type: 'start', duration: 5 });
  assert.equal(apply(s, { type: 'scenario', value: 'offline' }).scenario, 'normal');
});
