<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getAudioInfo } from '@/api/assets'

let activeAudio: HTMLAudioElement | null = null
let activeAudioToken: symbol | null = null

const props = defineProps<{
  src: string
  assetId?: string
  compact?: boolean
  playRequest?: number
  volume: number
}>()
const emit = defineEmits<{
  metadata: [value: { duration: number; sampleRate: number; channels?: number }]
}>()

const canvas = ref<HTMLCanvasElement>()
const audio = ref<HTMLAudioElement>()
const isPlaying = ref(false)
const isLoading = ref(true)
const isPlayable = ref(false)
const instanceToken = Symbol('audio-waveform')
let audioContext: AudioContext | null = null
let loadVersion = 0

function readUint32LE(data: Uint8Array, offset: number) {
  return (
    (data[offset] ?? 0) |
    ((data[offset + 1] ?? 0) << 8) |
    ((data[offset + 2] ?? 0) << 16) |
    ((data[offset + 3] ?? 0) << 24)
  )
}

function readUint16LE(data: Uint8Array, offset: number) {
  return (data[offset] ?? 0) | ((data[offset + 1] ?? 0) << 8)
}

function readGranule(data: Uint8Array, offset: number) {
  let value = 0n
  for (let index = 7; index >= 0; index -= 1) {
    value = (value << 8n) + BigInt(data[offset + index] ?? 0)
  }
  return value === 0xffffffffffffffffn ? -1 : Number(value)
}

function matchText(data: Uint8Array, offset: number, text: string) {
  for (let index = 0; index < text.length; index += 1) {
    if (data[offset + index] !== text.charCodeAt(index)) return false
  }
  return true
}

function parseWavMetadata(bytes: ArrayBuffer) {
  const data = new Uint8Array(bytes)
  if (!matchText(data, 0, 'RIFF') || !matchText(data, 8, 'WAVE')) return null

  let offset = 12
  let sampleRate = 0
  let byteRate = 0
  let dataSize = 0

  while (offset + 8 <= data.length) {
    const chunkId = String.fromCharCode(...data.slice(offset, offset + 4))
    const chunkSize = readUint32LE(data, offset + 4)
    const chunkDataOffset = offset + 8

    if (chunkId === 'fmt ') {
      sampleRate = readUint32LE(data, chunkDataOffset + 4)
      byteRate = readUint32LE(data, chunkDataOffset + 8)
    }
    if (chunkId === 'data') {
      dataSize = chunkSize
    }

    offset = chunkDataOffset + chunkSize + (chunkSize % 2)
  }

  if (!sampleRate || !byteRate || !dataSize) return null
  return { duration: dataSize / byteRate, sampleRate }
}

function parseOggMetadata(bytes: ArrayBuffer) {
  const data = new Uint8Array(bytes)
  let sampleRate = 0
  let opusPreSkip = 0
  let isOpus = false
  let lastGranule = -1

  for (let index = 0; index + 16 < data.length; index += 1) {
    if (data[index] === 1 && matchText(data, index + 1, 'vorbis')) {
      sampleRate = readUint32LE(data, index + 12)
      break
    }
    if (matchText(data, index, 'OpusHead')) {
      isOpus = true
      opusPreSkip = readUint16LE(data, index + 10)
      sampleRate = readUint32LE(data, index + 12)
      break
    }
  }

  let offset = 0
  while (offset + 27 <= data.length) {
    if (!matchText(data, offset, 'OggS')) {
      offset += 1
      continue
    }

    const granule = readGranule(data, offset + 6)
    if (granule >= 0) {
      lastGranule = granule
    }

    const segmentCount = data[offset + 26] ?? 0
    let bodySize = 0
    for (let index = 0; index < segmentCount; index += 1) {
      bodySize += data[offset + 27 + index] ?? 0
    }
    offset += 27 + segmentCount + bodySize
  }

  if (!sampleRate || lastGranule < 0) return null

  if (isOpus) {
    return {
      duration: Math.max(0, (lastGranule - opusPreSkip) / 48000),
      sampleRate: sampleRate || 48000,
    }
  }

  return { duration: lastGranule / sampleRate, sampleRate }
}

function parseAudioMetadata(bytes: ArrayBuffer) {
  return parseWavMetadata(bytes) ?? parseOggMetadata(bytes)
}

function drawBars(peaks: number[]) {
  const target = canvas.value
  if (!target) return

  const width = target.getBoundingClientRect().width || (props.compact ? 148 : 228)
  const height = props.compact ? 96 : 180
  const ratio = window.devicePixelRatio || 1
  const context = target.getContext('2d')
  if (!context) return

  target.width = width * ratio
  target.height = height * ratio
  target.style.height = `${height}px`

  context.setTransform(ratio, 0, 0, ratio, 0, 0)
  context.clearRect(0, 0, width, height)

  const center = height / 2
  const gap = props.compact ? 3 : 4
  const barCount = peaks.length
  const barWidth = Math.max(2, width / barCount - gap)

  context.lineCap = 'round'
  context.strokeStyle = '#8b8cf6'
  context.lineWidth = barWidth

  for (let index = 0; index < barCount; index += 1) {
    const peak = peaks[index] ?? 0
    const barHeight = Math.max(6, peak * height * 0.86)
    const x = index * (barWidth + gap) + barWidth / 2
    context.beginPath()
    context.moveTo(x, center - barHeight / 2)
    context.lineTo(x, center + barHeight / 2)
    context.stroke()
  }
}

function drawWave(data: Float32Array) {
  const barCount = props.compact ? 52 : 88
  const step = Math.max(1, Math.floor(data.length / barCount))
  const peaks = []

  for (let index = 0; index < barCount; index += 1) {
    let peak = 0
    const start = index * step
    const end = Math.min(start + step, data.length)
    for (let cursor = start; cursor < end; cursor += 1) {
      peak = Math.max(peak, Math.abs(data[cursor] ?? 0))
    }
    peaks.push(peak)
  }

  drawBars(peaks)
}

function drawPlaceholder() {
  const barCount = props.compact ? 52 : 88
  const peaks = Array.from({ length: barCount }, (_, index) => {
    const progress = index / Math.max(1, barCount - 1)
    return 0.12 + Math.sin(progress * Math.PI) * 0.34
  })
  drawBars(peaks)
}

async function loadWaveform() {
  const currentVersion = (loadVersion += 1)
  isLoading.value = true
  isPlayable.value = false
  isPlaying.value = false
  stopAudio()
  drawPlaceholder()
  await new Promise(requestAnimationFrame)

  try {
    if (props.assetId) {
      getAudioInfo(props.assetId)
        .then((metadata) => {
          if (currentVersion === loadVersion) {
            emit('metadata', metadata)
          }
        })
        .catch(() => undefined)
    }

    const response = await fetch(props.src)
    const bytes = await response.arrayBuffer()
    const metadata = parseAudioMetadata(bytes)
    if (metadata && currentVersion === loadVersion && !props.assetId) {
      emit('metadata', metadata)
    }
    audioContext ??= new AudioContext()
    const audioBuffer = await audioContext.decodeAudioData(bytes.slice(0))
    if (currentVersion === loadVersion) {
      if (!metadata) {
        emit('metadata', {
          duration: audioBuffer.duration,
          sampleRate: audioBuffer.sampleRate,
        })
      }
      drawWave(audioBuffer.getChannelData(0))
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
onMounted(() => {
  window.addEventListener('solo-audio-play', stopOtherAudio)
  if (audio.value) {
    audio.value.volume = props.volume
  }
  loadWaveform()
})
onBeforeUnmount(() => {
  window.removeEventListener('solo-audio-play', stopOtherAudio)
  stopAudio()
})
</script>

<template>
  <div class="waveform" :class="{ compact }">
    <button class="play-dot" :class="{ loading: isLoading && !isPlaying, pending: !isPlayable }" type="button" @click="togglePlay">
      <span v-if="isLoading && !isPlaying" class="loading-icon"></span>
      <span v-else-if="!isPlaying" class="play-icon"></span>
      <span v-else class="pause-icon"></span>
    </button>
    <canvas ref="canvas"></canvas>
    <audio
      ref="audio"
      preload="auto"
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
  min-height: 180px;
  padding: 18px;
  border-radius: 8px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.waveform.compact {
  grid-template-columns: 36px 1fr;
  gap: 10px;
  min-height: 112px;
  padding: 12px;
}

.play-dot {
  display: grid;
  width: 54px;
  height: 54px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: #5b5fc7;
  box-shadow: 0 10px 24px rgba(91, 95, 199, 0.24);
  cursor: pointer;
}

.play-dot.loading,
.play-dot.pending {
  cursor: progress;
}

.compact .play-dot {
  width: 36px;
  height: 36px;
}

.play-icon {
  width: 0;
  height: 0;
  margin-left: 4px;
  border-top: 9px solid transparent;
  border-bottom: 9px solid transparent;
  border-left: 14px solid #fff;
}

.compact .play-icon {
  border-top-width: 6px;
  border-bottom-width: 6px;
  border-left-width: 9px;
}

.pause-icon {
  width: 16px;
  height: 18px;
  border-right: 5px solid #fff;
  border-left: 5px solid #fff;
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
  border: 3px solid rgba(255, 255, 255, 0.36);
  border-top-color: #fff;
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
  width: 100%;
}

audio {
  display: none;
}
</style>
