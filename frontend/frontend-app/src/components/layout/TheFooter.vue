<template>
  <footer class="bg-gray-800 text-gray-400 py-6 mt-auto">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
        <p class="text-sm">
          &copy; {{ currentYear }} Cardano DRep Tracker
        </p>
        <div class="flex items-center space-x-4 text-sm">
          <span>Powered by Koios API</span>
          <span class="text-gray-600">|</span>
          <a href="https://cardano.org" target="_blank" rel="noopener noreferrer"
             class="hover:text-white transition-colors">
            Cardano
          </a>
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup>
const currentYear = new Date().getFullYear()
</script>
