<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getAudioInfo, getWaveform } from '@/api/assets'

let activeAudio: HTMLAudioElement | null = null
let activeAudioToken: symbol | null = null

const props = defineProps<{
  src: string
  assetId?: string
  compact?: boolean
  playRequest?: number
  volume: number
  /** 预计算的音频元数据（后端扫描时已存入 Asset），命中时不再请求 /assets/audio-info */
  metadata?: { duration: number; sampleRate: number; channels?: number }
  /** 懒加载：元素进入视口附近时才请求波形，减少切换分类时的并发请求 */
  lazy?: boolean
  /** 批量预取的波形峰值，命中时直接绘制，不再请求 /assets/waveform/{id} */
  initialPeaks?: number[]
}>()
const emit = defineEmits<{
  metadata: [value: { duration: number; sampleRate: number; channels?: number }]
}>()

const canvas = ref<HTMLCanvasElement>()
const canvasContainer = ref<HTMLDivElement>()
const rootRef = ref<HTMLDivElement>()
const audio = ref<HTMLAudioElement>()
const isPlaying = ref(false)
const isLoading = ref(true)
const isPlayable = ref(false)
const instanceToken = Symbol('audio-waveform')
let loadVersion = 0
let resizeObserver: ResizeObserver | null = null
let lazyObserver: IntersectionObserver | null = null
const loadedPeaks = ref<number[]>([])

function getCanvasWidth(): number {
  const container = canvasContainer.value
  if (container) {
    return container.clientWidth || (props.compact ? 148 : 228)
  }
  return props.compact ? 148 : 228
}

function computeBarCount(width: number): number {
  if (props.compact) {
    return Math.max(80, Math.min(500, Math.round(width * 0.6)))
  }
  return Math.max(120, Math.min(1500, Math.round(width * 0.85)))
}

function drawFilledWaveform(peaks: number[]) {
  const target = canvas.value
  if (!target || peaks.length === 0) return

  const width = getCanvasWidth()
  const height = props.compact ? 96 : 64
  const ratio = window.devicePixelRatio || 1
  const ctx = target.getContext('2d')
  if (!ctx) return

  target.width = width * ratio
  target.height = height * ratio
  target.style.height = `${height}px`

  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  ctx.clearRect(0, 0, width, height)

  const center = height / 2
  const halfH = height * 0.42 // 84% of half height
  const len = peaks.length

  // Draw main filled waveform envelope
  ctx.beginPath()
  ctx.moveTo(0, height)

  // Top envelope (left to right)
  for (let i = 0; i < len; i++) {
    const x = (i / Math.max(1, len - 1)) * width
    const y = center - (peaks[i] ?? 0) * halfH
    ctx.lineTo(x, y)
  }

  // Bottom envelope (right to left)
  for (let i = len - 1; i >= 0; i--) {
    const x = (i / Math.max(1, len - 1)) * width
    const y = center + (peaks[i] ?? 0) * halfH
    ctx.lineTo(x, y)
  }

  ctx.closePath()

  // Gradient fill
  const gradient = ctx.createLinearGradient(0, 0, 0, height)
  gradient.addColorStop(0, '#5eead4')   // teal-300
  gradient.addColorStop(0.3, '#2dd4bf') // teal-400
  gradient.addColorStop(0.7, '#2dd4bf') // teal-400
  gradient.addColorStop(1, '#5eead4')   // teal-300

  ctx.fillStyle = gradient
  ctx.fill()

  // Subtle center line
  ctx.beginPath()
  ctx.moveTo(0, center)
  ctx.lineTo(width, center)
  ctx.strokeStyle = 'rgba(45, 212, 191, 0.15)'
  ctx.lineWidth = 1
  ctx.stroke()
}

function drawPlaceholder() {
  const width = getCanvasWidth()
  const barCount = computeBarCount(width)
  const peaks = Array.from({ length: barCount }, (_, index) => {
    const progress = index / Math.max(1, barCount - 1)
    return 0.12 + Math.sin(progress * Math.PI) * 0.34
  })
  loadedPeaks.value = peaks
  drawFilledWaveform(peaks)
}

function handleResize() {
  if (loadedPeaks.value.length > 0) {
    drawFilledWaveform(loadedPeaks.value)
  }
}

async function loadWaveform() {
  const currentVersion = (loadVersion += 1)
  isLoading.value = true
  isPlayable.value = false
  isPlaying.value = false
  stopAudio()
  loadedPeaks.value = []
  drawPlaceholder()
  await new Promise(requestAnimationFrame)

  try {
    if (props.assetId) {
      // 优先使用预计算的元数据，避免额外请求 /assets/audio-info
      if (props.metadata && (props.metadata.duration || props.metadata.sampleRate || props.metadata.channels)) {
        if (currentVersion === loadVersion) {
          emit('metadata', props.metadata)
        }
      } else {
        getAudioInfo(props.assetId)
          .then((metadata) => {
            if (currentVersion === loadVersion) {
              emit('metadata', metadata)
            }
          })
          .catch(() => undefined)
      }

      // 优先使用批量预取的波形峰值，避免单独请求 /assets/waveform/{id}
      if (props.initialPeaks && props.initialPeaks.length > 0) {
        if (currentVersion === loadVersion) {
          loadedPeaks.value = props.initialPeaks
          drawFilledWaveform(props.initialPeaks)
          isLoading.value = false
          return
        }
      }

      // Fetch waveform peaks from backend with dynamic count
      try {
        const width = getCanvasWidth()
        const barCount = computeBarCount(width)
        const { peaks } = await getWaveform(props.assetId, barCount)
        if (currentVersion === loadVersion) {
          loadedPeaks.value = peaks
          drawFilledWaveform(peaks)
          isLoading.value = false
          return
        }
      } catch {
        // fallback: try browser decode
      }
    }

    // Fallback: decode audio in browser
    const response = await fetch(props.src)
    const bytes = await response.arrayBuffer()
    const audioContext = new AudioContext()
    const audioBuffer = await audioContext.decodeAudioData(bytes.slice(0))
    audioContext.close()
    if (currentVersion === loadVersion) {
      if (!props.assetId) {
        emit('metadata', {
          duration: audioBuffer.duration,
          sampleRate: audioBuffer.sampleRate,
        })
      }
      const data = audioBuffer.getChannelData(0)
      const width = getCanvasWidth()
      const barCount = computeBarCount(width)
      const step = Math.max(1, Math.floor(data.length / barCount))
      const peaks: number[] = []
      for (let index = 0; index < barCount; index += 1) {
        let peak = 0
        const start = index * step
        const end = Math.min(start + step, data.length)
        for (let cursor = start; cursor < end; cursor += 1) {
          peak = Math.max(peak, Math.abs(data[cursor] ?? 0))
        }
        peaks.push(peak)
      }
      loadedPeaks.value = peaks
      drawFilledWaveform(peaks)
      isLoading.value = false
    }
  } catch {
    if (currentVersion === loadVersion) {
      drawPlaceholder()
      isLoading.value = false
    }
  }
}

async function playAudio(restart = false) {
  const target = audio.value
  if (!target) return

  if (activeAudio && activeAudio !== target) {
    activeAudio.pause()
    activeAudio.currentTime = 0
  }
  activeAudio = target
  activeAudioToken = instanceToken
  window.dispatchEvent(new CustomEvent('solo-audio-play', { detail: instanceToken }))
  target.volume = props.volume
  if (restart) {
    target.currentTime = 0
  }
  if (target.readyState === 0) {
    target.load()
  }
  try {
    await target.play()
    isPlaying.value = true
  } catch {
    isPlaying.value = false
  }
}

async function togglePlay(event: MouseEvent) {
  event.stopPropagation()
  const target = audio.value
  if (!target) return

  if (target.paused) {
    await playAudio()
  } else {
    target.pause()
    isPlaying.value = false
  }
}

function syncPaused() {
  isPlaying.value = false
  if (activeAudioToken === instanceToken) {
    activeAudio = null
    activeAudioToken = null
  }
}

function markPlayable() {
  isPlayable.value = true
}

function markLoading() {
  isPlayable.value = false
}

function stopAudio() {
  const target = audio.value
  if (!target) return
  target.pause()
  target.currentTime = 0
  isPlaying.value = false
  if (activeAudioToken === instanceToken) {
    activeAudio = null
    activeAudioToken = null
  }
}

function stopOtherAudio(event: Event) {
  if ((event as CustomEvent<symbol>).detail !== instanceToken) {
    stopAudio()
  }
}

watch(() => [props.src, props.assetId], loadWaveform)
watch(
  () => props.volume,
  (value) => {
    if (audio.value) {
      audio.value.volume = value
    }
  },
)
watch(
  () => props.playRequest,
  () => {
    if (props.playRequest) {
      playAudio(true)
    }
  },
)

watch(
  () => props.initialPeaks,
  (peaks) => {
    // 批量预取结果到达时，若尚未加载波形则立即绘制，并使进行中的单独请求失效
    if (peaks && peaks.length > 0 && loadedPeaks.value.length === 0) {
      loadVersion += 1
      loadedPeaks.value = peaks
      drawFilledWaveform(peaks)
      isLoading.value = false
    }
  },
)
onMounted(() => {
  window.addEventListener('solo-audio-play', stopOtherAudio)
  if (audio.value) {
    audio.value.volume = props.volume
  }
  resizeObserver = new ResizeObserver(() => {
    handleResize()
  })
  if (canvasContainer.value) {
    resizeObserver.observe(canvasContainer.value)
  }
  if (props.lazy) {
    // 懒加载：卡片进入视口附近时才请求波形，减少切换分类时的并发请求
    const rootEl = rootRef.value
    if (rootEl && typeof IntersectionObserver !== 'undefined') {
      let triggered = false
      lazyObserver = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting && !triggered) {
              triggered = true
              loadWaveform()
              lazyObserver?.disconnect()
              lazyObserver = null
            }
          }
        },
        { rootMargin: '300px' },
      )
      lazyObserver.observe(rootEl)
    } else {
      loadWaveform()
    }
  } else {
    loadWaveform()
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('solo-audio-play', stopOtherAudio)
  resizeObserver?.disconnect()
  resizeObserver = null
  lazyObserver?.disconnect()
  lazyObserver = null
  stopAudio()
})
</script>

<template>
  <div ref="rootRef" class="waveform" :class="{ compact }">
    <button class="play-dot" :class="{ loading: isLoading && !isPlaying, pending: !isPlayable }" type="button" @click="togglePlay">
      <span v-if="isLoading && !isPlaying" class="loading-icon"></span>
      <span v-else-if="!isPlaying" class="play-icon"></span>
      <span v-else class="pause-icon"></span>
    </button>
    <div ref="canvasContainer" class="canvas-wrap">
      <canvas ref="canvas"></canvas>
    </div>
    <audio
      ref="audio"
      preload="none"
      :src="src"
      @canplay="markPlayable"
      @loadstart="markLoading"
      @ended="syncPaused"
      @pause="syncPaused"
    ></audio>
  </div>
</template>

<style scoped>
.waveform {
  display: grid;
  grid-template-columns: 54px 1fr;
  gap: 16px;
  align-items: center;
  width: 100%;
  min-height: auto;
  padding: 10px;
  border-radius: 10px;
  background: transparent;
}

.waveform.compact {
  grid-template-columns: 36px 1fr;
  gap: 10px;
  min-height: 112px;
  padding: 12px;
}

.canvas-wrap {
  width: 100%;
  overflow: hidden;
}

.play-dot {
  display: grid;
  width: 54px;
  height: 54px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: linear-gradient(140deg, #f5a524 0%, #d97706 100%);
  box-shadow: 0 8px 22px rgba(245, 165, 36, 0.34), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  cursor: pointer;
  transition: transform 0.18s, box-shadow 0.18s;
}

.play-dot:hover {
  transform: scale(1.06);
  box-shadow: 0 10px 26px rgba(245, 165, 36, 0.46), inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.play-dot.loading,
.play-dot.pending {
  cursor: progress;
}

.compact .play-dot {
  width: 36px;
  height: 36px;
  box-shadow: 0 6px 16px rgba(245, 165, 36, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.play-icon {
  width: 0;
  height: 0;
  margin-left: 4px;
  border-top: 9px solid transparent;
  border-bottom: 9px solid transparent;
  border-left: 14px solid #1a1206;
}

.compact .play-icon {
  border-top-width: 6px;
  border-bottom-width: 6px;
  border-left-width: 9px;
}

.pause-icon {
  width: 16px;
  height: 18px;
  border-right: 5px solid #1a1206;
  border-left: 5px solid #1a1206;
}

.compact .pause-icon {
  width: 12px;
  height: 14px;
  border-right-width: 4px;
  border-left-width: 4px;
}

.loading-icon {
  width: 18px;
  height: 18px;
  border: 3px solid rgba(26, 18, 6, 0.3);
  border-top-color: #1a1206;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.compact .loading-icon {
  width: 14px;
  height: 14px;
  border-width: 2px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

canvas {
  display: block;
  width: 100%;
}

audio {
  display: none;
}
</style>
