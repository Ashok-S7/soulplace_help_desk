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
            el.volume = 1;
            var played = el.play();
            if (played && played.catch) played.catch(function () { playBeepFallback(); });
            return;
        }
        var url = getNotificationSoundUrl();
        var audio = new Audio(url);
        audio.volume = 1;
        audio.onerror = function () { playBeepFallback(); };
        audio.play().catch(function () { playBeepFallback(); });
    }

    function playBeepFallback() {
        try {
            var ctx = getAudioContext();
            if (!ctx) return;
            if (ctx.state === 'suspended') ctx.resume();
            var t = ctx.currentTime;
            var osc1 = ctx.createOscillator();
            var gain1 = ctx.createGain();
            osc1.connect(gain1);
            gain1.connect(ctx.destination);
            osc1.frequency.value = 880;
            osc1.type = 'sine';
            gain1.gain.setValueAtTime(0.5, t);
            gain1.gain.exponentialRampToValueAtTime(0.01, t + 0.2);
            osc1.start(t);
            osc1.stop(t + 0.2);
            var osc2 = ctx.createOscillator();
            var gain2 = ctx.createGain();
            osc2.connect(gain2);
            gain2.connect(ctx.destination);
            osc2.frequency.value = 1100;
            osc2.type = 'sine';
            gain2.gain.setValueAtTime(0.45, t + 0.25);
            gain2.gain.exponentialRampToValueAtTime(0.01, t + 0.45);
            osc2.start(t + 0.25);
            osc2.stop(t + 0.45);
        } catch (e) {}
    }

    function playAttendedSound() {
        try {
            var ctx = getAudioContext();
            if (!ctx) return;
            if (ctx.state === 'suspended') ctx.resume();
            var t = ctx.currentTime;
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 523;
            osc.type = 'sine';
            gain.gain.setValueAtTime(0.3, t);
            gain.gain.exponentialRampToValueAtTime(0.01, t + 0.15);
            osc.start(t);
            osc.stop(t + 0.15);
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

    var lastPendingRequests = [];
    var acceptedTableNumbers = new Set();

    function updateTableGrid(pending, acceptedTabs) {
        lastPendingRequests = pending || [];
        var grid = document.getElementById('table-grid');
        if (!grid) return;
        var numTables = parseInt(grid.getAttribute('data-num-tables') || (document.getElementById('num-tables') && document.getElementById('num-tables').textContent), 10) || 10;
        var pendingTabs = new Set((pending || []).map(function (r) { return r.table; }));
        var html = '';
        for (var t = 1; t <= numTables; t++) {
            var cls = 'table-grid-cell';
            if (acceptedTabs && acceptedTabs.has(t)) cls += ' table-grid-attended';
            else if (pendingTabs.has(t)) cls += ' table-grid-pending';
            else cls += ' table-grid-free';
            html += '<div class="' + cls + '" aria-label="Table ' + t + '">' + t + '</div>';
        }
        grid.innerHTML = html;
        grid.setAttribute('data-num-tables', numTables);
    }

    function loadPendingRequests() {
        fetch(BASE + '/api/requests', { credentials: 'same-origin' })
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

                updateTableGrid(requests, acceptedTableNumbers);
                if (requests.length === 0) {
                    requestsList.innerHTML = '<p class="empty-state">No pending help requests.</p>';
                } else {
                    requestsList.innerHTML = requests
                        .map(
                            (r) => {
                                var cat = r.category ? '<span class="request-category">' + (r.category.replace(/</g, '&lt;')) + '</span>' : '';
                                var urg = r.urgent ? '<span class="request-urgent">Urgent</span>' : '';
                                return `
                    <div class="request-item" data-request-id="${r.id}" ${r.urgent ? 'data-urgent="1"' : ''}>
                        <div class="request-info">
                            <strong>Table ${r.table}</strong> ${urg}
                            ${cat}
                            ${r.note ? '<span class="request-note">' + (r.note.replace(/</g, '&lt;')) + '</span>' : ''}
                            <span class="request-time">${formatTime(r.raised_at)}</span>
                        </div>
                        <button type="button" class="btn-attend" data-id="${r.id}">I'm attending</button>
                    </div>
                `;
                            }
                        )
                        .join('');
                    requestsList.querySelectorAll('.btn-attend').forEach((btn) => {
                        btn.addEventListener('click', handleAccept);
                    });
                }
            })
            .catch(() => {
                requestsList.innerHTML = '<p class="empty-state">Failed to load requests.</p>';
            });
    }

    function loadAcceptedRequests() {
        fetch(BASE + '/api/requests/accepted', { credentials: 'same-origin' })
            .then((res) => res.json())
            .then((data) => {
                const accepted = data.accepted || [];
                acceptedTableNumbers = new Set(accepted.map((r) => r.table));
                if (typeof updateTableGrid === 'function') updateTableGrid(lastPendingRequests, acceptedTableNumbers);
                if (accepted.length === 0) {
                    acceptedTbody.innerHTML =
                        '<tr><td colspan="4" class="empty-cell">No accepted requests yet.</td></tr>';
                    return;
                }
                acceptedTbody.innerHTML = accepted
                    .map(
                        (r) => {
                            var parts = [];
                            if (r.note) parts.push(r.note.replace(/</g, '&lt;'));
                            if (r.category) parts.push(r.category.replace(/</g, '&lt;'));
                            var noteHtml = parts.length ? parts.join(' • ') : '—';
                            var status = (r.status || 'on_the_way').replace(/_/g, ' ');
                            var statusBtns = r.status === 'done' ? '<span class="status-done">Done</span>' :
                                '<span class="status-label">' + status + '</span> ' +
                                '<button type="button" class="btn-status btn-sm" data-request-id="' + r.request_id + '" data-status="at_table">At table</button> ' +
                                '<button type="button" class="btn-status btn-sm" data-request-id="' + r.request_id + '" data-status="done">Done</button>';
                            return `
                    <tr data-request-id="${r.request_id}">
                        <td>${r.table}</td>
                        <td><span class="accepted-note">${noteHtml}</span></td>
                        <td>${formatTime(r.raised_at)}</td>
                        <td class="status-cell">${statusBtns}</td>
                    </tr>
                `;
                        }
                    )
                    .join('');
                acceptedTbody.querySelectorAll('.btn-status').forEach((btn) => {
                    btn.addEventListener('click', function () {
                        var rid = btn.getAttribute('data-request-id');
                        var st = btn.getAttribute('data-status');
                        if (!rid || !st) return;
                        fetch(BASE + '/api/requests/accepted/' + encodeURIComponent(rid) + '/status', {
                            method: 'PATCH',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ status: st }),
                            credentials: 'same-origin'
                        })
                            .then((res) => res.json())
                            .then((d) => { if (d.ok) loadAcceptedRequests(); })
                            .catch(() => {});
                    });
                });
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
            credentials: 'same-origin',
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.ok) {
                    playAttendedSound();
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

    function setNotificationButtonLabel() {
        if (!enableNotificationsBtn || !('Notification' in window)) return;
        if (Notification.permission === 'granted') {
            enableNotificationsBtn.textContent = 'Disable notifications';
        } else {
            enableNotificationsBtn.textContent = 'Enable notifications';
        }
    }
    if (enableNotificationsBtn) {
        setNotificationButtonLabel();
        enableNotificationsBtn.addEventListener('click', function () {
            if (!('Notification' in window)) {
                alert('Notifications are not supported in this browser.');
                return;
            }
            if (Notification.permission === 'granted') {
                alert('To disable notifications, use your browser\'s site settings (e.g. click the lock icon in the address bar → Site settings → Notifications → set to Block).');
                return;
            }
            if (Notification.permission === 'denied') {
                alert('Notifications are blocked. To enable, open your browser settings (e.g. Chrome: lock icon → Site settings → Notifications) and allow this site, then refresh.');
                return;
            }
            Notification.requestPermission().then(function (p) {
                setNotificationButtonLabel();
                if (p === 'granted') {
                    var ctx = getAudioContext();
                    if (ctx && ctx.state === 'suspended') ctx.resume();
                    playNewRequestSound();
                    showNewRequestNotification([{ table: 'Test' }]);
                } else if (p === 'denied') {
                    alert('Notifications were blocked. You can allow them later in browser settings.');
                }
            });
        });
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
            fetch(BASE + '/api/requests/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin'
            })
                .then(function (res) {
                    if (!res.ok) throw new Error('Clear failed');
                    return res.json();
                })
                .then(function (data) {
                    if (data.ok) {
                        previousRequestIds = new Set();
                        loadPendingRequests();
                        loadAcceptedRequests();
                        clearAllPendingBtn.textContent = 'Cleared';
                        setTimeout(function () { clearAllPendingBtn.textContent = 'Clear all pending'; }, 2000);
                    }
                    clearAllPendingBtn.disabled = false;
                })
                .catch(function () {
                    clearAllPendingBtn.disabled = false;
                    alert('Could not clear. If you were logged out, sign in again and try again.');
                });
        });
    }

    // Analytics
    var analyticsContent = document.getElementById('analytics-content');
    var analyticsCsvLink = document.getElementById('analytics-csv-link');
    if (analyticsContent) {
        fetch(BASE + '/api/analytics', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (d) {
                var total = d.total || 0;
                var byDay = d.by_day || {};
                var byTable = d.by_table || {};
                var days = Object.keys(byDay).sort().slice(-7);
                var txt = 'Total (30 days): ' + total + '. Last 7 days: ';
                if (days.length) days.forEach(function (day) { txt += day + ' (' + byDay[day] + '); '; });
                else txt += '—';
                analyticsContent.textContent = txt;
            })
            .catch(function () { analyticsContent.textContent = 'Could not load analytics.'; });
    }
    if (analyticsCsvLink) {
        analyticsCsvLink.href = BASE + '/api/analytics?format=csv';
        analyticsCsvLink.download = 'soulplace_analytics.csv';
    }

    // Pause (quiet hours) – admin only section
    var pauseBtn = document.getElementById('pause-requests-btn');
    if (pauseBtn) {
        fetch(BASE + '/api/settings/pause', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (d) {
                pauseBtn.textContent = d.paused ? 'Resume requests' : 'Pause new requests';
            })
            .catch(function () { pauseBtn.textContent = 'Pause'; });
        pauseBtn.addEventListener('click', function () {
            pauseBtn.disabled = true;
            fetch(BASE + '/api/settings/pause', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    if (d.ok) pauseBtn.textContent = d.paused ? 'Resume requests' : 'Pause new requests';
                    pauseBtn.disabled = false;
                })
                .catch(function () { pauseBtn.disabled = false; });
        });
    }

    // Change password
    var changePwForm = document.getElementById('change-password-form');
    var changePwFeedback = document.getElementById('change-password-feedback');
    if (changePwForm && changePwFeedback) {
        changePwForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var current = document.getElementById('current-password').value;
            var newPwd = document.getElementById('new-password').value;
            if (!current || !newPwd) return;
            changePwFeedback.style.display = 'block';
            changePwFeedback.className = 'request-feedback';
            changePwFeedback.textContent = 'Updating…';
            fetch(BASE + '/api/settings/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ current: current, new: newPwd }),
                credentials: 'same-origin'
            })
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    if (d.ok) {
                        changePwFeedback.className = 'request-feedback success';
                        changePwFeedback.textContent = d.message || 'Password updated.';
                        changePwForm.reset();
                    } else {
                        changePwFeedback.className = 'request-feedback error';
                        changePwFeedback.textContent = d.error || 'Failed.';
                    }
                })
                .catch(function () {
                    changePwFeedback.className = 'request-feedback error';
                    changePwFeedback.textContent = 'Request failed.';
                });
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
