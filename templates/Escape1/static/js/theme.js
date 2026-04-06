// Escape1 Theme Toggle
(function() {
    'use strict';

    const STORAGE_KEY = 'theme';
    const DARK = 'dark';
    const LIGHT = 'light';

    function getStoredTheme() {
        try {
            return localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return null;
        }
    }

    function setStoredTheme(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) {
            // Ignore storage errors
        }
    }

    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK : LIGHT;
    }

    function getCurrentTheme() {
        return getStoredTheme() || getSystemTheme();
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        updateToggleButton(theme);
    }

    function updateToggleButton(theme) {
        const btn = document.querySelector('.theme-toggle');
        if (btn) {
            btn.textContent = theme === DARK ? '☀️' : '🌙';
            btn.setAttribute('aria-label', theme === DARK ? 'Switch to light mode' : 'Switch to dark mode');
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || LIGHT;
        const next = current === DARK ? LIGHT : DARK;
        applyTheme(next);
        setStoredTheme(next);
    }

    // Initialize - run immediately to prevent flash
    (function initTheme() {
        const theme = getCurrentTheme();
        document.documentElement.setAttribute('data-theme', theme);
        updateToggleButton(theme);
    })();

    // Bind click event
    document.addEventListener('DOMContentLoaded', function() {
        const btn = document.querySelector('.theme-toggle');
        if (btn) {
            btn.addEventListener('click', toggleTheme);
        }
    });

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (!getStoredTheme()) {
            applyTheme(e.matches ? DARK : LIGHT);
        }
    });
})();
