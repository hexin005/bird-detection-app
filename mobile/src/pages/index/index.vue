<script setup lang="ts">
// 薄路由:登录壳 + 登录后交给 AppHost(业务宿主,状态与语义动作全部内聚)
import { ref } from 'vue'
import { useOrchard } from '../../store'
import AuthView from '../../components/AuthView.vue'
import AppHost from '../../components/host/AppHost.vue'

const store = useOrchard()
const authMode = ref<'login' | 'register' | 'forgot'>('login')
</script>

<template>
  <view class="phone" id="app">

    <!-- ======================= 登录页 ======================= -->
    <view class="page page--nologin" :class="{ 'is-current': !store.token }">
      <view class="statusbar">
        <view class="qh-menubar">
          <svg width="16" height="13" viewBox="0 0 16 13" fill="none"><path d="M2 11V6L6 2h6l2 3v6h-3V8H5v3z" fill="currentColor"/><rect x="6" y="4" width="2" height="2" style="fill:var(--surface-card)"/></svg>
          <text class="qh-menubar__ttl">果园守护</text>
          <text class="qh-menubar__item">文件</text>
          <text class="qh-menubar__item">监测</text>
          <text class="qh-menubar__item">告警</text>
          <text class="qh-menubar__item">特效</text>
          <view class="qh-menubar__right"><text class="time">9:41</text></view>
        </view>
      </view>
      <view class="page__content">
        <AuthView :initial-mode="authMode" />
        <view class="qh-footer"><text>System 1.0 · 仅限局域网使用 · MVP</text></view>
      </view>
    </view>

    <!-- ======================= 业务宿主(主题布局路由) ======================= -->
    <template v-if="store.token">
      <AppHost />
    </template>
  </view>
</template>
