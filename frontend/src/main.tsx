import 'antd/dist/reset.css';
import './index.css';
import 'xterm/css/xterm.css';

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App as AntdApp, ConfigProvider, theme } from 'antd';
import koKR from 'antd/locale/ko_KR';
import App from './App.tsx';
import ProductProvider from './components/ProductProvider';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={koKR} theme={{ algorithm: theme.defaultAlgorithm }}>
      <AntdApp>
        <BrowserRouter>
          <ProductProvider><App /></ProductProvider>
        </BrowserRouter>
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>
);