import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Home from '../pages/Home';

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="*" element={<div>404 - 页面未找到</div>} />
    </Routes>
  );
};

export default AppRoutes;