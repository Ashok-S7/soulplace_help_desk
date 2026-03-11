/**
 * Soulplace Boardgames Help Desk – dashboard logic
 */

(function () {
    const BASE = window.SOULPLACE_BASE || "";
    const requestsList = document.getElementById('requests-list');
    const acceptedTbody = document.getElementById('accepted-tbody');
    const enableNotificationsBtn = document.getElementById('enable-notifications');
    const testSoundBtn = document.getElementById('test-sound-btn');

    // Only run dashboard logic on the dashboard (avoid running on login or other pages)
    if (!requestsList || !acceptedTbody) return;

    let previousRequestIds = new Set();
    let hasInitialLoad = false;  // Don't fire notification/sound on first load when opening login→dashboard
    let audioContext = null;

    /** Display time (backend sends Chennai IST already). */
    function formatTime(val) {
        return val != null ? String(val) : "";
    }

    function getAudioContext() {
        if (!audioContext) {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (Ctx) audioContext = new Ctx();
        }
        return audioContext;
    }

    function getNotificationSoundUrl() {
        var path = window.SOULPLACE_NOTIFICATION_SOUND || '/static/sounds/maroon_5_animals.mp3';
        if (path.indexOf('http') === 0) return path;
        var origin = window.location.origin || '';
        var p = path.charAt(0) === '/' ? path : '/' + path;
        return origin + p;
    }

    function playNewRequestSound() {
        var el = document.getElementById('notification-audio');
        if (el && el.src) {
            el.currentTime = 0;
            el.volume = 0.7;
            var played = el.play();
            if (played && played.catch) played.catch(function () { playBeepFallback(); });
            return;
        }
        var url = getNotificationSoundUrl();
        var audio = new Audio(url);
        audio.volume = 0.7;
        audio.onerror = function () { playBeepFallback(); };
        audio.play().catch(function () { playBeepFallback(); });
    }

    function playBeepFallback() {
        try {
            const ctx = getAudioContext();
            if (!ctx) return;
            if (ctx.state === 'suspended') ctx.resume();
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

    function showNewRequestNotification(requests) {
        if (!('Notification' in window)) return;
        if (Notification.permission !== 'granted') return;
        try {
            var title = 'Soulplace – New help request';
            var body;
            if (requests.length === 1) {
                var r = requests[0];
                body = 'Table ' + r.table;
                if (r.note) body += ' – ' + r.note;
                body += ' – needs a Soul.';
            } else {
                body = requests.length + ' new help requests.';
            }
            var n = new Notification(title, { body: body, requireInteraction: false });
            n.onclick = function () {
                window.focus();
                n.close();
            };
            setTimeout(function () { n.close(); }, 6000);
        } catch (err) {
            console.warn('Notification failed:', err);
        }
    }

    function loadPendingRequests() {
        fetch(BASE + '/api/requests')
            .then((res) => res.json())
            .then((data) => {
                const requests = data.requests || [];
                const currentIds = new Set(requests.map((r) => r.id));
                // Only play sound/show notification after first load, and only when NEW requests appear (not when opening the page)
                if (hasInitialLoad && previousRequestIds.size > 0 && currentIds.size > previousRequestIds.size) {
                    var newReqs = requests.filter(function (r) { return !previousRequestIds.has(r.id); });
                    if (newReqs.length) {
                        playNewRequestSound();
                        showNewRequestNotification(newReqs);
                    }
                }
                hasInitialLoad = true;
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
                            ${r.note ? '<span class="request-note">' + (r.note.replace(/</g, '&lt;')) + '</span>' : ''}
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
                        '<tr><td colspan="4" class="empty-cell">No accepted requests yet.</td></tr>';
                    return;
                }
                acceptedTbody.innerHTML = accepted
                    .map(
                        (r) => {
                            var noteHtml = r.note ? (r.note.replace(/</g, '&lt;')) : '—';
                            return `
                    <tr>
                        <td>${r.table}</td>
                        <td><span class="accepted-note">${noteHtml}</span></td>
                        <td>${formatTime(r.raised_at)}</td>
                        <td>${formatTime(r.accepted_at)}</td>
                    </tr>
                `;
                        }
                    )
                    .join('');
            })
            .catch(() => {
                acceptedTbody.innerHTML =
                    '<tr><td colspan="4" class="empty-cell">Failed to load.</td></tr>';
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

    if (testSoundBtn) {
        testSoundBtn.addEventListener('click', function () {
            var ctx = getAudioContext();
            if (ctx && ctx.state === 'suspended') ctx.resume();
            playNewRequestSound();
        });
    }

    if (enableNotificationsBtn) {
        enableNotificationsBtn.addEventListener('click', function () {
            if (!('Notification' in window)) {
                alert('Notifications are not supported in this browser.');
                return;
            }
            if (Notification.permission === 'granted') {
                enableNotificationsBtn.textContent = 'Notifications enabled';
                var ctx = getAudioContext();
                if (ctx && ctx.state === 'suspended') ctx.resume();
                playNewRequestSound();
                showNewRequestNotification([{ table: 'Test' }]);
                return;
            }
            if (Notification.permission === 'denied') {
                alert('Notifications are blocked. Please allow them in your browser settings (e.g. Chrome: lock icon → Site settings → Notifications) and refresh.');
                return;
            }
            Notification.requestPermission().then(function (p) {
                if (p === 'granted') {
                    enableNotificationsBtn.textContent = 'Notifications enabled';
                    var ctx = getAudioContext();
                    if (ctx && ctx.state === 'suspended') ctx.resume();
                    playNewRequestSound();
                    showNewRequestNotification([{ table: 'Test' }]);
                } else if (p === 'denied') {
                    alert('Notifications were blocked. You can allow them later in browser settings.');
                }
            });
        });
        if (Notification.permission === 'granted') {
            enableNotificationsBtn.textContent = 'Notifications enabled';
        }
    }

    var notificationAudio = document.getElementById('notification-audio');
    if (notificationAudio) {
        notificationAudio.onerror = function () { playBeepFallback(); };
    }

    loadPendingRequests();
    loadAcceptedRequests();

    // Poll every 2 seconds so new requests trigger sound/notification with minimal delay
    setInterval(loadPendingRequests, 2000);

    // Clear all pending (for testing – so you see only the request you just raised)
    const clearAllPendingBtn = document.getElementById('clear-all-pending-btn');
    if (clearAllPendingBtn) {
        clearAllPendingBtn.addEventListener('click', function () {
            if (!confirm('Clear all help requests and accepted list? Use this to reset when testing.')) return;
            clearAllPendingBtn.disabled = true;
            fetch(BASE + '/api/requests/clear', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.ok) {
                        previousRequestIds = new Set();
                        loadPendingRequests();
                        loadAcceptedRequests();
                    }
                    clearAllPendingBtn.disabled = false;
                })
                .catch(function () { clearAllPendingBtn.disabled = false; });
        });
    }

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
