import { computed, ref } from 'vue'

export type Locale = 'zh' | 'en'

const STORAGE_KEY = 'solo-asset-manager-locale'

const messages = {
  zh: {
    appTitle: '游戏资源管理工具',
    appSubtitle: 'Solo Asset Manager',
    pendingPool: '待选池',
    project: '项目',
    library: '仓库',
    settings: '设置',
    image: '图片',
    audio: '音频',
    searchPlaceholder: '搜索文件名 / 标签 / 来源 / 备注',
    search: '搜索',
    scanDirectory: '扫描目录',
    autoPlay: '自动播放',
    volume: '音量',
    allCategories: '全部分类',
    all: '全部',
    newCategoryName: '新分类名称',
    createCategory: '新建分类',
    audioPreview: '音频',
    uncategorized: '未分类',
    assetDetails: '资源详情',
    properties: '属性',
    duration: '时长',
    sampleRate: '采样率',
    channels: '声道',
    mono: '单声道',
    stereo: '立体声',
    secondsUnit: '秒',
    area: '区域',
    format: '格式',
    size: '大小',
    category: '分类',
    modifiedAt: '更新时间',
    sourceType: '来源类型',
    sourceUrl: '来源链接',
    tags: '标签',
    note: '备注',
    saveAssetInfo: '保存资源信息',
    targetCategory: '目标分类',
    moveAndNumber: '移动并自动编号',
    projectCategory: '项目分类',
    libraryCategory: '仓库分类',
    organizeAsset: '整理资源',
    subDirectory: '子目录',
    moveToProject: '移动到项目',
    moveToLibrary: '移动到仓库',
    openFolder: '打开所在文件夹',
    noAssetSelected: '未选择资源',
    ownerAssetsPath: '总资产目录',
    ownerAssetsPlaceholder: '例如 F:/OwnerAssets',
    saveAndInitialize: '保存并初始化',
    projectPath: '项目',
    projectPlaceholder: '选择项目',
    newProjectName: '新项目名',
    create: '创建',
    language: '语言',
    chinese: '中文',
    english: 'English',
    selfMade: '自制',
    onlineSource: '网络来源',
    savedSettings: '设置已保存',
    createdProject: '项目已创建',
    createdCategory: '分类已创建',
    scanned: '扫描完成',
    savedAssetInfo: '资源信息已保存',
    movedAsset: '资源已移动',
    renamed: '重命名成功',
    pageSize: '每页',
    totalItems: '共 {count} 项',
  },
  en: {
    appTitle: 'Game Asset Manager',
    appSubtitle: 'Solo Asset Manager',
    pendingPool: 'Pending Pool',
    project: 'Project',
    library: 'Library',
    settings: 'Settings',
    image: 'Image',
    audio: 'Audio',
    searchPlaceholder: 'Search filename / tag / source / note',
    search: 'Search',
    scanDirectory: 'Scan Directory',
    autoPlay: 'Auto Play',
    volume: 'Volume',
    allCategories: 'All Categories',
    all: 'All',
    newCategoryName: 'New category name',
    createCategory: 'New Category',
    audioPreview: 'Audio',
    uncategorized: 'Uncategorized',
    assetDetails: 'Asset Details',
    properties: 'Properties',
    duration: 'Duration',
    sampleRate: 'Sample Rate',
    channels: 'Channels',
    mono: 'Mono',
    stereo: 'Stereo',
    secondsUnit: 's',
    area: 'Area',
    format: 'Format',
    size: 'Size',
    category: 'Category',
    modifiedAt: 'Modified At',
    sourceType: 'Source Type',
    sourceUrl: 'Source URL',
    tags: 'Tags',
    note: 'Note',
    saveAssetInfo: 'Save Asset Info',
    targetCategory: 'Target Category',
    moveAndNumber: 'Move and Number',
    projectCategory: 'Project Category',
    libraryCategory: 'Library Category',
    organizeAsset: 'Organize Asset',
    subDirectory: 'Subdirectory',
    moveToProject: 'Move to Project',
    moveToLibrary: 'Move to Library',
    openFolder: 'Open Folder',
    noAssetSelected: 'No asset selected',
    ownerAssetsPath: 'Owner Assets Path',
    ownerAssetsPlaceholder: 'Example: F:/OwnerAssets',
    saveAndInitialize: 'Save and Initialize',
    projectPath: 'Project',
    projectPlaceholder: 'Select project',
    newProjectName: 'New project name',
    create: 'Create',
    language: 'Language',
    chinese: '中文',
    english: 'English',
    selfMade: 'Self-made',
    onlineSource: 'Online Source',
    savedSettings: 'Settings saved',
    createdProject: 'Project created',
    createdCategory: 'Category created',
    scanned: 'Scan completed',
    savedAssetInfo: 'Asset info saved',
    movedAsset: 'Asset moved',
    renamed: 'Renamed',
    pageSize: 'Per page',
    totalItems: '{count} items',
  },
} as const

type MessageKey = keyof typeof messages.zh

const initialLocale = (localStorage.getItem(STORAGE_KEY) as Locale | null) ?? 'zh'
const locale = ref<Locale>(initialLocale)

export function useI18n() {
  const localeOptions = computed(() => [
    { label: messages[locale.value].chinese, value: 'zh' },
    { label: messages[locale.value].english, value: 'en' },
  ])

  function setLocale(value: Locale) {
    locale.value = value
    localStorage.setItem(STORAGE_KEY, value)
  }

  function t(key: MessageKey, params: Record<string, string | number> = {}) {
    let text = messages[locale.value][key]
    for (const [name, value] of Object.entries(params)) {
      text = text.replace(`{${name}}`, String(value)) as typeof text
    }
    return text
  }

  return {
    locale,
    localeOptions,
    setLocale,
    t,
  }
}
