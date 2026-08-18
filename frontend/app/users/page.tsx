"use client";

import { FormEvent, useEffect, useState } from "react";
import { ArrowPathIcon, UserPlusIcon, XMarkIcon } from "@heroicons/react/24/outline";
import AppShell from "@/components/AppShell";
import { api } from "@/lib/api";

type UserRow = {
  id: string;
  name: string;
  email: string;
  role: "ADMIN" | "ANALYST";
  is_active: boolean;
};

export default function Users() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "ANALYST" });

  async function load() {
    setLoading(true);
    try {
      setUsers(await api<UserRow[]>("/users"));
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Users could not be loaded");
    } finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setSaving(true); setError("");
    try {
      const user = await api<UserRow>("/users", { method: "POST", body: JSON.stringify(form) });
      setUsers((current) => [...current, user]);
      setShow(false);
      setForm({ full_name: "", email: "", password: "", role: "ANALYST" });
      setMessage(`${user.name} was created.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The user could not be created");
    } finally { setSaving(false); }
  }

  async function update(user: UserRow, payload: Partial<UserRow>) {
    setSaving(true); setError("");
    try {
      const updated = await api<UserRow>(`/users/${user.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item));
      setMessage(`${updated.name} was updated.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The user could not be updated");
    } finally { setSaving(false); }
  }

  return <AppShell title="Users" subtitle="Manage workspace access and roles" actions={<>
    <button className="icon-btn" aria-label="Refresh users" onClick={() => void load()}><ArrowPathIcon /></button>
    <button className="primary-small" onClick={() => setShow(true)}><UserPlusIcon />New user</button>
  </>}>
    <div className="page-content">
      {error && <div className="error-banner"><span>{error}</span><button onClick={() => void load()}>Retry</button></div>}
      {message && <div className="success-banner"><span>{message}</span><button onClick={() => setMessage("")}>Dismiss</button></div>}
      <div className="panel"><table className="data-table">
        <thead><tr><th>User</th><th>Email</th><th>Role</th><th>Status</th></tr></thead>
        <tbody>{loading ? <tr><td colSpan={4} className="empty">Loading users...</td></tr> : users.map((user) => <tr key={user.id}>
          <td><b>{user.name}</b></td><td>{user.email}</td>
          <td><select className="table-select" value={user.role} disabled={saving} onChange={(event) => void update(user, { role: event.target.value as UserRow["role"] })}><option>ADMIN</option><option>ANALYST</option></select></td>
          <td><select className="table-select" value={user.is_active ? "ACTIVE" : "DISABLED"} disabled={saving} onChange={(event) => void update(user, { is_active: event.target.value === "ACTIVE" })}><option>ACTIVE</option><option>DISABLED</option></select></td>
        </tr>)}</tbody>
      </table></div>
    </div>
    {show && <div className="modal-overlay" onClick={() => setShow(false)}><form className="modal incident-form" onSubmit={create} onClick={(event) => event.stopPropagation()}>
      <button type="button" className="modal-close" aria-label="Close" onClick={() => setShow(false)}><XMarkIcon /></button>
      <h2>Create user</h2>
      <label>Full name<input required minLength={2} value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} /></label>
      <label>Email<input required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
      <label>Initial password<input required minLength={8} type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
      <label>Role<select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}><option>ANALYST</option><option>ADMIN</option></select></label>
      <div className="modal-actions"><button type="button" className="secondary-btn" onClick={() => setShow(false)}>Cancel</button><button className="primary-small" disabled={saving}>{saving ? "Creating..." : "Create user"}</button></div>
    </form></div>}
  </AppShell>;
}
