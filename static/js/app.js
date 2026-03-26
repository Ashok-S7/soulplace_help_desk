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
    let audioUnlocked = false;   // Set true on first user click so sound can play when new request arrives
    let beepAudioElement = null; // Inline beep played on click so it can replay when new request arrives (no user gesture)

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

    /** Create a short beep as WAV blob URL – play this on click so we can replay it when new request arrives (no gesture). */
    function createBeepAudioUrl() {
        var sampleRate = 8000;
        var duration = 0.4;
        var freq = 880;
        var numSamples = Math.floor(sampleRate * duration);
        var buffer = new ArrayBuffer(44 + numSamples * 2);
        var view = new DataView(buffer);
        var pos = 0;
        function writeStr(s) { for (var i = 0; i < s.length; i++) view.setUint8(pos++, s.charCodeAt(i)); }
        writeStr('RIFF');
        view.setUint32(pos, 36 + numSamples * 2, true); pos += 4;
        writeStr('WAVEfmt ');
        view.setUint32(pos, 16, true); pos += 4;
        view.setUint16(pos, 1, true); pos += 2;
        view.setUint16(pos, 1, true); pos += 2;
        view.setUint32(pos, sampleRate, true); pos += 4;
        view.setUint32(pos, sampleRate * 2, true); pos += 4;
        view.setUint16(pos, 2, true); pos += 2;
        view.setUint16(pos, 16, true); pos += 2;
        writeStr('data');
        view.setUint32(pos, numSamples * 2, true); pos += 4;
        for (var i = 0; i < numSamples; i++) {
            var t = i / sampleRate;
            var sample = Math.sin(2 * Math.PI * freq * t) * 0.7 * Math.exp(-t * 4);
            view.setInt16(pos, Math.max(-32768, Math.min(32767, sample * 32767)), true);
            pos += 2;
        }
        return URL.createObjectURL(new Blob([buffer], { type: 'audio/wav' }));
    }

    function playUnlockedBeep() {
        if (!beepAudioElement) return;
        try {
            beepAudioElement.currentTime = 0;
            beepAudioElement.volume = 1;
            beepAudioElement.play().catch(function () {});
        } catch (e) {}
    }

    function unlockAudio() {
        if (audioUnlocked) return;
        audioUnlocked = true;
        try {
            var ctx = getAudioContext();
            if (ctx && ctx.state === 'suspended') ctx.resume();
        } catch (e) {}
    }

    function playNewRequestSound() {
        // Play the inline beep first – this element was played on click so browser allows replay (no user gesture needed)
        playUnlockedBeep();
        try {
            var ctx = getAudioContext();
            if (ctx && ctx.state === 'suspended') ctx.resume();
        } catch (e) {}
        try { playBeepFallback(); } catch (e) {}
        function fallback(err) {
            if (typeof console !== 'undefined' && console.error) console.error('[Soulplace] Maroon failed:', err || 'blocked or load error');
        }
        var el = document.getElementById('notification-audio');
        if (el && el.src) {
            el.volume = 1;
            el.currentTime = 0;
            el.play().then(function () {}).catch(fallback);
            return;
        }
        var url = getNotificationSoundUrl();
        var audio = new Audio(url);
        audio.volume = 1;
        audio.onerror = fallback;
        audio.play().then(function () {}).catch(fallback);
    }

    function playBeepFallback() {
        try {
            var ctx = getAudioContext();
            if (!ctx) return;
            function playBeep() {
                var t = ctx.currentTime;
                var osc1 = ctx.createOscillator();
                var gain1 = ctx.createGain();
                osc1.connect(gain1);
                gain1.connect(ctx.destination);
                osc1.frequency.value = 880;
                osc1.type = 'sine';
                gain1.gain.setValueAtTime(0.7, t);
                gain1.gain.exponentialRampToValueAtTime(0.01, t + 0.25);
                osc1.start(t);
                osc1.stop(t + 0.25);
                var osc2 = ctx.createOscillator();
                var gain2 = ctx.createGain();
                osc2.connect(gain2);
                gain2.connect(ctx.destination);
                osc2.frequency.value = 1100;
                osc2.type = 'sine';
                gain2.gain.setValueAtTime(0.65, t + 0.3);
                gain2.gain.exponentialRampToValueAtTime(0.01, t + 0.55);
                osc2.start(t + 0.3);
                osc2.stop(t + 0.55);
            }
            if (ctx.state === 'suspended') {
                ctx.resume().then(playBeep).catch(function (err) {
                    if (typeof console !== 'undefined' && console.error) console.error('[Soulplace] Beep AudioContext resume error:', err);
                });
            } else {
                playBeep();
            }
        } catch (e) {
            if (typeof console !== 'undefined' && console.error) console.error('[Soulplace] Beep play error:', e);
        }
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
                // After first poll, play sound when any NEW request id appears (not on initial page load).
                // Note: must NOT require previousRequestIds.size > 0 — otherwise 0 → 1 pending never plays sound.
                if (hasInitialLoad) {
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
            .catch(function (err) {
                if (typeof console !== 'undefined' && console.error) console.error('[Soulplace] Failed to load requests:', err);
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
            .catch(function (err) {
                if (typeof console !== 'undefined' && console.error) console.error('[Soulplace] Failed to load accepted requests:', err);
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
            unlockAudio();
            var banner = document.getElementById('enable-sound-banner');
            if (banner) banner.style.display = 'none';
            try {
                var ctx = getAudioContext();
                if (ctx && ctx.state === 'suspended') ctx.resume();
                playNewRequestSound();
            } catch (e) {
                playBeepFallback();
            }
        });
    }

    function urlBase64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - base64String.length % 4) % 4);
        var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        var rawData = window.atob(base64);
        var outputArray = new Uint8Array(rawData.length);
        for (var i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
        return outputArray;
    }

    function subscribeToPush() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
        if (Notification.permission !== 'granted') return;
        navigator.serviceWorker.register(BASE + '/sw.js', { scope: BASE + '/' })
            .then(function (reg) {
                return fetch(BASE + '/api/push-vapid-public', { credentials: 'same-origin' }).then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (!data.publicKey) return;
                        return reg.pushManager.subscribe({
                            userVisibleOnly: true,
                            applicationServerKey: urlBase64ToUint8Array(data.publicKey)
                        });
                    });
            })
            .then(function (sub) {
                if (!sub) return;
                return fetch(BASE + '/api/push-subscribe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(sub),
                    credentials: 'same-origin'
                });
            })
            .then(function (r) { if (r && r.ok) console.log('Push subscribed (notifications when screen off)'); })
            .catch(function () {});
    }

    function setNotificationButtonLabel() {
        if (!enableNotificationsBtn || !('Notification' in window)) return;
        if (Notification.permission === 'granted') {
            // Already allowed — not a “disable” action in-app; turning off is only via browser site settings
            enableNotificationsBtn.textContent = 'Website notifications: On';
            enableNotificationsBtn.title = 'Browser already allows notifications for this site. Click to test sound. To turn off: lock icon → Site settings → Notifications → Block.';
        } else {
            enableNotificationsBtn.textContent = 'Enable website notifications';
            enableNotificationsBtn.title = 'Allow browser notifications for this site (in-app + lock screen when signed in).';
        }
    }
    if (enableNotificationsBtn) {
        setNotificationButtonLabel();
        if (Notification.permission === 'granted') subscribeToPush();
        enableNotificationsBtn.addEventListener('click', function () {
            if (!('Notification' in window)) {
                alert('Notifications are not supported in this browser.');
                return;
            }
            if (Notification.permission === 'granted') {
                unlockAudio();
                var banner = document.getElementById('enable-sound-banner');
                if (banner) banner.style.display = 'none';
                if (!beepAudioElement) {
                    var beepUrl = createBeepAudioUrl();
                    beepAudioElement = new Audio(beepUrl);
                    beepAudioElement.volume = 1;
                }
                beepAudioElement.currentTime = 0;
                beepAudioElement.play().then(function () {}).catch(function () {});
                var el = document.getElementById('notification-audio');
                if (el && el.src) { el.volume = 1; el.currentTime = 0; el.play().then(function () {}).catch(function () {}); }
                return;
            }
            if (Notification.permission === 'denied') {
                alert('Notifications were blocked earlier. To enable: click the lock icon in the address bar → Site settings → Notifications → set to Allow, then refresh this page.');
                return;
            }
            // permission is 'default' – request permission
            enableNotificationsBtn.disabled = true;
            enableNotificationsBtn.textContent = 'Asking…';
            Notification.requestPermission().then(function (p) {
                enableNotificationsBtn.disabled = false;
                setNotificationButtonLabel();
                if (p === 'granted') {
                    unlockAudio();
                    var banner = document.getElementById('enable-sound-banner');
                    if (banner) banner.style.display = 'none';
                    if (!beepAudioElement) {
                        var beepUrl = createBeepAudioUrl();
                        beepAudioElement = new Audio(beepUrl);
                        beepAudioElement.volume = 1;
                    }
                    beepAudioElement.currentTime = 0;
                    beepAudioElement.play().then(function () {}).catch(function () {});
                    var el = document.getElementById('notification-audio');
                    if (el && el.src) { el.volume = 1; el.currentTime = 0; el.play().then(function () {}).catch(function () {}); }
                    showNewRequestNotification([{ table: 'Test' }]);
                    subscribeToPush();
                    alert('Notifications enabled! You will get sound, pop-up, and notifications even when your mobile screen is off.');
                } else if (p === 'denied') {
                    alert('Notifications were blocked. You can allow them later in browser settings (lock icon → Site settings → Notifications).');
                }
            }).catch(function () {
                enableNotificationsBtn.disabled = false;
                setNotificationButtonLabel();
            });
        });
    }

    var notificationAudio = document.getElementById('notification-audio');
    if (notificationAudio) {
        notificationAudio.onerror = function () { try { playBeepFallback(); } catch (e) {} };
        notificationAudio.load(); // Start loading MP3 (maroon_5_animals) so it's ready when a request arrives
    }

    // Unlock audio on first click/touch so notification SOUND can play when new request arrives (browsers block sound until user interaction)
    function oneTimeUnlock() {
        unlockAudio();
        document.removeEventListener('click', oneTimeUnlock);
        document.removeEventListener('touchstart', oneTimeUnlock);
        var tip = document.getElementById('sound-unlock-tip');
        if (tip) tip.style.display = 'none';
        var banner = document.getElementById('enable-sound-banner');
        if (banner) banner.style.display = 'none';
    }
    document.addEventListener('click', oneTimeUnlock, { once: true, passive: true });
    document.addEventListener('touchstart', oneTimeUnlock, { once: true, passive: true });

    // Show "Enable notification sound" banner and handle button click
    var enableSoundBanner = document.getElementById('enable-sound-banner');
    var enableSoundBtn = document.getElementById('enable-sound-btn');
    if (enableSoundBanner && enableSoundBtn) {
        enableSoundBanner.style.display = 'block';
        enableSoundBtn.addEventListener('click', function () {
            unlockAudio();
            // Create and play inline beep in this click – same element we'll replay when new request arrives (browser allows replay)
            if (!beepAudioElement) {
                var beepUrl = createBeepAudioUrl();
                beepAudioElement = new Audio(beepUrl);
                beepAudioElement.volume = 1;
            }
            beepAudioElement.currentTime = 0;
            beepAudioElement.play().then(function () {}).catch(function () {});
            var el = document.getElementById('notification-audio');
            if (el && el.src) {
                el.volume = 1;
                el.currentTime = 0;
                el.play().then(function () {}).catch(function () {});
            }
            enableSoundBanner.style.display = 'none';
        });
    }

    loadPendingRequests();
    loadAcceptedRequests();

    // Poll every 1 second for quick sound/notification when new requests arrive
    setInterval(loadPendingRequests, 1000);

    // Admin-only: push (lock-screen) debug + test push
    var pushCountEl = document.getElementById('push-count');
    var vapidKeysEl = document.getElementById('vapid-keys');
    var pushTestBtn = document.getElementById('push-test-btn');
    var pushDebugResultEl = document.getElementById('push-debug-result');
    if (pushCountEl) {
        fetch(BASE + '/api/push-status', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (d) {
                if (!d || !d.ok) return;
                pushCountEl.textContent = d.push_subscriptions_count != null ? String(d.push_subscriptions_count) : '0';
                var priv = d.vapid_private_key_set ? 'set' : 'missing';
                var pub = d.vapid_public_key_set ? 'set' : 'missing';
                vapidKeysEl.textContent = 'private: ' + priv + ', public: ' + pub;
            })
            .catch(function () {});
    }
    if (pushTestBtn) {
        pushTestBtn.addEventListener('click', function () {
            if (pushDebugResultEl) pushDebugResultEl.textContent = 'Sending test push…';
            pushTestBtn.disabled = true;
            fetch(BASE + '/api/push-test', { method: 'POST', credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    if (!pushDebugResultEl) return;
                    if (d && d.ok) {
                        pushDebugResultEl.textContent = d.message || 'Test push sent.';
                    } else {
                        pushDebugResultEl.textContent = (d && d.error) ? d.error : 'Test push failed.';
                    }
                })
                .catch(function () {
                    if (pushDebugResultEl) pushDebugResultEl.textContent = 'Test push failed (request error).';
                })
                .finally(function () {
                    pushTestBtn.disabled = false;
                    // Refresh status after sending
                    if (pushCountEl) {
                        fetch(BASE + '/api/push-status', { credentials: 'same-origin' })
                            .then(function (r) { return r.json(); })
                            .then(function (d) {
                                if (!d || !d.ok) return;
                                pushCountEl.textContent = d.push_subscriptions_count != null ? String(d.push_subscriptions_count) : '0';
                            })
                            .catch(function () {});
                    }
                });
        });
    }

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
