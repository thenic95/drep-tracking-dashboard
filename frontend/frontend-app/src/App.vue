<template>
  <div class="min-h-screen flex flex-col bg-gray-50">
    <TheNavigation />

    <main class="flex-1">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>

    <TheFooter />
  </div>
</template>

<script setup>
import TheNavigation from './components/layout/TheNavigation.vue'
import TheFooter from './components/layout/TheFooter.vue'
</script>

<style>
/* Page transition animation */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
