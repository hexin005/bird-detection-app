<script setup lang="ts">
// 控制页策略层共享组件(S1):自动响应规则 + 定时巡逻 + 设备参数。
// 结构与文案四主题一致,观感随主题 token 换肤;语义动作全部走 host。
import { computed, reactive, ref, watch } from 'vue'
import { useHost, modeCn, triggerCn, type RepelMode } from './hostContext'
import type { AutoRule, Patrol, Preferences } from '../../types'

const host = useHost()
withDefaults(defineProps<{ showParams?: boolean }>(), { showParams: true })

/* ---- 响应规则 ---- */
const addOpen = ref(false)
const draft = reactive({ trigger: 'alarm_any' as AutoRule['trigger'], mode: 'acoustic' as RepelMode, duration: 3, cooldown_minutes: 10 })
const ruleDesc = (r: AutoRule) => `${triggerCn[r.trigger]} → ${modeCn[r.mode]} ${r.duration} 秒 · 冷却 ${r.cooldown_minutes} 分`
async function addRule() {
  const name = `规则 ${host.rules.length + 1}`
  await host.saveRule({ name, ...draft, enabled: 1 })
  addOpen.value = false
}
const toggleRule = (r: AutoRule) => host.run(() => host.saveRule({ enabled: r.enabled ? 0 : 1 }, r.id))
const removeRule = (r: AutoRule) => host.run(() => host.removeRule(r.id))

/* ---- 定时巡逻(本地草稿,保存一次提交) ---- */
const patrolDraft = reactive({ enabled: 0, start_minute: 360, end_minute: 1140, interval: 120, mode: 'acoustic' as RepelMode, duration: 3 })
const patrolError = ref('')
const formatMinute = (value: number) => `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`
const timeSide = ref<'start_minute' | 'end_minute'>('start_minute')
const hours = computed(() => Array.from({ length: timeSide.value === 'start_minute' ? 24 : 25 }, (_, hour) => hour))
const minutes = Array.from({ length: 60 }, (_, minute) => minute)
const wheelValue = computed(() => {
  const value = patrolDraft[timeSide.value]
  return [Math.floor(value / 60), value % 60]
})
function setWheelTime(event: { detail: { value: number[] } }) {
  const [hour, minute] = event.detail.value
  patrolDraft[timeSide.value] = hour * 60 + (hour === 24 ? 0 : minute)
  patrolError.value = ''
}
watch(() => host.patrol, p => {
  if (!p) return
  Object.assign(patrolDraft, { enabled: p.enabled, start_minute: p.start_minute, end_minute: p.end_minute, interval: p.interval_minutes, mode: p.mode, duration: p.duration })
  patrolError.value = ''
}, { immediate: true })
async function savePatrol() {
  if (patrolDraft.start_minute >= patrolDraft.end_minute) {
    patrolError.value = '开始时间须早于结束时间'
    return
  }
  patrolError.value = ''
  await host.savePatrol({ enabled: patrolDraft.enabled ? 1 : 0, start_minute: patrolDraft.start_minute, end_minute: patrolDraft.end_minute,
    interval_minutes: patrolDraft.interval, mode: patrolDraft.mode, duration: patrolDraft.duration })
}

/* ---- 设备参数(与设置弹窗共用 PUT /settings;两处均可改) ---- */
const params = reactive({ scenario: 'normal' as Preferences['scenario'], confidence: .4, consecutive: 2, cooldown: 20 })
const paramsDirty = ref(false)
watch(() => host.s?.settings, st => { if (st && !paramsDirty.value) Object.assign(params, st) }, { immediate: true })
const bump = (k: 'confidence' | 'consecutive', d: number) => {
  paramsDirty.value = true
  if (k === 'confidence') params.confidence = Math.min(.95, Math.max(.1, Math.round((params.confidence + d * .05) * 100) / 100))
  else params.consecutive = Math.min(10, Math.max(1, params.consecutive + d))
}
const saveParams = () => host.run(async() => { await host.store.mutate('/settings', 'PUT', { ...params }); paramsDirty.value = false; host.notify('参数已保存') })

</script>

<template>
  <!-- 自动响应规则 -->
  <view class="cs-card cs-card--flush">
    <view class="cs-card__hd bar"><text class="t">⚡ 自动响应</text><text class="qh-badge" :class="host.rules.some(r => r.enabled) ? 'qh-badge--new' : ''">{{ host.rules.some(r => r.enabled) ? '已启用' : '未启用' }}</text></view>
    <view v-for="r in host.rules" :key="r.id" class="cs-rule">
      <view class="cs-rule__mid">
        <text class="n">{{ r.name }}</text>
        <text class="d mono">{{ ruleDesc(r) }}</text>
      </view>
      <view class="cs-switch" :class="{ 'is-on': r.enabled }" @click="toggleRule(r)"><view class="knob"/></view>
      <text class="cs-del" @click="removeRule(r)">✕</text>
    </view>
    <view v-if="!host.rules.length" class="cs-emptynote">还没有规则 — 告警出现时不会自动驱离</view>
    <view v-if="addOpen" class="cs-addform">
      <view class="cs-frow"><text class="lab">触发</text>
        <view class="cs-chips"><text v-for="(cn, id) in triggerCn" :key="id" class="cs-chip" :class="{ 'is-on': draft.trigger === id }" @click="draft.trigger = id as AutoRule['trigger']">{{ cn }}</text></view>
      </view>
      <view class="cs-frow"><text class="lab">方式</text>
        <view class="cs-chips"><text v-for="m in ['acoustic', 'infrared', 'both']" :key="m" class="cs-chip" :class="{ 'is-on': draft.mode === m }" @click="draft.mode = m as RepelMode">{{ modeCn[m as RepelMode] }}</text></view>
      </view>
      <view class="cs-frow"><text class="lab">时长</text>
        <view class="cs-chips"><text v-for="d in [3, 5, 8]" :key="d" class="cs-chip" :class="{ 'is-on': draft.duration === d }" @click="draft.duration = d">{{ d }} 秒</text></view>
      </view>
      <view class="cs-frow"><text class="lab">冷却</text>
        <view class="cs-chips"><text v-for="c in [10, 30, 60]" :key="c" class="cs-chip" :class="{ 'is-on': draft.cooldown_minutes === c }" @click="draft.cooldown_minutes = c">{{ c }} 分</text></view>
      </view>
      <view class="cs-frow btns">
        <button class="cs-mini" @click="host.run(addRule)">保存规则</button>
        <button class="cs-mini ghost" @click="addOpen = false">取消</button>
      </view>
    </view>
    <view v-else class="cs-addbar" @click="addOpen = true">＋ 添加规则</view>
  </view>

  <!-- 定时巡逻 -->
  <view class="cs-card cs-card--flush">
    <view class="cs-card__hd bar"><text class="t">⏱ 定时巡逻</text>
      <view class="cs-switch" :class="{ 'is-on': patrolDraft.enabled }" @click="patrolDraft.enabled = patrolDraft.enabled ? 0 : 1"><view class="knob"/></view>
    </view>
    <view class="cs-patrol">
      <view class="cs-frow cs-frow--time"><text class="lab">时段</text>
        <view class="cs-hours">
          <view class="cs-time" :class="{ 'is-on': timeSide === 'start_minute' }" @click="timeSide = 'start_minute'"><text class="cs-time__label">开始</text><text class="mono">{{ formatMinute(patrolDraft.start_minute) }}</text></view>
          <text class="cs-time__dash">—</text>
          <view class="cs-time" :class="{ 'is-on': timeSide === 'end_minute' }" @click="timeSide = 'end_minute'"><text class="cs-time__label">结束</text><text class="mono">{{ formatMinute(patrolDraft.end_minute) }}</text></view>
        </view>
      </view>
      <view class="cs-wheel-area">
        <text class="cs-wheel-caption">滚动设置{{ timeSide === 'start_minute' ? '开始' : '结束' }}时间</text>
        <picker-view class="cs-wheel" :value="wheelValue" indicator-style="height:36px" @change="setWheelTime">
          <picker-view-column><view v-for="hour in hours" :key="hour" class="cs-wheel__item mono">{{ String(hour).padStart(2, '0') }}</view></picker-view-column>
          <picker-view-column><view v-for="minute in minutes" :key="minute" class="cs-wheel__item mono">{{ String(minute).padStart(2, '0') }}</view></picker-view-column>
        </picker-view>
        <text class="cs-wheel-colon">:</text>
      </view>
      <text v-if="patrolError" class="cs-patrol__error">{{ patrolError }}</text>
      <view class="cs-frow"><text class="lab">间隔</text>
        <view class="cs-chips"><text v-for="i in [30, 60, 120, 240]" :key="i" class="cs-chip" :class="{ 'is-on': patrolDraft.interval === i }" @click="patrolDraft.interval = i">{{ i }} 分</text></view>
      </view>
      <view class="cs-frow"><text class="lab">方式</text>
        <view class="cs-chips">
          <text v-for="m in ['acoustic', 'infrared', 'both']" :key="m" class="cs-chip" :class="{ 'is-on': patrolDraft.mode === m }" @click="patrolDraft.mode = m as RepelMode">{{ modeCn[m as RepelMode] }}</text>
          <text v-for="d in [3, 5, 8]" :key="d" class="cs-chip" :class="{ 'is-on': patrolDraft.duration === d }" @click="patrolDraft.duration = d">{{ d }}秒</text>
        </view>
      </view>
      <view class="cs-frow btns"><button class="cs-mini" @click="host.run(savePatrol)">保存巡逻计划</button></view>
    </view>
  </view>

  <!-- 设备参数(设置弹窗同款,两处均可改) -->
  <view v-if="showParams" class="cs-card cs-card--flush">
    <view class="cs-card__hd bar"><text class="t">⚙ 设备参数</text><text class="s">{{ paramsDirty ? '有未保存修改' : '与「设置」同步' }}</text></view>
    <view class="cs-param"><text class="lab">置信度阈值</text>
      <view class="cs-step"><text class="b" @click="bump('confidence', -1)">−</text><text class="v mono">{{ params.confidence.toFixed(2) }}</text><text class="b" @click="bump('confidence', 1)">＋</text></view>
    </view>
    <view class="cs-param"><text class="lab">连续检出帧数</text>
      <view class="cs-step"><text class="b" @click="bump('consecutive', -1)">−</text><text class="v mono">{{ params.consecutive }} 帧</text><text class="b" @click="bump('consecutive', 1)">＋</text></view>
    </view>
    <view class="cs-param"><text class="lab">事件合并间隔</text>
      <view class="cs-chips"><text v-for="c in [10, 20, 30, 60, 120]" :key="c" class="cs-chip" :class="{ 'is-on': params.cooldown === c }" @click="params.cooldown = c; paramsDirty = true">{{ c }} 秒</text></view>
    </view>
    <view class="cs-frow btns pad"><button class="cs-mini" :disabled="host.store.busy || !!host.store.active" @click="saveParams">应用参数</button></view>
  </view>
</template>

<style scoped>
.cs-card{margin:0 14px 12px;border:2px solid var(--ink-900);background:var(--surface-card);box-shadow:4px 4px 0 var(--shadow-ink);padding:11px 13px}
.cs-card--flush{padding:0}
.cs-card__hd{display:flex;align-items:center;gap:9px;margin-bottom:9px}
.cs-card__hd .t{flex:1;font-size:13.5px;font-weight:800;color:var(--ink-900);letter-spacing:1px}
.cs-card__hd .s{font-size:10px;color:var(--ink-400)}
.cs-card__hd.bar{padding:10px 13px;margin:0;border-bottom:2px solid var(--ink-900)}
.cs-rule{display:flex;align-items:center;gap:10px;padding:9px 13px;border-bottom:1px dashed var(--line-strong)}
.cs-rule__mid{flex:1;min-width:0}
.cs-rule__mid .n{display:block;font-size:12.5px;font-weight:800;color:var(--ink-900)}
.cs-rule__mid .d{display:block;font-size:10px;color:var(--ink-400);margin-top:2px}
.cs-switch{width:38px;height:20px;border:2px solid var(--ink-900);position:relative;flex-shrink:0;cursor:pointer;background:var(--surface-card)}
.cs-switch .knob{position:absolute;top:1px;left:1px;width:14px;height:14px;background:var(--ink-900);transition:left .15s}
.cs-switch.is-on{background:var(--ink-900)}
.cs-switch.is-on .knob{left:auto;right:1px;background:var(--surface-card)}
.cs-del{font-size:12px;color:var(--ink-400);padding:4px;cursor:pointer}
.cs-emptynote{padding:10px 13px;font-size:11.5px;color:var(--ink-400)}
.cs-addbar{padding:10px 13px;font-size:12.5px;font-weight:800;color:var(--ink-900);text-align:center;border-top:2px solid var(--ink-900);cursor:pointer}
.cs-addform{padding:10px 13px;border-top:2px solid var(--ink-900)}
.cs-frow{display:flex;align-items:center;gap:10px;padding:5px 0}
.cs-frow .lab{width:34px;font-size:11.5px;font-weight:700;color:var(--ink-400);flex-shrink:0}
.cs-frow.btns{padding-top:9px}
.cs-frow.btns.pad{padding:10px 13px}
.cs-mini{flex:1;border:2px solid var(--ink-900);background:var(--ink-900);color:var(--surface-card);font-size:12.5px;font-weight:800;padding:8px 0;cursor:pointer;border-radius:0}
.cs-mini.ghost{background:var(--surface-card);color:var(--ink-900)}
.cs-mini[disabled]{opacity:.45}
.cs-chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.cs-chip{border:2px solid var(--ink-900);background:var(--surface-card);color:var(--ink-900);font-size:11px;font-weight:700;padding:4px 10px;white-space:nowrap;cursor:pointer}
.cs-chip.is-on{background:var(--ink-900);color:var(--surface-card)}
.cs-chip.sm{padding:3px 7px;font-size:10.5px}
.cs-patrol{padding:8px 13px 12px}
.cs-hours{display:flex;align-items:center;gap:5px;flex:1;min-width:0}
.cs-time{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;gap:1px;padding:5px 2px;border:2px solid var(--ink-900);color:var(--ink-900);background:var(--surface-card);cursor:pointer}
.cs-time.is-on{background:var(--ink-900);color:var(--surface-card)}
.cs-time .mono{font-size:15px;font-weight:700;white-space:nowrap}
.cs-time__label{font-size:10px;color:var(--ink-400)}
.cs-time.is-on .cs-time__label{color:var(--surface-card)}
.cs-time__dash{color:var(--ink-400)}
.cs-wheel-area{position:relative;margin:6px 0 8px 44px;border:2px solid var(--ink-900);background:var(--surface-card);max-width:250px}
.cs-wheel-caption{display:block;border-bottom:1px dashed var(--line-strong);padding:3px 8px;font-size:10px;color:var(--ink-400);text-align:center}
.cs-wheel{height:108px;width:100%}
.cs-wheel__item{height:36px;line-height:36px;text-align:center;font-size:16px;font-weight:700;color:var(--ink-900)}
.cs-wheel-colon{position:absolute;left:50%;top:50%;transform:translate(-50%,0);font-weight:800;pointer-events:none;color:var(--ink-900)}
.cs-patrol__error{display:block;margin:2px 0 4px 44px;color:var(--accent);font-size:11px;font-weight:700}
.cs-param{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 13px;border-bottom:1px dashed var(--line-strong)}
.cs-param .lab{font-size:12px;font-weight:600;color:var(--ink-900)}
.cs-step{display:flex;align-items:center;gap:10px}
.cs-step .b{width:26px;height:26px;border:2px solid var(--ink-900);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;cursor:pointer;color:var(--ink-900);background:var(--surface-card)}
.cs-step .v{font-size:13px;font-weight:800;color:var(--ink-900);min-width:44px;text-align:center}
</style>
