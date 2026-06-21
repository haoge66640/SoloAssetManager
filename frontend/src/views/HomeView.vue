<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NDynamicTags,
  NForm,
  NFormItem,
  NIcon,
  NInput,
  NInputGroup,
  NPagination,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSpace,
  NSlider,
  NSpin,
  NSwitch,
  NTag,
  NTooltip,
  useMessage,
} from 'naive-ui'
import {
  AlbumsOutline,
  FolderOutline,
  ImageOutline,
  MusicalNotesOutline,
  PricetagOutline,
  RefreshOutline,
  SettingsOutline,
  TimeOutline,
} from '@vicons/ionicons5'
import { assetFileUrl, copyAssetToTarget, createCategory, getCategories, getCategoryPaths, getWaveformBatch, setCategoryPath, deleteCategoryFromDisk, importAssets, syncCategory } from '@/api/assets'
import AudioWaveform from '@/components/AudioWaveform.vue'
import { useI18n, type Locale } from '@/i18n'
import { useAssetStore } from '@/stores/assets'
import type { Asset, AssetArea, AssetType, TagCategory } from '@/types/asset'

type Section = AssetArea | 'tags' | 'settings'
type AudioInfo = {
  duration: number
  sampleRate: number
  channels?: number
}
const AUTO_PLAY_STORAGE_KEY = 'solo-asset-manager-auto-play'
const AUDIO_VOLUME_STORAGE_KEY = 'solo-asset-manager-audio-volume'

const store = useAssetStore()
const message = useMessage()
const { locale, localeOptions, setLocale, t } = useI18n()

const activeSection = ref<Section>('pending')
const settingsDraft = reactive({
  owner_assets_path: '',
  current_project: '',
  import_path: '',
})
const newProjectName = ref('')
const showNewProjectInput = ref(false)
const newCategoryName = ref('')
const metaForm = reactive({
  source_type: '',
  source_url: '',
  tags: [] as string[],
  note: '',
})
const moveForm = reactive({
  category: '',
})
const audioInfoById = reactive<Record<string, AudioInfo>>({})
const playRequestByKey = reactive<Record<string, number>>({})
const waveformByKey = reactive<Record<string, number[]>>({})
const projectMoveCategories = ref<string[]>([])
const libraryMoveCategories = ref<string[]>([])
const categoryPathsData = ref<Record<string, Record<string, Record<string, string>>>>({})
const newCategoryInputs = reactive<Record<string, string>>({ image: '', audio: '' })
const newLibraryCategoryInputs = reactive<Record<string, string>>({ image: '', audio: '' })
const savingPaths = reactive<Record<string, boolean>>({})
const editingPaths = reactive<Record<string, string>>({})
const newTagInputs = reactive<Record<string, string>>({ general: '', audio: '', image: '' })

async function fetchCategoryPaths(area: 'project' | 'library') {
  try {
    // Get saved paths
    const paths = await getCategoryPaths(area)
    // Also fetch existing categories from disk to ensure all are shown
    const [imageCats, audioCats] = await Promise.all([
      getCategories(area, 'image'),
      getCategories(area, 'audio'),
    ])
    // Merge existing categories into paths data
    const merged: Record<string, Record<string, string>> = {}
    merged.image = {}
    merged.audio = {}
    for (const cat of imageCats) {
      merged.image[cat] = paths.image?.[cat] ?? ''
    }
    for (const cat of audioCats) {
      merged.audio[cat] = paths.audio?.[cat] ?? ''
    }
    categoryPathsData.value[area] = merged
    // Initialize editing paths for all categories
    for (const type of ['image', 'audio'] as const) {
      for (const cat of Object.keys(merged[type] ?? {})) {
        editingPaths[`${area}:${type}:${cat}`] = merged[type]?.[cat] ?? ''
      }
    }
  } catch {
    categoryPathsData.value[area] = {}
  }
}

function getCategoryList(area: string, type: string): string[] {
  const areaData = categoryPathsData.value[area]
  if (!areaData) return []
  const typeData = areaData[type]
  return typeData ? Object.keys(typeData).sort() : []
}

function getCategoryTargetPath(area: string, type: string, category: string): string {
  return categoryPathsData.value[area]?.[type]?.[category] ?? ''
}

async function handleSetPath(area: 'project' | 'library', type: AssetType, category: string, targetPath: string) {
  const key = `${area}:${type}:${category}`
  savingPaths[key] = true
  try {
    await setCategoryPath(area, type, category, targetPath)
    const areaData = categoryPathsData.value[area] ??= {}
    const typeData = areaData[type] ??= {}
    typeData[category] = targetPath
  } catch {
    message.error(t('saveFailed'))
  } finally {
    savingPaths[key] = false
  }
}

async function handleAddCategory(area: 'project' | 'library', type: AssetType) {
  const name = newCategoryInputs[type]?.trim()
  if (!name) return
  newCategoryInputs[type] = ''
  try {
    await createCategory(area, type, name)
    const areaData = categoryPathsData.value[area] ??= {}
    const typeData = areaData[type] ??= {}
    typeData[name] = ''
    editingPaths[`${area}:${type}:${name}`] = ''
    message.success(t('createdCategory'))
  } catch {
    message.error(t('saveFailed'))
  }
}

async function handleDeleteCategory(area: 'project' | 'library', type: AssetType, category: string) {
  try {
    await deleteCategoryFromDisk(area, type, category)
    const typeData = categoryPathsData.value[area]?.[type]
    if (typeData) {
      delete typeData[category]
    }
    delete editingPaths[`${area}:${type}:${category}`]
    message.success(t('deletedCategory'))
  } catch {
    message.error(t('saveFailed'))
  }
}
const currentPage = ref(1)
const pageSize = ref(36)
const autoPlayEnabled = ref(localStorage.getItem(AUTO_PLAY_STORAGE_KEY) === 'true')
const audioVolume = ref(Number(localStorage.getItem(AUDIO_VOLUME_STORAGE_KEY) ?? 80))

const areaOptions = computed(() => [
  { label: t('pendingPool'), value: 'pending' },
  { label: t('project'), value: 'project' },
  { label: t('library'), value: 'library' },
])
const navOptions = computed(() => [...areaOptions.value, { label: t('tagManagement'), value: 'tags' }, { label: t('settings'), value: 'settings' }])
const typeOptions = computed(() => [
  { label: t('image'), value: 'image' },
  { label: t('audio'), value: 'audio' },
])
const sourceOptions = computed(() => [
  { label: t('selfMade'), value: '自制' },
  { label: t('onlineSource'), value: '网络' },
])
const pageSizeOptions = computed(() => [
  { label: '36', value: 36 },
])

const selectedAsset = computed(() => store.selectedAsset)
const pagedAssets = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return store.assets.slice(start, start + pageSize.value)
})
const categoryOptions = computed(() => store.categories.map((name) => ({ label: name, value: name })))
const pendingCategoryTabs = computed(() =>
  store.categories.map((name) => ({
    name,
    label: name,
  })),
)
const moveCategoryOptions = computed(() =>
  Array.from(new Set([...projectMoveCategories.value, ...libraryMoveCategories.value]))
    .sort()
    .map((name) => ({ label: name, value: name })),
)
const formatVersion = ref(0)

const currentFileUrl = computed(() => {
  if (!selectedAsset.value) return ''
  return `${assetFileUrl(selectedAsset.value.id)}?v=${formatVersion.value}`
})

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatDuration(seconds = 0) {
  if (seconds > 0 && seconds < 1.5) {
    return `${Math.round(seconds * 1000)}ms`
  }
  const totalSeconds = Math.max(0, Math.round(seconds))
  const minutes = Math.floor(totalSeconds / 60)
  const restSeconds = totalSeconds % 60
  return `${minutes}:${String(restSeconds).padStart(2, '0')}`
}

function formatSampleRate(sampleRate = 0) {
  if (!sampleRate) return ''
  return `${(sampleRate / 1000).toFixed(1)}kHz`
}

function formatDetailDuration(seconds?: number) {
  if (!seconds) return ''
  return `${seconds.toFixed(3)} ${t('secondsUnit')}`
}

function formatChannels(channels?: number) {
  if (channels === 1) return t('mono')
  if (channels === 2) return t('stereo')
  return ''
}

function saveAudioInfo(assetId: string, info: AudioInfo) {
  audioInfoById[assetId] = info
}

/** 优先返回 Asset 自带的预计算元数据，回退到运行时缓存的元数据 */
function audioMetaOf(asset: Asset): AudioInfo | undefined {
  if (asset.type !== 'audio') return undefined
  if (asset.duration || asset.sample_rate || asset.channels) {
    return { duration: asset.duration, sampleRate: asset.sample_rate, channels: asset.channels }
  }
  return audioInfoById[asset.id]
}

function playRequestKey(assetId: string, surface: 'card' | 'detail') {
  return `${surface}:${assetId}`
}

function requestPreviewPlay(assetId: string, assetType: AssetType, surface: 'card' | 'detail') {
  if (!autoPlayEnabled.value || assetType !== 'audio') return
  const key = playRequestKey(assetId, surface)
  playRequestByKey[key] = (playRequestByKey[key] ?? 0) + 1
}

async function selectAsset(asset: Asset) {
  store.selectedAssetId = asset.id
  await nextTick()
  requestPreviewPlay(asset.id, asset.type, 'card')
}

function selectSection(value: Section) {
  activeSection.value = value
  if (value !== 'settings' && value !== 'tags') {
    store.area = value
  }
  // Load category paths based on target section
  if (value === 'settings') {
    fetchCategoryPaths('project')
    fetchCategoryPaths('library')
  } else if (value === 'tags') {
    fetchCategoryPaths('project')
    store.refreshTags()
  } else if (store.area !== 'pending') {
    fetchCategoryPaths(store.area)
  }
}

function selectType(type: AssetType) {
  store.assetType = type
  selectSection('project')
}

function changeLocale(value: Locale) {
  setLocale(value)
}

async function saveSettings() {
  await store.persistSettings({ ...settingsDraft })
  await store.initializeOwnerAssets()
  message.success(t('savedSettings'))
}

async function createProject() {
  await store.addProject(newProjectName.value)
  settingsDraft.current_project = store.settings.current_project
  newProjectName.value = ''
  showNewProjectInput.value = false
  message.success(t('createdProject'))
}

async function changeProject(value: string) {
  settingsDraft.current_project = value
  await store.persistSettings({ ...store.settings, current_project: value })
  await store.refreshCategories()
  await store.refreshAssets()
  await fetchCategoryPaths('project')
}

async function handleCreateCategory() {
  await store.addCategory(newCategoryName.value)
  newCategoryName.value = ''
  await store.refreshAssets()
  message.success(t('createdCategory'))
}

async function scanAllAssets() {
  await store.scanAndRefresh()
  message.success(t('scanned'))
}

const moveCategoriesCache: { key: string; project: string[]; library: string[] } = { key: '', project: [], library: [] }

async function refreshMoveCategories(asset = selectedAsset.value) {
  if (!asset || asset.area !== 'pending') {
    projectMoveCategories.value = []
    libraryMoveCategories.value = []
    return
  }
  const cacheKey = asset.type
  if (moveCategoriesCache.key === cacheKey) {
    projectMoveCategories.value = moveCategoriesCache.project
    libraryMoveCategories.value = moveCategoriesCache.library
    return
  }
  const [project, library] = await Promise.all([
    getCategories('project', asset.type),
    getCategories('library', asset.type),
  ])
  moveCategoriesCache.key = cacheKey
  moveCategoriesCache.project = project
  moveCategoriesCache.library = library
  projectMoveCategories.value = project
  libraryMoveCategories.value = library
  if (
    moveForm.category
    && !projectMoveCategories.value.includes(moveForm.category)
    && !libraryMoveCategories.value.includes(moveForm.category)
  ) {
    moveForm.category = ''
  }
}

async function moveAsset(targetArea: 'project' | 'library') {
  if (!selectedAsset.value) return
  if (!metaForm.source_type) {
    message.warning(t('selectSourceType'))
    return
  }
  if (!moveForm.category) {
    message.warning(t('selectCategory'))
    return
  }
  await store.movePendingAsset({
    asset_id: selectedAsset.value.id,
    target_area: targetArea,
    category: moveForm.category,
    source_type: metaForm.source_type,
    source_url: metaForm.source_url,
    tags: metaForm.tags,
    note: metaForm.note,
  })
  message.success(t('movedAsset'))
}

async function openFolder() {
  if (!selectedAsset.value) return
  await store.openFolder(selectedAsset.value.id)
}

async function deleteCurrentAsset() {
  if (!selectedAsset.value) return
  await store.deleteAssetById(selectedAsset.value.id)
  message.success(t('deleted'))
}

const isCopyingToTarget = ref(false)
const isSyncingCategory = ref(false)
const isImporting = ref(false)

async function handleCopyToTarget() {
  const asset = selectedAsset.value
  if (!asset) return
  isCopyingToTarget.value = true
  try {
    const result = await copyAssetToTarget(asset.id)
    message.success(t('copiedToTarget', { target: result.target ?? '?' }))
  } catch {
    message.error(t('copyToTargetFailed'))
  } finally {
    isCopyingToTarget.value = false
  }
}

async function permanentDeleteCurrentAsset() {
  if (!selectedAsset.value) return
  await store.permanentDeleteAssetById(selectedAsset.value.id)
  message.success(t('fileDeleted'))
}

const isFormatting = ref(false)
const isSyncingMeta = ref(false)
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

function onSourceUrlChange(value: string) {
  if (metaForm.source_type !== '网络' && value.trim()) {
    metaForm.source_type = '网络'
  }
}

async function formatCurrentAsset() {
  if (!selectedAsset.value || isFormatting.value) return
  isFormatting.value = true
  try {
    await store.formatAssetById(selectedAsset.value.id)
    formatVersion.value += 1
    message.success(t('formatSuccess'))
  } finally {
    isFormatting.value = false
  }
}

// ---- Random rename ----
function getExtension(name: string) {
  const dot = name.lastIndexOf('.')
  return dot > 0 ? name.substring(dot) : ''
}

async function randomRename() {
  if (!selectedAsset.value) return
  const ext = getExtension(selectedAsset.value.name)
  const stem = ext ? selectedAsset.value.name.slice(0, -ext.length) : selectedAsset.value.name
  // If filename already starts with 6 digits, reuse them
  const match = stem.match(/^\d{6}/)
  const prefix = match ? match[0] : String(Math.floor(100000 + Math.random() * 900000))
  const newName = `${prefix}${ext}`
  if (newName === selectedAsset.value.name) return
  await store.renameAssetById(selectedAsset.value.id, newName)
  formatVersion.value += 1
  message.success(t('renamed'))
}

async function handleImport() {
  isImporting.value = true
  try {
    const result = await importAssets()
    if (result.imported.length > 0) {
      message.success(t('importedFiles', { count: result.imported.length }))
    } else {
      message.info(t('importNoFiles'))
    }
  } catch {
    message.error(t('importFailed'))
  } finally {
    isImporting.value = false
    store.refreshAssets()
  }
}

async function handleSyncCategory() {
  if (!store.category || store.area !== 'project') return
  isSyncingCategory.value = true
  try {
    const result = await syncCategory(store.area, store.assetType, store.category)
    if (result.copied.length > 0) {
      message.success(t('syncedFiles', { count: result.copied.length }))
    } else {
      message.info(t('syncNoChanges'))
    }
  } catch {
    message.error(t('syncFailed'))
  } finally {
    isSyncingCategory.value = false
    store.refreshAssets()
  }
}

async function handleCreateTag(category: TagCategory) {
  const name = newTagInputs[category]?.trim()
  if (!name) return
  newTagInputs[category] = ''
  try {
    await store.addTag(category, name)
    message.success(t('createdTag'))
  } catch {
    message.error(t('tagAlreadyExists'))
  }
}

async function handleDeleteTag(category: TagCategory, name: string) {
  try {
    await store.removeTagById(category, name)
    message.success(t('deletedTag'))
  } catch {
    message.error(t('saveFailed'))
  }
}

const tagCategoryOptions = computed(() => [
  { key: 'general', label: t('generalTags') },
  { key: 'audio', label: t('audioTags') },
  { key: 'image', label: t('imageTags') },
] as { key: TagCategory; label: string }[])

function tagsOfCategory(category: TagCategory) {
  return store.tags.filter((tag) => tag.category === category)
}

watch(
  () => store.settings,
  (settings) => {
    settingsDraft.owner_assets_path = settings.owner_assets_path
    settingsDraft.current_project = settings.current_project
    settingsDraft.import_path = settings.import_path ?? ''
  },
  { deep: true },
)

watch(
  selectedAsset,
  (asset) => {
    isSyncingMeta.value = true
    metaForm.source_type = asset?.source_type ?? ''
    metaForm.source_url = asset?.source_url ?? ''
    metaForm.tags = asset?.tags ?? []
    metaForm.note = asset?.note ?? ''
    void refreshMoveCategories(asset)
    // Keep isSyncingMeta true until after Vue flushes pending deep watchers
    void nextTick(() => { isSyncingMeta.value = false })
  },
  { immediate: true },
)

// Auto-save meta form changes with debounce
watch(
  metaForm,
  (newVal, oldVal) => {
    if (isSyncingMeta.value || !selectedAsset.value) return
    const asset = selectedAsset.value
    // Only save if values actually differ from stored asset
    if (newVal.source_type === asset.source_type
      && newVal.source_url === asset.source_url
      && newVal.note === asset.note
      && JSON.stringify(newVal.tags) === JSON.stringify(asset.tags)) return
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    autoSaveTimer = setTimeout(async () => {
      const asset = selectedAsset.value
      if (!asset) return
      await store.updateMeta({
        asset_id: asset.id,
        source_type: metaForm.source_type,
        source_url: metaForm.source_url,
        tags: metaForm.tags,
        note: metaForm.note,
      })
    }, 500)
  },
  { deep: true },
)

watch([() => store.area, () => store.assetType], async () => {
  await store.refreshCategories()
  await store.refreshAssets()
  if (store.area !== 'pending') {
    fetchCategoryPaths(store.area)
  }
})

watch(() => store.category, store.refreshAssets)

watch(
  () => [store.area, store.assetType, store.category, store.keyword],
  () => {
    currentPage.value = 1
  },
)

// 切换分类/翻页时，一次性批量预取当前页音频波形，把 N 个 /assets/waveform/{id} 合并为 1 个请求
watch(
  pagedAssets,
  async (assets) => {
    const audioIds = assets.filter((a) => a.type === 'audio').map((a) => a.id)
    if (audioIds.length === 0) return
    try {
      const waveforms = await getWaveformBatch(audioIds)
      Object.assign(waveformByKey, waveforms)
    } catch {
      // 批量失败时由卡片懒加载回退到单独请求
    }
  },
  { immediate: true },
)

watch(
  () => store.assets.length,
  () => {
    const maxPage = Math.max(1, Math.ceil(store.assets.length / pageSize.value))
    currentPage.value = Math.min(currentPage.value, maxPage)
  },
)

watch(pageSize, () => {
  currentPage.value = 1
})

watch(autoPlayEnabled, (value) => {
  localStorage.setItem(AUTO_PLAY_STORAGE_KEY, String(value))
})

watch(audioVolume, (value) => {
  localStorage.setItem(AUDIO_VOLUME_STORAGE_KEY, String(value))
})

onMounted(async () => {
  await store.loadSettings()
  await store.refreshProjects()
  await store.refreshCategories()
  await store.refreshAssets()
  if (store.area !== 'pending') {
    fetchCategoryPaths(store.area)
  }
})
</script>

<template>
  <div class="asset-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-icon">SAM</div>
        <div>
          <h1>{{ t('appTitle') }}</h1>
          <p>{{ t('appSubtitle') }}</p>
        </div>
      </div>

      <div class="nav-label">Workspace</div>
      <nav class="nav-list">
        <button
          :class="{ active: activeSection === 'pending' }"
          @click="selectSection('pending')"
        >
          <n-icon size="18"><TimeOutline /></n-icon>
          <span>{{ t('pendingPool') }}</span>
        </button>

        <div class="nav-group">
          <button
            class="nav-trigger"
            :class="{ active: activeSection === 'project' }"
            @click="selectSection('project')"
          >
            <n-icon size="18"><FolderOutline /></n-icon>
            <span>{{ t('project') }}</span>
          </button>
          <div class="nav-subs">
            <button
              v-for="opt in typeOptions"
              :key="opt.value"
              class="nav-sub"
              :class="{ active: activeSection === 'project' && store.assetType === opt.value }"
              @click="selectType(opt.value as AssetType)"
            >
              <n-icon size="16">
                <ImageOutline v-if="opt.value === 'image'" />
                <MusicalNotesOutline v-else />
              </n-icon>
              <span>{{ opt.label }}</span>
            </button>
          </div>
        </div>

        <button
          :class="{ active: activeSection === 'library' }"
          @click="selectSection('library')"
        >
          <n-icon size="18"><AlbumsOutline /></n-icon>
          <span>{{ t('library') }}</span>
        </button>

        <button
          :class="{ active: activeSection === 'tags' }"
          @click="selectSection('tags')"
        >
          <n-icon size="18"><PricetagOutline /></n-icon>
          <span>{{ t('tagManagement') }}</span>
        </button>

        <button
          :class="{ active: activeSection === 'settings' }"
          @click="selectSection('settings')"
        >
          <n-icon size="18"><SettingsOutline /></n-icon>
          <span>{{ t('settings') }}</span>
        </button>
      </nav>
    </aside>

    <main class="main-panel">
      <header class="toolbar">
        <template v-if="activeSection !== 'settings' && activeSection !== 'tags'">
          <n-input
            v-model:value="store.keyword"
            class="search"
            clearable
            :placeholder="t('searchPlaceholder')"
            @keyup.enter="store.refreshAssets"
          />
          <n-button @click="store.refreshAssets">{{ t('search') }}</n-button>
          <n-button @click="store.refreshCurrent">{{ t('refreshCurrent') }}</n-button>
        </template>
        <div v-else-if="activeSection === 'tags'" class="toolbar-title">{{ t('tagManagement') }}</div>
        <div v-else class="toolbar-title">{{ t('settings') }}</div>
        <div class="toolbar-controls">
          <n-button
            type="warning"
            size="small"
            secondary
            @click="scanAllAssets"
            :loading="store.loading"
          >
            <template #icon>
              <n-icon size="16"><RefreshOutline /></n-icon>
            </template>
            {{ t('refreshAll') }}
          </n-button>
          <div class="auto-play-control">
            <span>{{ t('autoPlay') }}</span>
            <n-switch v-model:value="autoPlayEnabled" size="small" />
          </div>
          <div class="volume-control">
            <span>{{ t('volume') }}</span>
            <n-slider v-model:value="audioVolume" :min="0" :max="100" :step="1" />
            <strong>{{ audioVolume }}</strong>
          </div>
        </div>
        <n-select
          class="locale-select"
          :value="locale"
          :options="localeOptions"
          @update:value="changeLocale"
        />
      </header>

      <section v-if="activeSection === 'tags'" class="settings-page">
        <h2 class="settings-page-title">{{ t('tagManagement') }}</h2>
        <div class="settings-grid">
          <div v-for="cat in tagCategoryOptions" :key="cat.key" class="settings-card">
            <div class="card-head">
              <div class="card-accent" :class="{ 'card-accent--green': cat.key === 'audio', 'card-accent--orange': cat.key === 'image' }"></div>
              <div class="card-title">
                <n-icon size="20" class="card-icon">
                  <PricetagOutline />
                </n-icon>
                <div>
                  <h3>{{ cat.label }}</h3>
                </div>
              </div>
            </div>
            <div class="card-body">
              <div class="tag-list">
                <div v-for="tag in tagsOfCategory(cat.key)" :key="tag.name" class="tag-row">
                  <n-tag type="info" size="medium">{{ tag.name }}</n-tag>
                  <span class="tag-count">{{ t('tagCount') }}: {{ tag.count }}</span>
                  <button class="cat-path-del" type="button" @click="handleDeleteTag(cat.key, tag.name)">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="3 6 5 6 21 6"/>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                  </button>
                </div>
                <div v-if="tagsOfCategory(cat.key).length === 0" class="tag-empty">{{ t('all') }} 0</div>
              </div>
              <div class="input-row input-row--add">
                <n-input v-model:value="newTagInputs[cat.key]" size="small" :placeholder="t('newTagName')" @keyup.enter="handleCreateTag(cat.key)" />
                <n-button size="small" @click="handleCreateTag(cat.key)">{{ t('createTag') }}</n-button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-else-if="activeSection === 'settings'" class="cfg-page">
        <header class="cfg-header">
          <div>
            <h2>{{ t('settings') }}</h2>
            <p>{{ t('assetSettingsDesc') }}</p>
          </div>
        </header>

        <!-- 概览状态条 -->
        <div class="cfg-overview">
          <div class="cfg-overview-item">
            <span class="cfg-overview-label">{{ t('currentProject') }}</span>
            <strong class="cfg-overview-value">{{ settingsDraft.current_project || '—' }}</strong>
          </div>
          <span class="cfg-overview-sep"></span>
          <div class="cfg-overview-item">
            <span class="cfg-overview-label">{{ t('ownerAssetsPath') }}</span>
            <strong class="cfg-overview-value" :title="settingsDraft.owner_assets_path">{{ settingsDraft.owner_assets_path || '—' }}</strong>
          </div>
          <span class="cfg-overview-sep"></span>
          <div class="cfg-overview-item">
            <span class="cfg-overview-label">{{ t('importPath') }}</span>
            <strong class="cfg-overview-value" :title="settingsDraft.import_path">{{ settingsDraft.import_path || '—' }}</strong>
          </div>
        </div>

        <!-- 存储路径配置 -->
        <section class="cfg-section">
          <div class="cfg-section-head">
            <div class="cfg-accent"></div>
            <div class="cfg-section-title">
              <svg class="cfg-section-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <div>
                <h3>{{ t('assetSettings') }}</h3>
                <p>{{ t('assetSettingsDesc') }}</p>
              </div>
            </div>
          </div>
          <div class="cfg-section-body">
            <div class="cfg-field">
              <label>{{ t('ownerAssetsPath') }}</label>
              <n-input v-model:value="settingsDraft.owner_assets_path" :placeholder="t('ownerAssetsPlaceholder')" />
            </div>
            <div class="cfg-field">
              <label>{{ t('importPath') }}</label>
              <n-input v-model:value="settingsDraft.import_path" :placeholder="t('importPathPlaceholder')" />
            </div>
            <div class="cfg-actions">
              <n-button type="primary" size="large" @click="saveSettings">{{ t('saveAndInitialize') }}</n-button>
            </div>
          </div>
        </section>

        <!-- 项目管理 + 项目分类路径（合并，体现绑定关系） -->
        <section class="cfg-section">
          <div class="cfg-section-head">
            <div class="cfg-accent cfg-accent--teal"></div>
            <div class="cfg-section-title">
              <svg class="cfg-section-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              </svg>
              <div>
                <h3>{{ t('projectManagement') }}</h3>
                <p>{{ t('projectManagementDesc') }}</p>
              </div>
            </div>
          </div>
          <div class="cfg-section-body">
            <!-- 项目选择 + 新建项目（低权重） -->
            <div class="cfg-project-bar">
              <div class="cfg-field cfg-field--grow">
                <label>{{ t('currentProject') }}</label>
                <n-select
                  v-model:value="settingsDraft.current_project"
                  :options="store.projects.map((name) => ({ label: name, value: name }))"
                  :placeholder="t('projectPlaceholder')"
                  @update:value="changeProject"
                />
              </div>
              <button
                v-if="!showNewProjectInput"
                class="cfg-ghost-link"
                type="button"
                @click="showNewProjectInput = true"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19"/>
                  <line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                {{ t('newProject') }}
              </button>
              <div v-else class="cfg-new-project-inline">
                <n-input v-model:value="newProjectName" size="small" :placeholder="t('newProjectName')" @keyup.enter="createProject" />
                <n-button size="small" type="primary" @click="createProject">{{ t('create') }}</n-button>
                <button class="cfg-ghost-link cfg-ghost-link--close" type="button" @click="showNewProjectInput = false; newProjectName = ''">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>

            <!-- 上下文绑定分隔条 -->
            <div class="cfg-context-bar">
              <span class="cfg-context-text">{{ t('categoryPaths') }}</span>
              <span class="cfg-context-arrow">›</span>
              <span class="cfg-context-chip">{{ settingsDraft.current_project || '—' }}</span>
            </div>

            <!-- 当前项目的分类路径 -->
            <div class="cfg-cat-grid">
              <!-- 图片分类 -->
              <div class="cfg-cat-col">
                <div class="cfg-cat-head">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                  </svg>
                  <span>{{ t('imageCategories') }}</span>
                  <em>{{ getCategoryList('project', 'image').length }}</em>
                </div>
                <div class="cfg-cat-list">
                  <div v-for="cat in getCategoryList('project', 'image')" :key="'image:' + cat" class="cfg-cat-row">
                    <span class="cfg-cat-name">{{ cat }}</span>
                    <div class="cfg-cat-input">
                      <n-input
                        v-model:value="editingPaths['project:image:' + cat]"
                        size="small"
                        :placeholder="t('targetPathPlaceholder')"
                        :loading="savingPaths['image:' + cat]"
                        @blur="handleSetPath('project', 'image', cat, editingPaths['project:image:' + cat] ?? '')"
                      />
                    </div>
                    <button class="cat-path-del" type="button" title="删除" @click="handleDeleteCategory('project', 'image', cat)">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
                  <div v-if="getCategoryList('project', 'image').length === 0" class="cfg-cat-empty">—</div>
                </div>
                <div class="cfg-input-row cfg-input-row--add">
                  <n-input v-model:value="newCategoryInputs.image" size="small" :placeholder="t('addCategory')" @keyup.enter="handleAddCategory('project', 'image')" />
                  <n-button size="small" @click="handleAddCategory('project', 'image')">{{ t('create') }}</n-button>
                </div>
              </div>

              <!-- 音频分类 -->
              <div class="cfg-cat-col">
                <div class="cfg-cat-head">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 18V5l12-2v13"/>
                    <circle cx="6" cy="18" r="3"/>
                    <circle cx="18" cy="16" r="3"/>
                  </svg>
                  <span>{{ t('audioCategories') }}</span>
                  <em>{{ getCategoryList('project', 'audio').length }}</em>
                </div>
                <div class="cfg-cat-list">
                  <div v-for="cat in getCategoryList('project', 'audio')" :key="'audio:' + cat" class="cfg-cat-row">
                    <span class="cfg-cat-name">{{ cat }}</span>
                    <div class="cfg-cat-input">
                      <n-input
                        v-model:value="editingPaths['project:audio:' + cat]"
                        size="small"
                        :placeholder="t('targetPathPlaceholder')"
                        :loading="savingPaths['audio:' + cat]"
                        @blur="handleSetPath('project', 'audio', cat, editingPaths['project:audio:' + cat] ?? '')"
                      />
                    </div>
                    <button class="cat-path-del" type="button" title="删除" @click="handleDeleteCategory('project', 'audio', cat)">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
                  <div v-if="getCategoryList('project', 'audio').length === 0" class="cfg-cat-empty">—</div>
                </div>
                <div class="cfg-input-row cfg-input-row--add">
                  <n-input v-model:value="newCategoryInputs.audio" size="small" :placeholder="t('addCategory')" @keyup.enter="handleAddCategory('project', 'audio')" />
                  <n-button size="small" @click="handleAddCategory('project', 'audio')">{{ t('create') }}</n-button>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 仓库分类管理（仅增删分类，无目标路径） -->
        <section class="cfg-section">
          <div class="cfg-section-head">
            <div class="cfg-accent cfg-accent--rose"></div>
            <div class="cfg-section-title">
              <svg class="cfg-section-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                <line x1="12" y1="22.08" x2="12" y2="12"/>
              </svg>
              <div>
                <h3>{{ t('libraryCategories') }}</h3>
                <p>{{ t('libraryCategoriesDesc') }}</p>
              </div>
            </div>
          </div>
          <div class="cfg-section-body">
            <div class="cfg-cat-grid">
              <!-- 仓库图片分类 -->
              <div class="cfg-cat-col">
                <div class="cfg-cat-head">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                  </svg>
                  <span>{{ t('imageCategories') }}</span>
                  <em>{{ getCategoryList('library', 'image').length }}</em>
                </div>
                <div class="cfg-cat-list">
                  <div v-for="cat in getCategoryList('library', 'image')" :key="'lib:image:' + cat" class="cfg-cat-row cfg-cat-row--simple">
                    <span class="cfg-cat-name">{{ cat }}</span>
                    <button class="cat-path-del" type="button" title="删除" @click="handleDeleteCategory('library', 'image', cat)">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
                  <div v-if="getCategoryList('library', 'image').length === 0" class="cfg-cat-empty">—</div>
                </div>
                <div class="cfg-input-row cfg-input-row--add">
                  <n-input v-model:value="newLibraryCategoryInputs.image" size="small" :placeholder="t('addCategory')" @keyup.enter="handleAddCategory('library', 'image')" />
                  <n-button size="small" @click="handleAddCategory('library', 'image')">{{ t('create') }}</n-button>
                </div>
              </div>

              <!-- 仓库音频分类 -->
              <div class="cfg-cat-col">
                <div class="cfg-cat-head">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 18V5l12-2v13"/>
                    <circle cx="6" cy="18" r="3"/>
                    <circle cx="18" cy="16" r="3"/>
                  </svg>
                  <span>{{ t('audioCategories') }}</span>
                  <em>{{ getCategoryList('library', 'audio').length }}</em>
                </div>
                <div class="cfg-cat-list">
                  <div v-for="cat in getCategoryList('library', 'audio')" :key="'lib:audio:' + cat" class="cfg-cat-row cfg-cat-row--simple">
                    <span class="cfg-cat-name">{{ cat }}</span>
                    <button class="cat-path-del" type="button" title="删除" @click="handleDeleteCategory('library', 'audio', cat)">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
                  <div v-if="getCategoryList('library', 'audio').length === 0" class="cfg-cat-empty">—</div>
                </div>
                <div class="cfg-input-row cfg-input-row--add">
                  <n-input v-model:value="newLibraryCategoryInputs.audio" size="small" :placeholder="t('addCategory')" @keyup.enter="handleAddCategory('library', 'audio')" />
                  <n-button size="small" @click="handleAddCategory('library', 'audio')">{{ t('create') }}</n-button>
                </div>
              </div>
            </div>
          </div>
        </section>
      </section>

      <section v-else class="content">
        <div class="asset-list-panel">
          <div class="filter-row">
            <div v-if="store.area === 'pending'" class="filter-bar">
              <div class="pending-tabs">
                <button
                  class="pending-tab"
                  :class="{ active: store.category === '' }"
                  type="button"
                  @click="store.category = ''"
                >
                  {{ t('all') }}
                </button>
                <n-tooltip v-for="item in pendingCategoryTabs" :key="item.name" trigger="hover">
                  <template #trigger>
                    <button
                      class="pending-tab"
                      :class="{ active: store.category === item.name }"
                      type="button"
                      @click="store.category = item.name"
                    >
                      {{ item.label }}
                    </button>
                  </template>
                  {{ item.name }}
                </n-tooltip>
              </div>
              <div class="filter-actions">
                <n-button
                  size="small"
                  type="primary"
                  :loading="isImporting"
                  :disabled="isImporting"
                  @click="handleImport"
                >
                  {{ t('importAssets') }}
                </n-button>
              </div>
            </div>

            <template v-else>
              <n-radio-group
                v-if="store.area === 'library'"
                v-model:value="store.assetType"
                button-style="solid"
                size="small"
              >
                <n-radio-button v-for="option in typeOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </n-radio-button>
              </n-radio-group>

              <div class="filter-bar">
                <div class="category-tabs">
                  <button
                    class="pending-tab"
                    :class="{ active: store.category === '' }"
                    type="button"
                    @click="store.category = ''"
                  >
                    {{ t('all') }}
                  </button>
                  <n-tooltip
                    v-for="cat in categoryOptions"
                    :key="cat.value"
                    trigger="hover"
                    :disabled="!getCategoryTargetPath(store.area, store.assetType, cat.value)"
                  >
                    <template #trigger>
                      <button
                        class="pending-tab"
                        :class="{ active: store.category === cat.value }"
                        type="button"
                        @click="store.category = cat.value"
                      >
                        {{ cat.label }}
                      </button>
                    </template>
                    {{ getCategoryTargetPath(store.area, store.assetType, cat.value) }}
                  </n-tooltip>
                  <div class="inline-create">
                    <n-input
                      v-model:value="newCategoryName"
                      :placeholder="t('newCategoryName')"
                      size="tiny"
                      class="inline-create-input"
                      @keyup.enter="handleCreateCategory"
                    />
                    <n-button size="tiny" @click="handleCreateCategory">{{ t('create') }}</n-button>
                  </div>
                </div>
                <div class="filter-actions">
                  <n-button
                    v-if="store.area === 'project'"
                    size="small"
                    type="primary"
                    :disabled="!store.category || isSyncingCategory"
                    :loading="isSyncingCategory"
                    @click="handleSyncCategory"
                  >
                    {{ t('syncCategory') }}
                  </n-button>
                </div>
              </div>
            </template>
          </div>

          <div class="asset-scroll">
          <n-spin :show="store.loading">
            <div class="asset-grid">
              <div
                v-for="asset in pagedAssets"
                :key="asset.id"
                class="asset-card"
                role="button"
                tabindex="0"
                :class="{ selected: store.selectedAssetId === asset.id }"
                @click="selectAsset(asset)"
                @keydown.enter="selectAsset(asset)"
              >
                <div class="preview">
                  <span class="format-badge">{{ asset.format.toUpperCase() }}</span>
                  <img v-if="asset.type === 'image'" :src="assetFileUrl(asset.id)" :alt="asset.name" />
                  <AudioWaveform
                    v-else
                    compact
                    lazy
                    :src="assetFileUrl(asset.id)"
                    :asset-id="asset.id"
                    :volume="audioVolume / 100"
                    :metadata="audioMetaOf(asset)"
                    :initial-peaks="waveformByKey[asset.id]"
                    :play-request="playRequestByKey[playRequestKey(asset.id, 'card')] ?? 0"
                    @metadata="saveAudioInfo(asset.id, $event)"
                  />
                </div>
                <div class="asset-name">{{ asset.name }}</div>
                <div v-if="asset.type === 'audio'" class="asset-audio-meta">
                  <span>{{ asset.format.toUpperCase() }}</span>
                  <span v-if="audioMetaOf(asset)?.sampleRate">{{ formatSampleRate(audioMetaOf(asset)?.sampleRate) }}</span>
                  <span v-if="audioMetaOf(asset)?.duration" class="duration-pill">
                    {{ formatDuration(audioMetaOf(asset)?.duration) }}
                  </span>
                </div>
                <div v-else class="asset-audio-meta">
                  <span>{{ asset.format.toUpperCase() }}</span>
                  <span>{{ formatSize(asset.size) }}</span>
                </div>
                <div class="tag-line">
                  <n-tag v-for="tag in asset.tags" :key="tag" size="small" type="info">{{ tag }}</n-tag>
                </div>
              </div>
            </div>
          </n-spin>
          </div>

          <div class="pagination-row">
            <span class="total-text">{{ t('totalItems', { count: store.assets.length }) }}</span>
            <div class="page-size">
              <span>{{ t('pageSize') }}</span>
              <n-select v-model:value="pageSize" :options="pageSizeOptions" />
            </div>
            <n-pagination
              v-model:page="currentPage"
              :page-size="pageSize"
              :item-count="store.assets.length"
            />
          </div>
        </div>

        <aside class="detail-panel">
          <template v-if="selectedAsset">
            <div class="detail-header">
              <h2>{{ t('assetDetails') }}</h2>
              <n-button size="tiny" quaternary class="header-open-btn" @click="openFolder">
                <template #icon>
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                </template>
                {{ t('openFolder') }}
              </n-button>
            </div>

            <div
              class="detail-preview"
              @click="requestPreviewPlay(selectedAsset.id, selectedAsset.type, 'detail')"
            >
              <img v-if="selectedAsset.type === 'image'" :src="currentFileUrl" :alt="selectedAsset.name" />
              <AudioWaveform
                v-else
                :src="currentFileUrl"
                :asset-id="selectedAsset.id"
                :volume="audioVolume / 100"
                :metadata="audioMetaOf(selectedAsset)"
                :initial-peaks="waveformByKey[selectedAsset.id]"
                :play-request="playRequestByKey[playRequestKey(selectedAsset.id, 'detail')] ?? 0"
                @metadata="saveAudioInfo(selectedAsset.id, $event)"
              />
            </div>

            <div class="detail-title" title="点击随机重命名" @click="randomRename">
              <span class="display-name">
                {{ selectedAsset.name }}
                <svg class="shuffle-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
                </svg>
              </span>
            </div>

            <!-- 操作区（最高频，上移） -->
            <div class="detail-actions">
              <template v-if="selectedAsset.area === 'pending'">
                <section class="move-panel">
                  <h3>{{ t('organizeAsset') }}</h3>
                  <div class="move-category-row">
                    <span>{{ t('category') }}</span>
                    <n-select
                      v-model:value="moveForm.category"
                      filterable
                      tag
                      :options="moveCategoryOptions"
                      :placeholder="t('category')"
                    />
                  </div>
                  <div class="move-button-row">
                    <n-button type="primary" block @click="moveAsset('project')">{{ t('moveToProject') }}</n-button>
                    <n-button block @click="moveAsset('library')">{{ t('moveToLibrary') }}</n-button>
                  </div>
                </section>
                <n-button block type="error" @click="permanentDeleteCurrentAsset">
                  {{ t('deleteFile') }}
                </n-button>
              </template>
              <template v-else>
                <n-button
                  v-if="selectedAsset.category"
                  block
                  type="primary"
                  :loading="isCopyingToTarget"
                  :disabled="isCopyingToTarget"
                  @click="handleCopyToTarget"
                >
                  {{ t('copyToTarget') }}
                </n-button>
                <n-button block type="warning" @click="deleteCurrentAsset">
                  {{ t('deleteAsset') }}
                </n-button>
              </template>
            </div>

            <!-- 来源信息（次高频） -->
            <div class="detail-source">
              <div class="source-row">
                <span class="source-label">{{ t('sourceType') }}</span>
                <n-radio-group v-model:value="metaForm.source_type" class="source-radio-group">
                  <n-radio-button v-for="option in sourceOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </n-radio-button>
                </n-radio-group>
              </div>
              <div class="source-row">
                <span class="source-label">{{ t('sourceUrl') }}</span>
                <n-input v-model:value="metaForm.source_url" size="small" @update:value="onSourceUrlChange" />
              </div>
            </div>

            <!-- 属性（合并为一个紧凑表格） -->
            <div class="property-header">
              <h3>{{ t('properties') }}</h3>
              <n-button
                v-if="selectedAsset.type === 'audio'"
                size="tiny"
                :loading="isFormatting"
                :disabled="isFormatting"
                class="format-btn"
                @click="formatCurrentAsset"
              >
                {{ t('formatAction') }}
              </n-button>
            </div>
            <div class="detail-table">
              <div v-if="selectedAsset.type === 'audio'">
                <span>{{ t('duration') }}</span>
                <strong>{{ formatDetailDuration(audioMetaOf(selectedAsset)?.duration) }}</strong>
              </div>
              <div v-if="selectedAsset.type === 'audio'">
                <span>{{ t('sampleRate') }}</span>
                <strong>{{ formatSampleRate(audioMetaOf(selectedAsset)?.sampleRate) }}</strong>
              </div>
              <div>
                <span>{{ t('format') }}</span>
                <strong>{{ selectedAsset.format }}</strong>
              </div>
              <div v-if="selectedAsset.type === 'audio' && formatChannels(audioMetaOf(selectedAsset)?.channels)">
                <span>{{ t('channels') }}</span>
                <strong>{{ formatChannels(audioMetaOf(selectedAsset)?.channels) }}</strong>
              </div>
              <div>
                <span>{{ t('size') }}</span>
                <strong>{{ formatSize(selectedAsset.size) }}</strong>
              </div>
              <div>
                <span>{{ t('modifiedAt') }}</span>
                <strong>{{ selectedAsset.modified_at }}</strong>
              </div>
            </div>

            <!-- 标签 + 备注（低频，底部） -->
            <div class="detail-meta">
              <div class="meta-field">
                <label>{{ t('tags') }}</label>
                <n-dynamic-tags v-model:value="metaForm.tags" size="small" />
              </div>
              <div class="meta-field">
                <label>{{ t('note') }}</label>
                <n-input v-model:value="metaForm.note" type="textarea" :autosize="{ minRows: 1, maxRows: 3 }" size="small" />
              </div>
            </div>
          </template>

          <div v-else class="empty-detail">{{ t('noAssetSelected') }}</div>
        </aside>
      </section>
    </main>
  </div>
</template>

<style scoped>
.asset-shell {
  display: grid;
  grid-template-columns: 264px 1fr;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-base);
  color: var(--text);
  position: relative;
}

/* ---------- Sidebar ---------- */
.sidebar {
  position: relative;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background:
    radial-gradient(120% 55% at 0% 0%, rgba(245, 165, 36, 0.09), transparent 60%),
    linear-gradient(180deg, #16191f 0%, #11131a 100%);
  padding: 22px 18px 18px;
  overflow: hidden;
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 24px;
  padding: 4px 6px 18px;
  border-bottom: 1px solid var(--border);
}

.brand-icon {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: 12px;
  background: linear-gradient(140deg, #f5a524 0%, #d97706 100%);
  color: #1a1206;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 13px;
  letter-spacing: -0.02em;
  box-shadow: 0 8px 22px rgba(245, 165, 36, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.32);
}

.brand h1 {
  margin: 0;
  font-family: 'Bricolage Grotesque', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}

.brand p {
  margin: 2px 0 0;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-3);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.nav-label {
  margin: 0 6px 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-3);
}

.nav-list {
  display: grid;
  gap: 4px;
}

.nav-list > button {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  padding: 11px 14px;
  text-align: left;
  transition: background 0.18s, color 0.18s;
}

.nav-list > button:hover {
  background: rgba(255, 255, 255, 0.045);
  color: var(--text);
}

.nav-list > button.active {
  background: var(--amber-soft);
  color: var(--amber);
  font-weight: 600;
}

.nav-list > button.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 0 3px 3px 0;
  background: var(--amber);
  box-shadow: 0 0 12px var(--amber-glow);
}

.nav-group {
  display: grid;
  gap: 2px;
}

.nav-trigger {
  margin-bottom: 0 !important;
}

.nav-trigger.active {
  background: var(--amber-soft) !important;
  color: var(--amber) !important;
  font-weight: 700;
}

.nav-subs {
  display: grid;
  gap: 2px;
  padding: 4px 0 6px 16px;
  margin-left: 14px;
  border-left: 1px solid var(--border);
}

.nav-sub {
  display: flex;
  align-items: center;
  gap: 9px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  font-size: 13px;
  padding: 8px 12px;
  text-align: left;
  transition: background 0.15s, color 0.15s;
}

.nav-sub:hover {
  background: rgba(255, 255, 255, 0.045);
  color: var(--text);
}

.nav-sub.active {
  background: rgba(45, 212, 191, 0.12);
  color: var(--teal);
  font-weight: 600;
}

/* ---------- Main panel ---------- */
.main-panel {
  display: grid;
  grid-template-rows: 68px 1fr;
  min-width: 0;
  min-height: 0;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  height: 68px;
  border-bottom: 1px solid var(--border);
  background: rgba(20, 23, 29, 0.72);
  backdrop-filter: blur(12px);
  padding: 0 22px;
}

.search {
  max-width: 560px;
}

.toolbar-title {
  font-family: 'Bricolage Grotesque', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: var(--text);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.toolbar-controls {
  display: flex;
  gap: 18px;
  align-items: center;
  margin-left: auto;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.025);
}

.auto-play-control,
.volume-control {
  display: flex;
  gap: 9px;
  align-items: center;
  color: var(--text-2);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.volume-control {
  width: 168px;
}

.volume-control :deep(.n-slider) {
  flex: 1;
}

.volume-control strong {
  width: 30px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text);
  font-weight: 600;
  font-size: 12px;
  text-align: right;
}

.locale-select {
  width: 128px;
}

/* ---------- Content layout ---------- */
.content {
  display: grid;
  grid-template-columns: 1fr 348px;
  gap: 16px;
  min-height: 0;
  padding: 16px;
  overflow: hidden;
}

/* ---------- Settings / Tags pages ---------- */
.settings-page {
  min-height: 0;
  overflow: auto;
  padding: 28px 32px;
}

.settings-page-title {
  margin: 0 0 24px;
  font-family: 'Bricolage Grotesque', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 20px;
  max-width: 980px;
}

.settings-card {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: linear-gradient(180deg, #1d2129 0%, #191c24 100%);
  overflow: hidden;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.3);
  transition: border-color 0.2s;
}

.settings-card:hover {
  border-color: var(--border-strong);
}

.card-head {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 20px 22px 0;
}

.card-accent {
  flex-shrink: 0;
  width: 4px;
  height: 38px;
  border-radius: 3px;
  background: linear-gradient(180deg, var(--amber), #d97706);
  margin-top: 2px;
  box-shadow: 0 0 16px var(--amber-glow);
}

.card-accent--green {
  background: linear-gradient(180deg, var(--teal), #0f9688);
  box-shadow: 0 0 16px rgba(45, 212, 191, 0.35);
}

.card-accent--orange {
  background: linear-gradient(180deg, var(--rose), #e11d48);
  box-shadow: 0 0 16px rgba(251, 113, 133, 0.35);
}

.card-title {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.card-icon {
  flex-shrink: 0;
  color: var(--text-2);
}

.card-title h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

.card-title p {
  margin: 3px 0 0;
  font-size: 12px;
  color: var(--text-3);
}

.card-body {
  display: grid;
  gap: 16px;
  padding: 18px 22px 24px;
}

.field {
  display: grid;
  gap: 7px;
}

.field label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--text-2);
  text-transform: uppercase;
}

.input-row {
  display: flex;
  gap: 8px;
}

.input-row :deep(.n-input) {
  flex: 1;
}

.card-body--compact {
  gap: 14px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.type-section {
  display: grid;
  gap: 8px;
}

.type-section-header {
  display: flex;
  gap: 7px;
  align-items: center;
  color: var(--text-2);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding-bottom: 2px;
}

.cat-path-list {
  display: grid;
  gap: 6px;
}

.cat-path-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
}

.cat-path-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--text-2);
  min-width: 48px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cat-path-input-wrap {
  min-width: 0;
}

.cat-path-input-wrap :deep(.n-input) {
  width: 100%;
}

.cat-path-del {
  flex-shrink: 0;
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.cat-path-del:hover {
  background: rgba(248, 113, 113, 0.14);
  color: #f87171;
}

.input-row--add {
  margin-top: 2px;
}

.tag-list {
  display: grid;
  gap: 8px;
}

.tag-row {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 7px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid var(--border);
}

.tag-count {
  margin-left: auto;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-3);
  font-size: 12px;
}

.tag-empty {
  padding: 16px;
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
  border: 1px dashed var(--border);
  border-radius: 8px;
}

/* ---------- Asset list panel ---------- */
.asset-list-panel,
.detail-panel {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: linear-gradient(180deg, #1a1e26 0%, #161920 100%);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.3);
}

.asset-list-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 16px;
}

.asset-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.filter-row {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}

.pending-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  width: 100%;
  max-height: 100px;
  overflow-x: hidden;
  overflow-y: auto;
  padding-right: 4px;
}

.pending-tab {
  flex: 0 0 auto;
  width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.025);
  color: var(--text-2);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
  padding: 10px 14px;
  text-align: center;
  transition: border-color 0.16s, color 0.16s, background 0.16s;
}

.pending-tab:hover {
  border-color: var(--border-strong);
  color: var(--text);
  background: rgba(255, 255, 255, 0.05);
}

.pending-tab.active {
  border-color: var(--amber);
  background: var(--amber-soft);
  color: var(--amber);
  font-weight: 700;
  box-shadow: 0 0 0 1px var(--amber-glow);
}

.filter-bar {
  display: flex;
  flex: 1;
  gap: 12px;
  align-items: flex-start;
  min-width: 0;
}

.category-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.filter-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
  padding-top: 3px;
}

.inline-create {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-shrink: 0;
}

.inline-create-input {
  width: 100px;
}

/* ---------- Asset grid ---------- */
.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(184px, 1fr));
  gap: 14px;
}

.pagination-row {
  flex-shrink: 0;
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: flex-end;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.total-text {
  margin-right: auto;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-3);
  font-size: 12px;
}

.page-size {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--text-2);
  font-size: 12px;
}

.page-size :deep(.n-select) {
  width: 86px;
}

.asset-card {
  display: grid;
  gap: 9px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--bg-card);
  cursor: pointer;
  padding: 10px;
  text-align: left;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s cubic-bezier(0.2, 0.7, 0.3, 1), border-color 0.2s,
    box-shadow 0.2s;
  animation: card-in 0.42s cubic-bezier(0.2, 0.7, 0.3, 1) both;
}

.asset-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--amber), transparent);
  opacity: 0;
  transition: opacity 0.2s;
}

.asset-card:hover {
  transform: translateY(-3px);
  border-color: var(--border-strong);
  box-shadow: 0 16px 34px rgba(0, 0, 0, 0.45);
}

.asset-card:hover::before {
  opacity: 1;
}

.asset-card.selected {
  border-color: var(--amber);
  box-shadow: 0 0 0 2px var(--amber-glow), 0 16px 34px rgba(0, 0, 0, 0.45);
}

.asset-card.selected::before {
  opacity: 1;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.preview {
  display: grid;
  position: relative;
  height: 116px;
  place-items: center;
  border-radius: 9px;
  background:
    radial-gradient(80% 60% at 50% 0%, rgba(255, 255, 255, 0.045), transparent),
    #0f1218;
  border: 1px solid var(--border);
  overflow: hidden;
}

.format-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 1;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  background: rgba(14, 16, 20, 0.82);
  backdrop-filter: blur(6px);
  color: var(--text);
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  line-height: 1;
  padding: 5px 7px;
}

.preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: transform 0.3s;
}

.asset-card:hover .preview img {
  transform: scale(1.04);
}

.asset-name {
  overflow: hidden;
  color: var(--text);
  font-weight: 600;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-audio-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-3);
  font-size: 11px;
}

.duration-pill {
  margin-left: auto;
  border-radius: 999px;
  background: rgba(45, 212, 191, 0.12);
  color: var(--teal);
  font-weight: 600;
  padding: 2px 8px;
}

.tag-line {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 22px;
}

/* ---------- Detail panel ---------- */
.detail-panel {
  min-height: 0;
  overflow-y: auto;
  padding: 22px;
}

.detail-panel h2 {
  margin: 0;
  font-family: 'Bricolage Grotesque', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text);
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 18px;
}

.header-open-btn {
  margin-left: auto;
  flex-shrink: 0;
}

.detail-preview {
  display: grid;
  min-height: 80px;
  place-items: center;
  border-radius: 12px;
  background:
    radial-gradient(70% 60% at 50% 30%, rgba(255, 255, 255, 0.05), transparent),
    #0a0c10;
  border: 1px solid var(--border);
  overflow: hidden;
  padding: 6px;
}

.detail-preview:has(.waveform) {
  min-height: auto;
  padding: 8px 10px;
  background: linear-gradient(180deg, #161920 0%, #10131a 100%);
}

.detail-preview img {
  max-width: 100%;
  max-height: 160px;
  object-fit: contain;
}

.detail-title {
  margin: 16px 0;
  color: var(--text);
  font-weight: 600;
  font-size: 14px;
  overflow-wrap: anywhere;
  white-space: normal;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  border-radius: 9px;
  padding: 8px 12px;
  margin-left: -12px;
  margin-right: -12px;
  position: relative;
  border: 1px solid transparent;
}

.detail-title:hover {
  background: var(--amber-soft);
  border-color: var(--border-strong);
}

.display-name {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.shuffle-icon {
  flex-shrink: 0;
  color: var(--text-3);
  transition: color 0.2s, transform 0.2s;
}

.detail-title:hover .shuffle-icon {
  color: var(--amber);
}

.detail-title:active .shuffle-icon {
  transform: rotate(180deg);
}

.property-panel {
  border: 1px solid var(--border);
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.022);
  margin-bottom: 16px;
  padding: 14px;
}

.property-panel h3 {
  margin: 0;
  font-family: 'Bricolage Grotesque', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.property-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 0 8px;
}

.property-header h3 {
  margin: 0;
  font-family: 'Bricolage Grotesque', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.format-btn {
  margin-left: auto;
  flex-shrink: 0;
}

/* detail actions (top priority zone) */
.detail-actions {
  display: grid;
  gap: 10px;
  margin: 14px 0 16px;
}

/* source info (compact inline) */
.detail-source {
  display: grid;
  gap: 10px;
  margin-bottom: 4px;
}

.source-row {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 10px;
  align-items: center;
}

.source-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--text-2);
  text-transform: uppercase;
}

/* tags + note (bottom, compact) */
.detail-meta {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.meta-field {
  display: grid;
  gap: 5px;
}

.meta-field label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--text-2);
  text-transform: uppercase;
}

.source-radio-group,
.source-radio-group :deep(.n-radio-group) {
  width: 100%;
}

.source-radio-group :deep(.n-radio-group) {
  display: flex;
}

.source-radio-group :deep(.n-radio-button) {
  flex: 1;
  text-align: center;
}

.move-panel {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 11px;
  background: rgba(245, 165, 36, 0.045);
}

.move-panel h3 {
  margin: 0;
  font-family: 'Bricolage Grotesque', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: var(--text);
  font-size: 15px;
  font-weight: 600;
}

.move-category-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 10px;
  align-items: center;
}

.move-category-row span {
  color: var(--text-2);
  font-size: 13px;
  font-weight: 600;
}

.move-button-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.detail-table {
  display: grid;
  gap: 1px;
  margin-bottom: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  background: var(--border);
}

.detail-table div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 12px;
  background: var(--bg-card);
  color: var(--text-2);
  font-size: 12px;
}

.detail-table strong {
  font-family: 'JetBrains Mono', monospace;
  color: var(--text);
  font-weight: 600;
  font-size: 12px;
  text-align: right;
}

.empty-detail {
  display: grid;
  min-height: calc(100vh - 144px);
  place-items: center;
  color: var(--text-3);
  font-size: 14px;
}

/* Staggered card entrance */
.asset-card:nth-child(1) { animation-delay: 0.02s; }
.asset-card:nth-child(2) { animation-delay: 0.05s; }
.asset-card:nth-child(3) { animation-delay: 0.08s; }
.asset-card:nth-child(4) { animation-delay: 0.11s; }
.asset-card:nth-child(5) { animation-delay: 0.14s; }
.asset-card:nth-child(6) { animation-delay: 0.17s; }
.asset-card:nth-child(7) { animation-delay: 0.20s; }
.asset-card:nth-child(8) { animation-delay: 0.23s; }
.asset-card:nth-child(n + 9) { animation-delay: 0.26s; }

/* ---------- Settings page (refined) ---------- */
.cfg-page {
  min-height: 0;
  overflow: auto;
  padding: 28px 32px 40px;
}

.cfg-header {
  margin-bottom: 20px;
}

.cfg-header h2 {
  margin: 0;
  font-family: 'Bricolage Grotesque', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}

.cfg-header p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-3);
}

/* overview status bar */
.cfg-overview {
  display: flex;
  align-items: stretch;
  margin-bottom: 22px;
  padding: 14px 20px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: linear-gradient(180deg, #1d2129 0%, #191c24 100%);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
}

.cfg-overview-item {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
  padding: 0 20px;
}

.cfg-overview-item:first-child {
  padding-left: 0;
}

.cfg-overview-item:last-child {
  padding-right: 0;
}

.cfg-overview-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-3);
}

.cfg-overview-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.cfg-overview-sep {
  flex-shrink: 0;
  width: 1px;
  align-self: stretch;
  background: var(--border);
}

/* section card */
.cfg-section {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: linear-gradient(180deg, #1d2129 0%, #191c24 100%);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.3);
  margin-bottom: 18px;
  overflow: hidden;
  transition: border-color 0.2s;
}

.cfg-section:hover {
  border-color: var(--border-strong);
}

.cfg-section-head {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 18px 22px;
  border-bottom: 1px solid var(--border);
}

.cfg-accent {
  flex-shrink: 0;
  width: 4px;
  height: 30px;
  border-radius: 3px;
  background: linear-gradient(180deg, var(--amber), #d97706);
  box-shadow: 0 0 16px var(--amber-glow);
}

.cfg-accent--teal {
  background: linear-gradient(180deg, var(--teal), #0f9688);
  box-shadow: 0 0 16px rgba(45, 212, 191, 0.35);
}

.cfg-accent--rose {
  background: linear-gradient(180deg, var(--rose), #e11d48);
  box-shadow: 0 0 16px rgba(251, 113, 133, 0.35);
}

.cfg-section-title {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.cfg-section-icon {
  flex-shrink: 0;
  color: var(--text-2);
}

.cfg-section-title h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

.cfg-section-title p {
  margin: 3px 0 0;
  font-size: 12px;
  color: var(--text-3);
}

.cfg-section-body {
  display: grid;
  gap: 16px;
  padding: 20px 22px 24px;
}

.cfg-grid-2 {
  grid-template-columns: 1fr 1fr;
  align-items: start;
}

.cfg-field {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.cfg-field label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--text-2);
  text-transform: uppercase;
}

.cfg-input-row {
  display: flex;
  gap: 8px;
}

.cfg-input-row :deep(.n-input) {
  flex: 1;
}

.cfg-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 2px;
}

/* category paths grid */
.cfg-cat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.cfg-cat-col {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.018);
}

.cfg-cat-head {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.cfg-cat-head em {
  display: grid;
  place-items: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(245, 165, 36, 0.14);
  color: var(--amber);
  font-style: normal;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
}

.cfg-cat-list {
  display: grid;
  gap: 7px;
  min-height: 32px;
}

.cfg-cat-row {
  display: grid;
  grid-template-columns: minmax(64px, auto) 1fr auto;
  gap: 8px;
  align-items: center;
}

.cfg-cat-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--text-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cfg-cat-input {
  min-width: 0;
}

.cfg-cat-input :deep(.n-input) {
  width: 100%;
}

.cfg-cat-empty {
  display: grid;
  place-items: center;
  min-height: 32px;
  color: var(--text-3);
  font-size: 13px;
  border: 1px dashed var(--border);
  border-radius: 8px;
}

.cfg-input-row--add {
  margin-top: 2px;
}

/* project bar: selector + ghost new-project toggle */
.cfg-project-bar {
  display: flex;
  gap: 16px;
  align-items: flex-end;
}

.cfg-field--grow {
  flex: 1;
  min-width: 0;
}

.cfg-ghost-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  border: 1px dashed var(--border-strong);
  border-radius: 8px;
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  padding: 7px 14px;
  white-space: nowrap;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.cfg-ghost-link:hover {
  border-color: var(--amber);
  color: var(--amber);
  background: var(--amber-soft);
}

.cfg-ghost-link--close {
  padding: 7px 9px;
  border-style: solid;
}

.cfg-new-project-inline {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.cfg-new-project-inline :deep(.n-input) {
  width: 180px;
}

/* context binding bar: ties categories to current project */
.cfg-context-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--teal);
  border-radius: 9px;
  background: rgba(45, 212, 191, 0.04);
}

.cfg-context-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-2);
}

.cfg-context-arrow {
  color: var(--text-3);
  font-size: 14px;
  line-height: 1;
}

.cfg-context-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(45, 212, 191, 0.14);
  color: var(--teal);
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* simplified category row (library: no path input) */
.cfg-cat-row--simple {
  grid-template-columns: 1fr auto;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid var(--border);
  transition: border-color 0.15s;
}

.cfg-cat-row--simple:hover {
  border-color: var(--border-strong);
}

@media (max-width: 1180px) {
  .cfg-grid-2,
  .cfg-cat-grid {
    grid-template-columns: 1fr;
  }
}
</style>
