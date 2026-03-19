import { createSlice, PayloadAction } from '@reduxjs/toolkit'
import { Notification } from '@/types'

interface UIState {
  theme: 'light' | 'dark'
  sidebarCollapsed: boolean
  notifications: Notification[]
  globalLoading: boolean
  modalStack: string[] // Stack of open modal IDs
  toastMessages: Array<{
    id: string
    type: 'info' | 'success' | 'warning' | 'error'
    message: string
    duration?: number
  }>
  language: string
}

const initialState: UIState = {
  theme: 'light',
  sidebarCollapsed: false,
  notifications: [],
  globalLoading: false,
  modalStack: [],
  toastMessages: [],
  language: 'zh-CN',
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    toggleTheme: (state) => {
      state.theme = state.theme === 'light' ? 'dark' : 'light'
    },
    setTheme: (state, action: PayloadAction<'light' | 'dark'>) => {
      state.theme = action.payload
    },
    toggleSidebar: (state) => {
      state.sidebarCollapsed = !state.sidebarCollapsed
    },
    setSidebarCollapsed: (state, action: PayloadAction<boolean>) => {
      state.sidebarCollapsed = action.payload
    },
    addNotification: (state, action: PayloadAction<Notification>) => {
      state.notifications.unshift(action.payload)
      // Keep only latest 50 notifications
      if (state.notifications.length > 50) {
        state.notifications.pop()
      }
    },
    markNotificationAsRead: (state, action: PayloadAction<string>) => {
      const notification = state.notifications.find(n => n.id === action.payload)
      if (notification) {
        notification.read = true
      }
    },
    removeNotification: (state, action: PayloadAction<string>) => {
      state.notifications = state.notifications.filter(n => n.id !== action.payload)
    },
    clearNotifications: (state) => {
      state.notifications = []
    },
    setGlobalLoading: (state, action: PayloadAction<boolean>) => {
      state.globalLoading = action.payload
    },
    openModal: (state, action: PayloadAction<string>) => {
      if (!state.modalStack.includes(action.payload)) {
        state.modalStack.push(action.payload)
      }
    },
    closeModal: (state, action: PayloadAction<string>) => {
      state.modalStack = state.modalStack.filter(id => id !== action.payload)
    },
    closeTopModal: (state) => {
      state.modalStack.pop()
    },
    clearModals: (state) => {
      state.modalStack = []
    },
    addToast: (state, action: PayloadAction<{
      type: 'info' | 'success' | 'warning' | 'error'
      message: string
      duration?: number
    }>) => {
      const id = Date.now().toString() + Math.random().toString(36).substr(2, 9)
      state.toastMessages.push({
        id,
        ...action.payload,
      })
    },
    removeToast: (state, action: PayloadAction<string>) => {
      state.toastMessages = state.toastMessages.filter(toast => toast.id !== action.payload)
    },
    clearToasts: (state) => {
      state.toastMessages = []
    },
    setLanguage: (state, action: PayloadAction<string>) => {
      state.language = action.payload
    },
    resetUIState: (state) => {
      state.theme = initialState.theme
      state.sidebarCollapsed = initialState.sidebarCollapsed
      state.notifications = initialState.notifications
      state.globalLoading = initialState.globalLoading
      state.modalStack = initialState.modalStack
      state.toastMessages = initialState.toastMessages
      state.language = initialState.language
    },
  },
})

export const {
  toggleTheme,
  setTheme,
  toggleSidebar,
  setSidebarCollapsed,
  addNotification,
  markNotificationAsRead,
  removeNotification,
  clearNotifications,
  setGlobalLoading,
  openModal,
  closeModal,
  closeTopModal,
  clearModals,
  addToast,
  removeToast,
  clearToasts,
  setLanguage,
  resetUIState,
} = uiSlice.actions

export default uiSlice.reducer