import { useEffect, useMemo, useState } from 'react'
import { ApiOutlined, CloudServerOutlined, DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined, RobotOutlined, UnorderedListOutlined } from '@ant-design/icons'
import { Button, Empty, Input, Modal, Select, Spin, Switch, Tag, message } from 'antd'
import {
  createModelConfig, createModelProvider, deleteModelConfig, deleteModelProvider,
  listModelConfigs, listModelProviders, listProviderModels, testModelProvider, updateModelConfig, updateModelProvider,
} from './api'
import type { ModelConfig, ModelConfigInput, ModelProvider, ModelProviderInput, ModelType, ProviderProtocol } from './types'

const protocolLabels: Record<ProviderProtocol, string> = {
  openai: 'OpenAI', anthropic: 'Anthropic', ollama: 'Ollama', openai_compatible: 'OpenAI Compatible',
}
const typeMeta: Record<ModelType, { label: string; description: string; color: string }> = {
  llm: { label: 'LLM 对话', description: '生成会议纪要及通用对话', color: 'blue' },
  rag: { label: '会议 RAG', description: '基于单场会议内容进行问答', color: 'purple' },
  asr: { label: '语音转文字', description: '识别会议录音并生成转写', color: 'green' },
}
const emptyProvider: ModelProviderInput = { name: '', protocol: 'openai_compatible', base_url: '', api_key: '', enabled: true }
const emptyModel: ModelConfigInput = { provider_id: '', name: '', model_id: '', model_type: 'llm', enabled: true, is_default: false }

export default function ModelManagement({ canManage = true }: { canManage?: boolean }) {
  const [providers, setProviders] = useState<ModelProvider[]>([])
  const [models, setModels] = useState<ModelConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [providerDraft, setProviderDraft] = useState<ModelProviderInput | null>(null)
  const [providerEditing, setProviderEditing] = useState<ModelProvider | null>(null)
  const [modelDraft, setModelDraft] = useState<ModelConfigInput | null>(null)
  const [modelEditing, setModelEditing] = useState<ModelConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [testingProvider, setTestingProvider] = useState('')
  const [loadingModels, setLoadingModels] = useState('')
  const [providerModels, setProviderModels] = useState<Record<string, string[]>>({})
  const [catalogProvider, setCatalogProvider] = useState<ModelProvider | null>(null)
  const providerNames = useMemo(() => Object.fromEntries(providers.map((item) => [item.id, item.name])), [providers])

  async function load() {
    setLoading(true)
    try {
      const [nextProviders, nextModels] = await Promise.all([listModelProviders(), listModelConfigs()])
      setProviders(nextProviders)
      setModels(nextModels)
    } catch {
      message.error('模型配置加载失败，请检查后端服务')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  function openProvider(item?: ModelProvider) {
    setProviderEditing(item || null)
    setProviderDraft(item ? {
      name: item.name, protocol: item.protocol, base_url: item.base_url, api_key: '', enabled: item.enabled,
    } : { ...emptyProvider })
  }

  async function openModel(item?: ModelConfig) {
    const providerId = item?.provider_id || providers[0]?.id || ''
    setModelEditing(item || null)
    setModelDraft(item ? {
      provider_id: item.provider_id, name: item.name, model_id: item.model_id,
      model_type: item.model_type, enabled: item.enabled, is_default: item.is_default,
    } : { ...emptyModel, provider_id: providerId })
    if (providerId && !providerModels[providerId]) await fetchModels(providerId)
  }

  async function saveProvider() {
    if (!providerDraft?.name.trim() || !providerDraft.base_url.trim()) return message.warning('请填写供应商名称和服务地址')
    setSaving(true)
    try {
      if (providerEditing) await updateModelProvider(providerEditing.id, providerDraft)
      else await createModelProvider(providerDraft)
      message.success(providerEditing ? '供应商已更新' : '供应商已创建')
      setProviderDraft(null)
      await load()
    } catch { message.error('供应商保存失败') } finally { setSaving(false) }
  }

  async function saveModel() {
    if (!modelDraft?.provider_id || !modelDraft.name.trim() || !modelDraft.model_id.trim()) return message.warning('请完整填写模型配置')
    setSaving(true)
    try {
      if (modelEditing) await updateModelConfig(modelEditing.id, modelDraft)
      else await createModelConfig(modelDraft)
      message.success(modelEditing ? '模型配置已更新' : '模型配置已创建')
      setModelDraft(null)
      await load()
    } catch { message.error('模型配置保存失败') } finally { setSaving(false) }
  }

  function removeProvider(item: ModelProvider) {
    Modal.confirm({
      title: '删除供应商？', content: `“${item.name}”及其全部模型配置将被删除。`, okText: '删除', okButtonProps: { danger: true }, cancelText: '取消',
      async onOk() { await deleteModelProvider(item.id); message.success('供应商已删除'); await load() },
    })
  }

  async function testProvider(item: ModelProvider) {
    setTestingProvider(item.id)
    try {
      const result = await testModelProvider(item.id)
      message.success(result.message)
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      message.error(detail || '连接测试失败')
    } finally {
      setTestingProvider('')
    }
  }

  async function fetchModels(providerId: string, showCatalog = false) {
    setLoadingModels(providerId)
    try {
      const items = await listProviderModels(providerId)
      setProviderModels((current) => ({ ...current, [providerId]: items }))
      if (showCatalog) {
        setCatalogProvider(providers.find((item) => item.id === providerId) || null)
        message.success(`已获取 ${items.length} 个模型`)
      }
      return items
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      message.error(detail || '模型列表获取失败')
      return []
    } finally {
      setLoadingModels('')
    }
  }

  function removeModel(item: ModelConfig) {
    Modal.confirm({
      title: '删除模型配置？', content: `确认删除“${item.name}”？`, okText: '删除', okButtonProps: { danger: true }, cancelText: '取消',
      async onOk() { await deleteModelConfig(item.id); message.success('模型配置已删除'); await load() },
    })
  }

  return <>
    <div className="page-heading models-heading">
      <div><p className="breadcrumb">系统管理&nbsp;&nbsp;/&nbsp;&nbsp;模型服务</p><h1>模型服务</h1><p>统一管理模型供应商，以及会议纪要、内容问答和语音转写所使用的模型</p></div>
      {canManage && <Button type="primary" size="large" icon={<PlusOutlined />} onClick={() => openProvider()}>添加供应商</Button>}
    </div>
    <Spin spinning={loading}>
      <section className="model-overview">
        {(Object.entries(typeMeta) as [ModelType, typeof typeMeta[ModelType]][]).map(([type, meta]) => {
          const active = models.find((item) => item.model_type === type && item.is_default && item.enabled)
          return <article key={type}><span className={`model-type-icon ${type}`}>{type === 'asr' ? <ApiOutlined /> : <RobotOutlined />}</span><div><small>{meta.label}</small><strong>{active?.name || '未设置默认模型'}</strong><p>{meta.description}</p></div><i className={active ? 'ready' : ''} /></article>
        })}
      </section>
      <div className="model-management-grid">
      <section className="management-section">
        <div className="management-head"><div><h2>供应商</h2><p>API Key 仅用于服务端调用，页面不会返回明文</p></div><Tag>{providers.length} 个</Tag></div>
        {providers.length ? <div className="provider-grid">{providers.map((item) => <article className="provider-card" key={item.id}>
          <div className="provider-card-head"><span><CloudServerOutlined /></span><div><strong>{item.name}</strong><small>{protocolLabels[item.protocol]}</small></div><Tag color={item.enabled ? 'success' : 'default'}>{item.enabled ? '已启用' : '已停用'}</Tag></div>
          <p>{item.base_url}</p><div className="provider-secret"><span>API KEY</span><code>{item.api_key_masked || '未配置'}</code></div>
          <div className="card-actions"><Button aria-label="获取模型列表" title="获取模型列表" icon={<UnorderedListOutlined />} loading={loadingModels === item.id} onClick={() => fetchModels(item.id, true)}><span className="action-label">模型</span></Button>{canManage && <><Button aria-label="测试供应商连接" title="测试供应商连接" icon={<ApiOutlined />} loading={testingProvider === item.id} onClick={() => testProvider(item)}><span className="action-label">测试</span></Button><Button aria-label="编辑供应商" title="编辑供应商" icon={<EditOutlined />} onClick={() => openProvider(item)}><span className="action-label">编辑</span></Button><Button aria-label="删除供应商" title="删除供应商" danger icon={<DeleteOutlined />} onClick={() => removeProvider(item)}><span className="action-label">删除</span></Button></>}</div>
        </article>)}</div> : <Empty description="还没有供应商配置">{canManage && <Button type="primary" onClick={() => openProvider()}>添加第一个供应商</Button>}</Empty>}
      </section>
      <section className="management-section">
        <div className="management-head"><div><h2>模型配置</h2><p>每种类型最多设置一个默认模型，业务调用将优先使用默认配置</p></div>{canManage && <Button icon={<PlusOutlined />} disabled={!providers.length} onClick={() => void openModel()}>添加模型</Button>}</div>
        {models.length ? <div className="model-list">{models.map((item) => <article key={item.id}>
          <span className={`model-type-icon ${item.model_type}`}>{item.model_type === 'asr' ? <ApiOutlined /> : <RobotOutlined />}</span>
          <div className="model-identity"><strong>{item.name}{item.is_default && <Tag color={typeMeta[item.model_type].color}>默认</Tag>}</strong><small>{item.model_id}</small></div>
          <div className="model-provider"><small>供应商</small><strong>{providerNames[item.provider_id] || '未知供应商'}</strong></div>
          <div className="model-status"><Tag color={typeMeta[item.model_type].color}>{typeMeta[item.model_type].label}</Tag><Tag color={item.enabled ? 'success' : 'default'}>{item.enabled ? '可用' : '停用'}</Tag></div>
          {canManage && <div className="card-actions"><Button type="text" icon={<EditOutlined />} onClick={() => void openModel(item)} /><Button danger type="text" icon={<DeleteOutlined />} onClick={() => removeModel(item)} /></div>}
        </article>)}</div> : <Empty description={providers.length ? '还没有模型配置' : '请先添加供应商'} />}
      </section>
      </div>
    </Spin>

    <Modal title={providerEditing ? '编辑供应商' : '添加供应商'} open={!!providerDraft} onCancel={() => setProviderDraft(null)} onOk={saveProvider} confirmLoading={saving} okText="保存" cancelText="取消">
      {providerDraft && <div className="config-form">
        <label>供应商名称</label><Input value={providerDraft.name} placeholder="例如：企业 OpenAI" onChange={(e) => setProviderDraft({ ...providerDraft, name: e.target.value })} />
        <label>协议类型</label><Select value={providerDraft.protocol} options={Object.entries(protocolLabels).map(([value, label]) => ({ value, label }))} onChange={(protocol) => setProviderDraft({ ...providerDraft, protocol })} />
        <label>服务地址</label><Input value={providerDraft.base_url} placeholder="https://api.example.com/v1" onChange={(e) => setProviderDraft({ ...providerDraft, base_url: e.target.value })} />
        <label>API Key {providerEditing?.api_key_configured && <small>留空则保持原密钥</small>}</label><Input.Password value={providerDraft.api_key} placeholder={providerEditing?.api_key_masked || '请输入 API Key'} onChange={(e) => setProviderDraft({ ...providerDraft, api_key: e.target.value })} />
        <label className="switch-field"><span>启用供应商<small>停用后，其模型不会被业务调用</small></span><Switch checked={providerDraft.enabled} onChange={(enabled) => setProviderDraft({ ...providerDraft, enabled })} /></label>
      </div>}
    </Modal>
    <Modal title={modelEditing ? '编辑模型配置' : '添加模型配置'} open={!!modelDraft} onCancel={() => setModelDraft(null)} onOk={saveModel} confirmLoading={saving} okText="保存" cancelText="取消">
      {modelDraft && <div className="config-form">
        <label>所属供应商</label><Select value={modelDraft.provider_id} options={providers.map((item) => ({ value: item.id, label: item.name }))} onChange={async (provider_id) => { setModelDraft({ ...modelDraft, provider_id, model_id: '' }); await fetchModels(provider_id) }} />
        <label>模型用途</label><Select value={modelDraft.model_type} options={(Object.entries(typeMeta) as [ModelType, typeof typeMeta[ModelType]][]).map(([value, meta]) => ({ value, label: `${meta.label} · ${meta.description}` }))} onChange={(model_type) => setModelDraft({ ...modelDraft, model_type })} />
        <label>显示名称</label><Input value={modelDraft.name} placeholder="例如：会议问答模型" onChange={(e) => setModelDraft({ ...modelDraft, name: e.target.value })} />
        <label className="field-label-with-action"><span>选择模型<small>来自供应商实时模型列表</small></span><Button type="link" size="small" icon={<ReloadOutlined />} loading={loadingModels === modelDraft.provider_id} onClick={() => fetchModels(modelDraft.provider_id)}>刷新列表</Button></label>
        <Select showSearch optionFilterProp="label" value={modelDraft.model_id || undefined} loading={loadingModels === modelDraft.provider_id} placeholder={loadingModels === modelDraft.provider_id ? '正在获取模型列表…' : '请选择模型'} notFoundContent={loadingModels === modelDraft.provider_id ? '正在加载…' : '该供应商未返回可用模型'} options={Array.from(new Set([...(providerModels[modelDraft.provider_id] || []), ...(modelDraft.model_id ? [modelDraft.model_id] : [])])).map((value) => ({ value, label: value }))} onOpenChange={(open) => { if (open && !providerModels[modelDraft.provider_id]) void fetchModels(modelDraft.provider_id) }} onChange={(model_id) => setModelDraft({ ...modelDraft, model_id })} />
        <label className="switch-field"><span>启用模型<small>停用后不可被业务调用</small></span><Switch checked={modelDraft.enabled} onChange={(enabled) => setModelDraft({ ...modelDraft, enabled })} /></label>
        <label className="switch-field"><span>设为默认<small>同用途的原默认模型将自动取消</small></span><Switch checked={modelDraft.is_default} onChange={(is_default) => setModelDraft({ ...modelDraft, is_default })} /></label>
      </div>}
    </Modal>
    <Modal title={`${catalogProvider?.name || ''} · 可用模型`} open={!!catalogProvider} footer={null} onCancel={() => setCatalogProvider(null)}>
      <div className="provider-model-catalog">
        {(catalogProvider && providerModels[catalogProvider.id]?.length) ? providerModels[catalogProvider.id].map((modelId) => <div key={modelId}><RobotOutlined /><code>{modelId}</code></div>) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="供应商未返回可用模型" />}
      </div>
    </Modal>
  </>
}
