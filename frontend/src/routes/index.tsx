import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Home from '../pages/Home';
import Script from '../pages/Script';
import Scene from '../pages/Scene';
import Storyboard from '../pages/Storyboard';
import Video from '../pages/Video';
import FinalCut from '../pages/FinalCut';
import Login from '../pages/Login';
import Register from '../pages/Register';
import Payment from '../pages/Payment';
import Settings from '../pages/Settings';
import { CaseDetail } from '../pages/CaseDetail';
import AssetLibrary from '../pages/AssetLibrary';
import ProtectedRoute from '../components/ProtectedRoute';

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* 公开页面 — 无需登录 */}
      <Route path="/" element={<Home />} />
      <Route path="/overview" element={<Home />} />
      <Route path="/case/:id" element={<CaseDetail />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* 需要登录才能访问的页面 */}
      <Route path="/script" element={<ProtectedRoute><Script /></ProtectedRoute>} />
      <Route path="/scene" element={<ProtectedRoute><Scene /></ProtectedRoute>} />
      <Route path="/storyboard" element={<ProtectedRoute><Storyboard /></ProtectedRoute>} />
      <Route path="/video" element={<ProtectedRoute><Video /></ProtectedRoute>} />
      <Route path="/final-cut" element={<ProtectedRoute><FinalCut /></ProtectedRoute>} />
      <Route path="/payment" element={<ProtectedRoute><Payment /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
      <Route path="/assets" element={<ProtectedRoute><AssetLibrary /></ProtectedRoute>} />

      <Route path="*" element={<div>404 - 页面未找到</div>} />
    </Routes>
  );
};

export default AppRoutes;