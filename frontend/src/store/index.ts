import { configureStore } from '@reduxjs/toolkit'
import { persistStore, persistReducer } from 'redux-persist'
import storage from 'redux-persist/lib/storage'
import { combineReducers } from 'redux'

import authReducer from './slices/authSlice'
import userReducer from './slices/userSlice'
import scriptReducer from './slices/scriptSlice'
import videoReducer from './slices/videoSlice'
import orderReducer from './slices/orderSlice'
import uiReducer from './slices/uiSlice'

// 持久化配置
const persistConfig = {
  key: 'root',
  storage,
  whitelist: ['auth', 'user'], // 只持久化auth和user状态
  version: 1,
}

// 合并reducer
const rootReducer = combineReducers({
  auth: authReducer,
  user: userReducer,
  script: scriptReducer,
  video: videoReducer,
  order: orderReducer,
  ui: uiReducer,
})

// 持久化reducer
const persistedReducer = persistReducer(persistConfig, rootReducer)

// 创建store
export const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['persist/PERSIST', 'persist/REHYDRATE'],
      },
    }),
  devTools: process.env.NODE_ENV !== 'production',
})

// 创建持久化store
export const persistor = persistStore(store)

// 导出类型
export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch