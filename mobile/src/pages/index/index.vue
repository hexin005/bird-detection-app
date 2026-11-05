<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useOrchard } from '../../store'
import VideoWorkspace from '../../components/VideoWorkspace.vue'
import VideoLibrary from '../../components/VideoLibrary.vue'
import BirdAlarms from '../../components/BirdAlarms.vue'
import type { Alarm, Command, Event, Preferences } from '../../types'

const store = useOrchard()
const page = ref('monitor'), modal = ref(''), selectedAlarm = ref<string | null>(null)
const recordMode = ref('videos'), archiveTask = ref(''), archiveTime = ref(0), archiveNonce = ref(0)
const detailId = ref(''), recordFilter = ref('all'), duration = ref(3)
const credentials = reactive({ server: store.server, username: 'orchard', password: '' })
const preferences = reactive<Preferences>({ scenario: 'normal', confidence: .35, consecutive: 2, cooldown: 20 })
const older = ref<Event[]>([]), historyEnd = ref(false)
const fetchedAlarm = ref<Alarm | null>(null), fetchedCommand = ref<Command | null>(null)
const s = computed(() => store.state)
const alarm = computed(() => s.value?.alarms.find(a => a.id === detailId.value) || (fetchedAlarm.value?.id === detailId.value ? fetchedAlarm.value : null))
const command = computed(() => s.value?.commands.find(c => c.id === detailId.value) || (fetchedCommand.value?.id === detailId.value ? fetchedCommand.value : null))
const pending = computed(() => s.value?.alarms.filter(a => a.status === 'new') || [])
const events = computed(() => {
  const unique = new Map<number, Event>()
  for (const e of [...older.value, ...(s.value?.events || [])]) unique.set(e.id, e)
  return [...unique.values()].sort((a,b) => b.id - a.id).filter(e => recordFilter.value === 'all' || (recordFilter.value === 'detection' ? e.kind === 'detection' : e.kind !== 'detection'))
})
const running = computed(() => ['starting', 'running', 'stopping'].includes(s.value?.monitor.status || ''))
const remaining = computed(() => store.active ? Math.min(store.active.duration, Math.max(0, Math.ceil(store.active.duration - (store.now - (store.active.started_at || store.now))))) : 0)
const statusNames: Record<string,string> = { new:'待处理', processing:'执行中', handled:'已处理', ignored:'已忽略', pending:'待执行', running:'执行中', completed:'已完成', failed:'执行超时', cancelled:'已停止', unknown:'结果未知', idle:'未开始', starting:'加载模型', stopping:'正在停止', stopped:'已停止', ended:'检测完成', interrupted:'服务中断', error:'检测异常' }
const names = (value: string) => statusNames[value] || value
const time = (value: number) => new Date(value * 1000).toLocaleString('zh-CN', { hour12:false })
const clock = (value: number) => new Date(value * 1000).toLocaleTimeString('zh-CN', { hour12:false, hour:'2-digit', minute:'2-digit' })
const notify = (message: string) => uni.showToast({ title: message, icon:'none', duration:3000 })
async function run(action: () => Promise<unknown>) {
  if (store.busy) return
  store.busy = true
  try { await action() } catch(e) { notify((e as Error).message) } finally { store.busy = false }
}
function go(value: string) { if(value!=='records')archiveTask.value='';page.value = value; uni.pageScrollTo({ scrollTop:0, duration:0 }) }
function openAlarm(a: Alarm) { fetchedAlarm.value = a; detailId.value = a.id; modal.value = 'alarm' }
function replayAlarm(a: Alarm) { modal.value=''; recordMode.value='videos'; archiveTask.value=a.task_id; archiveTime.value=a.video_time; archiveNonce.value++;go('records') }
function settings() { if (s.value) Object.assign(preferences, s.value.settings); modal.value = 'settings' }
function handle() { selectedAlarm.value = detailId.value; modal.value = ''; go('control') }
async function execute() { await store.command(duration.value, selectedAlarm.value); modal.value = ''; selectedAlarm.value = null; notify('已提交至模拟执行器') }
async function inspectEvent(e: Event) {
  const isAlarm = e.ref_id.startsWith('A')
  if (!(isAlarm ? s.value?.alarms : s.value?.commands)?.find(x => x.id === e.ref_id)) {
    const row = await store.request<Alarm | Command>('/detail/' + (isAlarm ? 'alarms' : 'commands') + '/' + e.ref_id)
    if (isAlarm) fetchedAlarm.value = row as Alarm
    else fetchedCommand.value = row as Command
  }
  detailId.value = e.ref_id; modal.value = isAlarm ? 'alarm' : 'record'
}
async function loadHistory() {
  const before = Math.min(...[...older.value, ...(s.value?.events || [])].map(e=>e.id))
  const result = await store.request<{items:Event[]}>('/history?kind=events&before=' + before)
  older.value.push(...result.items); historyEnd.value = result.items.length < 100
}
watch(() => store.token, () => { modal.value = ''; older.value = []; selectedAlarm.value = null; fetchedAlarm.value = fetchedCommand.value = null })
watch(() => s.value?.alarms.find(a => a.id === selectedAlarm.value)?.status, status => { if (status && status !== 'new') selectedAlarm.value = null })
</script>

<template>
  <view class="workspace">
    <view class="intro">
      <view class="brand"><text class="brand-mark">青</text><view><text class="brand-name">青禾</text><text class="brand-en">ORCHARD WATCH</text></view></view>
      <text class="eyebrow">一座果园 · 一份安心</text>
      <text class="intro-title">{{ '看见每一次来访，\n守护每一份收获。' }}</text>
      <text class="intro-description">{{ '让识别有依据，让行动有回应。\n从视频识别到结果归档。' }}</text>
      <view class="steps"><view v-for="(step,i) in ['发现 · 查看真实识别','判断 · 核对告警画面','行动 · 确认模拟驱离','回看 · 追溯操作记录']" :key="step" class="step"><text class="step-number">0{{ i + 1 }}</text><text>{{ step }}</text></view></view>
      <text class="intro-foot">MVP · 真实模型 / 预录视频 / 模拟设备</text>
    </view>

    <view class="phone">
      <view class="header"><view><text class="header-name">● 青禾示范果园 <text class="tag">MVP</text></text><text class="small">东区 · 01 号监控点</text></view><button v-if="store.token" class="icon-button" aria-label="设置" @click="settings">☷</button></view>

      <view v-if="!store.token" class="page login">
        <text class="eyebrow">欢迎回来</text><text class="title">开启今天的巡护</text><text class="subtitle">连接你的果园监测服务</text>
        <view class="login-art"><text>◉</text><text>青禾 · 看见，才能守护</text></view>
        <text class="field-label">服务地址</text><input v-model="credentials.server" class="input" placeholder="http://电脑局域网IP:8008" aria-label="服务地址" />
        <text class="field-label">账号</text><input v-model="credentials.username" class="input" placeholder="请输入账号" aria-label="账号" />
        <text class="field-label">密码</text><input v-model="credentials.password" class="input" password placeholder="请输入启动时生成的密码" aria-label="密码" />
        <button class="primary full" :disabled="store.busy || !credentials.password" @click="run(async () => { await store.login(credentials.server, credentials.username, credentials.password); credentials.password = '' })">{{ store.busy ? '正在连接…' : '登录并进入果园' }}</button>
        <text class="note">账号由本地服务创建。手机访问时，填写电脑的局域网地址，并保持网络互通。</text>
      </view>
      <template v-else>
        <view class="connection" :class="{warning:store.connection !== '实时连接'}"><text>{{ store.connection }}</text><text>{{ s ? '数据来自果园服务' : '等待同步' }}</text></view>
        <view v-if="store.error" class="error-banner"><text>{{ store.error }}</text><button class="text-button" @click="store.sync">重新连接</button></view>
        <view v-if="!s" class="empty page"><text>正在获取果园状态…</text><text class="note">请确认服务地址正确，后端服务已启动。</text><button class="secondary" @click="settings">连接设置</button></view>
        <view v-else class="page">
          <template v-if="page === 'monitor'">
            <view class="title-row"><view><text class="title">果园，尽在掌握</text><text class="subtitle">今日巡护，从这里开始。</text></view><text class="badge" :class="s.monitor.status">{{ s.monitor.status === 'running' ? '正在监测' : names(s.monitor.status) }}</text></view>
            <VideoWorkspace />
            <view class="metrics"><view><text>待处理告警</text><text class="metric-value">{{ s.counts.pending }}<text class="metric-unit">条</text></text></view><view><text>检测事件</text><text class="metric-value">{{ s.counts.total }}<text class="metric-unit">条</text></text></view><view><text>模拟执行完成</text><text class="metric-value">{{ s.counts.completed }}<text class="metric-unit">次</text></text></view></view>
            <view class="section-heading"><text>需要你的关注</text><button class="text-button" @click="go('alarms')">全部告警 ›</button></view>
            <view v-if="pending.length" class="alert-card" @click="openAlarm(pending[0])"><view class="row"><text class="bird-symbol">♧</text><view class="grow"><text class="card-title">发现 {{ pending[0].count }} 只{{ pending[0].species }}</text><text class="small">东区果园 · CAM 01</text></view><text class="badge new">待处理</text></view><view class="card-footer"><text>{{ clock(pending[0].at) }} · {{ (pending[0].confidence * 100).toFixed(0) }}%</text><text>查看并处理 ›</text></view></view>
            <view v-else class="empty compact"><text>暂无待处理告警</text><text class="small">监测开始后，连续检出将形成告警。</text></view>
            <view class="device-strip" @click="go('control')"><text class="bird-symbol">◉</text><view class="grow"><text class="card-title">声学驱鸟器 01</text><text class="small">模拟设备 · 人工确认后执行</text></view><text :class="s.settings.scenario === 'offline' ? 'offline' : 'online'">● {{ s.settings.scenario === 'offline' ? '离线' : '在线' }}</text></view>
            <text class="note">离开首页后，服务器继续分析；完成后在记录中回看。</text>
          </template>

          <template v-if="page === 'alarms'">
            <BirdAlarms @open="openAlarm" />
          </template>

          <template v-if="page === 'control'">
            <view class="title-row"><view><text class="title">远程控制</text><text class="subtitle">每一次行动，都有明确的回应。</text></view><text class="tag">模拟执行</text></view>
            <view class="control-hero"><text class="device-state">● {{ s.settings.scenario === 'offline' ? '设备离线' : '设备在线' }}</text><view class="device-orbit" :class="{pulsing:store.active}"><view class="device-body"><view class="speaker"/><text class="device-dot">●</text></view></view><text class="card-title">声学驱鸟器 01</text><text class="small">东区果园 · ACOUSTIC 01</text></view>
            <view v-if="selectedAlarm" class="linked">关联告警 {{ selectedAlarm }}<button class="text-button" @click="selectedAlarm = null">取消关联</button></view>
            <view class="form-card"><view class="section-heading"><text>单次执行时长</text><text class="small">定时结束 · 不连续运行</text></view><view class="durations"><button v-for="d in [3,5,8]" :key="d" :class="{selected:duration===d}" :disabled="!!store.active || store.busy" @click="duration=d">{{ d }} 秒</button></view></view>
            <view v-if="store.active" class="execution"><text class="card-title">{{ names(store.active.status) }} · {{ remaining }}s</text><text class="small">{{ store.active.message }}</text><progress :percent="store.active.status === 'pending' ? 0 : Math.min(100, (1-remaining/store.active.duration)*100)" activeColor="#355c43" stroke-width="5"/><button class="danger full" :disabled="store.busy" @click="run(() => store.mutate('/commands/' + store.active!.id + '/stop'))">停止本次执行</button></view>
            <button v-else class="primary full" :disabled="store.busy || s.settings.scenario === 'offline'" @click="modal='confirm'">{{ s.settings.scenario === 'offline' ? '设备离线，无法执行' : '执行一次驱离' }}</button>
            <view v-if="s.commands[0] && !store.active" class="result-card" :class="s.commands[0].status" @click="detailId=s.commands[0].id;modal='record'"><text class="card-title">{{ names(s.commands[0].status) }} ›</text><text class="small">{{ s.commands[0].message }}</text></view>
            <text class="note">本设备是模拟执行器，不会控制真实硬件。完成回执仅证明模拟流程结束，不代表实际驱鸟成功。</text><button class="text-button" @click="settings">☷ 切换离线 / 超时演示场景</button>
          </template>

          <template v-if="page === 'records'">
            <text class="title">检测档案</text><text class="subtitle">按视频回看，按鸟类查找。</text>
            <view class="tabs"><button :class="{selected:recordMode==='videos'}" @click="recordMode='videos'">视频与鸟类</button><button :class="{selected:recordMode==='actions'}" @click="recordMode='actions'">处理操作记录</button></view>
            <VideoLibrary v-if="recordMode==='videos'" :key="archiveNonce" :initial-task="archiveTask" :initial-time="archiveTime" />
            <template v-else>
            <view class="summary"><view><text class="metric-value">{{ s.counts.total }}</text><text class="small">检测事件</text></view><view><text class="metric-value">{{ s.counts.completed }}</text><text class="small">模拟执行完成</text></view></view>
            <view class="tabs"><button v-for="item in [{id:'all',name:'全部记录'},{id:'detection',name:'检测事件'},{id:'actions',name:'处理操作'}]" :key="item.id" :class="{selected:recordFilter===item.id}" @click="recordFilter=item.id">{{ item.name }}</button></view>
            <view v-for="event in events" :key="event.id" class="event-row" @click="run(() => inspectEvent(event))"><view class="event-dot"/><view class="grow"><text class="card-title">{{ event.message }}</text><text class="small">{{ time(event.at) }} · {{ event.ref_id }}</text></view><text>›</text></view>
            <view v-if="!events.length" class="empty"><text>开始巡护，留下第一条记录</text></view>
            <button v-if="!historyEnd && (s.events.length >= 100 || older.length)" class="secondary full" :disabled="store.busy" @click="run(loadHistory)">加载更早记录</button>
            <text class="note">记录保存在服务器，退出登录或刷新页面不会丢失。</text>
            </template>
          </template>
        </view>
        <view class="nav"><button v-for="item in [{id:'monitor',icon:'▣',name:'监控'},{id:'alarms',icon:'♧',name:'告警'},{id:'control',icon:'◉',name:'控制'},{id:'records',icon:'▤',name:'记录'}]" :key="item.id" :class="{active:page===item.id}" @click="go(item.id)"><text class="nav-icon">{{ item.icon }}</text><text>{{ item.name }}{{ item.id==='alarms' && s?.counts.pending ? ' · '+s.counts.pending : '' }}</text></button></view>
      </template>
    </view>
    <view class="aside"><text class="eyebrow">巡护提示</text><text class="aside-title">从一次监测开始</text><text>{{ '开始监测，等待模型识鸟。\n核对告警后，再确认模拟驱离。' }}</text><view class="aside-line"/><text>{{ '真实识别，保留抓拍证据。\n模拟设备，明确执行反馈。' }}</text><text class="small">{{ '录像结束后可重新开始。\n不根据录像变化判断驱鸟效果。' }}</text></view>
  </view>

  <view v-if="modal" class="overlay" @click.self="modal=''">
    <scroll-view scroll-y class="sheet"><view class="sheet-head"><text class="card-title">{{ ({settings:'设置',alarm:'告警详情',confirm:'确认本次驱离',record:'操作记录'} as Record<string,string>)[modal] }}</text><button class="icon-button" aria-label="关闭弹窗" @click="modal=''">×</button></view>
      <template v-if="modal==='settings'">
        <text class="subtitle">设备响应场景与检测参数</text>
        <button v-for="option in [{id:'normal',name:'正常执行',sub:'设备在线，按时返回完成回执'},{id:'offline',name:'设备离线',sub:'禁用下发入口，恢复后不自动重放'},{id:'timeout',name:'执行超时',sub:'允许下发，模拟未收到完成回执'}]" :key="option.id" class="option" :class="{selected:preferences.scenario===option.id}" @click="preferences.scenario=option.id as Preferences['scenario']"><text class="card-title">{{ option.name }}</text><text class="small">{{ option.sub }}</text></button>
        <view class="field-row"><text>置信度阈值</text><input v-model.number="preferences.confidence" type="digit" class="input short" /></view>
        <view class="field-row"><text>连续检出帧数</text><input v-model.number="preferences.consecutive" type="number" class="input short" /></view>
        <view class="field-row"><text>事件合并间隔（秒）</text><input v-model.number="preferences.cooldown" type="number" class="input short" /></view>
        <button class="primary full" :disabled="store.busy || !!store.active" @click="run(async()=>{await store.mutate('/settings','PUT',preferences);modal='';notify('设置已保存')})">保存设置</button>
        <text class="note">置信度 0.1–0.95，连续帧数 1–10，合并间隔 1–300 秒。执行期间不可修改。</text>
        <view class="service-info"><text>服务：{{ store.server }}</text><text>视频：{{ s?.monitor.source || '未连接' }}</text><text>推理：{{ s?.monitor.device || '—' }} · {{ s?.monitor.sample_fps || '—' }} 帧/秒抽样</text></view>
        <button class="secondary full" :disabled="store.busy" @click="run(() => store.logout())">退出登录 / 更换服务</button>
      </template>
      <template v-if="modal==='alarm' && alarm">
        <image class="capture" :src="store.media('captures/' + alarm.snapshot)" mode="aspectFit"/>
        <view class="detail-grid"><view><text class="small">识别鸟类</text><text>{{ alarm.species }} · {{ alarm.count }} 只</text></view><view><text class="small">模型置信度</text><text>{{ (alarm.confidence*100).toFixed(1) }}%</text></view><view><text class="small">发现时间</text><text>{{ time(alarm.at) }}</text></view><view><text class="small">录像位置</text><text>{{ alarm.video_time.toFixed(1) }}s · 帧 {{ alarm.frame_id }}</text></view></view>
        <view class="callout">{{ names(alarm.status) }} · 连续检出 {{ alarm.hits }} 次。抓拍与数量以首次告警画面为准。检测到鸟类不等同于发生鸟害。</view>
        <button class="secondary full" @click="replayAlarm(alarm)">回看对应视频 · {{ alarm.video_time.toFixed(1) }} 秒 ›</button>
        <view v-if="alarm.status==='new'" class="button-row"><button class="secondary" :disabled="store.busy" @click="run(async()=>{await store.mutate('/alarms/'+alarm!.id+'/ignore');modal=''})">忽略这次告警</button><button class="primary" :disabled="store.busy" @click="handle">确认并去驱离</button></view>
        <view v-for="c in s?.commands.filter(c=>c.alarm_id===alarm!.id)" :key="c.id" class="result-card" @click="detailId=c.id;modal='record'"><text>{{ c.id }} · {{ names(c.status) }} ›</text></view>
      </template>
      <template v-if="modal==='confirm'">
        <text class="subtitle">将向东区果园的模拟声学驱鸟器下达一次指令。</text><view class="detail-grid"><view><text class="small">执行时长</text><text>{{ duration }} 秒</text></view><view><text class="small">关联事件</text><text>{{ selectedAlarm || '手动操作' }}</text></view></view>
        <view class="callout">可以在执行过程中停止。结果以模拟回执为准，记录自动保存。</view><view class="button-row"><button class="secondary" @click="modal=''">再看一下</button><button class="primary" :disabled="store.busy" @click="run(execute)">{{ store.busy ? '正在提交…' : '确认执行' }}</button></view>
      </template>
      <template v-if="modal==='record' && command">
        <text class="badge" :class="command.status">{{ names(command.status) }}</text><view class="timeline"><text class="card-title">人工确认并下发指令</text><text class="small">{{ time(command.at) }} · {{ command.duration }} 秒</text><text class="card-title">{{ command.started_at ? '模拟设备开始执行' : '尚未执行' }}</text><text v-if="command.started_at" class="small">{{ time(command.started_at) }}</text><text class="card-title">{{ names(command.status) }}</text><text class="small">{{ command.message }}</text><text v-if="command.ended_at" class="small">{{ time(command.ended_at) }}</text></view>
        <view class="callout">{{ command.status==='completed' ? '此记录只证明模拟指令完成，不代表真实驱鸟成功。' : '未完成的操作不会将告警标记为已处理，也不会自动重试。' }}</view>
        <button v-if="command.alarm_id" class="secondary full" @click="run(()=>inspectEvent({ref_id:command!.alarm_id!,id:0,kind:'detection',at:0,message:''}))">查看关联告警</button>
      </template>
    </scroll-view>
  </view>
</template>
