import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Home from '../pages/Home';
import Settings from '../pages/Settings';
import Script from '../pages/Script';
import Scene from '../pages/Scene';
import Storyboard from '../pages/Storyboard';
import Video from '../pages/Video';
import FinalCut from '../pages/FinalCut';
import Login from '../pages/Login';
import Register from '../pages/Register';
import Payment from '../pages/Payment';

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/overview" element={<Settings />} />
      <Route path="/script" element={<Script />} />
      <Route path="/scene" element={<Scene />} />
      <Route path="/storyboard" element={<Storyboard />} />
      <Route path="/video" element={<Video />} />
      <Route path="/final-cut" element={<FinalCut />} />
      <Route path="/payment" element={<Payment />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="*" element={<div>404 - 页面未找到</div>} />
    </Routes>
  );
};

export default AppRoutes;