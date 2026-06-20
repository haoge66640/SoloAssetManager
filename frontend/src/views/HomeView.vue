<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NDynamicTags,
  NForm,
  NFormItem,
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
import { assetFileUrl, copyAssetToTarget, createCategory, getCategories, getCategoryPaths, setCategoryPath, deleteCategoryFromDisk } from '@/api/assets'
import AudioWaveform from '@/components/AudioWaveform.vue'
import { useI18n, type Locale } from '@/i18n'
import { useAssetStore } from '@/stores/assets'
import type { Asset, AssetArea, AssetType } from '@/types/asset'

type Section = AssetArea | 'settings'
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
})
const newProjectName = ref('')
const newCategoryName = ref('')
const metaForm = reactive({
  source_type: '自制',
  source_url: '',
  tags: [] as string[],
  note: '',
})
const moveForm = reactive({
  category: '',
})
const audioInfoById = reactive<Record<string, AudioInfo>>({})
const playRequestByKey = reactive<Record<string, number>>({})
const projectMoveCategories = ref<string[]>([])
const libraryMoveCategories = ref<string[]>([])
const categoryPathsData = ref<Record<string, Record<string, string>>>({})
const newCategoryInputs = reactive<Record<string, string>>({ image: '', audio: '' })
const savingPaths = reactive<Record<string, boolean>>({})
const editingPaths = reactive<Record<string, string>>({})

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
    categoryPathsData.value = merged
    // Initialize editing paths for all categories
    for (const type of ['image', 'audio'] as const) {
      for (const cat of Object.keys(merged[type])) {
        editingPaths[`${type}:${cat}`] = merged[type][cat]
      }
    }
  } catch {
    categoryPathsData.value = {}
  }
}

function getCategoryList(type: string): string[] {
  const typeData = categoryPathsData.value[type]
  return typeData ? Object.keys(typeData).sort() : []
}

function getCategoryTargetPath(type: string, category: string): string {
  return categoryPathsData.value[type]?.[category] ?? ''
}

async function handleSetPath(area: 'project' | 'library', type: AssetType, category: string, targetPath: string) {
  const key = `${type}:${category}`
  savingPaths[key] = true
  try {
    await setCategoryPath(area, type, category, targetPath)
    if (!categoryPathsData.value[type]) {
      categoryPathsData.value[type] = {}
    }
    categoryPathsData.value[type][category] = targetPath
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
    if (!categoryPathsData.value[type]) {
      categoryPathsData.value[type] = {}
    }
    categoryPathsData.value[type][name] = ''
    editingPaths[`${type}:${name}`] = ''
    message.success(t('createdCategory'))
  } catch {
    message.error(t('saveFailed'))
  }
}

async function handleDeleteCategory(area: 'project' | 'library', type: AssetType, category: string) {
  try {
    await deleteCategoryFromDisk(area, type, category)
    const typeData = categoryPathsData.value[type]
    if (typeData) {
      delete typeData[category]
    }
    delete editingPaths[`${type}:${category}`]
    message.success(t('deletedCategory'))
  } catch {
    message.error(t('saveFailed'))
  }
}
const currentPage = ref(1)
const pageSize = ref(24)
const autoPlayEnabled = ref(localStorage.getItem(AUTO_PLAY_STORAGE_KEY) === 'true')
const audioVolume = ref(Number(localStorage.getItem(AUDIO_VOLUME_STORAGE_KEY) ?? 80))

const areaOptions = computed(() => [
  { label: t('pendingPool'), value: 'pending' },
  { label: t('project'), value: 'project' },
  { label: t('library'), value: 'library' },
])
const navOptions = computed(() => [...areaOptions.value, { label: t('settings'), value: 'settings' }])
const typeOptions = computed(() => [
  { label: t('image'), value: 'image' },
  { label: t('audio'), value: 'audio' },
])
const sourceOptions = computed(() => [
  { label: t('selfMade'), value: '自制' },
  { label: t('onlineSource'), value: '网络' },
])
const pageSizeOptions = computed(() => [
  { label: '12', value: 12 },
  { label: '24', value: 24 },
  { label: '48', value: 48 },
  { label: '96', value: 96 },
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
  if (value !== 'settings') {
    store.area = value
  } else {
    fetchCategoryPaths('project')
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
  message.success(t('createdProject'))
}

async function changeProject(value: string) {
  settingsDraft.current_project = value
  await store.persistSettings({ ...store.settings, current_project: value })
  await store.refreshCategories()
  await store.refreshAssets()
  await fetchCategoryPaths('project')
}

async function createCategory() {
  await store.addCategory(newCategoryName.value)
  newCategoryName.value = ''
  await store.refreshAssets()
  message.success(t('createdCategory'))
}

async function scanAssets() {
  await store.scanAndRefresh()
  message.success(t('scanned'))
}

async function refreshMoveCategories(asset = selectedAsset.value) {
  if (!asset || asset.area !== 'pending') {
    projectMoveCategories.value = []
    libraryMoveCategories.value = []
    return
  }
  projectMoveCategories.value = await getCategories('project', asset.type)
  libraryMoveCategories.value = await getCategories('library', asset.type)
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
  if (metaForm.source_type === '自制' && value.trim()) {
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

watch(
  () => store.settings,
  (settings) => {
    settingsDraft.owner_assets_path = settings.owner_assets_path
    settingsDraft.current_project = settings.current_project
  },
  { deep: true },
)

watch(
  selectedAsset,
  (asset) => {
    isSyncingMeta.value = true
    metaForm.source_type = asset?.source_type ?? ''
    if (!metaForm.source_type) {
      metaForm.source_type = '自制'
    }
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
      await store.updateMeta({
        asset_id: selectedAsset.value.id,
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
})

watch(() => store.category, store.refreshAssets)

watch(
  () => [store.area, store.assetType, store.category, store.keyword],
  () => {
    currentPage.value = 1
  },
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
  fetchCategoryPaths('project')
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

      <nav class="nav-list">
        <button
          :class="{ active: activeSection === 'pending' }"
          @click="selectSection('pending')"
        >
          {{ t('pendingPool') }}
        </button>

        <div class="nav-group">
          <button
            class="nav-trigger"
            :class="{ active: activeSection === 'project' }"
            @click="selectSection('project')"
          >
            {{ t('project') }}
          </button>
          <div class="nav-subs">
            <button
              v-for="opt in typeOptions"
              :key="opt.value"
              class="nav-sub"
              :class="{ active: activeSection === 'project' && store.assetType === opt.value }"
              @click="selectType(opt.value as AssetType)"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <button
          :class="{ active: activeSection === 'library' }"
          @click="selectSection('library')"
        >
          {{ t('library') }}
        </button>

        <button
          :class="{ active: activeSection === 'settings' }"
          @click="selectSection('settings')"
        >
          {{ t('settings') }}
        </button>
      </nav>
    </aside>

    <main class="main-panel">
      <header class="toolbar">
        <template v-if="activeSection !== 'settings'">
          <n-input
            v-model:value="store.keyword"
            class="search"
            clearable
            :placeholder="t('searchPlaceholder')"
            @keyup.enter="store.refreshAssets"
          />
          <n-button @click="store.refreshAssets">{{ t('search') }}</n-button>
          <n-button type="primary" @click="scanAssets">{{ t('scanDirectory') }}</n-button>
        </template>
        <div v-else class="toolbar-title">{{ t('settings') }}</div>
        <div class="toolbar-controls">
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

      <section v-if="activeSection === 'settings'" class="settings-page">
        <h2 class="settings-page-title">{{ t('settings') }}</h2>
        <div class="settings-grid">

          <!-- Asset Settings -->
          <div class="settings-card">
            <div class="card-head">
              <div class="card-accent"></div>
              <div class="card-title">
                <svg class="card-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <div>
                  <h3>{{ t('assetSettings') }}</h3>
                  <p>{{ t('assetSettingsDesc') }}</p>
                </div>
              </div>
            </div>
            <div class="card-body">
              <div class="field">
                <label>{{ t('ownerAssetsPath') }}</label>
                <n-input v-model:value="settingsDraft.owner_assets_path" :placeholder="t('ownerAssetsPlaceholder')" />
              </div>
              <div class="field">
                <label>{{ t('newProject') }}</label>
                <div class="input-row">
                  <n-input v-model:value="newProjectName" :placeholder="t('newProjectName')" />
                  <n-button type="primary" @click="createProject">{{ t('create') }}</n-button>
                </div>
              </div>
              <n-button type="primary" block size="large" @click="saveSettings">{{ t('saveAndInitialize') }}</n-button>
            </div>
          </div>

          <!-- Project Management -->
          <div class="settings-card">
            <div class="card-head">
              <div class="card-accent card-accent--green"></div>
              <div class="card-title">
                <svg class="card-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
                </svg>
                <div>
                  <h3>{{ t('projectManagement') }}</h3>
                  <p>{{ t('projectManagementDesc') }}</p>
                </div>
              </div>
            </div>
            <div class="card-body">
              <div class="field">
                <label>{{ t('currentProject') }}</label>
                <n-select
                  v-model:value="settingsDraft.current_project"
                  :options="store.projects.map((name) => ({ label: name, value: name }))"
                  :placeholder="t('projectPlaceholder')"
                  @update:value="changeProject"
                />
              </div>
            </div>

            <!-- Category target paths section -->
            <div class="card-body card-body--compact">

              <!-- Image categories -->
              <div class="type-section">
                <div class="type-section-header">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                  </svg>
                  <span>{{ t('imageCategories') }}</span>
                </div>
                <div class="cat-path-list">
                  <div v-for="cat in getCategoryList('image')" :key="'image:' + cat" class="cat-path-row">
                    <span class="cat-path-name">{{ cat }}</span>
                    <div class="cat-path-input-wrap">
                      <n-input
                        v-model:value="editingPaths['image:' + cat]"
                        size="tiny"
                        :placeholder="t('targetPathPlaceholder')"
                        :loading="savingPaths['image:' + cat]"
                        @blur="handleSetPath('project', 'image', cat, editingPaths['image:' + cat])"
                      />
                    </div>
                    <button class="cat-path-del" type="button" title="删除" @click="handleDeleteCategory('project', 'image', cat)">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
                </div>
                <div class="input-row input-row--add">
                  <n-input v-model:value="newCategoryInputs.image" size="tiny" :placeholder="t('addCategory')" @keyup.enter="handleAddCategory('project', 'image')" />
                  <n-button size="tiny" @click="handleAddCategory('project', 'image')">{{ t('create') }}</n-button>
                </div>
              </div>

              <!-- Audio categories -->
              <div class="type-section">
                <div class="type-section-header">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 18V5l12-2v13"/>
                    <circle cx="6" cy="18" r="3"/>
                    <circle cx="18" cy="16" r="3"/>
                  </svg>
                  <span>{{ t('audioCategories') }}</span>
                </div>
                <div class="cat-path-list">
                  <div v-for="cat in getCategoryList('audio')" :key="'audio:' + cat" class="cat-path-row">
                    <span class="cat-path-name">{{ cat }}</span>
                    <div class="cat-path-input-wrap">
                      <n-input
                        v-model:value="editingPaths['audio:' + cat]"
                        size="tiny"
                        :placeholder="t('targetPathPlaceholder')"
                        :loading="savingPaths['audio:' + cat]"
                        @blur="handleSetPath('project', 'audio', cat, editingPaths['audio:' + cat])"
                      />
                    </div>
                    <button class="cat-path-del" type="button" title="删除" @click="handleDeleteCategory('project', 'audio', cat)">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
                </div>
                <div class="input-row input-row--add">
                  <n-input v-model:value="newCategoryInputs.audio" size="tiny" :placeholder="t('addCategory')" @keyup.enter="handleAddCategory('project', 'audio')" />
                  <n-button size="tiny" @click="handleAddCategory('project', 'audio')">{{ t('create') }}</n-button>
                </div>
              </div>

            </div>
          </div>

        </div>
      </section>

      <section v-else class="content">
        <div class="asset-list-panel">
          <div class="filter-row">
            <div v-if="store.area === 'pending'" class="pending-tabs">
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

              <div class="category-tabs">
                <button
                  class="pending-tab"
                  :class="{ active: store.category === '' }"
                  type="button"
                  @click="store.category = ''"
                >
                  {{ t('all') }}
                </button>
                <button
                  v-for="cat in categoryOptions"
                  :key="cat.value"
                  class="pending-tab"
                  :class="{ active: store.category === cat.value }"
                  type="button"
                  @click="store.category = cat.value"
                >
                  {{ cat.label }}
                </button>
                <div class="inline-create">
                  <n-input
                    v-model:value="newCategoryName"
                    :placeholder="t('newCategoryName')"
                    size="tiny"
                    class="inline-create-input"
                    @keyup.enter="createCategory"
                  />
                  <n-button size="tiny" @click="createCategory">{{ t('create') }}</n-button>
                </div>
              </div>
            </template>
          </div>

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
                    :src="assetFileUrl(asset.id)"
                    :asset-id="asset.id"
                    :volume="audioVolume / 100"
                    :play-request="playRequestByKey[playRequestKey(asset.id, 'card')] ?? 0"
                    @metadata="saveAudioInfo(asset.id, $event)"
                  />
                </div>
                <div class="asset-name">{{ asset.name }}</div>
                <div v-if="asset.type === 'audio'" class="asset-audio-meta">
                  <span>{{ asset.format.toUpperCase() }}</span>
                  <span v-if="audioInfoById[asset.id]?.sampleRate">{{ formatSampleRate(audioInfoById[asset.id]?.sampleRate) }}</span>
                  <span v-if="audioInfoById[asset.id]?.duration" class="duration-pill">
                    {{ formatDuration(audioInfoById[asset.id]?.duration) }}
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
            <section class="property-panel">
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
                  {{ t('format') }}
                </n-button>
              </div>
              <div class="detail-table">
                <div v-if="selectedAsset.type === 'audio'">
                  <span>{{ t('duration') }}</span>
                  <strong>{{ formatDetailDuration(audioInfoById[selectedAsset.id]?.duration) }}</strong>
                </div>
                <div v-if="selectedAsset.type === 'audio'">
                  <span>{{ t('sampleRate') }}</span>
                  <strong>{{ formatSampleRate(audioInfoById[selectedAsset.id]?.sampleRate) }}</strong>
                </div>
                <div>
                  <span>{{ t('format') }}</span>
                  <strong>{{ selectedAsset.format }}</strong>
                </div>
                <div v-if="selectedAsset.type === 'audio' && formatChannels(audioInfoById[selectedAsset.id]?.channels)">
                  <span>{{ t('channels') }}</span>
                  <strong>{{ formatChannels(audioInfoById[selectedAsset.id]?.channels) }}</strong>
                </div>
              </div>
            </section>

            <div class="detail-table">
              <div>
                <span>{{ t('size') }}</span>
                <strong>{{ formatSize(selectedAsset.size) }}</strong>
              </div>
              <div>
                <span>{{ t('modifiedAt') }}</span>
                <strong>{{ selectedAsset.modified_at }}</strong>
              </div>
            </div>

            <n-form label-placement="top">
              <n-form-item :label="t('sourceType')">
                <n-radio-group v-model:value="metaForm.source_type" class="source-radio-group">
                  <n-radio-button v-for="option in sourceOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </n-radio-button>
                </n-radio-group>
              </n-form-item>
              <n-form-item :label="t('sourceUrl')">
                <n-input v-model:value="metaForm.source_url" @update:value="onSourceUrlChange" />
              </n-form-item>
              <n-form-item :label="t('tags')">
                <n-dynamic-tags v-model:value="metaForm.tags" />
              </n-form-item>
              <n-form-item :label="t('note')">
                <n-input v-model:value="metaForm.note" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" />
              </n-form-item>
            </n-form>

            <n-space vertical>
              <template v-if="selectedAsset.area === 'pending'">
                <section class="move-panel">
                  <h3>{{ t('organizeAsset') }}</h3>
                  <div class="move-category-row">
                    <span>{{ t('subDirectory') }}</span>
                    <n-select
                      v-model:value="moveForm.category"
                      filterable
                      tag
                      :options="moveCategoryOptions"
                      :placeholder="t('subDirectory')"
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

              <n-button
                v-if="selectedAsset.area !== 'pending' && selectedAsset.category"
                block
                type="primary"
                :loading="isCopyingToTarget"
                :disabled="isCopyingToTarget"
                @click="handleCopyToTarget"
              >
                {{ t('copyToTarget') }}
              </n-button>
              <n-button
                v-if="selectedAsset.area !== 'pending'"
                block
                type="warning"
                @click="deleteCurrentAsset"
              >
                {{ t('deleteAsset') }}
              </n-button>
            </n-space>
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
  grid-template-columns: 280px 1fr;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e5e7eb;
  background: #fff;
  padding: 20px;
  overflow: hidden;
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 24px;
}

.brand-icon {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  font-weight: 700;
}

.brand h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}

.brand p {
  margin: 2px 0 0;
  color: #64748b;
  font-size: 12px;
}

.nav-list {
  display: grid;
  gap: 8px;
}

.nav-list button {
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #334155;
  cursor: pointer;
  font-size: 15px;
  padding: 12px 14px;
  text-align: left;
}

.nav-list button.active {
  background: #eaf1ff;
  color: #1d4ed8;
  font-weight: 700;
}

.nav-group {
  display: grid;
  gap: 2px;
}

.nav-trigger {
  margin-bottom: 0 !important;
}

.nav-trigger.active {
  background: #eaf1ff;
  color: #1d4ed8;
  font-weight: 700;
}

.nav-subs {
  display: grid;
  gap: 2px;
  padding-left: 16px;
}

.nav-sub {
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 13px;
  padding: 8px 14px;
  text-align: left;
  transition: background 0.15s, color 0.15s;
}

.nav-sub:hover {
  background: #f1f5f9;
  color: #334155;
}

.nav-sub.active {
  background: #ecfdf5;
  color: #047857;
  font-weight: 700;
}

.main-panel {
  display: grid;
  grid-template-rows: 72px 1fr;
  min-width: 0;
  min-height: 0;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  height: 72px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
  padding: 0 24px;
}

.search {
  max-width: 620px;
}

.toolbar-title {
  color: #111827;
  font-size: 18px;
  font-weight: 700;
}

.toolbar-controls {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-left: auto;
}

.auto-play-control,
.volume-control {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.volume-control {
  width: 170px;
}

.volume-control :deep(.n-slider) {
  flex: 1;
}

.volume-control strong {
  width: 28px;
  color: #334155;
  font-weight: 600;
  text-align: right;
}

.locale-select {
  width: 132px;
}

.content {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 16px;
  min-height: 0;
  padding: 16px;
  overflow: hidden;
}

.settings-page {
  min-height: 0;
  overflow: auto;
  padding: 24px 32px;
}

.settings-page-title {
  margin: 0 0 24px;
  font-size: 20px;
  font-weight: 700;
  color: #111827;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 20px;
  max-width: 960px;
}

.settings-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.card-head {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 18px 20px 0;
}

.card-accent {
  flex-shrink: 0;
  width: 4px;
  height: 36px;
  border-radius: 2px;
  background: #2563eb;
  margin-top: 2px;
}

.card-accent--green {
  background: #059669;
}

.card-title {
  display: flex;
  gap: 12px;
  align-items: center;
  min-width: 0;
}

.card-icon {
  flex-shrink: 0;
  color: #64748b;
}

.card-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #111827;
}

.card-title p {
  margin: 2px 0 0;
  font-size: 13px;
  color: #94a3b8;
}

.card-body {
  display: grid;
  gap: 16px;
  padding: 18px 20px 22px;
}

.field {
  display: grid;
  gap: 6px;
}

.field label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
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
  padding-top: 14px;
}

.type-section {
  display: grid;
  gap: 6px;
}

.type-section-header {
  display: flex;
  gap: 6px;
  align-items: center;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
  padding-bottom: 2px;
}

.cat-path-list {
  display: grid;
  gap: 6px;
}

.cat-path-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 6px;
  align-items: center;
}

.cat-path-name {
  font-size: 12px;
  color: #64748b;
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
  width: 24px;
  height: 24px;
  place-items: center;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.cat-path-del:hover {
  background: #fef2f2;
  color: #ef4444;
}

.input-row--add {
  margin-top: 2px;
}

.asset-list-panel,
.detail-panel {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.asset-list-panel {
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
}

.filter-row {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
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
  border: 1px solid #d6dce6;
  border-radius: 6px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  padding: 10px 14px;
  text-align: center;
}

.pending-tab.active {
  border-color: #18a058;
  background: #ecfdf5;
  color: #047857;
  font-weight: 700;
}

.category-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
  min-width: 0;
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

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 14px;
}

.pagination-row {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: flex-end;
  margin-top: 18px;
}

.total-text {
  margin-right: auto;
  color: #64748b;
  font-size: 13px;
}

.page-size {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #64748b;
  font-size: 13px;
}

.page-size :deep(.n-select) {
  width: 86px;
}

.asset-card {
  display: grid;
  gap: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  padding: 10px;
  text-align: left;
}

.asset-card.selected {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px #dbeafe;
}

.preview {
  display: grid;
  position: relative;
  height: 112px;
  place-items: center;
  border-radius: 6px;
  background: #f8fafc;
  overflow: hidden;
}

.format-badge {
  position: absolute;
  top: 0;
  right: 0;
  z-index: 1;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  color: #334155;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  padding: 6px 8px;
}

.preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.asset-name {
  overflow: hidden;
  color: #111827;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-audio-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #64748b;
  font-size: 12px;
}

.duration-pill {
  margin-left: auto;
  border-radius: 999px;
  background: #f1f5f9;
  color: #334155;
  font-weight: 700;
  padding: 2px 8px;
}

.tag-line {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 22px;
}

.detail-panel {
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
}

.detail-panel h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.header-open-btn {
  margin-left: auto;
  flex-shrink: 0;
}

.detail-preview {
  display: grid;
  min-height: 180px;
  place-items: center;
  border-radius: 8px;
  background: #0f172a;
  overflow: hidden;
}

.detail-preview:has(.waveform) {
  background: #fff;
}

.detail-preview img {
  max-width: 100%;
  max-height: 220px;
  object-fit: contain;
}

.detail-title {
  margin: 14px 0;
  color: #111827;
  font-weight: 700;
  overflow-wrap: anywhere;
  white-space: normal;
  cursor: pointer;
  transition: background 0.15s, box-shadow 0.15s;
  border-radius: 8px;
  padding: 6px 10px;
  margin-left: -10px;
  margin-right: -10px;
  position: relative;
}

.detail-title:hover {
  background: #f0f4ff;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

.display-name {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.shuffle-icon {
  flex-shrink: 0;
  color: #93c5fd;
  transition: color 0.2s, transform 0.2s;
}

.detail-title:hover .shuffle-icon {
  color: #2563eb;
}

.detail-title:active .shuffle-icon {
  transform: rotate(180deg);
}

.property-panel {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
  margin-bottom: 16px;
  padding: 12px;
}

.property-panel h3 {
  margin: 0;
  color: #111827;
  font-size: 15px;
  font-weight: 700;
}

.property-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.format-btn {
  margin-left: auto;
  flex-shrink: 0;
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
}

.move-panel h3 {
  margin: 0;
  color: #111827;
  font-size: 16px;
  font-weight: 700;
}

.move-category-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 10px;
  align-items: center;
}

.move-category-row span {
  color: #334155;
  font-size: 14px;
  font-weight: 600;
}

.move-button-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.detail-table {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.detail-table div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #64748b;
  font-size: 13px;
}

.detail-table strong {
  color: #334155;
  font-weight: 600;
  text-align: right;
}

.empty-detail {
  display: grid;
  min-height: calc(100vh - 144px);
  place-items: center;
  color: #94a3b8;
}
</style>
