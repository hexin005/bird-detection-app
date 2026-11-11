<script setup lang="ts">
// B 主题视频工作区(预览批次 docs/ui-flow/monitor.html 方案):
// 未选视频态=拍摄指引卡;检测完成态=本次汇总卡(N 种 · M 只 + 物种分布),一键进记录 / 3D 复现;
// 「使用演示视频」零后端(monitor/start 不带 video_id 时服务端自动注册演示录像)。
// 状态与动作来自共享工作区控制器:主题壳切换时上传/选中/错误不丢失。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useOrchard } from '../store'
import VideoPlayer from './VideoPlayer.vue'
import { useWorkspace } from './host/useWorkspace'
import { useHost } from './host/hostContext'
import type { LibraryDetail } from '../types'

const store = useOrchard()
const host = useHost()
const ws = useWorkspace(store)
onMounted(() => { void ws.init().catch(() => { /* 连接横幅负责展示故障 */ }) })
onBeforeUnmount(() => ws.destroyPicker())

// 本次检测汇总:仅「本会话内看到完成」的任务展示(服务重启恢复的旧 ended 任务不冒充本次)
const summary = ref<LibraryDetail | null>(null)
const freshTask = ref('')
const showSummary = computed(() =>
  !!freshTask.value && freshTask.value === ws.monitor.value?.task_id &&
  !!ws.monitor.value?.result_ready && ws.sameVideo.value)
watch(() => ws.monitor.value?.status, st => {
  const task = ws.monitor.value?.task_id
  if ((st === 'ended' || st === 'stopped') && task && task !== freshTask.value) {
    freshTask.value = task; summary.value = null
    void store.request<LibraryDetail>('/library/' + task).then(d => { summary.value = d }).catch(() => { summary.value = null })
  }
})
const totalBirds = computed(() => summary.value?.species.reduce((n, s) => n + s.peak_count, 0) ?? 0)

/** 汇总卡 → 记录页深链(复用 DetectionRecords 的自动展开) */
function goRecord() {
  const task = ws.monitor.value?.task_id
  if (!task) return
  host.archiveTask = task; host.archiveTime = 0; host.archiveNonce++
  host.nav('records')
}
/** 使用演示视频:清空选择直接启动,服务端自动注册 assets 演示录像(已分析过会提示去记录查看) */
function demoStart() { ws.selected.value = null; void ws.start() }
</script>
<template>
  <VideoPlayer v-if="ws.path.value" :path="ws.path.value" :autoplay="ws.running.value" />
  <view v-else class="qh-video">
    <text class="qh-video__tag qh-video__tag--tl">录像演示 · YOLOv8</text>
    <view class="qh-scanline"/>
    <view class="qh-detect-box" style="left:50%;top:32%;width:34%;height:46%;opacity:.25"/>
    <text class="qh-video__tag qh-video__tag--bl">{{ ws.running.value ? '正在准备检测视频…' : '导入视频，开始一次鸟类巡护' }}</text>
  </view>

  <!-- 害鸟图鉴入口(非检测中常驻) -->
  <view v-if="!ws.running.value" class="qh-guidebar" @click="host.nav('guide')">
    <text class="qh-guidebar__t">本园重点防范：八哥 · 树麻雀 · 白喉红臀鹎 等 7 种害鸟</text>
    <text class="qh-guidebar__go">害鸟图鉴 ›</text>
  </view>

  <!-- 拍摄指引(未选视频时) -->
  <view v-if="!ws.running.value && !ws.uploading.value && !ws.selected.value" class="qh-card qh-shootguide">
    <view class="qh-shootguide__hd">
      <text class="qh-shootguide__t">拍得对，才检得准</text>
      <text class="qh-badge qh-badge--new">拍摄指引</text>
    </view>
    <view class="qh-shootguide__item"><text class="qh-shootguide__n">1</text><text class="qh-shootguide__d">固定机位，画面对准<b>挂果树冠</b>，一段视频一个场景</text></view>
    <view class="qh-shootguide__item"><text class="qh-shootguide__n">2</text><text class="qh-shootguide__d">白天自然光拍摄，逆光 / 夜间画面检出率明显下降</text></view>
    <view class="qh-shootguide__item"><text class="qh-shootguide__n">3</text><text class="qh-shootguide__d">建议单段 <b>15 秒 – 5 分钟</b>，鸟身别只占几个像素</text></view>
    <view class="qh-shootguide__item"><text class="qh-shootguide__n">4</text><text class="qh-shootguide__d">同一视频重复上传会被识别并拒收，结果请到记录页查看</text></view>
  </view>

  <view class="qh-srcrow">
    <view class="qh-srcrow__info">
      <text class="qh-srcrow__name">{{ ws.selected.value?.name || '服务器演示录像' }}</text>
      <text class="qh-srcrow__dur">{{ ws.selected.value ? `时长 ${ws.selected.value.duration.toFixed(1)} 秒` : '支持 MP4 / MOV / AVI / WebM，最大 500 MB' }}</text>
    </view>
    <button v-if="!ws.running.value && !ws.uploading.value" class="qh-btn qh-btn--secondary" :disabled="store.busy" @click="demoStart">使用演示视频</button>
    <button class="qh-btn qh-btn--secondary" :disabled="ws.running.value || ws.uploading.value || store.busy" @click="ws.choose">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="1.5" y="3" width="9" height="10" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M10.5 6.5l4-2.5v8l-4-2.5" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>选择视频
    </button>
  </view>

  <!-- 上传进度 -->
  <view v-if="ws.uploading.value" class="qh-upload">
    <view class="qh-upload__top">
      <text class="qh-upload__label">{{ ws.percent.value === 100 ? '上传完成，正在校验…' : '正在上传' }}</text>
      <text class="qh-upload__pct">{{ ws.percent.value }}%</text>
    </view>
    <view class="qh-progress"><view class="qh-progress__bar" :style="{ width: ws.percent.value + '%' }"/></view>
  </view>

  <view v-if="ws.error.value" class="qh-card" style="background:var(--danger-bg);border-color:var(--danger-line)">
    <text style="font-size:var(--text-xs);color:var(--danger-fg)">{{ ws.error.value }}</text>
  </view>

  <button class="qh-btn qh-btn--primary" :disabled="ws.uploading.value || store.busy || ws.monitor.value?.status === 'stopping'" @click="ws.running.value ? ws.stop() : ws.start()">
    <svg v-if="!ws.running.value" width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3.5 2.2v9.6c0 .8.9 1.3 1.6.9l7.3-4.8c.6-.4.6-1.4 0-1.8L5.1 1.3c-.7-.4-1.6.1-1.6.9z" fill="currentColor"/></svg>
    {{ ws.running.value ? '停止分析' : '开始检测' }}
  </button>

  <!-- 检测进度 -->
  <view v-if="ws.running.value" class="qh-upload">
    <view class="qh-upload__top">
      <text class="qh-upload__label">{{ ws.monitor.value?.message || '正在分析录像' }}</text>
      <text class="qh-upload__pct">{{ Math.floor(ws.monitor.value?.progress || 0) }}%</text>
    </view>
    <view class="qh-progress"><view class="qh-progress__bar" :style="{ width: (ws.monitor.value?.progress || 0) + '%' }"/></view>
  </view>

  <!-- 本次检测汇总卡(一检一记入口) -->
  <view v-if="showSummary" class="qh-card qh-sumcard">
    <view class="qh-sumcard__hd">
      <text class="qh-sumcard__t">本次检测</text>
      <text v-if="summary" class="qh-badge qh-badge--handled">{{ summary.species.length }} 种 · {{ totalBirds }} 只</text>
      <text v-else class="qh-badge">汇总中…</text>
    </view>
    <template v-if="summary">
      <view class="qh-sumcard__rows">
        <view v-for="s in summary.species" :key="s.species" class="qh-sumcard__row">
          <text class="sp">{{ s.species }}</text><view class="dots"/><text class="n">{{ s.peak_count }}</text>
        </view>
        <text v-if="!summary.species.length" class="qh-note" style="padding:3px 0">本次未检出鸟类 — 结果已归档，可回看完整视频</text>
      </view>
      <text class="qh-sumcard__meta">逐帧明细与回放已归档到「检测记录」 · 检测中产生 {{ summary.alarms.length }} 条告警</text>
      <view class="qh-btnrow">
        <button class="qh-btn qh-btn--secondary qh-btn--half" @click="goRecord">查看记录</button>
        <button class="qh-btn qh-btn--primary qh-btn--half" @click="host.openScene(ws.monitor.value?.task_id)">3D 场景复现驱赶</button>
      </view>
      <text class="qh-link" style="display:block;margin-top:9px">
        <a :href="store.media(`media/${ws.monitor.value!.task_id}/result.mp4`)+'&download=true'" style="color:inherit">下载结果视频 ↓</a>
      </text>
    </template>
  </view>

  <text v-if="!showSummary" class="qh-hint" style="display:block;text-align:left">{{ ws.sameVideo.value ? (ws.monitor.value?.message || '') : '视频已就绪，点击开始检测' }}</text>
</template>

<style scoped>
/* 害鸟图鉴入口条 */
.qh-guidebar{display:flex;align-items:center;gap:8px;margin:9px 14px 0;padding:8px 11px;border:2px dashed var(--ink-900);background:var(--surface-sunken);cursor:pointer}
.qh-guidebar__t{flex:1;font-size:var(--text-xs);font-weight:700;color:var(--ink-800)}
.qh-guidebar__go{font-size:var(--text-xs);font-weight:700;color:var(--ink-900);white-space:nowrap}
/* 拍摄指引卡 */
.qh-shootguide__hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.qh-shootguide__t{font-size:var(--text-md);font-weight:700;letter-spacing:1px}
.qh-shootguide__item{display:flex;align-items:flex-start;gap:8px;padding:4px 0}
.qh-shootguide__n{display:inline-flex;width:20px;height:20px;border:2px solid var(--ink-900);background:var(--accent);color:var(--accent-fg);align-items:center;justify-content:center;font-size:var(--text-2xs);font-weight:700;flex-shrink:0}
.qh-shootguide__d{font-size:var(--text-xs);color:var(--ink-700);line-height:var(--leading-snug);padding-top:2px}
/* 本次检测汇总卡 */
.qh-sumcard{box-shadow:5px 5px 0 var(--shadow-ink)}
.qh-sumcard__hd{display:flex;align-items:center;justify-content:space-between}
.qh-sumcard__t{font-size:var(--text-xl);font-weight:700;letter-spacing:1px}
.qh-sumcard__rows{margin-top:6px}
.qh-sumcard__row{display:flex;align-items:baseline;gap:8px;padding:5px 0;border-bottom:1px solid var(--line-soft)}
.qh-sumcard__row:last-child{border-bottom:none}
.qh-sumcard__row .sp{font-size:var(--text-base);font-weight:700}
.qh-sumcard__row .dots{flex:1;border-bottom:2px dotted var(--ink-200);transform:translateY(-3px)}
.qh-sumcard__row .n{font-size:var(--text-lg);font-family:var(--font-num);font-weight:700}
.qh-sumcard__meta{display:block;font-size:var(--text-2xs);color:var(--ink-400);margin-top:8px;line-height:var(--leading-normal)}
</style>
