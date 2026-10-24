/**
 * utils.js — Shared UI helpers: toast, modal, spinner, redirect guard
 */

// ── Toast ─────────────────────────────────────────────────────────────────────
export function showToast(message, type = 'info', duration = 3500) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const icons = {
        success: `<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>`,
        error: `<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>`,
        warning: `<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>`,
        info: `<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" d="M12 16v-4m0-4h.01"/></svg>`,
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type === 'error' ? 'error' : type}`;
    toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ── Modal ─────────────────────────────────────────────────────────────────────
export function openModal(id) {
    document.getElementById(id)?.classList.add('open');
    document.body.style.overflow = 'hidden';
}
export function closeModal(id) {
    document.getElementById(id)?.classList.remove('open');
    document.body.style.overflow = '';
}

// ── Auth guard ────────────────────────────────────────────────────────────────
export function requireAuth(allowedRole) {
    const token = localStorage.getItem('pdp_token');
    const user = JSON.parse(localStorage.getItem('pdp_user') || 'null');

    if (!token || !user) {
        window.location.href = '/index.html';
        return null;
    }

    if (allowedRole && user.role !== allowedRole) {
        if (user.role === 'admin') window.location.href = '/pages/admin/dashboard.html';
        if (user.role === 'teacher') window.location.href = '/pages/teacher/dashboard.html';
        if (user.role === 'student') window.location.href = '/pages/student/dashboard.html';
        return null;
    }

    return user;
}

// ── Theme management ──────────────────────────────────────────────────────────
export function initTheme() {
    const saved = localStorage.getItem('pdp_theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);

    // Also toggle the active icon in any theme toggler if present
    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
        // We'll update toggle button icon in the dashboard specific scripts
    }
}

export function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('pdp_theme', next);
    return next;
}

// ── Set user name in sidebar ──────────────────────────────────────────────────
export function initUserDisplay() {
    initTheme();
    const user = JSON.parse(localStorage.getItem('pdp_user') || 'null');
    const el = document.getElementById('user-name');
    if (el && user) el.textContent = user.full_name;

    const roleEl = document.getElementById('user-role');
    if (roleEl && user) {
        const labels = { admin: 'Administrator', teacher: 'Teacher', student: 'Student' };
        roleEl.textContent = labels[user.role] || user.role;
    }

    const avatarEl = document.getElementById('user-avatar');
    if (avatarEl && user && user.avatar_url) {
        avatarEl.src = user.avatar_url;
    }
}

// ── Logout ────────────────────────────────────────────────────────────────────
export function logout() {
    localStorage.removeItem('pdp_token');
    localStorage.removeItem('pdp_user');
    window.location.href = '/index.html';
}

// ── Format date ───────────────────────────────────────────────────────────────
export function formatDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}
