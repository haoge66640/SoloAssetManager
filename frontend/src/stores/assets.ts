import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createCategory,
  createProject,
  deleteAsset,
  formatAsset,
  getAssets,
  getCategories,
  getProjects,
  getSettings,
  initAssets,
  moveAsset,
  openAssetFolder,
  permanentDeleteAsset,
  renameAsset,
  saveSettings,
  scanAssets,
  updateAssetMeta,
} from '@/api/assets'
import type { Asset, AssetArea, AssetMetaPayload, AssetType, MoveAssetPayload, Settings } from '@/types/asset'

export const useAssetStore = defineStore('assets', () => {
  const settings = ref<Settings>({ owner_assets_path: '', current_project: '' })
  const projects = ref<string[]>([])
  const categories = ref<string[]>([])
  const assets = ref<Asset[]>([])
  const selectedAssetId = ref('')
  const area = ref<AssetArea>('pending')
  const assetType = ref<AssetType>('image')
  const category = ref('')
  const keyword = ref('')
  const loading = ref(false)

  const selectedAsset = computed(() => assets.value.find((asset) => asset.id === selectedAssetId.value))

  async function loadSettings() {
    settings.value = await getSettings()
  }

  async function persistSettings(nextSettings: Settings) {
    settings.value = await saveSettings(nextSettings)
  }

  async function initializeOwnerAssets() {
    await initAssets()
    await refreshProjects()
    await refreshCategories()
    await refreshAssets()
  }

  async function refreshProjects() {
    projects.value = await getProjects()
  }

  async function addProject(name: string) {
    settings.value = await createProject(name)
    await refreshProjects()
    await refreshCategories()
  }

  async function refreshCategories() {
    if (area.value === 'pending') {
      categories.value = await getCategories(area.value)
      if (category.value && !categories.value.includes(category.value)) {
        category.value = ''
      }
      return
    }
    categories.value = await getCategories(area.value, assetType.value)
    if (category.value && !categories.value.includes(category.value)) {
      category.value = ''
    }
  }

  async function addCategory(name: string) {
    if (area.value === 'pending') return
    await createCategory(area.value, assetType.value, name)
    await refreshCategories()
    category.value = name
  }

  async function refreshAssets() {
    loading.value = true
    assets.value = await getAssets({
      area: area.value,
      type: area.value === 'pending' ? undefined : assetType.value,
      category: category.value,
      keyword: keyword.value,
    })
    if (!assets.value.some((asset) => asset.id === selectedAssetId.value)) {
      selectedAssetId.value = assets.value[0]?.id ?? ''
    }
    loading.value = false
  }

  async function scanAndRefresh() {
    await scanAssets('all')
    await refreshCategories()
    await refreshAssets()
  }

  async function updateMeta(payload: AssetMetaPayload) {
    const updated = await updateAssetMeta(payload)
    assets.value = assets.value.map((asset) => (asset.id === updated.id ? updated : asset))
  }

  async function movePendingAsset(payload: MoveAssetPayload) {
    await moveAsset(payload)
    await refreshCategories()
    await refreshAssets()
  }

  async function openFolder(assetId: string) {
    await openAssetFolder(assetId)
  }

  async function renameAssetById(assetId: string, newName: string) {
    const updated = await renameAsset(assetId, newName)
    // remove old asset (by original id) and add the new one (id may have changed due to path hash)
    assets.value = [...assets.value.filter((asset) => asset.id !== assetId), updated]
    if (selectedAssetId.value === assetId) {
      selectedAssetId.value = updated.id
    }
  }

  async function deleteAssetById(assetId: string) {
    const updated = await deleteAsset(assetId)
    // Remove from current list (asset moved back to pending)
    assets.value = assets.value.filter((asset) => asset.id !== assetId && asset.id !== updated.id)
    if (selectedAssetId.value === assetId) {
      selectedAssetId.value = assets.value[0]?.id ?? ''
    }
  }

  async function permanentDeleteAssetById(assetId: string) {
    await permanentDeleteAsset(assetId)
    // Remove from current list (file physically deleted)
    assets.value = assets.value.filter((asset) => asset.id !== assetId)
    if (selectedAssetId.value === assetId) {
      selectedAssetId.value = assets.value[0]?.id ?? ''
    }
  }

  async function formatAssetById(assetId: string) {
    const updated = await formatAsset(assetId)
    // remove old asset (by original id) and add the new one (id may have changed)
    assets.value = [...assets.value.filter((asset) => asset.id !== assetId), updated]
    if (selectedAssetId.value === assetId) {
      selectedAssetId.value = updated.id
    }
  }

  return {
    settings,
    projects,
    categories,
    assets,
    selectedAssetId,
    selectedAsset,
    area,
    assetType,
    category,
    keyword,
    loading,
    loadSettings,
    persistSettings,
    initializeOwnerAssets,
    refreshProjects,
    addProject,
    refreshCategories,
    addCategory,
    refreshAssets,
    scanAndRefresh,
    updateMeta,
    movePendingAsset,
    openFolder,
    renameAssetById,
    deleteAssetById,
    permanentDeleteAssetById,
    formatAssetById,
  }
})
