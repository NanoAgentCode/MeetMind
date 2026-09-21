import { useEffect, useMemo, useState } from 'react'
import { ApartmentOutlined, DeleteOutlined, EditOutlined, PlusOutlined, SafetyCertificateOutlined, TeamOutlined } from '@ant-design/icons'
import { Button, Checkbox, Empty, Input, InputNumber, Modal, Select, Spin, Switch, Table, Tabs, Tag, Tree, message } from 'antd'
import {
  createDepartment, createRole, createUser, deleteDepartment, deleteRole, deleteUser,
  listDepartments, listPermissions, listRoles, listUsers, updateDepartment, updateRole, updateUser,
} from './api'
import type { Department, DepartmentInput, PermissionItem, Role, RoleInput, User, UserCreateInput } from './types'

type Editor = { kind: 'user'; item?: User } | { kind: 'role'; item?: Role } | { kind: 'department'; item?: Department }
type UserDraft = UserCreateInput & { is_active: boolean }
type DepartmentNode = { key: string; title: string; children: DepartmentNode[] }

function errorText(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

export default function AccessManagement({ currentUser, onPermissionsChanged }: { currentUser: User; onPermissionsChanged: () => void }) {
  const can = (permission: string) => currentUser.permissions.includes(permission)
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [permissions, setPermissions] = useState<PermissionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [tab, setTab] = useState('users')
  const [selectedDepartment, setSelectedDepartment] = useState<string | null>(null)
  const [editor, setEditor] = useState<Editor | null>(null)
  const [userDraft, setUserDraft] = useState<UserDraft>({ username: '', display_name: '', password: '', department_id: null, role_ids: ['member'], is_active: true })
  const [roleDraft, setRoleDraft] = useState<RoleInput>({ name: '', description: '', permissions: [] })
  const [departmentDraft, setDepartmentDraft] = useState<DepartmentInput>({ name: '', parent_id: null, sort_order: 0 })

  const roleNames = useMemo(() => Object.fromEntries(roles.map((role) => [role.id, role.name])), [roles])
  const departmentNames = useMemo(() => Object.fromEntries(departments.map((department) => [department.id, department.name])), [departments])
  const treeData = useMemo(() => {
    const build = (parentId: string | null): DepartmentNode[] =>
      departments.filter((department) => department.parent_id === parentId).map((department) => ({
        key: department.id, title: `${department.name} · ${department.member_count} 人`, children: build(department.id),
      }))
    return build(null)
  }, [departments])
  const blockedParentIds = useMemo(() => {
    const blocked = new Set<string>()
    if (editor?.kind !== 'department' || !editor.item) return blocked
    const pending = [editor.item.id]
    while (pending.length) {
      const id = pending.pop()!
      blocked.add(id)
      departments.filter((department) => department.parent_id === id).forEach((department) => pending.push(department.id))
    }
    return blocked
  }, [departments, editor])
  const selected = departments.find((department) => department.id === selectedDepartment)

  async function load() {
    setLoading(true)
    try {
      const [nextUsers, nextRoles, nextDepartments, nextPermissions] = await Promise.all([
        can('user:read') || can('user:manage') ? listUsers() : Promise.resolve([]),
        can('role:read') || can('role:manage') || can('user:manage') ? listRoles() : Promise.resolve([]),
        can('department:read') || can('department:manage') || can('user:manage') ? listDepartments() : Promise.resolve([]),
        can('role:read') || can('role:manage') ? listPermissions() : Promise.resolve([]),
      ])
      setUsers(nextUsers)
      setRoles(nextRoles)
      setDepartments(nextDepartments)
      setPermissions(nextPermissions)
    } catch (error) {
      message.error(errorText(error, '权限数据加载失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [currentUser.id])

  function openUser(item?: User) {
    setUserDraft(item ? {
      username: item.username, display_name: item.display_name, password: '', department_id: item.department_id,
      role_ids: item.role_ids, is_active: item.is_active,
    } : { username: '', display_name: '', password: '', department_id: null, role_ids: ['member'], is_active: true })
    setEditor({ kind: 'user', item })
  }

  function openRole(item?: Role) {
    setRoleDraft(item ? { name: item.name, description: item.description, permissions: item.permissions } : { name: '', description: '', permissions: [] })
    setEditor({ kind: 'role', item })
  }

  function openDepartment(item?: Department, parentId?: string | null) {
    setDepartmentDraft(item ? { name: item.name, parent_id: item.parent_id, sort_order: item.sort_order } : { name: '', parent_id: parentId || null, sort_order: 0 })
    setEditor({ kind: 'department', item })
  }

  async function save() {
    if (!editor) return
    setSaving(true)
    try {
      if (editor.kind === 'user') {
        if (!userDraft.display_name.trim() || !userDraft.role_ids.length || (!editor.item && !userDraft.username.trim()) || (userDraft.password && userDraft.password.length < 8) || (!editor.item && !userDraft.password)) {
          message.warning('请填写账号、姓名、至少一个角色和不少于 8 位的密码')
          return
        }
        if (editor.item) {
          const data = { display_name: userDraft.display_name.trim(), department_id: userDraft.department_id,
            role_ids: userDraft.role_ids, is_active: userDraft.is_active,
            ...(userDraft.password ? { password: userDraft.password } : {}) }
          await updateUser(editor.item.id, data)
        } else {
          await createUser({ username: userDraft.username.trim(), display_name: userDraft.display_name.trim(),
            password: userDraft.password, department_id: userDraft.department_id, role_ids: userDraft.role_ids })
        }
      } else if (editor.kind === 'role') {
        if (!roleDraft.name.trim()) { message.warning('请填写角色名称'); return }
        const data = { ...roleDraft, name: roleDraft.name.trim() }
        if (editor.item) await updateRole(editor.item.id, data)
        else await createRole(data)
      } else {
        if (!departmentDraft.name.trim()) { message.warning('请填写部门名称'); return }
        const data = { ...departmentDraft, name: departmentDraft.name.trim() }
        if (editor.item) await updateDepartment(editor.item.id, data)
        else await createDepartment(data)
      }
      message.success('保存成功')
      setEditor(null)
      await load()
      onPermissionsChanged()
    } catch (error) {
      message.error(errorText(error, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  function remove(kind: Editor['kind'], id: string, name: string) {
    Modal.confirm({
      title: `删除${kind === 'user' ? '用户' : kind === 'role' ? '角色' : '部门'}？`,
      content: `确认删除“${name}”？有关联会议、成员或下级部门时，系统会阻止删除。`,
      okText: '删除', okButtonProps: { danger: true }, cancelText: '取消',
      async onOk() {
        try {
          if (kind === 'user') await deleteUser(id)
          else if (kind === 'role') await deleteRole(id)
          else await deleteDepartment(id)
          if (kind === 'department' && selectedDepartment === id) setSelectedDepartment(null)
          message.success('删除成功')
          await load()
          onPermissionsChanged()
        } catch (error) { message.error(errorText(error, '删除失败')) }
      },
    })
  }

  const availableTabs = [
    (can('user:read') || can('user:manage')) && { key: 'users', label: '用户管理' },
    (can('role:read') || can('role:manage')) && { key: 'roles', label: '角色权限' },
    (can('department:read') || can('department:manage')) && { key: 'departments', label: '部门管理' },
  ].filter((item): item is { key: string; label: string } => Boolean(item))
  const activeTab = availableTabs.some((item) => item.key === tab) ? tab : availableTabs[0]?.key

  return <>
    <div className="page-heading access-heading"><div><p className="breadcrumb">系统管理&nbsp;&nbsp;/&nbsp;&nbsp;权限管理</p><h1>组织与权限</h1><p>统一管理用户、角色授权与部门层级，权限调整即时生效</p></div><Tag color="blue" icon={<SafetyCertificateOutlined />}>RBAC</Tag></div>
    <section className="access-overview">
      <article><TeamOutlined /><span>用户总数<strong>{users.length}</strong></span></article>
      <article><SafetyCertificateOutlined /><span>角色总数<strong>{roles.length}</strong></span></article>
      <article><ApartmentOutlined /><span>部门总数<strong>{departments.length}</strong></span></article>
    </section>
    <Spin spinning={loading}><section className="access-panel"><Tabs activeKey={activeTab} onChange={setTab} items={availableTabs.map((item) => ({ ...item, children: item.key === 'users' ? <>
      <div className="access-toolbar"><div><h2>用户管理</h2><p>账号登录、角色授权与部门归属</p></div>{can('user:manage') && <Button type="primary" icon={<PlusOutlined />} onClick={() => openUser()}>添加用户</Button>}</div>
      <Table<User> rowKey="id" dataSource={users} pagination={{ pageSize: 8 }} columns={[
        { title: '用户', dataIndex: 'display_name', render: (_: string, user: User) => <div className="access-identity"><span>{user.display_name.slice(0, 1)}</span><div><strong>{user.display_name}</strong><small>{user.username}</small></div></div> },
        { title: '部门', dataIndex: 'department_id', render: (id: string | null) => departmentNames[id || ''] || '未分配' },
        { title: '角色', dataIndex: 'role_ids', render: (ids: string[]) => ids.map((id) => <Tag key={id}>{roleNames[id] || id}</Tag>) },
        { title: '状态', dataIndex: 'is_active', render: (active: boolean) => <Tag color={active ? 'success' : 'default'}>{active ? '启用' : '停用'}</Tag> },
        { title: '操作', key: 'actions', render: (_: unknown, user: User) => can('user:manage') && <div className="access-actions"><Button size="small" icon={<EditOutlined />} onClick={() => openUser(user)}>编辑</Button><Button size="small" danger icon={<DeleteOutlined />} disabled={user.id === currentUser.id} onClick={() => remove('user', user.id, user.display_name)}>删除</Button></div> },
      ]} />
    </> : item.key === 'roles' ? <>
      <div className="access-toolbar"><div><h2>角色与权限</h2><p>内置角色不可修改；自定义角色可按业务能力授权</p></div>{can('role:manage') && <Button type="primary" icon={<PlusOutlined />} onClick={() => openRole()}>添加角色</Button>}</div>
      <Table<Role> rowKey="id" dataSource={roles} pagination={{ pageSize: 8 }} columns={[
        { title: '角色', dataIndex: 'name', render: (_: string, role: Role) => <div className="access-role"><strong>{role.name}</strong><small>{role.description || '暂无说明'}</small></div> },
        { title: '类型', dataIndex: 'is_system', render: (system: boolean) => <Tag color={system ? 'blue' : 'default'}>{system ? '内置' : '自定义'}</Tag> },
        { title: '成员', dataIndex: 'member_count', render: (count: number) => `${count} 人` },
        { title: '权限', dataIndex: 'permissions', render: (keys: string[]) => <span className="access-permission-summary">{keys.length} 项 · {keys.slice(0, 3).map((key) => permissions.find((item) => item.key === key)?.label || key).join('、')}</span> },
        { title: '操作', key: 'actions', render: (_: unknown, role: Role) => can('role:manage') && !role.is_system && <div className="access-actions"><Button size="small" icon={<EditOutlined />} onClick={() => openRole(role)}>编辑</Button><Button size="small" danger icon={<DeleteOutlined />} disabled={role.member_count > 0} onClick={() => remove('role', role.id, role.name)}>删除</Button></div> },
      ]} />
    </> : <>
      <div className="access-toolbar"><div><h2>部门管理</h2><p>层级可调整；含成员或下级部门的节点不可删除</p></div>{can('department:manage') && <Button type="primary" icon={<PlusOutlined />} onClick={() => openDepartment()}>添加部门</Button>}</div>
      <div className="department-layout"><div className="department-tree">{treeData.length ? <Tree blockNode defaultExpandAll treeData={treeData} selectedKeys={selectedDepartment ? [selectedDepartment] : []} onSelect={(keys) => setSelectedDepartment(String(keys[0] || ''))} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无部门" />}</div><div className="department-detail">{selected ? <><span className="department-detail-icon"><ApartmentOutlined /></span><h3>{selected.name}</h3><p>直属成员 {selected.member_count} 人 · {selected.parent_id ? `上级部门：${departmentNames[selected.parent_id]}` : '顶级部门'}</p>{can('department:manage') && <div className="access-actions"><Button icon={<PlusOutlined />} onClick={() => openDepartment(undefined, selected.id)}>添加下级</Button><Button icon={<EditOutlined />} onClick={() => openDepartment(selected)}>编辑部门</Button><Button danger icon={<DeleteOutlined />} onClick={() => remove('department', selected.id, selected.name)}>删除部门</Button></div>}</> : <Empty description="选择左侧部门查看详情" />}</div></div>
    </> }))} /></section></Spin>

    <Modal title={editor?.kind === 'user' ? editor.item ? '编辑用户' : '添加用户' : editor?.kind === 'role' ? editor.item ? '编辑角色' : '添加角色' : editor?.item ? '编辑部门' : '添加部门'} open={!!editor} onCancel={() => setEditor(null)} onOk={() => void save()} confirmLoading={saving} okText="保存" cancelText="取消" width={editor?.kind === 'role' ? 640 : 520}>
      {editor?.kind === 'user' && <div className="config-form">
        <label>登录账号</label><Input aria-label="登录账号" value={userDraft.username} disabled={!!editor.item} onChange={(event) => setUserDraft({ ...userDraft, username: event.target.value })} placeholder="仅英文、数字、点、下划线或短横线" />
        <label>显示名称</label><Input aria-label="显示名称" value={userDraft.display_name} onChange={(event) => setUserDraft({ ...userDraft, display_name: event.target.value })} />
        <label>登录密码 <small>{editor.item ? '留空则不修改' : '至少 8 位'}</small></label><Input.Password aria-label="登录密码" value={userDraft.password} onChange={(event) => setUserDraft({ ...userDraft, password: event.target.value })} />
        <label>所属部门</label><Select allowClear placeholder="未分配部门" value={userDraft.department_id || undefined} options={departments.map((department) => ({ value: department.id, label: department.name }))} onChange={(department_id) => setUserDraft({ ...userDraft, department_id: department_id || null })} />
        <label>角色</label><Select mode="multiple" value={userDraft.role_ids} options={roles.map((role) => ({ value: role.id, label: role.name }))} onChange={(role_ids) => setUserDraft({ ...userDraft, role_ids })} />
        {!!editor.item && <label className="switch-field"><span>启用账号<small>停用后现有会话立即失效</small></span><Switch checked={userDraft.is_active} onChange={(is_active) => setUserDraft({ ...userDraft, is_active })} /></label>}
      </div>}
      {editor?.kind === 'role' && <div className="config-form">
        <label>角色名称</label><Input aria-label="角色名称" value={roleDraft.name} onChange={(event) => setRoleDraft({ ...roleDraft, name: event.target.value })} />
        <label>角色说明</label><Input aria-label="角色说明" value={roleDraft.description} onChange={(event) => setRoleDraft({ ...roleDraft, description: event.target.value })} />
        <label>权限项</label><Checkbox.Group value={roleDraft.permissions} onChange={(values) => setRoleDraft({ ...roleDraft, permissions: values.map(String) })}><div className="permission-grid">{permissions.map((permission) => <Checkbox key={permission.key} value={permission.key}>{permission.label}</Checkbox>)}</div></Checkbox.Group>
      </div>}
      {editor?.kind === 'department' && <div className="config-form">
        <label>部门名称</label><Input aria-label="部门名称" value={departmentDraft.name} onChange={(event) => setDepartmentDraft({ ...departmentDraft, name: event.target.value })} />
        <label>上级部门</label><Select allowClear placeholder="顶级部门" value={departmentDraft.parent_id || undefined} options={departments.filter((department) => !blockedParentIds.has(department.id)).map((department) => ({ value: department.id, label: department.name }))} onChange={(parent_id) => setDepartmentDraft({ ...departmentDraft, parent_id: parent_id || null })} />
        <label>排序序号</label><InputNumber aria-label="排序序号" min={0} value={departmentDraft.sort_order} onChange={(sort_order) => setDepartmentDraft({ ...departmentDraft, sort_order: sort_order || 0 })} />
      </div>}
    </Modal>
  </>
}
