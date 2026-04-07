/* =============================================================================
   FlyMyByte — Pure JS UI Modules (0 dependencies, ~4KB gzipped)
   ============================================================================= */

(function() {
    'use strict';

    // =========================================================================
    // 1. BURGER MENU
    // =========================================================================

    function initBurgerMenu() {
        var burger = document.querySelector('.icon-menu');
        var menuBody = document.querySelector('.menu__body');
        if (!burger || !menuBody) return;

        burger.addEventListener('click', function() {
            document.body.classList.toggle('_lock');
            burger.classList.toggle('_active');
            menuBody.classList.toggle('_active');
        });

        // Close on link click (mobile)
        var links = menuBody.querySelectorAll('a');
        links.forEach(function(link) {
            link.addEventListener('click', function() {
                document.body.classList.remove('_lock');
                burger.classList.remove('_active');
                menuBody.classList.remove('_active');
            });
        });
    }

    // =========================================================================
    // 2. POPUP (MODAL) — with scroll lock and ESC
    // =========================================================================

    var _popupOpen = null;

    function openPopup(id) {
        var popup = document.getElementById(id);
        if (!popup) return;
        popup.classList.add('modal--open');
        document.body.classList.add('_lock');
        _popupOpen = popup;
    }

    function closePopup(id) {
        var popup = id ? document.getElementById(id) : _popupOpen;
        if (!popup) return;
        popup.classList.remove('modal--open');
        document.body.classList.remove('_lock');
        if (_popupOpen === popup) _popupOpen = null;
    }

    function initPopup() {
        // Open buttons
        document.querySelectorAll('[data-popup]').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                var target = this.getAttribute('data-popup');
                openPopup(target);
            });
        });

        // Close buttons
        document.querySelectorAll('[data-close]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                closePopup();
            });
        });

        // Close on overlay click
        document.querySelectorAll('.modal').forEach(function(modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    closePopup();
                }
            });
        });

        // Close on ESC
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && _popupOpen) {
                closePopup();
            }
        });
    }

    // =========================================================================
    // 3. TABS
    // =========================================================================

    function initTabs() {
        document.querySelectorAll('[data-tabs]').forEach(function(tabsBlock) {
            var nav = tabsBlock.querySelector('[data-tabs-titles]');
            var content = tabsBlock.querySelector('[data-tabs-body]');
            if (!nav || !content) return;

            var titles = nav.querySelectorAll('[data-tabs-title]');
            var bodies = content.querySelectorAll('[data-tabs-body-item]');

            titles.forEach(function(title, i) {
                title.addEventListener('click', function() {
                    if (title.classList.contains('_tab-active')) return;

                    titles.forEach(function(t) { t.classList.remove('_tab-active'); });
                    bodies.forEach(function(b) { b.classList.remove('_tab-active'); });

                    title.classList.add('_tab-active');
                    if (bodies[i]) bodies[i].classList.add('_tab-active');
                });
            });
        });
    }

    // =========================================================================
    // 4. SPOILERS (ACCORDION)
    // =========================================================================

    function initSpoilers() {
        document.querySelectorAll('[data-spoilers]').forEach(function(group) {
            var isAccordion = group.hasAttribute('data-one-spoiler');
            var items = group.querySelectorAll('[data-spoiler-item]');

            items.forEach(function(item) {
                var title = item.querySelector('[data-spoiler-title]');
                var body = item.querySelector('[data-spoiler-body]');
                if (!title || !body) return;

                // Init state from class
                if (title.classList.contains('_spoller-active')) {
                    body.style.maxHeight = body.scrollHeight + 'px';
                    body.style.overflow = '';
                } else {
                    body.style.maxHeight = '0';
                    body.style.overflow = 'hidden';
                }

                title.addEventListener('click', function() {
                    var isActive = title.classList.contains('_spoller-active');

                    if (isAccordion && !isActive) {
                        // Close all others
                        items.forEach(function(other) {
                            if (other === item) return;
                            var otherTitle = other.querySelector('[data-spoiler-title]');
                            var otherBody = other.querySelector('[data-spoiler-body]');
                            if (otherTitle) otherTitle.classList.remove('_spoller-active');
                            if (otherBody) {
                                otherBody.style.maxHeight = '0';
                                otherBody.style.overflow = 'hidden';
                            }
                        });
                    }

                    if (isActive) {
                        title.classList.remove('_spoller-active');
                        body.style.maxHeight = '0';
                        body.style.overflow = 'hidden';
                    } else {
                        title.classList.add('_spoller-active');
                        body.style.maxHeight = body.scrollHeight + 'px';
                        body.style.overflow = '';
                    }
                });
            });
        });
    }

    // =========================================================================
    // 5. SHOW MORE (truncate long content)
    // =========================================================================

    function initShowMore() {
        document.querySelectorAll('[data-showmore]').forEach(function(block) {
            var content = block.querySelector('[data-showmore-content]');
            var btn = block.querySelector('[data-showmore-button]');
            if (!content || !btn) return;

            var maxHeight = parseInt(content.getAttribute('data-showmore-content')) || 200;

            function checkHeight() {
                if (content.scrollHeight > maxHeight && !block.classList.contains('_showmore-active')) {
                    content.style.maxHeight = maxHeight + 'px';
                    content.style.overflow = 'hidden';
                    btn.style.display = '';
                }
            }

            btn.addEventListener('click', function() {
                block.classList.toggle('_showmore-active');
                if (block.classList.contains('_showmore-active')) {
                    content.style.maxHeight = 'none';
                    content.style.overflow = '';
                    btn.textContent = btn.getAttribute('data-showmore-text-hide') || 'Скрыть';
                } else {
                    content.style.maxHeight = maxHeight + 'px';
                    content.style.overflow = 'hidden';
                    btn.textContent = btn.getAttribute('data-showmore-text-show') || 'Показать ещё';
                }
            });

            checkHeight();
            window.addEventListener('resize', checkHeight);
        });
    }

    // =========================================================================
    // 6. SMOOTH SCROLL (data-goto)
    // =========================================================================

    function initSmoothScroll() {
        document.querySelectorAll('[data-goto]').forEach(function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                var target = this.getAttribute('data-goto');
                var el = document.querySelector(target);
                if (!el) return;

                var headerOffset = 0;
                if (this.hasAttribute('data-goto-header')) {
                    var header = document.querySelector('.navbar');
                    if (header) headerOffset = header.offsetHeight;
                }
                var topOffset = parseInt(this.getAttribute('data-goto-top')) || 0;

                var top = el.getBoundingClientRect().top + window.pageYOffset - headerOffset - topOffset;
                window.scrollTo({ top: top, behavior: 'smooth' });
            });
        });
    }

    // =========================================================================
    // 7. VIEW PASSWORD (toggle password visibility)
    // =========================================================================

    function initViewPass() {
        document.querySelectorAll('.viewpass').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var input = this.closest('.form-group').querySelector('input[type="password"], input[type="text"]');
                if (!input) return;

                var isPassword = input.type === 'password';
                input.type = isPassword ? 'text' : 'password';
                this.classList.toggle('_active', isPassword);

                // Update icon text
                this.textContent = isPassword ? 'Скрыть' : 'Показать';
            });
        });
    }

    // =========================================================================
    // INIT ALL
    // =========================================================================

    function init() {
        initBurgerMenu();
        initPopup();
        initTabs();
        initSpoilers();
        initShowMore();
        initSmoothScroll();
        initViewPass();
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose to global for inline handlers
    window.openModal = openPopup;
    window.closeModal = closePopup;

})();
