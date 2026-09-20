import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#c56b3c',
          colorText: '#172925',
          colorBgContainer: '#fffdf7',
          borderRadius: 6,
          fontFamily: '"Noto Serif SC", "Source Han Serif SC", serif',
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)

