import { useState } from 'react'
import { Button, Input } from 'antd'

type Props = {
  busy: boolean
  onLogin: (username: string, password: string) => Promise<boolean>
}

export default function LoginPage({ busy, onLogin }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  async function submit() {
    if (await onLogin(username.trim(), password)) setPassword('')
  }

  return <div className="login-page"><div className="login-brand"><span className="brand-symbol">会</span><strong>会智录</strong><small>MEETMIND</small></div><section className="login-card"><p className="login-eyebrow">企业会议工作空间</p><h1>欢迎回来</h1><p>登录后继续处理录音、纪要与会议问答</p><form onSubmit={(event) => { event.preventDefault(); void submit() }}><label htmlFor="login-username">账号</label><Input id="login-username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="请输入账号" /><label htmlFor="login-password">密码</label><Input.Password id="login-password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="请输入密码" /><Button type="primary" htmlType="submit" loading={busy} disabled={!username.trim() || !password}>登录工作台</Button></form></section><span className="login-footnote">安全协作 · 会议内容仅对账号所属用户可见</span></div>
}
