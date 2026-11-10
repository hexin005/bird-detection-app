<script setup lang="ts">
// 塔台监控主页 —— 1:1 复刻 docs/ui-y/a-tower.html(真实数据 + 语义事件)
// 边界:视频内检测框由后端管线绘制进帧,本主题琥珀只作用于播放器边框/取景角/外部状态。
import { computed } from 'vue'
import { useHost, clock, badgeText, monClass, type RepelMode } from '../host/hostContext'
import { useWorkspace } from '../host/useWorkspace'
import { useOrchard } from '../../store'
import VideoPlayer from '../VideoPlayer.vue'

const host = useHost()
const store = useOrchard()
const ws = useWorkspace(store)

const flights = computed(() => (host.s?.alarms || []).slice(0, 5))
const flightNo = (id: string) => `BRD-${id.slice(-4).toUpperCase()}` // 仅显示简称,点击/关联用完整 id
const statusText = (st: string) => st === 'running' ? '执行中' : ({ new: '待处理', processing: '执行中', handled: '已处理', ignored: '已忽略' } as Record<string, string>)[st] || st
const latest = computed(() => host.pending[0] || null)
const canRepel = computed(() => !host.store.busy && !host.offline && !host.store.active)
const patrolLabel = computed(() => ws.running.value ? '停止分析' : '开始检测')
function requestRepel() {
  if (!canRepel.value) return
  host.selectedAlarm = latest.value?.id ?? null
  host.modal = 'mConfirm'
}
</script>

<template>
  <!-- 塔台标牌 -->
  <view class="twr-top">
    <view class="twr-id"><text class="twr-name">果园塔台</text><text class="twr-en">QINGHE TWR</text></view>
    <button class="twr-3d mono" @click="host.openScene">3D 沙盘 ▸</button>
    <view class="twr-clock mono"><text class="twr-time">9:41 LCL</text><text class="twr-sub">东区 · 01 号 · YOLOv8</text></view>
  </view>

  <!-- LIVE 机坪 -->
  <view class="twr-apron">
    <VideoPlayer v-if="ws.path.value" :path="ws.path.value" :autoplay="ws.running.value" />
    <view v-else class="twr-apron-empty">
      <text class="twr-apron-hint">{{ ws.running.value ? '正在准备检测视频…' : '导入视频，开始一次鸟类巡护' }}</text>
    </view>
    <i class="twr-brk tl"/><i class="twr-brk tr"/><i class="twr-brk bl"/><i class="twr-brk br"/>
    <view class="twr-live mono"><i class="twr-live-dot"/>LIVE · CAM-01 · 2 FPS 抽样</view>
    <view v-if="host.s?.monitor.message" class="twr-live-msg mono">{{ host.s.monitor.message }}</view>
  </view>

  <!-- PATROL 行:开始/停止检测 + 进度 -->
  <view class="twr-patrol">
    <view class="twr-patrol-row">
      <view class="twr-patrol-tag mono">PATROL</view>
      <button class="twr-patrol-btn" :disabled="ws.uploading.value || host.store.busy || ws.monitor.value?.status === 'stopping'" @click="ws.running.value ? ws.stop() : ws.start()">
        {{ ws.uploading.value ? '上传中…' : patrolLabel }}
      </button>
    </view>
    <view v-if="ws.running.value" class="twr-patrol-prog">
      <view class="twr-patrol-bar"><view :style="{ width: (ws.monitor.value?.progress || 0) + '%' }"/></view>
      <text class="mono">{{ Math.floor(ws.monitor.value?.progress || 0) }}%</text>
    </view>
    <text v-if="ws.error.value" class="twr-patrol-err">{{ ws.error.value }}</text>
  </view>

  <!-- 计数翻牌 -->
  <view class="twr-counters">
    <view class="twr-cnt warn">
      <view class="twr-digits mono"><text class="d">{{ String(host.s?.counts.pending || 0).padStart(2, '0')[0] }}</text><text class="d">{{ String(host.s?.counts.pending || 0).padStart(2, '0')[1] }}</text></view>
      <text class="twr-cnt-lb">待处理告警</text>
    </view>
    <view class="twr-cnt">
      <view class="twr-digits mono"><text class="d">{{ String(host.s?.counts.total || 0).padStart(3, '0')[0] }}</text><text class="d">{{ String(host.s?.counts.total || 0).padStart(3, '0')[1] }}</text><text class="d">{{ String(host.s?.counts.total || 0).padStart(3, '0')[2] }}</text></view>
      <text class="twr-cnt-lb">检测事件</text>
    </view>
    <view class="twr-cnt">
      <view class="twr-digits mono"><text class="d">{{ String(host.s?.counts.completed || 0).padStart(2, '0')[0] }}</text><text class="d">{{ String(host.s?.counts.completed || 0).padStart(2, '0')[1] }}</text></view>
      <text class="twr-cnt-lb">执行完成</text>
    </view>
  </view>

  <!-- 航显板:今日鸟情 -->
  <view class="twr-board">
    <view class="twr-board-hd"><text class="twr-board-t">今日鸟情 BOARD</text><text class="twr-board-en mono">BIRD MOVEMENTS · 24H</text></view>
    <view class="twr-cols mono"><text>班次</text><text>鸟种</text><text>数量</text><text>时刻</text><text style="text-align:right">状态</text></view>
    <view v-for="f in flights" :key="f.id" class="twr-row" :class="{ 'is-new': f.status === 'new' }" style="cursor:pointer" @click="host.openAlarm(f)">
      <text class="twr-fno mono">{{ flightNo(f.id) }}</text>
      <view class="twr-spn"><text class="twr-spn-name">{{ f.species }} ×{{ f.count }}</text><text class="twr-spn-sub mono">置信度 {{ Math.round(f.confidence * 100) }}%</text></view>
      <text class="twr-qty mono">{{ f.count }}</text>
      <text class="twr-tm mono">{{ clock(f.at).slice(0, 5) }}</text>
      <view class="twr-st"><text class="twr-flap mono" :class="'twr-flap--' + f.status">{{ statusText(f.status) }}</text></view>
    </view>
    <view v-if="!flights.length" class="twr-empty mono">NO MOVEMENTS · 开始检测后显示鸟情</view>
  </view>

  <!-- 放行许可 -->
  <view class="twr-clearance">
    <view class="twr-cl-hd mono"><text class="twr-cl-t">CLEARANCE · 放行许可</text><text class="twr-cl-link">{{ latest ? '关联 ' + flightNo(latest.id) : '手动操作' }}</text></view>
    <view class="twr-cl-body">
      <view class="twr-cl-modes">
        <view v-for="m in [{ id: 'acoustic', n: '声波', en: 'ACOUSTIC' }, { id: 'infrared', n: '红外', en: 'INFRARED' }, { id: 'both', n: '双模联动', en: 'DUAL-MODE' }]" :key="m.id" class="twr-cl-mode" :class="{ on: host.mode === m.id }" @click="host.mode = m.id as RepelMode">
          <text class="n">{{ m.n }}</text><text class="en mono">{{ m.en }}</text>
        </view>
      </view>
      <button class="twr-cl-go" :disabled="!canRepel" @click="requestRepel">
        <text class="go-t">确认放行</text>
        <text class="go-s mono">{{ host.offline ? '设备离线' : host.store.active ? '执行中' : `双模 · ${host.duration} 秒` }}</text>
      </button>
    </view>
  </view>
</template>

<style scoped>
.twr-top { display:flex; justify-content:space-between; align-items:center; padding:2px 0 10px; border-bottom:1px solid var(--twr-line, #2a313c); }
.twr-id { display:flex; align-items:baseline; gap:8px; }
.twr-name { font-size:16px; font-weight:800; letter-spacing:2px; color:var(--ink-900); white-space:nowrap; }
.twr-en { font-family:var(--font-num); font-size:9px; letter-spacing:1.5px; color:#ffb400; border:1px solid #8a6a1e; padding:2px 5px; }
.twr-clock { text-align:right; font-size:9px; line-height:1.6; color:var(--ink-400); letter-spacing:1px; display:flex; flex-direction:column; }
.twr-time { font-size:13px; letter-spacing:2px; color:var(--ink-900); }
.twr-sub { font-family:var(--font-sans); font-weight:700; white-space:nowrap; }
.twr-3d { border:1px solid #8a6a1e; background:transparent; color:#ffb400; font-size:9px; letter-spacing:1px; padding:4px 7px; font-family:var(--font-num); font-weight:700; cursor:pointer; flex-shrink:0; white-space:nowrap; }
.twr-3d:active { background:rgba(255,180,0,.15); }
/* LIVE 机坪:取景角画在容器上(视频内检测框保持后端绘制) */
.twr-apron { position:relative; height:190px; background:#000; border:1px solid #3d4756; margin-top:10px; }
.twr-apron-empty { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; }
.twr-apron-hint { color:#5d6672; font-size:12px; font-weight:700; letter-spacing:1px; }
.twr-apron :deep(video), .twr-apron :deep(uni-image), .twr-apron :deep(image) { width:100%; height:100%; object-fit:cover; }
.twr-brk { position:absolute; width:16px; height:16px; border:2px solid #ffb400; z-index:3; }
.twr-brk.tl { left:6px; top:6px; border-right:0; border-bottom:0; }
.twr-brk.tr { right:6px; top:6px; border-left:0; border-bottom:0; }
.twr-brk.bl { left:6px; bottom:6px; border-right:0; border-top:0; }
.twr-brk.br { right:6px; bottom:6px; border-left:0; border-top:0; }
.twr-live { position:absolute; left:10px; top:10px; display:flex; align-items:center; gap:6px; background:rgba(6,8,11,.85); border:1px solid #3d4756; padding:3px 8px; font-size:10px; letter-spacing:2px; color:#e9e9e4; z-index:3; }
.twr-live-dot { width:7px; height:7px; border-radius:50%; background:#ff4b3e; animation:qhBlink 1.1s steps(2) infinite; }
.twr-live-msg { position:absolute; right:10px; bottom:8px; font-size:9px; letter-spacing:1px; color:#7d8794; z-index:3; }
/* PATROL 行 */
.twr-patrol { margin-top:10px; border:1px solid #2a313c; background:var(--surface-raised); padding:8px 10px; display:flex; flex-direction:column; gap:7px; }
.twr-patrol-row { display:flex; align-items:center; gap:10px; }
.twr-patrol-tag { font-size:10px; letter-spacing:3px; color:#8a6a1e; border:1px solid #8a6a1e; padding:2px 7px; }
.twr-patrol-btn { flex:1; min-height:36px; background:#ffb400; color:#161307; font-size:13px; font-weight:800; letter-spacing:2px; border:none; }
.twr-patrol-btn[disabled] { background:#20262f; color:#5d6672; }
.twr-patrol-prog { display:flex; align-items:center; gap:8px; }
.twr-patrol-bar { flex:1; height:8px; border:1px solid #3d4756; background:#12161c; }
.twr-patrol-bar view { height:100%; background:#ffb400; }
.twr-patrol-prog text { font-size:10px; color:#ffb400; }
.twr-patrol-err { font-size:10px; color:#ff4b3e; }
/* 计数翻牌 */
.twr-counters { display:flex; gap:8px; margin-top:10px; }
.twr-cnt { flex:1; border:1px solid #2a313c; background:var(--surface-raised); padding:8px 0 7px; text-align:center; }
.twr-digits { display:inline-flex; gap:3px; }
.twr-cnt .d { width:20px; height:30px; background:linear-gradient(180deg,#20262f 0 50%,#12161c 50%); color:#ffb400; font-size:20px; font-weight:700; line-height:29px; text-align:center; position:relative; }
.twr-cnt .d::after { content:''; position:absolute; left:0; right:0; top:50%; height:1px; background:#000; }
.twr-cnt.warn .d { color:#ff4b3e; }
.twr-cnt-lb { display:block; font-size:9px; letter-spacing:2px; color:var(--ink-400); margin-top:5px; }
/* 航显板 */
.twr-board { margin-top:10px; border:1px solid #2a313c; }
.twr-board-hd { display:flex; justify-content:space-between; align-items:center; padding:7px 10px; border-bottom:1px solid #2a313c; background:var(--surface-raised); }
.twr-board-t { font-size:11px; letter-spacing:3px; color:var(--ink-900); font-weight:800; }
.twr-board-en { font-size:9px; letter-spacing:2px; color:#5d6672; }
.twr-cols { display:grid; grid-template-columns:64px 1fr 34px 44px 58px; padding:5px 10px; font-size:9px; letter-spacing:2px; color:#5d6672; border-bottom:1px solid #2a313c; }
.twr-row { display:grid; grid-template-columns:64px 1fr 34px 44px 58px; align-items:center; padding:0 10px; border-bottom:1px solid rgba(42,49,60,.55); }
.twr-row:last-child { border-bottom:0; }
.twr-row .fl, .twr-row > text, .twr-row > view { padding:7px 0; }
.twr-row.is-new { background:linear-gradient(90deg,rgba(255,75,62,.12),transparent 65%); box-shadow:inset 3px 0 0 #ff4b3e; }
.twr-fno { font-size:11px; font-weight:700; color:#ffb400; letter-spacing:1px; }
.twr-spn { display:flex; flex-direction:column; gap:1px; min-width:0; }
.twr-spn-name { font-size:13px; font-weight:700; color:var(--ink-900); letter-spacing:1px; }
.twr-spn-sub { font-size:8.5px; letter-spacing:1.5px; color:#5d6672; }
.twr-qty { font-size:14px; color:var(--ink-900); }
.twr-tm { font-size:11px; color:#7d8794; }
.twr-st { justify-self:end; }
.twr-flap { display:inline-block; min-width:52px; text-align:center; font-size:10px; font-weight:800; letter-spacing:2px; padding:4px 0 3px; position:relative; }
.twr-flap::after { content:''; position:absolute; left:0; right:0; top:50%; height:1px; background:rgba(0,0,0,.45); }
.twr-flap--new { background:#ff4b3e; color:var(--warn-fg); }
.twr-flap--processing, .twr-flap--running { background:#ffb400; color:#161307; animation:qhBlink 1.4s steps(2) infinite; }
.twr-flap--handled, .twr-flap--ignored { background:#171c24; color:#5d6672; border:1px solid #2a313c; }
.twr-empty { padding:18px 10px; text-align:center; font-size:10px; letter-spacing:2px; color:#5d6672; }
/* 放行许可 */
.twr-clearance { margin-top:10px; border:1px solid #8a6a1e; background:var(--surface-raised); }
.twr-cl-hd { display:flex; justify-content:space-between; padding:6px 10px; border-bottom:1px dashed #2a313c; font-size:9px; letter-spacing:2px; }
.twr-cl-t { color:#ffb400; font-weight:700; }
.twr-cl-link { color:#5d6672; }
.twr-cl-body { display:flex; align-items:stretch; }
.twr-cl-modes { display:flex; flex:1; }
.twr-cl-mode { flex:1; text-align:center; padding:9px 0 8px; font-size:11px; font-weight:700; letter-spacing:2px; color:#7d8794; border-right:1px solid #2a313c; display:flex; flex-direction:column; gap:2px; }
.twr-cl-mode .en { font-size:8px; letter-spacing:1px; color:#3d4756; font-weight:400; }
.twr-cl-mode.on { color:#161307; background:#ffb400; }
.twr-cl-mode.on .en { color:rgba(22,19,7,.65); }
.twr-cl-go { width:96px; text-align:center; background:#ffb400; color:#161307; font-weight:800; font-size:12px; letter-spacing:2px; border:none; display:flex; flex-direction:column; justify-content:center; gap:2px; }
.twr-cl-go[disabled] { background:#20262f; color:#5d6672; }
.twr-cl-go .go-s { font-size:9px; letter-spacing:1px; opacity:.7; }
</style>
