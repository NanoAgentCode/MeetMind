import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './app/App'
import './shared/styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#155eef',
          colorText: '#182230',
          colorBgContainer: '#ffffff',
          colorBorder: '#d0d5dd',
          borderRadius: 6,
          controlHeight: 38,
          fontFamily: '"Noto Sans SC", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)
