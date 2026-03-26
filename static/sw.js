/* Service worker for Web Push – lock screen & background notifications with Maroon sound */
self.addEventListener('push', function (event) {
    var data = { title: 'Soulplace', body: 'New help request', sound: '' };
    try {
        if (event.data) {
            var json = event.data.json();
            if (json.title) data.title = json.title;
            if (json.body) data.body = json.body;
            if (json.sound) data.sound = json.sound;
        }
    } catch (e) {}
    var origin = self.location.origin;
    var opts = {
        body: data.body,
        icon: origin + '/static/images/logo.png',
        badge: origin + '/static/images/logo.png',
        tag: 'soulplace-help',
        requireInteraction: false,
        silent: false
    };
    var soundUrl = data.sound || (origin + '/static/sounds/maroon_5_animals.mp3');
    opts.sound = soundUrl;
    event.waitUntil(self.registration.showNotification(data.title, opts));
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    var url = self.location.origin + '/soulplace/dashboard';
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
            for (var i = 0; i < list.length; i++) {
                if (list[i].url.indexOf('/soulplace') !== -1) {
                    list[i].focus();
                    return;
                }
            }
            if (clients.openWindow) clients.openWindow(url);
        })
    );
});
