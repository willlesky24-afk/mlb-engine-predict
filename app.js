// Debugging para móviles (Muestra errores en pantalla)
window.onerror = function (msg, url, line) {
    alert("Error: " + msg + "\nLínea: " + line);
    return false;
};

// Configuración de API dinámica
const API_DOMAIN = window.location.hostname || 'localhost';
// Cambia CLOUD_API_URL por la URL que te dará Railway o Render después de subir el server.py
const CLOUD_API_URL = 'https://inertial-magnetar-1.onrender.com';
const API_BASE_URL = API_DOMAIN.includes('netlify.app') ? `${CLOUD_API_URL}/api` : `http://${API_DOMAIN}:5000/api`;
let isOffline = false;

// Persistence and State
const state = {
    userId: localStorage.getItem('sdia_user_id') || null,
    currentView: 'dashboard',
    clients: [],
    payments: [],
    currency: 'USD',
    exchangeRate: 45.45
};

// Cargar datos desde el Servidor (MongoDB bridge) con Fallback a Local
async function loadData() {
    if (!state.userId) return renderLogin();

    state.exchangeRate = parseFloat(localStorage.getItem('stitch_tasa')) || 45.45;
    const tasaInput = document.getElementById('tasa-dia');
    if (tasaInput) tasaInput.value = state.exchangeRate;

    try {
        const fetchConfig = {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'X-User-ID': state.userId
            }
        };

        const [clientsRes, paymentsRes] = await Promise.all([
            fetch(`${API_BASE_URL}/clients`, fetchConfig),
            fetch(`${API_BASE_URL}/payments`, fetchConfig)
        ]);

        state.clients = await clientsRes.json();
        state.payments = await paymentsRes.json();
        isOffline = false;
        console.log('Sincronizado con MongoDB');
    } catch (error) {
        console.warn('Modo Offline: Usando almacenamiento local');
        isOffline = true;
        state.clients = JSON.parse(localStorage.getItem(`sdia_clients_${state.userId}`)) || [];
        state.payments = JSON.parse(localStorage.getItem(`sdia_payments_${state.userId}`)) || [];
    }
    renderCurrentView();
}

// Persistencia Local (Como respaldo)
function saveLocalState() {
    if (!state.userId) return;
    localStorage.setItem(`sdia_clients_${state.userId}`, JSON.stringify(state.clients));
    localStorage.setItem(`sdia_payments_${state.userId}`, JSON.stringify(state.payments));
    localStorage.setItem('sdia_user_id', state.userId);
}

function renderLogin() {
    viewContainer.innerHTML = `
        <div class="fade-in" style="max-width: 400px; margin: 100px auto; padding: 2rem; background: var(--bg-card); border-radius: 24px; border: 1px solid var(--border); text-align: center;">
            <div class="logo-icon" style="margin: 0 auto 1.5rem; width: 60px; height: 60px;">
                <i data-lucide="shield-check" style="width: 30px; height: 30px;"></i>
            </div>
            <h2 style="margin-bottom: 0.5rem;">S.D.I.A Acceso</h2>
            <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 2rem;">Ingresa tu llave para gestionar tu base de datos personal.</p>
            
            <input type="text" id="login-id" placeholder="ID de tu Negocio / Proyecto" class="form-input" style="text-align: center; font-weight: 600; font-size: 1.1rem; letter-spacing: 1px; margin-bottom: 1.5rem;">
            
            <button class="btn btn-primary" style="width: 100%; justify-content: center; padding: 1rem;" onclick="window.handleLogin()">
                Abrir Mi Panel <i data-lucide="arrow-right"></i>
            </button>
            <p style="margin-top: 1.5rem; font-size: 0.75rem; color: var(--text-muted);">Tus datos se guardan de forma aislada y segura en la nube.</p>
        </div>
    `;
    safeCreateIcons();
}

window.handleLogin = () => {
    const id = document.getElementById('login-id').value.trim();
    if (id.length < 3) return alert('La llave debe tener al menos 3 caracteres');
    state.userId = id;
    saveLocalState();
    loadData();
};

window.logout = () => {
    if (confirm('¿Cerrar sesión? Seguirás teniendo acceso con tu llave.')) {
        state.userId = null;
        localStorage.removeItem('sdia_user_id');
        location.reload();
    }
};

// DOM Elements
const viewContainer = document.getElementById('view-container');
const navItems = document.querySelectorAll('.nav-item');
const modalContainer = document.getElementById('modal-container');
const btnNewPayment = document.getElementById('btn-new-payment');

// Initialize
const safeCreateIcons = () => {
    try {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    } catch (e) {
        console.warn('Lucide icons not loaded (Offline)');
    }
};

safeCreateIcons();
loadData(); // Iniciar carga desde DB

// Search and Filter Logic
const searchInput = document.querySelector('.search-bar input');
if (searchInput) {
    searchInput.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        if (state.currentView === 'clients') {
            renderClients(null, term);
        } else if (state.currentView === 'payments') {
            renderPayments(null, term);
        }
    });
}

// Navigation Logic
navItems.forEach(item => {
    item.addEventListener('click', () => {
        const view = item.getAttribute('data-view');
        switchView(view);
    });
});

// Listener para tasa de cambio y moneda (Configuración manual)
window.addEventListener('DOMContentLoaded', () => {
    const tasaInput = document.getElementById('tasa-dia');
    const currencyToggle = document.getElementById('currency-toggle');

    if (tasaInput) {
        tasaInput.addEventListener('change', (e) => {
            state.exchangeRate = parseFloat(e.target.value);
            localStorage.setItem('stitch_tasa', state.exchangeRate);
            renderCurrentView();
        });
    }

    if (currencyToggle) {
        currencyToggle.addEventListener('change', (e) => {
            state.currency = e.target.value;
            renderCurrentView();
        });
    }
});

if (btnNewPayment) {
    btnNewPayment.addEventListener('click', () => {
        window.openModal('payment');
    });
}

function switchView(viewName) {
    state.currentView = viewName;
    navItems.forEach(item => {
        item.classList.toggle('active', item.getAttribute('data-view') === viewName);
    });
    renderCurrentView();
}

window.switchView = switchView; // Exponer globalmente para el dashboard

// Lógica de Instalación (Convertir a APP/APK)
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    // Mostrar botón de instalación si no está instalada
    const installBtn = document.getElementById('btn-install-app');
    if (installBtn) installBtn.style.display = 'flex';
});

window.installApp = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
        deferredPrompt = null;
        const installBtn = document.getElementById('btn-install-app');
        if (installBtn) installBtn.style.display = 'none';
    }
};

// Rendering Views
function renderCurrentView() {
    if (!state.userId) return renderLogin();

    viewContainer.innerHTML = '';
    const container = document.createElement('div');
    container.className = 'fade-in';

    switch (state.currentView) {
        case 'dashboard': renderDashboardView(container); break;
        case 'clients': renderClients(container); break;
        case 'payments': renderPayments(container); break;
        case 'pending_clients': window.renderPendingClientsView(container); break;
    }

    viewContainer.appendChild(container);
    safeCreateIcons();
}

function renderDashboardView(container) {
    const totalPending = state.clients.filter(c => c.status === 'pending').length;
    const totalCollectedUSD = state.payments.reduce((acc, p) => acc + Number(p.amount), 0);

    // Formateo según moneda elegida
    const displayCollected = state.currency === 'VES'
        ? `Bs ${(totalCollectedUSD * state.exchangeRate).toLocaleString()}`
        : `$ ${totalCollectedUSD.toLocaleString()}`;

    container.innerHTML = `
        <div class="view-header">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2>Panel Resumen</h2>
                    <p>Métricas simplificadas de cobranza.</p>
                </div>
                <div id="sync-status" class="status-pill ${isOffline ? 'status-pending' : 'status-paid'}" style="padding: 8px 16px;">
                    <i data-lucide="${isOffline ? 'cloud-off' : 'cloud'}"></i>
                    <span>${isOffline ? 'Local' : 'En la Nube'}</span>
                </div>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card" onclick="window.switchView('clients')" style="cursor: pointer; border: 2px solid var(--primary); transition: transform 0.2s;">
                <div class="stat-icon" style="background: rgba(99, 102, 241, 0.1); color: var(--primary);"><i data-lucide="users"></i></div>
                <div class="stat-info">
                    <span>Total Clientes (Ver lista)</span>
                    <h3>${state.clients.length}</h3>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(16, 185, 129, 0.1); color: var(--accent);"><i data-lucide="wallet"></i></div>
                <div class="stat-info">
                    <span>Recaudado Total (${state.currency})</span>
                    <h3>${displayCollected}</h3>
                </div>
            </div>
            <div class="stat-card clickable" onclick="window.renderPendingClientsView()" style="cursor: pointer; border: 2px solid var(--accent-red); transition: transform 0.2s;">
                <div class="stat-icon" style="background: rgba(239, 68, 68, 0.1); color: var(--accent-red);"><i data-lucide="alert-circle"></i></div>
                <div class="stat-info">
                    <span>Clientes por Pagar</span>
                    <h3>${totalPending}</h3>
                </div>
            </div>
        </div>

        <div class="info-card" style="background: var(--bg-card); padding: 2rem; border-radius: 20px; border: 1px solid var(--border); margin-top: 1rem;">
            <h3>Interfaz Simplificada</h3>
            <p style="color: var(--text-muted); margin-top: 10px;">Hemos quitado las gráficas pesadas para que la app cargue más rápido en tu teléfono. Toda la data se aloja en el dispositivo y se sincroniza si hay servidor.</p>
        </div>
    `;
}

window.renderPendingClientsView = (targetContainer) => {
    state.currentView = 'pending_clients';
    const container = targetContainer || document.createElement('div');
    if (!targetContainer) {
        viewContainer.innerHTML = '';
        viewContainer.appendChild(container);
    }
    container.className = 'fade-in';

    // Filtrar estrictamente clientes con deuda mayor a 0
    const pendingClients = state.clients.filter(c => c.totalDebt > 0);

    container.innerHTML = `
        <div class="view-header" style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <button onclick="window.switchView('dashboard')" class="btn" style="background: var(--glass); margin-bottom: 1rem; padding: 5px 10px; font-size: 0.8rem;">
                    <i data-lucide="arrow-left"></i> Volver al Panel
                </button>
                <h2>Clientes por Pagar</h2>
                <p>Lista de cobros pendientes (Se eliminan automáticamente al saldar).</p>
            </div>
        </div>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Nombre / Editar</th>
                        <th style="color: var(--accent-red);">Deuda</th>
                        <th style="color: var(--accent);">Último Abono</th>
                        <th>Fecha</th>
                    </tr>
                </thead>
                <tbody>
                    ${pendingClients.map(client => {
        const clientPayments = state.payments.filter(p => p.clientId === client.idCard);
        const lastPayment = clientPayments.length > 0 ? clientPayments[clientPayments.length - 1] : null;

        return `
                        <tr>
                            <td onclick="window.viewClientDetails('${client.idCard}')" style="cursor: pointer;">
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <strong>${client.name} ${client.lastname}</strong>
                                    <button class="icon-button" onclick="event.stopPropagation(); window.openEditClientModal('${client.idCard}')" style="padding: 4px; background: rgba(99,102,241,0.1);">
                                        <i data-lucide="edit-3" style="width: 14px;"></i>
                                    </button>
                                </div>
                            </td>
                            <td style="color: var(--accent-red); font-weight: bold;">$ ${client.totalDebt.toFixed(2)}</td>
                            <td style="color: var(--accent); font-weight: bold;">
                                ${lastPayment ? `$ ${lastPayment.amount.toFixed(2)}` : '---'}
                            </td>
                            <td style="font-size: 0.8rem; color: var(--text-muted);">
                                ${lastPayment ? new Date(lastPayment.date).toLocaleDateString() : 'Sin pagos'}
                            </td>
                        </tr>`;
    }).join('')}
                    ${pendingClients.length === 0 ? '<tr><td colspan="4" style="text-align: center; padding: 2rem;">No hay clientes con deuda pendiente.</td></tr>' : ''}
                </tbody>
            </table>
        </div>
    `;
    safeCreateIcons();
};

window.openEditClientModal = (idCard) => {
    const client = state.clients.find(c => c.idCard === idCard);
    const content = modalContainer.querySelector('.modal-content');
    modalContainer.classList.remove('hidden');

    content.innerHTML = `
        <h3>Editar Datos de Cobro</h3>
        <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1.5rem;">Cédula: ${client.idCard}</p>
        <form id="edit-client-form" style="display: flex; flex-direction: column; gap: 1rem;">
            <div style="display: flex; gap: 10px;">
                <input type="text" id="edit-name" value="${client.name}" class="form-input" placeholder="Nombre" required>
                <input type="text" id="edit-lastname" value="${client.lastname}" class="form-input" placeholder="Apellido" required>
            </div>
            <label style="font-size: 0.8rem; color: var(--text-muted);">Ajustar Deuda Manualmente ($):</label>
            <input type="number" id="edit-debt" value="${client.totalDebt}" step="0.01" class="form-input" required>
            
            <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                <button type="button" class="btn" style="background: var(--glass); flex: 1;" onclick="window.closeModal()">Cancelar</button>
                <button type="submit" class="btn btn-primary" style="flex: 1;">Actualizar</button>
            </div>
        </form>
    `;
    document.getElementById('edit-client-form').onsubmit = (e) => window.handleEditClientSubmit(e, idCard);
    safeCreateIcons();
};

window.handleEditClientSubmit = async (e, idCard) => {
    e.preventDefault();
    const updatedData = {
        name: document.getElementById('edit-name').value,
        lastname: document.getElementById('edit-lastname').value,
        totalDebt: parseFloat(document.getElementById('edit-debt').value)
    };

    try {
        if (!isOffline) {
            await fetch(`${API_BASE_URL}/clients/${idCard}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-ID': state.userId
                },
                body: JSON.stringify(updatedData)
            });
        }

        // Actualizar estado local
        const client = state.clients.find(c => c.idCard === idCard);
        if (client) {
            client.name = updatedData.name;
            client.lastname = updatedData.lastname;
            client.totalDebt = updatedData.totalDebt;
            client.status = client.totalDebt > 0 ? 'pending' : 'paid';
        }

        saveLocalState();
        window.closeModal();
        if (state.currentView === 'pending_clients') window.renderPendingClientsView();
        else renderCurrentView();

    } catch (err) {
        alert('Error al actualizar datos');
    }
};

function renderClients(container, filterTerm = '') {
    const target = container || viewContainer.firstChild;
    const filteredClients = state.clients.filter(c =>
        `${c.name} ${c.lastname} ${c.idCard}`.toLowerCase().includes(filterTerm)
    );

    target.innerHTML = `
        <div class="view-header" style="display: flex; justify-content: space-between; align-items: flex-end;">
            <div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <h2>Gestión de Clientes</h2>
                    <span class="status-pill ${isOffline ? 'status-pending' : 'status-paid'}" style="font-size: 0.7rem; padding: 4px 8px;">
                        <i data-lucide="${isOffline ? 'cloud-off' : 'cloud'}" style="width: 12px; height: 12px;"></i>
                        ${isOffline ? 'Local' : 'Nube'}
                    </span>
                </div>
                <p>${filteredClients.length} registros ${isOffline ? 'en este dispositivo' : 'en la nube'}.</p>
            </div>
            <button class="btn btn-primary" onclick="window.openModal('client')"><i data-lucide="user-plus"></i> Nuevo Cliente</button>
        </div>
        <div class="table-container">
            <table>
                <thead><tr><th>Nombre y Apellido</th><th>Cédula</th><th>Estado / Saldo</th><th>Acciones</th></tr></thead>
                <tbody>
                    ${filteredClients.map(client => `
                        <tr>
                            <td>
                                <strong>${client.name} ${client.lastname}</strong>
                                <div style="font-size: 0.75rem; color: var(--text-muted)">${client.phone}</div>
                            </td>
                            <td>${client.idCard}</td>
                            <td>
                                <div style="display: flex; flex-direction: column; gap: 4px;">
                                    <span class="status-pill status-${client.status}">${client.status === 'paid' ? 'Solvente' : 'Deudor'}</span>
                                    ${client.totalDebt > 0 ? `<small style="color: var(--accent-red); font-weight: 600;">Debe: $${client.totalDebt}</small>` : ''}
                                </div>
                            </td>
                            <td>
                                <div style="display: flex; gap: 12px; justify-content: flex-end;">
                                    <button class="icon-button" onclick="window.viewClientDetails('${client.idCard}')" style="background: rgba(99, 102, 241, 0.15); color: var(--primary);"><i data-lucide="eye" style="width: 18px;"></i></button>
                                    <button class="icon-button" onclick="window.deleteClient('${client.idCard}')" style="background: rgba(239, 68, 68, 0.15); color: var(--accent-red);"><i data-lucide="trash-2" style="width: 18px;"></i></button>
                                </div>
                            </td>
                        </tr>`).join('')}
                </tbody>
            </table>
        </div>
    `;
    safeCreateIcons();
}

window.deleteClient = async (idCard) => {
    if (!confirm('¿Estás seguro de eliminar este cliente? Se borrarán sus datos permanentemente.')) return;

    try {
        if (!isOffline) {
            await fetch(`${API_BASE_URL}/clients/${idCard}`, {
                method: 'DELETE',
                headers: { 'X-User-ID': state.userId }
            });
        }
        state.clients = state.clients.filter(c => c.idCard !== idCard);
        state.payments = state.payments.filter(p => p.clientId !== idCard);
        saveLocalState();
        renderCurrentView();
    } catch (e) {
        alert('Error al eliminar cliente');
    }
};

window.viewClientDetails = (clientIdCard, viewMode = 'month') => {
    const client = state.clients.find(c => c.idCard === clientIdCard);
    const payments = state.payments.filter(p => p.clientId === clientIdCard);
    const content = modalContainer.querySelector('.modal-content');
    modalContainer.classList.remove('hidden');

    const now = new Date();
    const currentYear = now.getFullYear();

    const hasPaidInMonth = (month) => payments.some(p => {
        const d = new Date(p.date);
        return d.getMonth() === month && d.getFullYear() === currentYear;
    });

    const getWeekNumber = (d) => {
        d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
        d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
        var yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
        return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    };

    const hasPaidInWeek = (week) => payments.some(p => {
        const d = new Date(p.date);
        return getWeekNumber(d) === week && d.getFullYear() === currentYear;
    });

    content.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem;">
            <div>
                <h3 style="font-size: 1.5rem;">${client.name} ${client.lastname}</h3>
                <p style="color: var(--text-muted); font-size: 0.8rem;">${client.idCard} | ${client.phone}</p>
            </div>
            <button onclick="window.closeModal()" class="icon-button"><i data-lucide="x"></i></button>
        </div>

        <div style="display: flex; gap: 10px; margin-bottom: 1rem;">
            <button class="btn ${viewMode === 'month' ? 'btn-primary' : ''}" style="flex: 1; font-size: 0.7rem; padding: 5px;" onclick="window.viewClientDetails('${clientIdCard}', 'month')">Mensual</button>
            <button class="btn ${viewMode === 'week' ? 'btn-primary' : ''}" style="flex: 1; font-size: 0.7rem; padding: 5px;" onclick="window.viewClientDetails('${clientIdCard}', 'week')">Semanal</button>
        </div>

        <div style="background: var(--bg-main); padding: 1rem; border-radius: 16px; margin-bottom: 1.5rem; border: 1px solid var(--border); text-align: center;">
            <p style="font-size: 0.7rem; color: var(--text-muted);">Deuda Pendiente:</p>
            <h2 style="color: ${client.totalDebt > 0 ? 'var(--accent-red)' : 'var(--accent)'};">$ ${client.totalDebt.toFixed(2)}</h2>
        </div>

        <div class="calendar-view">
            <h4 style="margin-bottom: 15px; font-size: 0.9rem;">Historial (${viewMode === 'month' ? 'Meses' : 'Semanas'})</h4>
            <div style="display: grid; grid-template-columns: repeat(${viewMode === 'month' ? '4' : '5'}, 1fr); gap: 8px; max-height: 200px; overflow-y: auto; padding-right: 5px;">
                ${viewMode === 'month'
            ? ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'].map((m, i) => `
                        <div style="background: var(--bg-card); padding: 8px; border-radius: 12px; text-align: center; border: 1px solid ${hasPaidInMonth(i) ? 'var(--accent)' : 'var(--border)'};">
                            <p style="font-size: 0.6rem; color: var(--text-muted);">${m}</p>
                            <i data-lucide="${hasPaidInMonth(i) ? 'check-circle' : 'circle'}" style="width: 14px; margin-top: 4px; color: ${hasPaidInMonth(i) ? 'var(--accent)' : 'var(--accent-red)'}"></i>
                        </div>
                    `).join('')
            : Array.from({ length: 20 }, (_, i) => {
                const w = getWeekNumber(now) - i;
                if (w <= 0) return '';
                return `
                        <div style="background: var(--bg-card); padding: 8px; border-radius: 12px; text-align: center; border: 1px solid ${hasPaidInWeek(w) ? 'var(--accent)' : 'var(--border)'};">
                            <p style="font-size: 0.6rem; color: var(--text-muted);">S${w}</p>
                            <i data-lucide="${hasPaidInWeek(w) ? 'check-circle' : 'circle'}" style="width: 14px; margin-top: 4px; color: ${hasPaidInWeek(w) ? 'var(--accent)' : 'var(--accent-red)'}"></i>
                        </div> `;
            }).reverse().join('')
        }
            </div>
        </div>

        <div style="margin-top: 1.5rem; display: flex; gap: 10px;">
            <button class="btn btn-primary" style="flex: 2;" onclick="window.closeModal(); window.openPaymentModal('${client.idCard}')">
                <i data-lucide="plus"></i> Registrar Pago
            </button>
            <button class="btn" style="flex: 1; background: rgba(239, 68, 68, 0.1); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.2);" onclick="window.closeModal(); window.deleteClient('${client.idCard}')">
                <i data-lucide="trash-2" style="width: 16px;"></i>
            </button>
        </div>
    `;
    safeCreateIcons();
};

function renderPayments(container, filterTerm = '') {
    const target = container || viewContainer.firstChild;
    const filteredPayments = state.payments.filter(p => {
        const client = state.clients.find(c => c.idCard === p.clientId || c.idCard === p.clientIdCard);
        const clientName = client ? `${client.name} ${client.lastname}` : '';
        return clientName.toLowerCase().includes(filterTerm) || p.method.toLowerCase().includes(filterTerm);
    });

    target.innerHTML = `
        <div class="view-header">
            <h2>Historial de Pagos</h2>
            <p>Lista de transacciones registradas.</p>
        </div>
        <div class="table-container">
            <table>
                <thead><tr><th>Cliente</th><th>Monto</th><th>Fecha</th><th>Método</th><th>Recibo</th></tr></thead>
                <tbody>
                    ${filteredPayments.slice().reverse().map(payment => {
        const client = state.clients.find(c => c.idCard === payment.clientId);
        const displayAmount = state.currency === 'VES'
            ? `Bs ${(payment.amount * state.exchangeRate).toLocaleString()}`
            : `$ ${payment.amount}`;
        return `<tr>
                            <td>${client ? client.name + ' ' + client.lastname : 'Desconocido'}</td>
                            <td style="color: var(--accent); font-weight: 600;">${displayAmount}</td>
                            <td>${new Date(payment.date).toLocaleDateString()}</td>
                            <td><span class="status-pill" style="background: var(--glass)">${payment.method}</span></td>
                            <td><button class="icon-button" style="color: var(--primary);" onclick="window.generatePDF('${payment._id || payment.id}')"><i data-lucide="file-text" style="width: 14px;"></i></button></td>
                        </tr>`;
    }).join('')}
                </tbody>
            </table>
        </div>
    `;
    safeCreateIcons();
}

// Modal Logic
window.openModal = (type) => {
    const content = modalContainer.querySelector('.modal-content');
    modalContainer.classList.remove('hidden');

    if (type === 'client') {
        content.innerHTML = `
            <h3>Nuevo Registro de Cliente</h3>
            <form id="client-form" style="display: flex; flex-direction: column; gap: 1rem;">
                <input type="text" id="c-name" placeholder="Nombre" class="form-input" required>
                <input type="text" id="c-lastname" placeholder="Apellido" class="form-input" required>
                <input type="text" id="c-id" placeholder="Cédula" class="form-input" required>
                <input type="text" id="c-phone" placeholder="Teléfono" class="form-input" required>
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <button type="button" class="btn" style="background: var(--glass); flex: 1;" onclick="window.closeModal()">Cancelar</button>
                    <button type="submit" class="btn btn-primary" style="flex: 1;">Guardar Cliente</button>
                </div>
            </form>
        `;
        document.getElementById('client-form').onsubmit = handleClientSubmit;
    } else if (type === 'payment') {
        content.innerHTML = `
            <h3>Registrar Pago</h3>
            <form id="payment-form" style="display: flex; flex-direction: column; gap: 1rem;">
                <select id="p-client" class="form-input" required>
                    <option value="">Seleccionar Cliente</option>
                    ${state.clients.map(c => `<option value="${c.idCard}">${c.name} ${c.lastname}</option>`).join('')}
                </select>
                <div style="display: flex; gap: 10px;">
                    <input type="number" id="p-amount" placeholder="Monto" class="form-input" required style="flex: 2;">
                    <select id="p-currency" class="form-input" style="flex: 1;">
                        <option value="USD">$ USD</option>
                        <option value="VES">Bs VES</option>
                    </select>
                </div>
                <p id="p-calc" style="font-size: 0.75rem; color: var(--accent); margin-top: -10px;">Equivalente: $ 0.00</p>
                <select id="p-method" class="form-input" required>
                    <option value="Efectivo">Efectivo</option>
                    <option value="Zelle">Zelle</option>
                    <option value="Pago Móvil">Pago Móvil</option>
                    <option value="Transferencia">Transferencia</option>
                </select>
                <input type="date" id="p-date" class="form-input" required value="${new Date().toISOString().split('T')[0]}">
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <button type="button" class="btn" style="background: var(--glass); flex: 1;" onclick="window.closeModal()">Cancelar</button>
                    <button type="submit" class="btn btn-primary" style="flex: 1;">Registrar</button>
                </div>
            </form>
        `;

        const amtInput = document.getElementById('p-amount');
        const pCurr = document.getElementById('p-currency');
        const pCalc = document.getElementById('p-calc');

        const updateCalc = () => {
            const val = parseFloat(amtInput.value) || 0;
            const res = pCurr.value === 'VES' ? val / state.exchangeRate : val;
            pCalc.innerText = `Equivalente: $ ${res.toFixed(2)}`;
        };

        amtInput.oninput = updateCalc;
        pCurr.onchange = updateCalc;
        document.getElementById('payment-form').onsubmit = handlePaymentSubmit;
    }
};

window.openPaymentModal = (clientIdCard) => {
    window.openModal('payment');
    setTimeout(() => {
        const select = document.getElementById('p-client');
        if (select) select.value = clientIdCard;
    }, 0);
};

window.closeModal = () => modalContainer.classList.add('hidden');

async function handleClientSubmit(e) {
    e.preventDefault();
    const newClient = {
        name: document.getElementById('c-name').value,
        lastname: document.getElementById('c-lastname').value,
        idCard: document.getElementById('c-id').value,
        phone: document.getElementById('c-phone').value,
        totalDebt: 0,
        status: 'paid',
        createdAt: new Date().toISOString()
    };

    try {
        if (!isOffline) {
            const res = await fetch(`${API_BASE_URL}/clients`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-ID': state.userId
                },
                body: JSON.stringify(newClient)
            });
            const saved = await res.json();
            state.clients.push(saved);
        } else {
            state.clients.push(newClient);
        }
        saveLocalState();
    } catch (err) {
        state.clients.push(newClient);
        saveLocalState();
    }
    window.closeModal();
    renderCurrentView();
}

async function handlePaymentSubmit(e) {
    e.preventDefault();
    const idCard = document.getElementById('p-client').value;
    const rawAmount = parseFloat(document.getElementById('p-amount').value);
    const pCurr = document.getElementById('p-currency').value;

    // Convertir a USD para la DB
    const amountUSD = pCurr === 'VES' ? rawAmount / state.exchangeRate : rawAmount;

    const newPayment = {
        clientId: idCard,
        clientIdCard: idCard,
        amount: amountUSD,
        method: document.getElementById('p-method').value,
        date: document.getElementById('p-date').value,
        currencyOrig: pCurr,
        amountOrig: rawAmount
    };

    try {
        if (!isOffline) {
            await fetch(`${API_BASE_URL}/payments`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-ID': state.userId
                },
                body: JSON.stringify(newPayment)
            });
        }
    } catch (err) { console.warn('Sync error'); }

    state.payments.push(newPayment);
    const client = state.clients.find(c => c.idCard === idCard);
    if (client) {
        client.totalDebt = Math.max(0, client.totalDebt - amountUSD);
        client.status = client.totalDebt <= 0 ? 'paid' : 'pending';
    }
    saveLocalState();
    window.closeModal();
    renderCurrentView();
    setTimeout(() => { if (confirm('¿Descargar recibo?')) window.generatePDF(newPayment.id || Date.now()); }, 500);
}

window.generatePDF = (paymentId) => {
    const p = state.payments.find(p => p._id === paymentId || p.id === paymentId) || state.payments[state.payments.length - 1];
    const client = state.clients.find(c => c.idCard === p.clientId);
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ unit: 'mm', format: [80, 100] });

    doc.setFontSize(10);
    doc.text('RECIBO DE PAGO', 40, 10, { align: 'center' });
    doc.text('--------------------------', 40, 15, { align: 'center' });
    doc.text(`Cliente: ${client.name} ${client.lastname}`, 5, 25);
    doc.text(`Monto: $${p.amount.toFixed(2)}`, 5, 35);
    if (p.amountOrig) doc.text(`Pago: ${p.amountOrig} ${p.currencyOrig}`, 5, 45);
    doc.text(`Fecha: ${p.date}`, 5, 55);
    doc.text('--------------------------', 40, 65, { align: 'center' });
    doc.text('¡Gracias!', 40, 75, { align: 'center' });
    doc.save(`Recibo_${client.lastname}.pdf`);
};

const style = document.createElement('style');
style.textContent = `
    .form-input { background: var(--bg-card); border: 1px solid var(--border); color: white; padding: 10px; border-radius: 10px; width: 100%; font-family: inherit; margin-bottom: 1rem; outline: none; transition: border 0.3s; }
    .form-input:focus { border-color: var(--primary); }
    .clickable:active { transform: scale(0.98); }
`;
document.head.appendChild(style);
