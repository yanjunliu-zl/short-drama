import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Home from '../pages/Home';
import Settings from '../pages/Settings';
import Script from '../pages/Script';
import Scene from '../pages/Scene';
import Storyboard from '../pages/Storyboard';
import Video from '../pages/Video';
import Dubbing from '../pages/Dubbing';
import Preview from '../pages/Preview';

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/script" element={<Script />} />
      <Route path="/scene" element={<Scene />} />
      <Route path="/storyboard" element={<Storyboard />} />
      <Route path="/video" element={<Video />} />
      <Route path="/dubbing" element={<Dubbing />} />
      <Route path="/preview" element={<Preview />} />
      <Route path="*" element={<div>404 - 页面未找到</div>} />
    </Routes>
  );
};

export default AppRoutes;