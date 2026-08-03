(function () {
    "use strict";

    var container = document.getElementById("comments-container");
    if (!container || container.dataset.commentsInitialized === "true") return;
    container.dataset.commentsInitialized = "true";

    var loadingMsg = container.querySelector(".comments-loading");
    var commentsRepo = container.dataset.commentsRepo;
    var issueNumber = container.dataset.issueNumber;
    var sourceRepo = container.dataset.sourceRepo;
    var commentsTheme = container.dataset.commentsTheme;
    var commentsThemeMode = container.dataset.commentsThemeMode;
    var defaultBlogTheme = container.dataset.blogThemeDefault || "light";

    var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    var isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    var isWebKit =
        /AppleWebKit/.test(navigator.userAgent) &&
        !/Chrome|CriOS/.test(navigator.userAgent);
    var LIGHT_THEME = "github-light";
    var DARK_THEME = "photon-dark";

    function getCurrentBlogTheme() {
        return (
            document.documentElement.getAttribute("data-theme") || defaultBlogTheme
        );
    }

    function getUtterancesTheme() {
        if (commentsThemeMode === "auto") {
            return getCurrentBlogTheme() === "dark" ? DARK_THEME : LIGHT_THEME;
        }
        return commentsTheme;
    }

    function updateUtterancesTheme() {
        var iframe = container.querySelector("iframe");
        if (iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage(
                { type: "set-theme", theme: getUtterancesTheme() },
                "https://utteranc.es"
            );
        }
    }

    // Utterances injects a lazy iframe. Safari/WebKit may never load it when
    // the parent initially has zero height, so remove that attribute both at
    // insertion time and from subsequently-added descendants.
    var originalInsertAdjacentHTML = Element.prototype.insertAdjacentHTML;
    Element.prototype.insertAdjacentHTML = function (position, text) {
        if (
            typeof text === "string" &&
            text.indexOf("<iframe") !== -1 &&
            text.indexOf('loading="lazy"') !== -1
        ) {
            text = text.replace(/loading="lazy"/g, "");
        }
        return originalInsertAdjacentHTML.call(this, position, text);
    };

    var lazyObserver = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType !== 1) return;
                if (
                    node.tagName === "IFRAME" &&
                    node.getAttribute("loading") === "lazy"
                ) {
                    node.removeAttribute("loading");
                }
                var iframes = node.querySelectorAll
                    ? node.querySelectorAll('iframe[loading="lazy"]')
                    : [];
                for (var i = 0; i < iframes.length; i++) {
                    iframes[i].removeAttribute("loading");
                }
            });
        });
    });
    lazyObserver.observe(container, { childList: true, subtree: true });

    var utterancesScript = document.createElement("script");
    utterancesScript.src = "https://utteranc.es/client.js";
    utterancesScript.setAttribute("repo", commentsRepo);
    utterancesScript.setAttribute("issue-number", issueNumber);
    utterancesScript.setAttribute("theme", getUtterancesTheme());
    utterancesScript.async = true;

    var checkInterval;
    var checkCount = 0;
    var resizeReceived = false;

    function showError() {
        if (!loadingMsg) return;
        loadingMsg.textContent = "Comments may not be available.";
        if (isIOS || isSafari || isWebKit) {
            var safariHint = document.createElement("small");
            safariHint.textContent =
                ' iOS Safari may block third-party content. Try turning off "Prevent Cross-Site Tracking".';
            loadingMsg.appendChild(document.createElement("br"));
            loadingMsg.appendChild(safariHint);
        }
        var link = document.createElement("a");
        link.href =
            "https://github.com/" + sourceRepo + "/issues/" + issueNumber;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "View or add comment on GitHub →";
        loadingMsg.appendChild(document.createElement("br"));
        loadingMsg.appendChild(link);
        loadingMsg.className = "comments-error";
    }

    function checkIframe() {
        checkCount++;
        var maxChecks = isIOS || isSafari || isWebKit ? 100 : 75;
        if (checkCount > maxChecks) {
            clearInterval(checkInterval);
            showError();
        }
    }

    utterancesScript.onload = function () {
        checkInterval = setInterval(checkIframe, 200);
        if (commentsThemeMode === "auto") {
            var themeObserver = new MutationObserver(function (mutations) {
                mutations.forEach(function (mutation) {
                    if (mutation.attributeName === "data-theme") {
                        updateUtterancesTheme();
                    }
                });
            });
            themeObserver.observe(document.documentElement, { attributes: true });
        }
    };

    utterancesScript.onerror = function () {
        clearInterval(checkInterval);
        showError();
    };

    window.addEventListener("message", function (event) {
        if (event.origin !== "https://utteranc.es") return;
        var iframe = container.querySelector("iframe");
        if (!iframe || event.source !== iframe.contentWindow) return;
        if (!event.data) return;

        if (event.data.type === "resize") {
            resizeReceived = true;
            if (loadingMsg) loadingMsg.style.display = "none";
            clearInterval(checkInterval);
        } else if (event.data.type === "error") {
            resizeReceived = true;
            clearInterval(checkInterval);
            showError();
        }
    });

    container.appendChild(utterancesScript);

    setTimeout(function () {
        clearInterval(checkInterval);
        if (!resizeReceived && loadingMsg) showError();
    }, 20000);
})();
