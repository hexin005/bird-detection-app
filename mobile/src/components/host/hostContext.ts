// AppHost 上下文:跨主题共享的业务状态与统一语义动作。
// 所有主题布局/页面只通过 inject(hostKey) 发语义调用,不各自持有业务状态。
import { computed, reactive, ref } from 'vue'
import { useOrchard } from '../../store'
import type { Alarm, AutoRule, Command, Event, LibrarySummary, Patrol, Preferences } from '../../types'
import { askAssistant, assistantState, resetAssistant, stopAssistant } from '../../data/assistantStore'
import { applyTheme, type ThemeId } from '../../theme'

export type PageId = 'monitor' | 'alarms' | 'control' | 'records' | 'guide' | 'me' | 'themes' | 'analytics'
export type RepelMode = 'acoustic' | 'infrared' | 'both'

export const statusNames: Record<string, string> = {
  new: '待处理', processing: '执行中', handled: '已处理', ignored: '已忽略',
  pending: '待执行', running: '执行中', completed: '已完成', failed: '执行超时',
  cancelled: '已停止', unknown: '结果未知', idle: '未开始', starting: '加载模型',
  stopping: '正在停止', stopped: '已停止', ended: '检测完成', interrupted: '服务中断', error: '检测异常',
}
export const names = (v: string) => statusNames[v] || v
export const time = (v: number) => new Date(v * 1000).toLocaleString('zh-CN', { hour12: false })
export const clock = (v: number) => new Date(v * 1000).toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })
export const shortTime = (v: number) => new Date(v * 1000).toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
export const notify = (m: string) => uni.showToast({ title: m, icon: 'none', duration: 3000 })

/* 徽标映射：监控 8 态 / 告警 4 态 / 指令 6 态，全部落到 qh-badge 体系 */
const monBadge: Record<string, string> = { idle: 'neutral', starting: 'info', running: 'running', stopping: 'info', stopped: 'neutral', ended: 'ended', interrupted: 'new', error: 'failed' }
export const monClass = (st: string) => 'qh-badge qh-badge--' + (monBadge[st] || 'ended')
export const alarmClass = (st: string) => 'qh-badge qh-badge--' + st
export const badgeText = (st: string) => st === 'running' ? '正在监测' : names(st)

export const modeMeta: Record<RepelMode, { name: string; device: string; code: string; desc: string }> = {
  acoustic: { name: '声学驱鸟器 01', device: '声学驱鸟器 01', code: '东区果园 · ACOUSTIC 01', desc: '设备将以声波方式驱离鸟类，定时结束后自动停止。' },
  infrared: { name: '红外驱鸟器 02', device: '红外驱鸟器 02', code: '东区果园 · INFRARED 02', desc: '设备将以红外脉冲方式驱离鸟类，定时结束后自动停止。' },
  both: { name: '双模驱离系统', device: '声学 01 + 红外 02', code: '东区果园 · DUAL-MODE', desc: '声波与红外脉冲将同时执行，双模联动驱离鸟类，定时结束后自动停止。' },
}
export const modeCn: Record<RepelMode, string> = { acoustic: '声波', infrared: '红外', both: '双模' }
export const triggerCn: Record<string, string> = { alarm_any: '告警出现', alarm_burst: '10 分钟内 ≥3 报' }

/* R1 巡逻日志:事件按指令链(ref=C*)归组,自动化上下文事件作为组副标题 */
export type EventGroup = {
  key: string; kind: 'command' | 'detection' | 'ignored' | 'auto'
  ref: string; title: string; status?: string; automatic: boolean; autoMsg?: string
  lines: Event[]; at: number; day: string; today: boolean
}

export function createHost() {
  const store = useOrchard()
  const page = ref<PageId>('monitor')
  const modal = ref('')
  const selectedAlarm = ref<string | null>(null)
  const mode = ref<RepelMode>('both')
  const duration = ref(5)
  const recordMode = ref('videos'), archiveTask = ref(''), archiveTime = ref(0), archiveNonce = ref(0)
  const recordFilter = ref('all')
  const detailId = ref('')
  const preferences = reactive<Preferences>({ scenario: 'normal', confidence: .45, consecutive: 3, cooldown: 60 })
  const older = ref<Event[]>([]), historyEnd = ref(false)
  const fetchedAlarm = ref<Alarm | null>(null), fetchedCommand = ref<Command | null>(null)
  const theme = ref<ThemeId>('b1bit')
  const rules = ref<AutoRule[]>([])
  const patrol = ref<Patrol | null>(null)
  /** 记录页统计(一检一记):今日/累计的检测场次与发现鸟数,进入记录页时刷新 */
  const recordsSummary = ref<LibrarySummary | null>(null)
  /** 告警页物种过滤(状态提升到 host:图鉴「查看该鸟告警」等语义动作可外部设置) */
  const alarmSpecies = ref('')
  const guideSpecies = ref('')
  /** AI 助手三态:按钮(两者皆 false)/小窗(open)/整页(max);消息与草稿在 data/assistantStore,切态不丢 */
  const assistantOpen = ref(false)
  const assistantMax = ref(false)

  const s = computed(() => store.state)
  const alarm = computed(() => s.value?.alarms.find(a => a.id === detailId.value) || (fetchedAlarm.value?.id === detailId.value ? fetchedAlarm.value : null))
  const command = computed(() => s.value?.commands.find(c => c.id === detailId.value) || (fetchedCommand.value?.id === detailId.value ? fetchedCommand.value : null))
  const pending = computed(() => s.value?.alarms.filter(a => a.status === 'new') || [])
  const events = computed(() => {
    const unique = new Map<number, Event>()
    for (const e of [...older.value, ...(s.value?.events || [])]) unique.set(e.id, e)
    return [...unique.values()].sort((a, b) => b.id - a.id).filter(e => recordFilter.value === 'all' || (recordFilter.value === 'detection' ? e.kind === 'detection' : e.kind !== 'detection'))
  })
  const remaining = computed(() => store.active ? Math.min(store.active.duration, Math.max(0, Math.ceil(store.active.duration - (store.now - (store.active.started_at || store.now))))) : 0)
  const offline = computed(() => s.value?.settings.scenario === 'offline')
  const activeMode = computed(() => modeMeta[mode.value])
  const tickerText = computed(() => {
    const items = (s.value?.events || []).slice(0, 5).map(e => `${clock(e.at)} ${e.message}`)
    return items.length ? items.join('  ｜  ') + '  ｜  ' : '暂无鸟情播报 — 开始监测后自动滚动  ｜  '
  })
  const todayAlarms = ref(0)
  /** R1 巡逻日志:把事件流归组——指令链(确认→执行→回执)合并,自动化事件做组标题,检测/忽略为单行 */
  const groupedEvents = computed<EventGroup[]>(() => {
    const now = new Date()
    const today = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`
    const dayOf = (ts: number) => {
      const d = new Date(ts * 1000)
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
      return { key, label: `${d.getMonth() + 1}月${d.getDate()}日`, today: key === today }
    }
    const groups: EventGroup[] = []
    const byRef = new Map<string, EventGroup>()
    for (const e of [...events.value].sort((a, b) => a.id - b.id)) {
      const chain = e.kind !== 'detection' && e.kind !== 'ignored' && e.ref_id.startsWith('C')
      const day = dayOf(e.at)
      if (chain && byRef.has(e.ref_id)) {
        const g = byRef.get(e.ref_id)!
        g.lines.push(e)
        g.at = e.at
        g.status = e.kind
        continue
      }
      if (e.kind === 'automation' && byRef.has(e.ref_id)) {
        const g = byRef.get(e.ref_id)!
        g.autoMsg = e.message
        g.automatic = true
        g.lines.push(e)
        continue
      }
      const kind: EventGroup['kind'] = e.kind === 'detection' ? 'detection' : e.kind === 'ignored' ? 'ignored' : chain ? 'command' : 'auto'
      const g: EventGroup = {
        key: String(e.id), kind, ref: e.ref_id, automatic: false, lines: [e], at: e.at,
        day: day.label, today: day.today,
        title: kind === 'detection' ? e.message : kind === 'ignored' ? e.message : kind === 'auto' ? e.message
          : e.message.startsWith('自动策略触发') ? '自动驱离' : '人工驱离',
        status: chain ? e.kind : undefined,
      }
      if (chain) byRef.set(e.ref_id, g)
      groups.push(g)
    }
    return groups.reverse()
  })

  async function run(action: () => Promise<unknown>) {
    if (store.busy) return
    store.busy = true
    try { await action() } catch (e) { notify((e as Error).message) } finally { store.busy = false }
  }

  function nav(p: PageId) {
    if (p !== 'records') archiveTask.value = ''
    // 离开首页即收起 AI 助手;进行中的流式回答按产品约定中断并标记"已停止"(消息保留)
    if (p !== 'monitor') {
      assistantOpen.value = false
      assistantMax.value = false
      stopAssistant()
    }
    page.value = p
    uni.pageScrollTo({ scrollTop: 0, duration: 0 })
  }
  function openAlarm(a: Alarm) { fetchedAlarm.value = a; detailId.value = a.id; modal.value = 'mAlarm' }
  function replayAlarm(a: Alarm) {
    modal.value = ''; recordMode.value = 'videos'
    archiveTask.value = a.task_id; archiveTime.value = a.video_time
    archiveNonce.value++; nav('records')
  }
  function settings() { if (s.value) Object.assign(preferences, s.value.settings); modal.value = 'mSet' }
  function openScene(taskId?: unknown) {
    if (typeof window === 'undefined') return
    // 场景挂载在后端 /scene/；开发时前端在 5178，必须用后端绝对地址。
    // taskId 仅接受字符串(模板里 @click="host.openScene" 会把 MouseEvent 传进来,需忽略)
    const task = typeof taskId === 'string' && taskId ? `?task=${encodeURIComponent(taskId)}` : ''
    const base = (store.server || window.location.origin).replace(/\/$/, '')
    window.open(base + '/scene/' + task, '_blank')
  }
  function handle() { selectedAlarm.value = detailId.value; modal.value = 'mConfirm' }
  async function execute() {
    await store.command(duration.value, selectedAlarm.value, mode.value)
    modal.value = ''; selectedAlarm.value = null
    notify('已提交至模拟执行器')
  }
  async function inspectEvent(e: Event) {
    const isAlarm = e.ref_id.startsWith('A')
    if (!(isAlarm ? s.value?.alarms : s.value?.commands)?.find(x => x.id === e.ref_id)) {
      const row = await store.request<Alarm | Command>('/detail/' + (isAlarm ? 'alarms' : 'commands') + '/' + e.ref_id)
      if (isAlarm) fetchedAlarm.value = row as Alarm
      else fetchedCommand.value = row as Command
    }
    detailId.value = e.ref_id; modal.value = isAlarm ? 'mAlarm' : 'mLog'
  }
  async function loadHistory() {
    const before = Math.min(...[...older.value, ...(s.value?.events || [])].map(e => e.id))
    const result = await store.request<{ items: Event[] }>('/history?kind=events&before=' + before)
    older.value.push(...result.items); historyEnd.value = result.items.length < 100
  }
  /** 统一忽略动作(主题页语义调用;告警弹窗同款接口) */
  async function requestIgnore(id: string) {
    await store.mutate('/alarms/' + id + '/ignore')
    notify('已忽略该告警')
  }
  /** 今日检测告警数(语义=告警事件,口径见 /api/stats);供各主题 HUD/信号牌使用 */
  async function refreshToday() {
    try {
      const stats = await store.request<{ breakdown: Record<string, number> }>('/stats?range=today')
      const b = stats.breakdown
      todayAlarms.value = b.new + b.processing + b.handled + b.ignored
    } catch { todayAlarms.value = 0 }
  }
  /** 记录页统计(口径=已归档任务,鸟数=各场峰值合计,见 /api/library/summary) */
  async function loadRecordsSummary() {
    try { recordsSummary.value = await store.request<LibrarySummary>('/library/summary') } catch { recordsSummary.value = null }
  }
  /** A1 分诊台:跳过详情直接弹确认框驱离指定告警 */
  function quickRepel(id: string) { selectedAlarm.value = id; modal.value = 'mConfirm' }
  /** 图鉴详情 → 告警页按物种过滤(过滤状态在 host.alarmSpecies,BirdAlarms watch 它自动刷新) */
  function viewSpeciesAlarms(name: string) {
    alarmSpecies.value = name
    nav('alarms')
  }
  function viewSpeciesGuide(name: string) {
    guideSpecies.value = name
    nav('guide')
  }
  /** 告警详情「问 AI 怎么处理」:打开助手小窗并携带告警上下文自动提问;流式进行中则预填草稿 */
  function askAIAbout(a: Alarm) {
    const pct = Math.round((a.confidence || 0) * 100)
    const question = `刚检测到${a.species} ${a.count} 只（置信度 ${pct}%），这条告警现在该怎么处理？`
    assistantOpen.value = true
    assistantMax.value = false
    if (assistantState.busy) {
      assistantState.draft = question
      notify('AI 正在回答上一条，问题已填入输入框')
    } else {
      void askAssistant(question, { server: store.server, token: store.token })
    }
  }
  /** S1 自动哨兵:规则/巡逻的读取与变更(错误经 run→toast 呈现) */
  async function loadAutomation() {
    const [r, p] = await Promise.all([
      store.request<{ items: AutoRule[] }>('/automation/rules'),
      store.request<Patrol>('/automation/patrol'),
    ])
    rules.value = r.items
    patrol.value = p
  }
  async function saveRule(patch: Partial<AutoRule>, id?: number) {
    const row = await store.request<AutoRule>(id ? '/automation/rules/' + id : '/automation/rules', id ? 'PUT' : 'POST', id ? patch : patch as Record<string, unknown>)
    if (id) rules.value = rules.value.map(r => (r.id === id ? row : r))
    else rules.value = [...rules.value, row]
    notify(id ? '规则已更新' : '规则已添加')
  }
  async function removeRule(id: number) {
    await store.request('/automation/rules/' + id, 'DELETE')
    rules.value = rules.value.filter(r => r.id !== id)
    notify('规则已删除')
  }
  async function savePatrol(patch: Partial<Patrol>) {
    patrol.value = await store.request<Patrol>('/automation/patrol', 'PUT', patch)
    notify('巡逻计划已保存')
  }
  /** 未提交的确认弹窗在切主题时关闭并清理关联(切主题规则表) */
  function resetTransient() {
    if (modal.value === 'mConfirm') { modal.value = ''; selectedAlarm.value = null }
  }
  /** 切主题:ref + DOM 同步应用(全局缓存写在 applyTheme 内;账号权威偏好存服务端) */
  function setTheme(id: ThemeId) {
    theme.value = id
    applyTheme(id)
  }
  /** 登录/登出时的会话级清理 */
  function onTokenChange(token: string | undefined) {
    modal.value = ''; older.value = []; selectedAlarm.value = null
    fetchedAlarm.value = fetchedCommand.value = null
    assistantOpen.value = false
    assistantMax.value = false
    resetAssistant()
    if (!token) page.value = 'monitor'
  }

  const host = reactive({
    store, s, page, modal, selectedAlarm, mode, duration, detailId,
    recordMode, archiveTask, archiveTime, archiveNonce, recordFilter,
    preferences, older, historyEnd, fetchedAlarm, fetchedCommand, theme,
    alarm, command, pending, events, groupedEvents, remaining, offline, activeMode, tickerText, todayAlarms,
    rules, patrol, recordsSummary, alarmSpecies, guideSpecies, assistantOpen, assistantMax,
    run, nav, openAlarm, replayAlarm, settings, openScene, handle, execute, notify, requestIgnore, viewSpeciesAlarms, viewSpeciesGuide,
    quickRepel, loadAutomation, saveRule, removeRule, savePatrol, askAIAbout,
    inspectEvent, loadHistory, refreshToday, loadRecordsSummary, resetTransient, setTheme, onTokenChange,
  })
  return host
}

export type Host = ReturnType<typeof createHost>

import { inject } from 'vue'
export const hostKey: unique symbol = Symbol('orchard-host')
export function useHost(): Host {
  const host = inject<Host>(hostKey)
  if (!host) throw new Error('HostContext 缺失:该组件必须在 AppHost 内使用')
  return host
}
