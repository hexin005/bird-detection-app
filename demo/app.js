import { seed, transition, restore } from './state.js';
const $ = id => document.getElementById(id);
const key = 'orchard-watch-demo-v1';
let state;
try { state = restore(JSON.parse(localStorage.getItem(key))); } catch { state = seed(); }
let page = ['monitor', 'alarms', 'control', 'records'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'monitor';
let alarmFilter = 'all', recordFilter = 'all', selectedAlarm = null, duration = 3, modal = null, lastFocus = null;
let toastTimer;
const paths = {
 monitor: '<rect x="3" y="4" width="18" height="13" rx="3"/><path d="M8 21h8m-4-4v4m-5-10 3 3 4-5 3 2"/>',
 alarms: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
 control: '<path d="M9 3v8a3 3 0 0 0 6 0V3M6 9H3v5a9 9 0 0 0 18 0V9h-3M12 19v3"/><path d="M9 5h6"/>',
 records: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6m-6 4h6m-6 4h4"/>',
 settings: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor" stroke="none"/><circle cx="15" cy="17" r="3" fill="currentColor" stroke="none"/>',
 arrow: '<path d="m9 5 7 7-7 7"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>',
 bird: '<path d="M3 13c4 0 5-7 10-6l2-3 3 3 3 1-3 2c0 5-4 8-9 6l-5 3 1-5Z"/><path d="m8 11 4 2m-2 4-1 4m5-5v5"/><circle cx="15" cy="8" r=".5"/>',
 pause: '<path d="M8 5v14M16 5v14"/>', play: '<path d="m8 5 11 7-11 7Z"/>', expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
 check: '<path d="m5 12 4 4L19 6"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
 sound: '<path d="m11 5-6 4H2v6h3l6 4ZM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
 plus: '<path d="M12 5v14M5 12h14"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 refresh: '<path d="M20 11a8 8 0 1 0-2 6M20 4v7h-7"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
 wifi: '<path d="M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0m-11 4a5 5 0 0 1 8 0m-4 4h.1"/>'
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.info}</svg>`;
const labels = { new: '待处理', processing: '执行中', handled: '已处理', ignored: '已忽略', running: '执行中', completed: '已完成', failed: '执行超时', cancelled: '已停止', unknown: '结果未知' };
const badge = status => `<span class="badge ${status}">${labels[status]}</span>`;
const time = value => new Date(value).toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' });
const fullTime = value => new Date(value).toLocaleString('zh-CN', { hour12: false });
const pending = () => state.alarms.filter(a => a.status === 'new');
const active = () => state.commands.find(c => c.id === state.activeId);
const recentCommand = () => state.commands[0];
function persist() { try { localStorage.setItem(key, JSON.stringify(state)); } catch { /* Session remains usable if storage is unavailable. */ } }
persist();
function toast(message) { clearTimeout(toastTimer); $('toast').textContent = message; $('toast').classList.add('visible'); toastTimer = setTimeout(() => $('toast').classList.remove('visible'), 3600); }
function dispatch(action, message) { const result = transition(state, action); state = result.state; persist(); render(); if (result.message || message) toast(result.message || message); return !result.message; }
function go(target) { page = target; location.hash = target; render(); window.scrollTo({ top: 0, behavior: 'instant' }); }
function camera(large = false) {
 return `<div class="camera ${!state.monitoring ? 'paused' : ''} ${large ? 'large-camera' : ''}"><img src="./orchard.svg" alt="模拟果园监控插画：果树行间有三只鸟"><div class="camera-bar"><span class="camera-label"><span class="tiny-dot"></span> ${state.monitoring ? '监测中' : '监测暂停'}</span><span>场景插画 · 模拟识别</span></div>${state.monitoring ? '<div class="detection-box"></div><div class="detection-box second"></div><div class="detection-box third"></div>' : '<div class="paused-label">演示监测已暂停</div>'}<div class="camera-bottom"><div><strong>东区果园 · CAM 01</strong><small>本地交互演示 / 无实时视频接入</small></div><div class="camera-tools"><button data-action="pause" aria-label="${state.monitoring ? '暂停监测' : '恢复监测'}">${icon(state.monitoring ? 'pause' : 'play')}</button><button data-action="expand" aria-label="放大监控画面">${icon('expand')}</button></div></div></div>`;
}
function title(name, sub, right = '') { return `<div class="page-title"><div><h2>${name}</h2><p class="subtitle">${sub}</p></div>${right}</div>`; }
function deviceStatus() { return `<span class="online ${state.scenario === 'offline' ? 'offline' : ''}"><span class="tiny-dot"></span>${state.scenario === 'offline' ? '设备离线' : '设备在线'}</span>`; }
function alarmCard(a, compact = false) {
 if (compact) return `<button class="alert-card" data-action="alarm-detail" data-id="${a.id}"><div class="alert-top"><span class="bird-icon">${icon('bird')}</span><div class="alert-text"><h4>发现 ${a.count} 只${a.species}</h4><p>东区果园 · 01 号监控点</p></div>${badge(a.status)}</div><div class="alert-bottom"><span>${time(a.at)} · 置信度 ${a.confidence}%</span><strong>查看并处理 ${icon('arrow')}</strong></div></button>`;
 return `<button class="list-card" data-action="alarm-detail" data-id="${a.id}"><div class="alert-top"><img class="thumbnail" src="./orchard.svg" alt="模拟告警画面"><div class="alert-text"><h4>${a.species} <span class="count-label">${a.count} 只</span></h4><p>东区果园 · CAM 01</p></div>${badge(a.status)}</div><div class="card-footer"><span>${time(a.at)} · 置信度 ${a.confidence}%${a.hits > 1 ? ` · 已合并 ${a.hits} 次检出` : ''}</span><span>${a.id} ${icon('arrow')}</span></div></button>`;
}
function monitorPage() {
 const next = pending()[0];
 return title('果园，尽在掌握', '今日巡护，从这里开始。', `<span class="status-pill"><span class="tiny-dot"></span>${state.monitoring ? '正在守护' : '监测暂停'}</span>`) + camera() + `<div class="metrics"><div class="metric"><small>当前检测</small><div>${state.monitoring ? '3' : '—'}<span>只鸟</span></div><em>${state.monitoring ? '树麻雀 · 模拟结果' : '等待恢复监测'}</em></div><div class="metric"><small>待处理告警</small><div>${pending().length}<span>条</span></div><em>${pending().length ? '等待你的判断' : '全部处理完毕'}</em></div><div class="metric"><small>模拟执行</small><div>${state.commands.filter(c => c.status === 'completed').length}<span>次</span></div><em>已收到完成回执</em></div></div><div class="section-heading"><h3>需要你的关注 ${pending().length ? '· ' + pending().length : ''}</h3><button class="text-button" data-action="go" data-page="alarms">全部告警 ${icon('arrow')}</button></div>${next ? alarmCard(next, true) : '<div class="callout">当前没有待处理告警，果园状态已检查。</div>'}<button class="device-strip full" data-action="go" data-page="control">${icon('sound')}<div style="text-align:left"><strong>声学驱鸟器 01</strong><small>模拟设备 · 人工确认后执行</small></div>${deviceStatus()}${icon('arrow')}</button><div class="screen-foot">每一次发现，都值得认真对待</div>`;
}
function alarmsPage() {
 const list = state.alarms.filter(a => alarmFilter === 'all' || (alarmFilter === 'done' ? ['handled', 'ignored'].includes(a.status) : a.status === alarmFilter));
 return title('告警中心', `${pending().length} 条待处理 · 所有事件均为模拟`, `<button class="icon-button" data-action="new-alarm" aria-label="模拟新增告警">${icon('plus')}</button>`) + `<div class="tabs">${[['all', '全部'], ['new', '待处理'], ['done', '已处理']].map(([value, label]) => `<button class="tab ${alarmFilter === value ? 'selected' : ''}" data-action="alarm-filter" data-value="${value}">${label}</button>`).join('')}</div>${list.length ? list.map(a => alarmCard(a)).join('') : empty('这里暂时没有告警', '新告警会在识别到持续出现的鸟类时显示。')}<p class="muted-note">连续检出会合并为同一事件。请结合画面判断是否需要处理。</p>`;
}
function empty(heading, description) { return `<div class="empty">${icon('check')}<h4>${heading}</h4><p>${description}</p></div>`; }
function controlPage() {
 const command = active(), last = recentCommand(), alarm = state.alarms.find(a => a.id === selectedAlarm);
 if (alarm && alarm.status !== 'new' && !command) selectedAlarm = null;
 return title('远程控制', '每一次行动，都有明确的回应。', '<span class="demo-tag">模拟执行</span>') + `<div class="control-hero"><span class="hero-status">${deviceStatus()}</span><div class="device-orbit ${command ? 'running-ring' : ''}"><div class="device-drawing"><div class="speaker"></div><span class="device-led"></span></div></div><div class="device-name">声学驱鸟器 01</div><div class="device-model">东区果园 · ACOUSTIC 01</div></div>${selectedAlarm && alarm ? `<div class="linked-alert"><span>关联告警：${alarm.species} · ${alarm.id}</span><button data-action="unlink" ${command ? 'disabled' : ''}>取消关联</button></div>` : ''}<div class="form-card"><div class="label-row">单次执行时长<span>定时结束 · 不连续运行</span></div><div class="durations">${[3, 5, 8].map(d => `<button class="duration ${d === duration ? 'selected' : ''}" data-action="duration" data-value="${d}" ${command ? 'disabled' : ''}>${d} 秒</button>`).join('')}</div></div>${command ? `<div class="command-panel"><h4>正在模拟执行 <span id="countdown"></span></h4><p>${command.id} · 已下发至声学驱鸟器 01</p><div class="progress-track"><div class="progress-fill" id="progress"></div></div><button class="danger full" data-action="stop">${icon('stop')}停止本次执行</button></div>` : `<button class="primary full" style="margin-top:18px" data-action="confirm-command" ${state.scenario === 'offline' ? 'disabled' : ''}>${icon('sound')}${state.scenario === 'offline' ? '设备离线，无法执行' : '执行一次驱离'}</button>${last && Date.now() - (last.endedAt || 0) < 300000 ? `<button class="command-panel ${last.status === 'failed' ? 'failed' : ''} full" data-action="record-detail" data-id="${last.id}" style="text-align:left"><h4>${labels[last.status]} ${icon(last.status === 'completed' ? 'check' : 'info')}</h4><p>${commandMessage(last)} · 查看记录 →</p></button>` : ''}`}<p class="muted-note">本设备为模拟执行器，不会产生声音或控制真实硬件。执行完成不代表实际驱鸟成功。</p><button class="text-button" data-action="settings">${icon('settings')} 切换离线 / 超时演示场景</button>`;
}
function commandMessage(c) { return c.status === 'completed' ? '已收到模拟完成回执' : c.status === 'failed' ? '未在规定时间内收到完成回执' : c.status === 'cancelled' ? '已收到模拟停止回执' : c.status === 'unknown' ? '演示被刷新中断，请重新确认' : '正在等待模拟设备回执'; }
function recordsPage() {
 let items = [...state.commands.map(c => ({ ...c, kind: 'command' })), ...state.alarms.map(a => ({ ...a, kind: 'alarm' }))].filter(x => recordFilter === 'all' || x.kind === recordFilter).sort((a, b) => b.at - a.at);
 return title('巡护记录', '从发现到处理，每一步都留有记录。') + `<div class="record-summary"><div><strong>${state.alarms.length}</strong><small>检测事件</small></div><div><strong>${state.commands.length}</strong><small>模拟指令</small></div><div><strong>${state.commands.filter(c => c.status === 'completed').length}</strong><small>执行完成</small></div></div><div class="tabs">${[['all', '全部记录'], ['alarm', '检测事件'], ['command', '驱离操作']].map(([value, label]) => `<button class="tab ${recordFilter === value ? 'selected' : ''}" data-action="record-filter" data-value="${value}">${label}</button>`).join('')}</div>${items.map(x => x.kind === 'alarm' ? alarmCard(x) : `<button class="list-card" data-action="record-detail" data-id="${x.id}"><div class="alert-top"><span class="record-icon ${x.status}">${icon(x.status === 'completed' ? 'check' : x.status === 'running' ? 'sound' : 'info')}</span><div class="alert-text"><h4>声学驱离 · ${x.duration} 秒</h4><p>${x.alarmId ? '关联告警 ' + x.alarmId : '手动发起'} · 模拟执行</p></div>${badge(x.status)}</div><div class="card-footer"><span>${time(x.at)} · 声学驱鸟器 01</span><span>${x.id} ${icon('arrow')}</span></div></button>`).join('')}<div class="screen-foot">仅保存于当前浏览器 · 可在演示设置中重置</div>`;
}
function render() {
 $('settings-button').innerHTML = icon('settings');
 $('app').innerHTML = `<div class="page">${({ monitor: monitorPage, alarms: alarmsPage, control: controlPage, records: recordsPage })[page]()}</div>`;
 $('nav').innerHTML = [['monitor','监控'],['alarms','告警'],['control','控制'],['records','记录']].map(([id,label]) => `<button class="nav-item ${page === id ? 'active' : ''}" data-action="go" data-page="${id}" ${page === id ? 'aria-current="page"' : ''}><span class="nav-icon">${icon(id)}</span>${label}${id === 'alarms' && pending().length ? `<span class="nav-count">${pending().length}</span>` : ''}</button>`).join('');
 document.querySelectorAll('[data-step]').forEach(el => el.classList.toggle('current', el.dataset.step === page));
 if (modal) renderModal();
 updateProgress();
}
function openModal(type, id) { if (!modal) lastFocus = document.activeElement; modal = { type, id }; renderModal(); document.querySelector('.sheet .icon-button')?.focus(); }
function closeModal() { modal = null; $('overlay').innerHTML = ''; document.body.style.overflow = ''; document.querySelector('.workspace').inert = false; if (lastFocus?.isConnected) lastFocus.focus(); else $('settings-button').focus(); }
function renderModal() {
 let heading = '', body = '';
 if (modal.type === 'alarm') {
   const a = state.alarms.find(a => a.id === modal.id); if (!a) return closeModal();
   const commands = state.commands.filter(c => c.alarmId === a.id);
   heading = '告警详情';
   body = `<div class="camera" style="height:190px"><img src="./orchard.svg" alt="模拟告警抓拍插画"><div class="camera-bar"><span class="camera-label">模拟抓拍</span>${badge(a.status)}</div></div><div class="detail-grid"><div><small>识别鸟类</small><strong>${a.species} · ${a.count} 只</strong></div><div><small>模型置信度（模拟）</small><strong>${a.confidence}%</strong></div><div><small>发现时间</small><strong>${time(a.at)}</strong></div><div><small>监控点位</small><strong>东区果园 · CAM 01</strong></div></div><div class="callout">建议先核对画面，再决定是否驱离。检测到鸟类不直接代表发生鸟害。</div>${commands.length ? `<div class="section-heading"><h3>关联操作</h3></div>${commands.map(c => `<button class="setting-option" data-action="record-detail" data-id="${c.id}">${icon('sound')}<div><strong>${c.id} · ${labels[c.status]}</strong><small>${commandMessage(c)}</small></div></button>`).join('')}` : ''}${a.status === 'new' ? `<div class="button-row"><button class="secondary" data-action="ignore" data-id="${a.id}">忽略这次告警</button><button class="primary" data-action="handle" data-id="${a.id}">确认并去驱离 ${icon('arrow')}</button></div>` : `<p class="sheet-footer">${a.id} · ${labels[a.status]}</p>`}`;
 } else if (modal.type === 'confirm') {
   heading = '确认本次驱离';
   const a = state.alarms.find(a => a.id === selectedAlarm);
   body = `<p>将向东区果园的模拟声学驱鸟器下达一次执行指令。</p><div class="detail-grid"><div><small>执行方式</small><strong>声学驱离 · 模拟</strong></div><div><small>执行时长</small><strong>${duration} 秒</strong></div><div><small>关联事件</small><strong>${a ? a.id + ' · ' + a.species : '手动操作'}</strong></div><div><small>设备状态</small><strong>${state.scenario === 'offline' ? '离线' : '在线'}</strong></div></div><div class="callout">执行过程中可以随时停止。模拟完成后，记录将自动保存。</div><div class="button-row"><button class="secondary" data-action="close">再看一下</button><button class="primary" data-action="start">确认执行</button></div>`;
 } else if (modal.type === 'record') {
   const c = state.commands.find(c => c.id === modal.id); if (!c) return closeModal();
   const a = state.alarms.find(a => a.id === c.alarmId);
   heading = '操作记录';
   body = `${badge(c.status)}<div class="timeline">${a ? `<div class="timeline-item"><span class="tiny-dot"></span><div><strong>发现${a.species} · ${a.count} 只</strong><p>${time(a.at)} · 告警 ${a.id}</p></div></div>` : ''}<div class="timeline-item"><span class="tiny-dot"></span><div><strong>人工确认并下发指令</strong><p>${time(c.at)} · ${c.id} · ${c.duration} 秒</p></div></div><div class="timeline-item"><span class="tiny-dot"></span><div><strong>${labels[c.status]}</strong><p>${commandMessage(c)}</p>${c.endedAt ? `<p>${fullTime(c.endedAt)}</p>` : ''}</div></div></div><div class="callout ${c.status === 'failed' ? 'warning' : ''}">${c.status === 'completed' ? '此记录只证明模拟指令流程完成。没有真实硬件和后续检测证据，无法判断驱鸟效果。' : c.status === 'failed' || c.status === 'unknown' ? '没有收到可确认的完成回执，关联告警保留为待处理。恢复后不会自动重新执行。' : c.status === 'cancelled' ? '本次模拟任务已停止，关联告警保留为待处理。' : '指令正在模拟执行中，可前往控制页停止。'}</div>${a ? `<button class="secondary full" style="margin-top:18px" data-action="alarm-detail" data-id="${a.id}">查看关联告警 ${icon('arrow')}</button>` : ''}`;
 } else if (modal.type === 'settings') {
   heading = '演示设置';
   body = `<p>切换场景，体验不同情况下的操作反馈。所有数据均为本地模拟。</p><div class="settings-label">设备响应场景</div>${[['normal', '正常执行', '设备在线，按时返回完成回执'], ['offline', '设备离线', '禁用执行入口，不下发任何指令'], ['timeout', '执行超时', '可以下发，但最终未收到完成回执']].map(([value, name, desc]) => `<button class="setting-option ${state.scenario === value ? 'selected' : ''}" data-action="scenario" data-value="${value}" ${active() ? 'disabled' : ''}><span class="radio"></span><div><strong>${name}</strong><small>${desc}</small></div></button>`).join('')}<div class="settings-label">演示数据</div><button class="secondary full" data-action="new-alarm">${icon('plus')}模拟新增一条告警</button><p class="muted-note">30 秒内连续添加会合并，方便观察告警去重。当前监测${state.monitoring ? '已开启' : '已暂停'}。</p><button class="text-button" data-action="reset-confirm">${icon('refresh')}重置所有演示数据</button>`;
 } else if (modal.type === 'reset') {
   heading = '重新开始演示'; body = '<p>将清空本次演示操作，恢复初始告警与设备状态。仅影响这个浏览器中的模拟数据。</p><div class="button-row"><button class="secondary" data-action="close">保留记录</button><button class="primary" data-action="reset">确认重置</button></div>';
 } else if (modal.type === 'camera') { heading = '东区果园 · CAM 01'; body = camera(true) + '<p class="muted-note">当前为静态场景插画与预设检测框。此 Demo 用于体验界面流程，未运行真实视频识别。</p>'; }
 $('overlay').innerHTML = `<div class="overlay-backdrop"><section class="sheet" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="sheet-head"><h3 id="modal-title">${heading}</h3><button class="icon-button" data-action="close" aria-label="关闭弹窗">${icon('close')}</button></div>${body}</section></div>`;
 document.body.style.overflow = 'hidden'; document.querySelector('.workspace').inert = true;
}
function updateProgress() { const c = active(); if (!c) return; const elapsed = Date.now() - c.at, percent = Math.min(100, elapsed / (c.duration * 1000) * 100); if ($('progress')) $('progress').style.width = `${percent}%`; if ($('countdown')) $('countdown').textContent = `· ${Math.max(0, Math.ceil(c.duration - elapsed / 1000))}s`; }
document.addEventListener('click', event => {
 const button = event.target.closest('[data-action]');
 if (!button) { if (event.target.classList.contains('overlay-backdrop')) closeModal(); return; }
 const { action, id, value } = button.dataset;
 if (action === 'go') go(button.dataset.page);
 else if (action === 'settings') openModal('settings');
 else if (action === 'close') closeModal();
 else if (action === 'expand') openModal('camera');
 else if (action === 'pause') dispatch({ type: 'monitor' }, state.monitoring ? '演示监测已暂停' : '演示监测已恢复');
 else if (action === 'alarm-detail') openModal('alarm', id);
 else if (action === 'record-detail') openModal('record', id);
 else if (action === 'alarm-filter') { alarmFilter = value; render(); }
 else if (action === 'record-filter') { recordFilter = value; render(); }
 else if (action === 'duration') { duration = Number(value); render(); }
 else if (action === 'ignore') { closeModal(); dispatch({ type: 'ignore', id }, '已忽略，可在记录中回看'); }
 else if (action === 'handle') { selectedAlarm = id; closeModal(); go('control'); }
 else if (action === 'unlink') { selectedAlarm = null; render(); }
 else if (action === 'confirm-command') openModal('confirm');
 else if (action === 'start') { closeModal(); dispatch({ type: 'start', duration, alarmId: selectedAlarm }, '模拟指令已下发'); }
 else if (action === 'stop') dispatch({ type: 'stop' }, '已停止本次模拟执行');
 else if (action === 'scenario') { dispatch({ type: 'scenario', value }); document.querySelector(`[data-action="scenario"][data-value="${value}"]`)?.focus(); }
 else if (action === 'new-alarm') { dispatch({ type: 'alarm' }, '已生成模拟告警'); }
 else if (action === 'reset-confirm') openModal('reset');
 else if (action === 'reset') { closeModal(); state = seed(); selectedAlarm = null; alarmFilter = recordFilter = 'all'; duration = 3; persist(); go('monitor'); toast('演示数据已重置'); }
});
document.addEventListener('keydown', event => {
 if (!modal) return;
 if (event.key === 'Escape') closeModal();
 if (event.key === 'Tab') {
   const items = [...document.querySelectorAll('.sheet button:not(:disabled), .sheet a[href]')];
   if (!items.length) return;
   const first = items[0], last = items.at(-1);
   if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
   else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
 }
});
window.addEventListener('hashchange', () => { const next = location.hash.slice(1); if (['monitor','alarms','control','records'].includes(next)) { page = next; render(); } });
setInterval(() => {
 const c = active();
 if (c && Date.now() - c.at >= c.duration * 1000) dispatch({ type: 'finish', id: c.id }, c.scenario === 'timeout' ? '执行超时，告警仍待处理' : '模拟执行完成，记录已保存');
 else updateProgress();
}, 200);
render();
