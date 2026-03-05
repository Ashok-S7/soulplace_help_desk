/**
 * Soulplace Boardgames Help Desk – dashboard logic
 */

(function () {
    const BASE = window.SOULPLACE_BASE || "";
    const requestsList = document.getElementById('requests-list');
    const acceptedTbody = document.getElementById('accepted-tbody');
    const enableNotificationsBtn = document.getElementById('enable-notifications');

    let previousRequestIds = new Set();

    /** Display time (backend sends Chennai IST already). */
    function formatTime(val) {
        return val != null ? String(val) : "";
    }

    function playNewRequestSound() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880;
            osc.type = 'sine';
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.15);
            const osc2 = ctx.createOscillator();
            const gain2 = ctx.createGain();
            osc2.connect(gain2);
            gain2.connect(ctx.destination);
            osc2.frequency.value = 1100;
            osc2.type = 'sine';
            gain2.gain.setValueAtTime(0.12, ctx.currentTime + 0.2);
            gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
            osc2.start(ctx.currentTime + 0.2);
            osc2.stop(ctx.currentTime + 0.35);
        } catch (e) {}
    }

    function loadPendingRequests() {
        fetch(BASE + '/api/requests')
            .then((res) => res.json())
            .then((data) => {
                const requests = data.requests || [];
                const currentIds = new Set(requests.map((r) => r.id));
                if (previousRequestIds.size > 0 && currentIds.size > previousRequestIds.size) {
                    playNewRequestSound();
                }
                previousRequestIds = currentIds;

                if (requests.length === 0) {
                    requestsList.innerHTML = '<p class="empty-state">No pending help requests.</p>';
                    return;
                }
                requestsList.innerHTML = requests
                    .map(
                        (r) => `
                    <div class="request-item" data-request-id="${r.id}">
                        <div class="request-info">
                            <strong>Table ${r.table}</strong>
                            <span class="request-time">${formatTime(r.raised_at)}</span>
                        </div>
                        <button type="button" class="btn-attend" data-id="${r.id}">I'm attending</button>
                    </div>
                `
                    )
                    .join('');

                requestsList.querySelectorAll('.btn-attend').forEach((btn) => {
                    btn.addEventListener('click', handleAccept);
                });
            })
            .catch(() => {
                requestsList.innerHTML = '<p class="empty-state">Failed to load requests.</p>';
            });
    }

    function loadAcceptedRequests() {
        fetch(BASE + '/api/requests/accepted')
            .then((res) => res.json())
            .then((data) => {
                const accepted = data.accepted || [];
                if (accepted.length === 0) {
                    acceptedTbody.innerHTML =
                        '<tr><td colspan="3" class="empty-cell">No accepted requests yet.</td></tr>';
                    return;
                }
                acceptedTbody.innerHTML = accepted
                    .map(
                        (r) => `
                    <tr>
                        <td>${r.table}</td>
                        <td>${formatTime(r.raised_at)}</td>
                        <td>${formatTime(r.accepted_at)}</td>
                    </tr>
                `
                    )
                    .join('');
            })
            .catch(() => {
                acceptedTbody.innerHTML =
                    '<tr><td colspan="3" class="empty-cell">Failed to load.</td></tr>';
            });
    }

    function handleAccept(e) {
        const btn = e.target;
        const id = btn.getAttribute('data-id');
        if (!id || btn.disabled) return;
        btn.disabled = true;
        btn.textContent = 'Accepted';

        fetch(BASE + '/api/requests/accept', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ request_id: id }),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.ok) {
                    const item = requestsList.querySelector(`[data-request-id="${id}"]`);
                    if (item) item.remove();
                    if (requestsList.querySelectorAll('.request-item').length === 0) {
                        requestsList.innerHTML = '<p class="empty-state">No pending help requests.</p>';
                    }
                    loadAcceptedRequests();
                } else {
                    btn.disabled = false;
                    btn.textContent = "I'm attending";
                }
            })
            .catch(() => {
                btn.disabled = false;
                btn.textContent = "I'm attending";
            });
    }

    if (enableNotificationsBtn) {
        enableNotificationsBtn.addEventListener('click', function () {
            if (!('Notification' in window)) {
                alert('Notifications are not supported in this browser.');
                return;
            }
            if (Notification.permission === 'granted') {
                alert('Notifications are already enabled.');
                return;
            }
            Notification.requestPermission().then((p) => {
                if (p === 'granted') {
                    this.textContent = 'Notifications enabled';
                }
            });
        });
    }

    loadPendingRequests();
    loadAcceptedRequests();

    // Refresh pending list every 5 seconds (so new scans are noticed quickly)
    setInterval(loadPendingRequests, 5000);

    // API Token (admin only): show and copy
    const showTokenBtn = document.getElementById('show-token-btn');
    const tokenInput = document.getElementById('api-token-input');
    const copyTokenBtn = document.getElementById('copy-token-btn');
    if (showTokenBtn && tokenInput) {
        showTokenBtn.addEventListener('click', function () {
            if (tokenInput.value) {
                tokenInput.type = 'password';
                tokenInput.value = '';
                tokenInput.placeholder = 'Click to load';
                showTokenBtn.textContent = 'Show token';
                if (copyTokenBtn) copyTokenBtn.style.display = 'none';
                return;
            }
            fetch(BASE + '/api/settings/token')
                .then((res) => res.json())
                .then((data) => {
                    if (data.api_token) {
                        tokenInput.type = 'text';
                        tokenInput.value = data.api_token;
                        tokenInput.placeholder = '';
                        showTokenBtn.textContent = 'Hide';
                        if (copyTokenBtn) copyTokenBtn.style.display = 'inline-block';
                    }
                })
                .catch(() => {});
        });
        if (copyTokenBtn) {
            copyTokenBtn.addEventListener('click', function () {
                tokenInput.select();
                try {
                    navigator.clipboard.writeText(tokenInput.value);
                } catch (e) {
                    document.execCommand('copy');
                }
                copyTokenBtn.textContent = 'Copied!';
                setTimeout(function () { copyTokenBtn.textContent = 'Copy'; }, 2000);
            });
        }
    }
})();
