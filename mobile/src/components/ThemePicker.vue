<script setup lang="ts">
import { ref } from 'vue'
import { THEMES, type ThemeId } from '../theme'
import { useOrchard } from '../store'

const props = defineProps<{ current: ThemeId }>()
const emit = defineEmits<{ apply: [id: ThemeId] }>()
const store = useOrchard()
const applying = ref<ThemeId | null>(null)
const notify = (m: string) => uni.showToast({ title: m, icon: 'none', duration: 2500 })

/** 用户主动切换:立即换肤 + 保存账号偏好;请求序号防快速切换乱序。 */
async function apply(id: ThemeId) {
  if (id === props.current || applying.value) return
  applying.value = id
  const stamp = applying.value
  try {
    await store.mutate('/me/preferences', 'PUT', { theme: id })
    emit('apply', id)
  } catch (e) {
    notify((e as Error).message)
  } finally {
    if (applying.value === stamp) applying.value = null
  }
}
</script>

<template>
  <view class="qh-header">
    <view class="qh-header__brand">
      <text class="qh-page-title">主题</text>
      <text class="qh-page-subtitle">大图预览 · 点击即换,仅改变外观</text>
    </view>
  </view>

  <view v-for="t in THEMES" :key="t.id" class="qh-window qh-theme-card" :class="{ 'is-applying': applying === t.id }">
    <view class="qh-theme-shot">
      <!-- A 果园塔台 -->
      <view v-if="t.id === 'tower'" class="qh-shot-a" style="height:100%">
        <view class="h"><b>果园塔台</b><span>QINGHE TWR</span></view>
        <view class="flap"><view class="f hot">03</view><view class="f">1·2·8</view><view class="f">52</view><view class="f">RUN</view></view>
        <view class="flap"><view class="f">BRD-1114</view><view class="f" style="flex:2.2">珠颈斑鸠 ×2</view><view class="f">09:41</view><view class="f hot">NEW</view></view>
        <view class="flap"><view class="f">BRD-1097</view><view class="f" style="flex:2.2">白喉红臀鹎 ×2</view><view class="f">08:12</view><view class="f">EXEC</view></view>
        <view class="cl">▸ CLEARANCE · 双模 5 秒 · 确认放行</view>
      </view>
      <!-- B 果园守护 1.0 -->
      <view v-else-if="t.id === 'b1bit'" class="qh-shot-b" style="height:100%">
        <view class="w" style="width:82%"><view class="tb"><i>监测 — CAM-01</i></view><view class="bd2"><view class="v"></view><view style="flex:1"><view class="ln"></view><view class="ln o"></view><view class="ln o"></view></view></view></view>
        <view class="w w2"><view class="tb"><i>今日鸟情</i></view><view class="bd2"><view style="flex:1"><view class="ln" style="margin-top:2px"></view><view class="ln o"></view></view></view></view>
      </view>
      <!-- C 鸟情信号站 -->
      <view v-else-if="t.id === 'signal'" class="qh-shot-c" style="height:100%">
        <view class="tick"></view>
        <view class="mast">
          <view class="rail"></view>
          <view class="plate"><b>3</b><i>鸟情密集</i></view>
          <view class="lv"><i class="y"></i><i class="o"></i><i class="r"></i></view>
        </view>
        <view class="tags"><i class="hot">待处理 3</i><i>执行中 1</i><i>已处理</i></view>
      </view>
      <!-- D 像素果园 -->
      <view v-else class="qh-shot-d" style="height:100%">
        <view class="sky"><i></i></view>
        <view class="field" style="position:relative;height:64px">
          <view class="tree"></view><view class="tree t2"></view><view class="bird"></view>
          <view class="dlg">野生的<b>珠颈斑鸠 ×2</b> 出现了!置信度 <i>93%</i> ▶</view>
        </view>
      </view>
    </view>
    <view class="qh-theme-nm">
      <text>{{ t.label }}</text>
      <text class="qh-mvp">{{ t.tag }}</text>
    </view>
    <view class="qh-theme-ds">{{ t.desc }}</view>
    <view class="qh-theme-btnrow">
      <button v-if="t.id === current" class="qh-btn qh-btn--secondary" disabled>当前主题</button>
      <button v-else class="qh-btn qh-btn--primary" :disabled="!!applying" @click="apply(t.id)">{{ applying === t.id ? '正在应用…' : '应用主题' }}</button>
    </view>
  </view>

  <text class="qh-note">切换即时生效 · 仅改变外观,监测数据与设备配置不受影响 · 主题跟随账号保存</text>
</template>
