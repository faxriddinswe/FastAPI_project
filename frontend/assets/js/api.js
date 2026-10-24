/**
 * api.js — Centralized API client
 * All fetch calls go through here. JWT token is automatically attached.
 */

const API_BASE = 'http://127.0.0.1:8000';

function getToken() {
    return localStorage.getItem('pdp_token');
}

function getUser() {
    const raw = localStorage.getItem('pdp_user');
    return raw ? JSON.parse(raw) : null;
}

function setAuth(tokenData) {
    localStorage.setItem('pdp_token', tokenData.access_token);
    localStorage.setItem('pdp_user', JSON.stringify({
        role: tokenData.role,
        full_name: tokenData.full_name,
        user_id: tokenData.user_id,
    }));
}

function clearAuth() {
    localStorage.removeItem('pdp_token');
    localStorage.removeItem('pdp_user');
}

async function apiFetch(path, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...(options.headers || {}),
    };

    const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
        const msg = data.detail || `HTTP ${res.status}`;
        throw new Error(Array.isArray(msg) ? msg.map(e => e.msg).join(', ') : msg);
    }

    return data;
}

const api = {
    // Auth
    signup: (body) => apiFetch('/auth/signup', { method: 'POST', body }),
    login: (body) => apiFetch('/auth/login', { method: 'POST', body }),

    // Admin
    createTeacher: (body) => apiFetch('/admin/teachers', { method: 'POST', body }),
    listTeachers: () => apiFetch('/admin/teachers'),
    deleteTeacher: (id) => apiFetch(`/admin/teachers/${id}`, { method: 'DELETE' }),
    adminStats: () => apiFetch('/admin/stats'),

    // Teacher
    createTest: (body) => apiFetch('/teacher/tests', { method: 'POST', body }),
    listTests: () => apiFetch('/teacher/tests'),
    getTest: (id) => apiFetch(`/teacher/tests/${id}`),
    updateTest: (id, body) => apiFetch(`/teacher/tests/${id}`, { method: 'PUT', body }),
    deleteTest: (id) => apiFetch(`/teacher/tests/${id}`, { method: 'DELETE' }),
    addQuestion: (testId, body) => apiFetch(`/teacher/tests/${testId}/questions`, { method: 'POST', body }),
    generateLink: (testId, body) => apiFetch(`/teacher/tests/${testId}/links`, { method: 'POST', body }),
    testResults: (testId) => apiFetch(`/teacher/tests/${testId}/results`),
    duplicateTest: (testId) => apiFetch(`/teacher/tests/${testId}/duplicate`, { method: 'POST' }),
    gradeSession: (sessionId, body) => apiFetch(`/teacher/sessions/${sessionId}/grade`, { method: 'POST', body }),
    createGroup: (body) => apiFetch('/teacher/groups', { method: 'POST', body }),
    listGroups: () => apiFetch('/teacher/groups'),
    getGroup: (groupId) => apiFetch(`/teacher/groups/${groupId}`),
    addStudentsToGroup: (groupId, body) => apiFetch(`/teacher/groups/${groupId}/students`, { method: 'POST', body }),
    getTeacherAttendance: () => apiFetch('/teacher/attendance'),
    getTeacherTimetable: () => apiFetch('/teacher/timetable'),
    getTeacherProfile: () => apiFetch('/teacher/profile'),
    updateTeacherProfile: (body) => apiFetch('/teacher/profile', { method: 'PUT', body }),
    getUngradedSessions: () => apiFetch('/teacher/ungraded-sessions'),

    // Student
    accessTest: (token) => apiFetch(`/student/tests/${token}`),
    reportViolation: (token) => apiFetch(`/student/tests/${token}/violation`, { method: 'POST', body: {} }),
    submitTest: (token, body) => apiFetch(`/student/tests/${token}/submit`, { method: 'POST', body }),
    myStats: () => apiFetch('/student/stats'),
    leaderboard: (groupId) => apiFetch(`/student/leaderboard${groupId ? `?group_id=${groupId}` : ''}`),
    getStudentTimetable: () => apiFetch('/student/timetable'),
    getStudentProfile: () => apiFetch('/student/profile'),
    updateStudentProfile: (body) => apiFetch('/student/profile', { method: 'PUT', body }),
};

export { api, getToken, getUser, setAuth, clearAuth };
