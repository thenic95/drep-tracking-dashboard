<template>
  <nav class="bg-gradient-to-r from-primary to-secondary shadow-lg">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16">
        <!-- Logo/Brand -->
        <div class="flex items-center">
          <router-link to="/" class="flex items-center space-x-3">
            <div class="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <span class="text-white font-semibold text-lg hidden sm:block">
              Cardano DRep Tracker
            </span>
          </router-link>
        </div>

        <!-- Desktop Navigation Links -->
        <div class="hidden md:flex items-center space-x-1">
          <router-link
            v-for="link in navLinks"
            :key="link.path"
            :to="link.path"
            class="px-4 py-2 rounded-lg text-white/80 hover:text-white hover:bg-white/10
                   transition-all duration-200 font-medium"
            :class="{ 'bg-white/20 text-white': isActive(link.path) }"
          >
            {{ link.name }}
          </router-link>
        </div>

        <!-- Mobile Menu Button -->
        <div class="md:hidden flex items-center">
          <button
            @click="mobileMenuOpen = !mobileMenuOpen"
            class="text-white p-2 rounded-lg hover:bg-white/10"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path v-if="!mobileMenuOpen" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Mobile Menu -->
    <div v-show="mobileMenuOpen" class="md:hidden bg-primary/95 border-t border-white/10">
      <div class="px-4 py-3 space-y-2">
        <router-link
          v-for="link in navLinks"
          :key="link.path"
          :to="link.path"
          class="block px-4 py-2 rounded-lg text-white/80 hover:text-white hover:bg-white/10"
          :class="{ 'bg-white/20 text-white': isActive(link.path) }"
          @click="mobileMenuOpen = false"
        >
          {{ link.name }}
        </router-link>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const mobileMenuOpen = ref(false)

const navLinks = [
  { name: 'Overview', path: '/' },
  { name: 'DRep Profiles', path: '/dreps' },
  { name: 'Manage DReps', path: '/manage' },
  { name: 'Governance', path: '/governance' },
  { name: 'CF Delegation', path: '/cf-delegation' },
]

const isActive = (path) => {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>
