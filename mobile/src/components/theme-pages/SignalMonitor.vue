<script setup lang="ts">
// 信号站监控主页 —— 1:1 复刻 docs/ui-y/c-signal.html(真实数据 + 语义事件)
// 口径:信号等级=「待处理等级」(counts.pending 全量);0 条=独立"静止"态,不高亮警示。
import { computed, onMounted, ref } from 'vue'
import { useHost, clock, shortTime, modeCn } from '../host/hostContext'
import { useWorkspace } from '../host/useWorkspace'
import { useOrchard } from '../../store'
import VideoPlayer from '../VideoPlayer.vue'
import type { Stats } from '../../types'

const host = useHost()
const store = useOrchard()
const ws = useWorkspace(store)

const stats = ref<Stats | null>(null)
const wsOpen = ref(false)
const disconnected = computed(() => host.store.connection !== '实时连接')
const pendingCount = computed(() => host.s?.counts.pending || 0)
const level = computed(() => pendingCount.value >= 3 ? 3 : pendingCount.value >= 2 ? 2 : pendingCount.value >= 1 ? 1 : 0) // 0=静止
const canRepel = computed(() => !host.store.busy && !host.offline && !host.store.active)
const tags = computed(() => (host.s?.alarms || []).filter(a => a.status === 'new' || a.status === 'processing').slice(0, 3))
const latest = computed(() => tags.value[0] ?? null)
const ticker = computed(() => {
  if (disconnected.value) return `● 连接中断(${host.store.connection})—— 正在尝试恢复,当前数据可能滞后  ｜  `
  const items = (host.s?.events || []).slice(0, 4).map(e => `${clock(e.at)} ${e.message}`)
  return items.length ? items.join('  ｜  ') + '  ｜  ' : '暂无鸟情播报  ｜  '
})
const fmtSec = (v: number | null | undefined) => v == null ? '暂无' : `${v.toFixed(1)}s`

async function loadStats() { try { stats.value = await store.request<Stats>('/stats?range=today') } catch { /* 观测带显示 0 */ } }
onMounted(loadStats)

function requestRepel() {
  if (!canRepel.value) return
  host.selectedAlarm = tags.value[0]?.id ?? null
  host.modal = 'mConfirm'
}
</script>

<template>
  <!-- 台标 -->
  <view class="sgn-head">
    <view class="sgn-head-left">
      <text class="sgn-title">鸟情信号站</text>
      <text class="sgn-en">QINGHE SIGNAL SERVICE · ST.01 东区</text>
    </view>
    <button class="sgn-3d mono" @click="host.openScene">3D 沙盘 ▸</button>
  </view>

  <!-- 广播跑马灯 -->
  <view class="sgn-ticker"><text class="sgn-belt" :class="{ down: disconnected }">{{ ticker }}</text></view>

  <!-- 挂杆 + 信号牌 + 等级牌桌 -->
  <view class="sgn-mast">
    <view class="sgn-rail"/>
    <view class="sgn-chain" style="left:96px"/><view class="sgn-chain" style="left:110px"/>
    <view class="sgn-plate" :class="'lv' + level">
      <text class="sgn-plate-no">鸟情信号 · 待处理等级</text>
      <text v-if="level > 0" class="sgn-plate-big">{{ level }}</text>
      <text v-else class="sgn-plate-big sgn-quiet">静</text>
      <text class="sgn-plate-nm">{{ level === 0 ? '观测平静 · 无待处理' : level === 2 ? '鸟情频繁 · 建议值守' : '鸟群密集 · 建议驱离' }}</text>
      <text class="sgn-plate-en">SIGNAL {{ level > 0 ? ['','I','II','III'][level] : 'QUIET' }} · {{ pendingCount }} 条待处理</text>
    </view>
    <view class="sgn-levels">
      <text class="sgn-levels-hd">待处理等级表</text>
      <view class="sgn-lv" :class="{ cur: level === 1 }"><view class="sq" style="background:#f5c400;color:#111"><text>1</text></view><view class="t"><text class="t1">偶发到访</text><text class="t2">保持记录 · 无需处理</text></view></view>
      <view class="sgn-lv" :class="{ cur: level === 2 }"><view class="sq" style="background:#e07a18"><text>2</text></view><view class="t"><text class="t1">频繁活动</text><text class="t2">建议值守 · 关注返场</text></view></view>
      <view class="sgn-lv" :class="{ cur: level === 3 }"><view class="sq" style="background:#d3212c"><text>3</text></view><view class="t"><text class="t1">密集取食</text><text class="t2">待处理 {{ pendingCount }} 条 · 建议驱离</text></view></view>
    </view>
  </view>

  <!-- 最新鸟情条:最新一报 + 待处理计数,处置在告警墙 -->
  <view class="sgn-strip" @click="host.nav('alarms')">
    <view class="strip-hd">
      <text class="strip-t">最新鸟情</text>
      <text class="strip-n mono" :class="{ zero: !pendingCount }">待处理 {{ pendingCount }}</text>
    </view>
    <view class="strip-bd">
      <template v-if="latest">
        <text class="strip-sp">{{ latest.species }} <text class="x mono">×{{ latest.count }}</text></text>
        <text class="strip-m mono">{{ shortTime(latest.at) }} · {{ latest.site }} · 置信 {{ Math.round(latest.confidence * 100) }}%</text>
        <text class="strip-st" :class="{ run: latest.status !== 'new' }">{{ latest.status === 'new' ? '待处理' : '执行中' }}</text>
      </template>
      <template v-else>
        <text class="strip-sp">暂无进行中鸟情</text>
        <text class="strip-m">历史见「记录」页</text>
      </template>
    </view>
    <view class="strip-go">
      <text>打开告警墙 · 逐条处置</text>
      <text class="sub">挂牌墙 · 筛选 · 历史 ›</text>
    </view>
  </view>

  <!-- 应急驱离条:一键升起(方式/时长在升降页调整) -->
  <view class="sgn-emg">
    <view class="emg-cfg">
      <text class="cfg-t">应急驱离</text>
      <text class="cfg-cur mono">{{ modeCn[host.mode] }} · {{ host.duration }} 秒</text>
      <text class="cfg-link" @click.stop="host.nav('control')">去调整 ›</text>
    </view>
    <button class="emg-btn" :class="{ off: !canRepel }" :disabled="!canRepel" @click="requestRepel">
      <i class="flag"/>
      <view class="emg-main">
        <text class="emg-t">升起驱离信号</text>
        <text class="emg-s mono">{{ host.offline ? '设备离线 · 无法升起' : host.store.active ? '信号升空中 · ' + Math.max(0, host.remaining) + 's' : '关联 ' + (tags[0]?.id ?? '手动操作') + ' · 人工确认后执行' }}</text>
      </view>
    </button>
  </view>

  <!-- 观测工作区(折叠) -->
  <view class="sgn-ws">
    <view class="sgn-ws-hd" style="cursor:pointer" @click="wsOpen = !wsOpen">
      <text class="sgn-ws-t">观测工作区 {{ wsOpen ? '▾' : '▸' }}</text>
      <text class="sgn-ws-s">{{ ws.running.value ? '观测进行中 · ' + Math.floor(ws.monitor.value?.progress || 0) + '%' : '选择视频 · 开始/停止观测' }}</text>
    </view>
    <view v-if="wsOpen" class="sgn-ws-bd">
      <VideoPlayer v-if="ws.path.value" :path="ws.path.value" :autoplay="ws.running.value" />
      <view v-else class="sgn-ws-empty"><text>{{ ws.selected.value?.name || '服务器演示录像' }}</text></view>
      <view class="sgn-ws-row">
        <button class="sgn-ws-btn" :disabled="ws.uploading.value || host.store.busy || ws.monitor.value?.status === 'stopping'" @click="ws.running.value ? ws.stop() : ws.start()">{{ ws.running.value ? '停止观测' : '开始观测' }}</button>
        <button class="sgn-ws-btn" :disabled="ws.running.value || ws.uploading.value || host.store.busy" @click="ws.choose">选择视频</button>
      </view>
      <view v-if="ws.uploading.value" class="sgn-ws-prog"><text class="lbl">上传 {{ ws.percent.value }}%</text><view class="bar"><view :style="{ width: ws.percent.value + '%' }"/></view></view>
      <view v-if="ws.running.value" class="sgn-ws-prog"><text class="lbl">分析 {{ Math.floor(ws.monitor.value?.progress || 0) }}%</text><view class="bar"><view :style="{ width: (ws.monitor.value?.progress || 0) + '%' }"/></view></view>
      <text v-if="ws.error.value" class="sgn-ws-err">{{ ws.error.value }}</text>
      <text v-if="ws.sameVideo.value && ws.monitor.value?.result_ready && ws.monitor.value?.task_id" class="sgn-ws-err" style="color:var(--ink-500)">
        结果已归档 ·
        <a :href="store.media(`media/${ws.monitor.value!.task_id}/result.mp4`)+'&download=true'" style="color:inherit">下载结果视频</a>
      </text>
    </view>
  </view>

  <!-- 今日观测带 -->
  <view class="sgn-obs">
    <view><text class="b mono">{{ stats ? stats.breakdown.new + stats.breakdown.processing + stats.breakdown.handled + stats.breakdown.ignored : 0 }}</text><text class="s">今日告警</text></view>
    <view><text class="b mono">{{ stats?.exec.completed ?? 0 }}</text><text class="s">执行完成</text></view>
    <view><text class="b mono">{{ fmtSec(stats?.exec.avg_start_seconds) }}</text><text class="s">平均响应</text></view>
    <view><text class="b mono">{{ stats?.exec.dual_share == null ? '暂无' : Math.round(stats.exec.dual_share * 100) + '%' }}</text><text class="s">双模占比</text></view>
  </view>
</template>

<style scoped>
.sgn-head { background:#191919; color:#f2f1ea; padding:10px 14px 8px; display:flex; justify-content:space-between; align-items:center; gap:10px; }
.sgn-head-left { display:flex; flex-direction:column; gap:2px; min-width:0; }
.sgn-3d { border:1px solid #f5c400; background:transparent; color:#f5c400; font-size:10px; letter-spacing:2px; padding:5px 9px; font-family:var(--font-num); font-weight:700; cursor:pointer; flex-shrink:0; }
.sgn-3d:active { background:rgba(245,196,0,.18); }
.sgn-title { font-size:21px; font-weight:900; letter-spacing:6px; }
.sgn-en { font-size:8.5px; letter-spacing:2px; color:#9a9a92; font-family:var(--font-num); font-weight:700; }
/* 跑马灯 */
.sgn-ticker { background:#f5c400; border-top:2px solid #191919; border-bottom:2px solid #191919; overflow:hidden; height:26px; display:flex; align-items:center; }
.sgn-belt { white-space:nowrap; font-size:11px; font-weight:800; letter-spacing:1px; color:#191919; padding-left:100%; animation:qhTicker 18s linear infinite; }
.sgn-belt.down { background:#d3212c; color:#fff; margin-left:-100%; padding:6px 14px; animation:none; }
/* 挂杆区 */
.sgn-mast { position:relative; height:300px; padding:0 16px; margin-top:12px; }
.sgn-rail { position:absolute; left:8px; right:8px; top:6px; height:5px; background:#191919; }
.sgn-chain { position:absolute; top:10px; width:0; height:34px; border-left:2px dashed #191919; }
.sgn-plate { position:absolute; left:44px; top:44px; width:170px; background:#d3212c; border:3px solid #191919; color:#fff; text-align:center; padding:14px 0 12px; box-shadow:5px 6px 0 rgba(25,25,25,.28); transform-origin:50% -30px; animation:qhSway 5s ease-in-out infinite; display:flex; flex-direction:column; gap:2px; }
.sgn-plate.lv2 { background:#e07a18; }
.sgn-plate.lv0 { background:#ecebe2; color:#191919; border-color:#6f6f68; }
.sgn-plate-no { font-size:10px; letter-spacing:3px; font-weight:900; }
.sgn-plate-big { font-size:64px; font-weight:900; line-height:1.05; }
.sgn-plate-big.sgn-quiet { font-size:44px; }
.sgn-plate-nm { font-size:12px; font-weight:900; letter-spacing:2px; border-top:2px solid rgba(255,255,255,.6); margin:4px 12px 0; padding-top:6px; }
.sgn-plate.lv0 .sgn-plate-nm { border-color:rgba(25,25,25,.4); }
.sgn-plate-en { font-size:8px; letter-spacing:2px; opacity:.85; font-family:var(--font-num); font-weight:700; }
/* 等级牌桌 */
.sgn-levels { position:absolute; right:14px; top:40px; width:128px; }
.sgn-levels-hd { font-size:10px; font-weight:900; letter-spacing:3px; border-bottom:2px solid #191919; padding-bottom:5px; margin-bottom:8px; display:block; color:#191919; }
.sgn-lv { display:flex; gap:7px; align-items:flex-start; margin-bottom:9px; opacity:.5; }
.sgn-lv.cur { opacity:1; }
.sgn-lv .sq { width:28px; height:28px; flex-shrink:0; border:2px solid #191919; display:flex; align-items:center; justify-content:center; font-weight:900; font-size:14px; color:#fff; }
.sgn-lv .t { display:flex; flex-direction:column; gap:1px; }
.sgn-lv .t1 { font-size:10.5px; font-weight:800; color:#191919; }
.sgn-lv .t2 { font-size:9px; color:#6f6f68; }
/* 最新鸟情条(替代挂牌告警区) */
.sgn-strip { margin:12px 14px 0; border:2px solid #191919; background:var(--surface-card); box-shadow:3px 4px 0 var(--shadow-ink); cursor:pointer; }
.strip-hd { display:flex; align-items:center; gap:8px; padding:8px 11px; border-bottom:1px dashed #6f6f68; }
.strip-t { font-size:11px; font-weight:900; letter-spacing:1px; }
.strip-n { margin-left:auto; font-size:9.5px; font-weight:900; background:#d3212c; color:#fff; padding:1px 7px; }
.strip-n.zero { background:var(--surface-muted); color:var(--ink-400); }
.strip-bd { display:flex; align-items:center; gap:8px; padding:9px 11px; }
.strip-sp { font-size:14px; font-weight:900; min-width:0; overflow-wrap:anywhere; }
.strip-sp .x { font-size:10px; background:#191919; color:#f5c400; padding:1px 6px; }
.strip-m { font-size:9px; color:var(--ink-400); flex:1; min-width:0; }
.strip-st { flex-shrink:0; font-size:9.5px; font-weight:900; border:2px solid #191919; padding:2px 8px; transform:rotate(-3deg); background:#d3212c; border-color:#d3212c; color:#fff; }
.strip-st.run { background:#f5c400; border-color:#191919; color:#191919; }
.strip-go { display:flex; justify-content:space-between; align-items:center; gap:8px; border-top:2px solid #191919; padding:8px 11px; font-size:11px; font-weight:900; background:#191919; color:#f5c400; }
.strip-go .sub { font-size:9px; color:#9a9a92; font-weight:700; text-align:right; }
/* 应急驱离条(替代升降控制面板) */
.sgn-emg { margin:10px 14px 0; border:2px solid #191919; background:var(--surface-card); box-shadow:3px 4px 0 var(--shadow-ink); }
.emg-cfg { display:flex; align-items:center; gap:8px; padding:8px 11px; border-bottom:1px dashed #6f6f68; }
.cfg-t { font-size:11px; font-weight:900; letter-spacing:1px; }
.cfg-cur { margin-left:auto; font-size:10px; font-weight:700; border:1px solid #191919; padding:2px 8px; color:#191919; }
.cfg-link { font-size:10px; font-weight:900; color:#d3212c; text-decoration:underline; cursor:pointer; flex-shrink:0; }
.emg-btn { display:flex; align-items:center; width:100%; background:#191919; border:0; cursor:pointer; padding:0; }
.emg-btn .flag { width:14px; align-self:stretch; background:repeating-linear-gradient(-45deg,#f5c400 0 9px,#191919 9px 18px); border-right:2px solid #f5c400; }
.emg-main { flex:1; text-align:center; padding:11px 0 10px; min-width:0; }
.emg-t { display:block; color:#f5c400; font-size:14px; font-weight:900; letter-spacing:4px; }
.emg-s { display:block; text-align:center; font-size:9px; color:#9a9a92; letter-spacing:1px; margin-top:2px; }
.emg-btn.off, .emg-btn[disabled] { opacity:.55; }
/* 观测工作区 */
.sgn-ws { margin-top:12px; border:2px solid #191919; background:var(--surface-card); }
.sgn-ws-hd { display:flex; justify-content:space-between; align-items:center; padding:9px 12px; }
.sgn-ws-t { font-size:12px; font-weight:900; letter-spacing:2px; }
.sgn-ws-s { font-size:9px; color:var(--ink-400); font-family:var(--font-num); font-weight:700; }
.sgn-ws-bd { padding:0 12px 12px; display:flex; flex-direction:column; gap:9px; }
.sgn-ws-empty { height:120px; border:2px solid #191919; display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700; color:var(--ink-400); }
.sgn-ws-row { display:flex; gap:8px; }
.sgn-ws-btn { flex:1; min-height:36px; border:2px solid #191919; background:var(--surface-card); font-size:12px; font-weight:800; letter-spacing:1px; color:#191919; }
.sgn-ws-btn[disabled] { background:var(--surface-sunken); color:var(--ink-400); }
.sgn-ws-prog { display:flex; align-items:center; gap:8px; }
.sgn-ws-prog .lbl { font-size:10px; font-weight:800; font-family:var(--font-num); white-space:nowrap; }
.sgn-ws-prog .bar { flex:1; height:10px; border:2px solid #191919; }
.sgn-ws-prog .bar view { height:100%; background:#191919; }
.sgn-ws-err { font-size:10px; color:#d3212c; font-weight:700; }
/* 今日观测带 */
.sgn-obs { display:flex; margin-top:12px; border:2px solid #191919; background:var(--surface-card); }
.sgn-obs > view { flex:1; text-align:center; padding:9px 0 8px; border-right:2px solid #191919; display:flex; flex-direction:column; gap:2px; }
.sgn-obs > view:last-child { border-right:0; }
.sgn-obs .b { font-size:18px; font-weight:700; color:#191919; }
.sgn-obs .s { font-size:8.5px; letter-spacing:2px; color:var(--ink-400); font-weight:700; }
</style>
