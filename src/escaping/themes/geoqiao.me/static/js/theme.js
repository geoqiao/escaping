// geoqiao.me Signal Blue theme controller.
(function() {
    'use strict';

    var STORAGE_KEY = 'theme';
    var LIGHT = 'light';
    var DARK = 'dark';
    var THEME_COLORS = { light: '#f4f6f8', dark: '#0c1118' };

    function storedTheme() {
        try {
            var value = localStorage.getItem(STORAGE_KEY);
            return value === LIGHT || value === DARK ? value : null;
        } catch (error) {
            return null;
        }
    }

    function systemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK : LIGHT;
    }

    function updateButton(theme) {
        var button = document.querySelector('.theme-toggle');
        if (!button) return;
        var dark = theme === DARK;
        var label = button.querySelector('[data-theme-label]');
        button.setAttribute('aria-pressed', dark ? 'true' : 'false');
        button.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
        if (label) label.textContent = dark ? 'Light' : 'Dark';
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        var themeColor = document.querySelector('#theme-color');
        if (themeColor) themeColor.setAttribute('content', THEME_COLORS[theme]);
        updateButton(theme);
    }

    function rememberTheme(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (error) {
            // A blocked storage API must not make the theme control unusable.
        }
    }

    applyTheme(storedTheme() || systemTheme());

    document.addEventListener('DOMContentLoaded', function() {
        updateButton(document.documentElement.getAttribute('data-theme') || LIGHT);
        var button = document.querySelector('.theme-toggle');
        if (!button) return;
        button.addEventListener('click', function() {
            var current = document.documentElement.getAttribute('data-theme') || LIGHT;
            var next = current === DARK ? LIGHT : DARK;
            applyTheme(next);
            rememberTheme(next);
        });
    });

    var media = window.matchMedia('(prefers-color-scheme: dark)');
    var followSystem = function(event) {
        if (!storedTheme()) applyTheme(event.matches ? DARK : LIGHT);
    };
    if (media.addEventListener) media.addEventListener('change', followSystem);
    else if (media.addListener) media.addListener(followSystem);
})();
