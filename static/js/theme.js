/**
 * Dark / Light theme toggle – injects button and applies saved theme on every page.
 */
(function () {
    var STORAGE_KEY = 'soulplace-theme';
    var sun = '\u2600';   /* ☀ */
    var moon = '\u263D';  /* ☽ */

    function getTheme() {
        try {
            var s = localStorage.getItem(STORAGE_KEY);
            if (s === 'dark' || s === 'light') return s;
        } catch (e) {}
        return 'light';
    }

    function setTheme(theme) {
        var root = document.documentElement;
        root.setAttribute('data-theme', theme);
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) {}
        if (window.updateThemeToggle) window.updateThemeToggle(theme);
    }

    function bindToggle(btn) {
        if (!btn) return;
        function setSymbol(theme) {
            btn.textContent = theme === 'dark' ? sun : moon;
        }
        setSymbol(getTheme());
        window.updateThemeToggle = setSymbol;
        btn.addEventListener('click', function () {
            var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            setTheme(next);
        });
    }

    function init() {
        setTheme(getTheme());
        var btn = document.getElementById('theme-toggle') || document.querySelector('.theme-toggle');
        if (btn) {
            bindToggle(btn);
        } else {
            var newBtn = document.createElement('button');
            newBtn.type = 'button';
            newBtn.className = 'theme-toggle';
            newBtn.id = 'theme-toggle';
            newBtn.setAttribute('aria-label', 'Toggle dark / light theme');
            newBtn.setAttribute('title', 'Dark / Light');
            document.body.insertBefore(newBtn, document.body.firstChild);
            bindToggle(newBtn);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
