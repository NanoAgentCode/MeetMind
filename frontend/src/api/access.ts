import { api } from './client'
import type { Department, DepartmentInput, PermissionItem, Role, RoleInput, User, UserCreateInput, UserUpdateInput } from '../shared/types'

export const listUsers = async () => (await api.get<User[]>('/users')).data
export const createUser = async (data: UserCreateInput) => (await api.post<User>('/users', data)).data
export const updateUser = async (id: string, data: UserUpdateInput) => (await api.put<User>(`/users/${id}`, data)).data
export const deleteUser = async (id: string) => { await api.delete(`/users/${id}`) }
export const listRoles = async () => (await api.get<Role[]>('/roles')).data
export const listPermissions = async () => (await api.get<PermissionItem[]>('/permissions')).data
export const createRole = async (data: RoleInput) => (await api.post<Role>('/roles', data)).data
export const updateRole = async (id: string, data: RoleInput) => (await api.put<Role>(`/roles/${id}`, data)).data
export const deleteRole = async (id: string) => { await api.delete(`/roles/${id}`) }
export const listDepartments = async () => (await api.get<Department[]>('/departments')).data
export const createDepartment = async (data: DepartmentInput) => (await api.post<Department>('/departments', data)).data
export const updateDepartment = async (id: string, data: DepartmentInput) => (await api.put<Department>(`/departments/${id}`, data)).data
export const deleteDepartment = async (id: string) => { await api.delete(`/departments/${id}`) }
