export function seed(now = Date.now()) {
  return { version: 1, scenario: 'normal', monitoring: true, nextId: 104,
    alarms: [
      { id: 'A103', species: '树麻雀', count: 3, confidence: 94, at: now - 120000, status: 'new', hits: 1 },
      { id: 'A102', species: '珠颈斑鸠', count: 1, confidence: 91, at: now - 840000, status: 'new', hits: 1 },
      { id: 'A101', species: '喜鹊', count: 2, confidence: 96, at: now - 3600000, status: 'handled', hits: 1 }
    ],
    commands: [{ id: 'C101', alarmId: 'A101', at: now - 3500000, duration: 3, status: 'completed', endedAt: now - 3497000, scenario: 'normal' }], activeId: null };
}
export function transition(input, action, now = Date.now()) {
  const s = structuredClone(input);
  const active = s.commands.find(x => x.id === s.activeId);
  if (action.type === 'scenario') {
    if (active) return { state: input, message: '请先停止当前任务，再切换演示场景' };
    if (!['normal', 'offline', 'timeout'].includes(action.value)) return { state: input, message: '未知场景' };
    s.scenario = action.value;
  } else if (action.type === 'monitor') { s.monitoring = !s.monitoring;
  } else if (action.type === 'alarm') {
    if (!s.monitoring) return { state: input, message: '请先恢复监测' };
    const recent = s.alarms.find(a => a.species === '树麻雀' && a.status === 'new' && now - a.at < 30000);
    if (recent) { recent.hits++; return { state: s, message: '连续检出已合并到同一条告警' }; }
    s.alarms.unshift({ id: `A${s.nextId++}`, species: '树麻雀', count: 3, confidence: 94, at: now, status: 'new', hits: 1 });
  } else if (action.type === 'ignore') {
    const alarm = s.alarms.find(a => a.id === action.id);
    if (!alarm || alarm.status !== 'new') return { state: input, message: '这条告警已经处理' };
    alarm.status = 'ignored'; alarm.handledAt = now;
  } else if (action.type === 'start') {
    if (active) return { state: input, message: '已有任务执行中，请勿重复下发' };
    if (s.scenario === 'offline') return { state: input, message: '设备离线，未下发指令。请在演示设置中恢复在线' };
    if (![3, 5, 8].includes(action.duration)) return { state: input, message: '请选择有效的执行时长' };
    const alarm = s.alarms.find(a => a.id === action.alarmId);
    if (action.alarmId && (!alarm || alarm.status !== 'new')) return { state: input, message: '关联告警已处理，请重新选择' };
    const command = { id: `C${s.nextId++}`, alarmId: alarm?.id || null, at: now, duration: action.duration, status: 'running', scenario: s.scenario };
    s.commands.unshift(command); s.activeId = command.id;
    if (alarm) alarm.status = 'processing';
  } else if (action.type === 'finish' || action.type === 'stop' || action.type === 'interrupt') {
    if (!active || (action.id && action.id !== active.id)) return { state: input };
    if (action.type === 'finish' && now - active.at < active.duration * 1000) return { state: input };
    active.status = action.type === 'stop' ? 'cancelled' : action.type === 'interrupt' ? 'unknown' : active.scenario === 'timeout' ? 'failed' : 'completed';
    active.endedAt = now;
    const alarm = s.alarms.find(a => a.id === active.alarmId);
    if (alarm) alarm.status = active.status === 'completed' ? 'handled' : 'new';
    s.activeId = null;
  }
  return { state: s };
}
export function restore(value) {
  if (!value || value.version !== 1 || !Array.isArray(value.alarms) || !Array.isArray(value.commands) || !Number.isInteger(value.nextId)) return seed();
  if (value.activeId) return transition(value, { type: 'interrupt' }).state;
  return value;
}
