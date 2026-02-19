/**
 * AI-226: User Onboarding Flow - First-Run Experience & Setup Wizard
 *
 * Implements a 5-step onboarding wizard as a modal overlay for first-time
 * dashboard users. State is persisted in localStorage.
 *
 * Steps:
 *   1. Welcome & Plan Selection
 *   2. Connect Repository
 *   3. Connect Linear (Optional)
 *   4. Configure First Agent Run
 *   5. Watch It Work (live progress simulation)
 */

'use strict';

(function (global) {

    // -------------------------------------------------------------------------
    // Constants
    // -------------------------------------------------------------------------

    var STORAGE_KEY_STEP = 'onboarding_step';
    var STORAGE_KEY_COMPLETE = 'onboarding_complete';
    var STORAGE_KEY_DATA = 'onboarding_data';

    var TOTAL_STEPS = 5;

    var PLAN_LABELS = {
        explorer: 'Explorer — Free',
        builder: 'Builder — $29/mo',
        team: 'Team — $99/mo',
        scale: 'Scale — Custom'
    };

    var MODEL_OPTIONS = [
        { value: 'claude-haiku-3-5', label: 'Claude Haiku (Default – Free)' },
        { value: 'claude-sonnet-4-5', label: 'Claude Sonnet' },
        { value: 'claude-opus-4-6', label: 'Claude Opus' }
    ];

    var DEMO_STEPS = [
        'Fetching ticket AI-001: "Add pagination to API"...',
        'Analyzing codebase structure...',
        'Planning implementation (3 files)...',
        'Writing code changes...',
        'Running tests... (12/12 passing)',
        'Creating pull request...',
        'Done! PR #42 opened successfully.'
    ];

    // -------------------------------------------------------------------------
    // OnboardingWizard Class
    // -------------------------------------------------------------------------

    /**
     * @class OnboardingWizard
     * Manages the 5-step onboarding modal overlay.
     */
    function OnboardingWizard(options) {
        options = options || {};
        this._storage = options.storage || (typeof localStorage !== 'undefined' ? localStorage : null);
        this._document = options.document || (typeof document !== 'undefined' ? document : null);
        this._overlayId = 'onboarding-overlay';
        this._demoTimer = null;
        this._demoIndex = 0;
    }

    // -------------------------------------------------------------------------
    // State helpers
    // -------------------------------------------------------------------------

    /**
     * Returns the current onboarding step (1-5), defaulting to 1.
     */
    OnboardingWizard.prototype.getCurrentStep = function () {
        if (!this._storage) return 1;
        var val = parseInt(this._storage.getItem(STORAGE_KEY_STEP), 10);
        if (isNaN(val) || val < 1 || val > TOTAL_STEPS) return 1;
        return val;
    };

    /**
     * Persists the current step to localStorage.
     * @param {number} step
     */
    OnboardingWizard.prototype.setCurrentStep = function (step) {
        if (!this._storage) return;
        this._storage.setItem(STORAGE_KEY_STEP, String(step));
    };

    /**
     * Returns true when onboarding has been marked complete.
     */
    OnboardingWizard.prototype.isComplete = function () {
        if (!this._storage) return false;
        return this._storage.getItem(STORAGE_KEY_COMPLETE) === 'true';
    };

    /**
     * Marks onboarding as complete in localStorage.
     */
    OnboardingWizard.prototype.markComplete = function () {
        if (!this._storage) return;
        this._storage.setItem(STORAGE_KEY_COMPLETE, 'true');
        this._storage.removeItem(STORAGE_KEY_STEP);
    };

    /**
     * Resets onboarding state so the wizard can be relaunched.
     */
    OnboardingWizard.prototype.reset = function () {
        if (!this._storage) return;
        this._storage.removeItem(STORAGE_KEY_COMPLETE);
        this._storage.removeItem(STORAGE_KEY_STEP);
        this._storage.removeItem(STORAGE_KEY_DATA);
    };

    /**
     * Persists wizard form data (repo, api key, etc.) across refreshes.
     * @param {Object} data
     */
    OnboardingWizard.prototype.saveData = function (data) {
        if (!this._storage) return;
        try {
            var existing = this.loadData();
            var merged = Object.assign({}, existing, data);
            this._storage.setItem(STORAGE_KEY_DATA, JSON.stringify(merged));
        } catch (e) { /* ignore quota errors */ }
    };

    /**
     * Loads previously saved wizard data.
     * @returns {Object}
     */
    OnboardingWizard.prototype.loadData = function () {
        if (!this._storage) return {};
        try {
            var raw = this._storage.getItem(STORAGE_KEY_DATA);
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            return {};
        }
    };

    // -------------------------------------------------------------------------
    // First-run detection
    // -------------------------------------------------------------------------

    /**
     * Returns true if the user should see onboarding (no onboarding_complete flag).
     */
    OnboardingWizard.prototype.shouldShow = function () {
        return !this.isComplete();
    };

    // -------------------------------------------------------------------------
    // Wizard lifecycle
    // -------------------------------------------------------------------------

    /**
     * Initialises and shows the onboarding wizard on first load.
     * Called from DOMContentLoaded; no-ops when onboarding is already complete.
     */
    OnboardingWizard.prototype.init = function () {
        if (!this.shouldShow()) return;
        this.show();
    };

    /**
     * Renders the overlay DOM (if not already present) and shows the wizard.
     */
    OnboardingWizard.prototype.show = function () {
        var doc = this._document;
        if (!doc) return;

        var overlay = doc.getElementById(this._overlayId);
        if (!overlay) {
            overlay = this._buildOverlay(doc);
            doc.body.appendChild(overlay);
        }

        overlay.style.display = 'flex';
        overlay.setAttribute('aria-hidden', 'false');

        this._renderStep(this.getCurrentStep());
    };

    /**
     * Hides the wizard overlay without marking onboarding complete.
     */
    OnboardingWizard.prototype.hide = function () {
        var doc = this._document;
        if (!doc) return;
        var overlay = doc.getElementById(this._overlayId);
        if (overlay) {
            overlay.style.display = 'none';
            overlay.setAttribute('aria-hidden', 'true');
        }
        this._stopDemo();
    };

    /**
     * Navigates to the next step.
     */
    OnboardingWizard.prototype.nextStep = function () {
        var step = this.getCurrentStep();
        this._collectStepData(step);
        if (step < TOTAL_STEPS) {
            step += 1;
            this.setCurrentStep(step);
            this._renderStep(step);
        } else {
            this._finish();
        }
    };

    /**
     * Navigates back one step.
     */
    OnboardingWizard.prototype.prevStep = function () {
        var step = this.getCurrentStep();
        if (step > 1) {
            step -= 1;
            this.setCurrentStep(step);
            this._renderStep(step);
        }
    };

    /**
     * Skips the current step and moves to the next.
     */
    OnboardingWizard.prototype.skipStep = function () {
        var step = this.getCurrentStep();
        if (step < TOTAL_STEPS) {
            step += 1;
            this.setCurrentStep(step);
            this._renderStep(step);
        } else {
            this._finish();
        }
    };

    /**
     * Marks onboarding complete, hides overlay, and notifies server.
     */
    OnboardingWizard.prototype._finish = function () {
        this.markComplete();
        this.hide();
        this._notifyServer();
    };

    /**
     * Notifies the backend that onboarding is complete (fire-and-forget).
     */
    OnboardingWizard.prototype._notifyServer = function () {
        try {
            if (typeof fetch !== 'undefined') {
                fetch('/api/onboarding/complete', { method: 'GET' }).catch(function () {});
            }
        } catch (e) { /* ignore */ }
    };

    // -------------------------------------------------------------------------
    // Data collection per step
    // -------------------------------------------------------------------------

    OnboardingWizard.prototype._collectStepData = function (step) {
        var doc = this._document;
        if (!doc) return;
        var data = {};

        if (step === 1) {
            var selected = doc.querySelector('.ob-plan-card.selected');
            if (selected) data.plan = selected.getAttribute('data-plan');
        } else if (step === 2) {
            var repoInput = doc.getElementById('ob-repo-url');
            if (repoInput) data.repoUrl = repoInput.value;
            var branchInput = doc.getElementById('ob-branch');
            if (branchInput) data.branch = branchInput.value || 'main';
        } else if (step === 3) {
            var apiKeyInput = doc.getElementById('ob-linear-api-key');
            if (apiKeyInput) data.linearApiKey = apiKeyInput.value;
            var projectInput = doc.getElementById('ob-linear-project');
            if (projectInput) data.linearProject = projectInput.value;
        } else if (step === 4) {
            var ticketInput = doc.getElementById('ob-ticket');
            if (ticketInput) data.ticket = ticketInput.value;
            var modelSelect = doc.getElementById('ob-model');
            if (modelSelect) data.model = modelSelect.value;
        }

        if (Object.keys(data).length > 0) {
            this.saveData(data);
        }
    };

    // -------------------------------------------------------------------------
    // Rendering
    // -------------------------------------------------------------------------

    /**
     * Updates the overlay to display the given step.
     * @param {number} step 1-5
     */
    OnboardingWizard.prototype._renderStep = function (step) {
        var doc = this._document;
        if (!doc) return;

        this._stopDemo();

        // Update progress dots
        for (var i = 1; i <= TOTAL_STEPS; i++) {
            var dot = doc.getElementById('ob-dot-' + i);
            if (dot) {
                dot.className = 'ob-dot' + (i === step ? ' ob-dot-active' : '') + (i < step ? ' ob-dot-done' : '');
            }
        }

        // Hide all step panels
        var panels = doc.querySelectorAll('.ob-step-panel');
        for (var p = 0; p < panels.length; p++) {
            panels[p].style.display = 'none';
        }

        // Show active panel
        var active = doc.getElementById('ob-step-' + step);
        if (active) active.style.display = 'block';

        // Update nav buttons
        var backBtn = doc.getElementById('ob-btn-back');
        var skipBtn = doc.getElementById('ob-btn-skip');
        var nextBtn = doc.getElementById('ob-btn-next');

        if (backBtn) backBtn.style.display = step > 1 ? 'inline-flex' : 'none';
        if (skipBtn) skipBtn.style.display = step > 1 ? 'inline-flex' : 'none';

        if (nextBtn) {
            if (step === TOTAL_STEPS) {
                nextBtn.textContent = 'Go to Dashboard';
            } else if (step === 4) {
                nextBtn.textContent = 'Run your first ticket';
            } else if (step === 1) {
                nextBtn.textContent = 'Start for free';
            } else {
                nextBtn.textContent = 'Next';
            }
        }

        // Restore any previously entered data
        this._restoreStepData(step);

        // Step 5: kick off demo
        if (step === TOTAL_STEPS) {
            this._startDemo();
        }
    };

    OnboardingWizard.prototype._restoreStepData = function (step) {
        var doc = this._document;
        var data = this.loadData();
        if (!doc || !data) return;

        if (step === 1 && data.plan) {
            var cards = doc.querySelectorAll('.ob-plan-card');
            for (var c = 0; c < cards.length; c++) {
                if (cards[c].getAttribute('data-plan') === data.plan) {
                    cards[c].classList.add('selected');
                } else {
                    cards[c].classList.remove('selected');
                }
            }
        } else if (step === 2) {
            if (data.repoUrl) {
                var repoInput = doc.getElementById('ob-repo-url');
                if (repoInput) repoInput.value = data.repoUrl;
            }
            if (data.branch) {
                var branchInput = doc.getElementById('ob-branch');
                if (branchInput) branchInput.value = data.branch;
            }
        } else if (step === 3) {
            if (data.linearApiKey) {
                var apiKeyInput = doc.getElementById('ob-linear-api-key');
                if (apiKeyInput) apiKeyInput.value = data.linearApiKey;
            }
            if (data.linearProject) {
                var projectInput = doc.getElementById('ob-linear-project');
                if (projectInput) projectInput.value = data.linearProject;
            }
        } else if (step === 4) {
            if (data.ticket) {
                var ticketInput = doc.getElementById('ob-ticket');
                if (ticketInput) ticketInput.value = data.ticket;
            }
            if (data.model) {
                var modelSelect = doc.getElementById('ob-model');
                if (modelSelect) modelSelect.value = data.model;
            }
        }
    };

    // -------------------------------------------------------------------------
    // Step 5: Demo simulation
    // -------------------------------------------------------------------------

    OnboardingWizard.prototype._startDemo = function () {
        var self = this;
        var doc = this._document;
        if (!doc) return;

        var log = doc.getElementById('ob-demo-log');
        var celebration = doc.getElementById('ob-celebration');
        if (!log) return;

        log.innerHTML = '';
        if (celebration) celebration.style.display = 'none';

        self._demoIndex = 0;

        function tick() {
            if (self._demoIndex >= DEMO_STEPS.length) {
                if (celebration) {
                    celebration.style.display = 'block';
                }
                return;
            }
            var line = doc.createElement('div');
            line.className = 'ob-demo-line';
            line.textContent = DEMO_STEPS[self._demoIndex];
            log.appendChild(line);
            log.scrollTop = log.scrollHeight;
            self._demoIndex += 1;
            self._demoTimer = setTimeout(tick, 800);
        }

        self._demoTimer = setTimeout(tick, 400);
    };

    OnboardingWizard.prototype._stopDemo = function () {
        if (this._demoTimer) {
            clearTimeout(this._demoTimer);
            this._demoTimer = null;
        }
        this._demoIndex = 0;
    };

    // -------------------------------------------------------------------------
    // DOM construction
    // -------------------------------------------------------------------------

    OnboardingWizard.prototype._buildOverlay = function (doc) {
        var self = this;
        var overlay = doc.createElement('div');
        overlay.id = this._overlayId;
        overlay.className = 'ob-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-label', 'Setup Wizard');

        var modal = doc.createElement('div');
        modal.className = 'ob-modal';
        modal.innerHTML = this._buildModalHTML();
        overlay.appendChild(modal);

        // Wire navigation buttons
        setTimeout(function () {
            var backBtn = doc.getElementById('ob-btn-back');
            var skipBtn = doc.getElementById('ob-btn-skip');
            var nextBtn = doc.getElementById('ob-btn-next');

            if (backBtn) {
                backBtn.addEventListener('click', function () { self.prevStep(); });
            }
            if (skipBtn) {
                skipBtn.addEventListener('click', function () { self.skipStep(); });
            }
            if (nextBtn) {
                nextBtn.addEventListener('click', function () { self.nextStep(); });
            }

            // Plan card selection
            var planCards = doc.querySelectorAll('.ob-plan-card');
            for (var i = 0; i < planCards.length; i++) {
                (function (card) {
                    card.addEventListener('click', function () {
                        var allCards = doc.querySelectorAll('.ob-plan-card');
                        for (var j = 0; j < allCards.length; j++) {
                            allCards[j].classList.remove('selected');
                        }
                        card.classList.add('selected');
                    });
                })(planCards[i]);
            }
        }, 0);

        return overlay;
    };

    OnboardingWizard.prototype._buildModalHTML = function () {
        var modelOptionsHTML = MODEL_OPTIONS.map(function (m) {
            return '<option value="' + m.value + '"' + (m.value === 'claude-haiku-3-5' ? ' selected' : '') + '>' + m.label + '</option>';
        }).join('');

        var planCardsHTML = Object.keys(PLAN_LABELS).map(function (key) {
            return '<div class="ob-plan-card' + (key === 'explorer' ? ' selected' : '') + '" data-plan="' + key + '" role="button" tabindex="0">' +
                '<div class="ob-plan-name">' + PLAN_LABELS[key] + '</div>' +
                '</div>';
        }).join('');

        return [
            /* Progress dots */
            '<div class="ob-progress">',
            '  <div id="ob-dot-1" class="ob-dot ob-dot-active" aria-label="Step 1"></div>',
            '  <div id="ob-dot-2" class="ob-dot" aria-label="Step 2"></div>',
            '  <div id="ob-dot-3" class="ob-dot" aria-label="Step 3"></div>',
            '  <div id="ob-dot-4" class="ob-dot" aria-label="Step 4"></div>',
            '  <div id="ob-dot-5" class="ob-dot" aria-label="Step 5"></div>',
            '</div>',

            /* Step 1: Welcome & Plan Selection */
            '<div id="ob-step-1" class="ob-step-panel">',
            '  <div class="ob-step-icon">&#128640;</div>',
            '  <h2 class="ob-step-title">Welcome to Agent Dashboard</h2>',
            '  <p class="ob-step-desc">Your AI-powered engineering workflow starts here. Pick a plan to get started.</p>',
            '  <div class="ob-plan-grid">' + planCardsHTML + '</div>',
            '</div>',

            /* Step 2: Connect Repository */
            '<div id="ob-step-2" class="ob-step-panel" style="display:none">',
            '  <div class="ob-step-icon">&#128279;</div>',
            '  <h2 class="ob-step-title">Connect Repository</h2>',
            '  <p class="ob-step-desc">Enter your GitHub repository URL to let agents create PRs and commits.</p>',
            '  <label class="ob-label" for="ob-repo-url">GitHub Repository URL</label>',
            '  <input id="ob-repo-url" class="ob-input" type="url" placeholder="https://github.com/org/repo" autocomplete="off" />',
            '  <label class="ob-label" for="ob-branch">Default Branch</label>',
            '  <input id="ob-branch" class="ob-input" type="text" placeholder="main" value="main" autocomplete="off" />',
            '</div>',

            /* Step 3: Connect Linear (Optional) */
            '<div id="ob-step-3" class="ob-step-panel" style="display:none">',
            '  <div class="ob-step-icon">&#9889;</div>',
            '  <h2 class="ob-step-title">Connect Linear <span class="ob-optional">(Optional)</span></h2>',
            '  <p class="ob-step-desc">Provide your Linear API key to let agents pick up tickets automatically.</p>',
            '  <label class="ob-label" for="ob-linear-api-key">Linear API Key</label>',
            '  <input id="ob-linear-api-key" class="ob-input" type="password" placeholder="lin_api_..." autocomplete="off" />',
            '  <label class="ob-label" for="ob-linear-project">Project Name</label>',
            '  <input id="ob-linear-project" class="ob-input" type="text" placeholder="My Project" autocomplete="off" />',
            '</div>',

            /* Step 4: Configure First Agent Run */
            '<div id="ob-step-4" class="ob-step-panel" style="display:none">',
            '  <div class="ob-step-icon">&#128736;</div>',
            '  <h2 class="ob-step-title">Configure First Agent Run</h2>',
            '  <p class="ob-step-desc">Pick a sample ticket and model for your first automated run.</p>',
            '  <label class="ob-label" for="ob-ticket">Sample Ticket</label>',
            '  <input id="ob-ticket" class="ob-input" type="text" value="AI-001: Add pagination to the REST API" autocomplete="off" />',
            '  <label class="ob-label" for="ob-model">Model</label>',
            '  <select id="ob-model" class="ob-input ob-select">' + modelOptionsHTML + '</select>',
            '</div>',

            /* Step 5: Watch It Work */
            '<div id="ob-step-5" class="ob-step-panel" style="display:none">',
            '  <div class="ob-step-icon">&#127775;</div>',
            '  <h2 class="ob-step-title">Watch It Work</h2>',
            '  <p class="ob-step-desc">Your agent is running! Here\'s a live preview of what it does.</p>',
            '  <div id="ob-demo-log" class="ob-demo-log" aria-live="polite"></div>',
            '  <div id="ob-celebration" class="ob-celebration" style="display:none">',
            '    &#127881; Agent run complete! Your dashboard is ready.',
            '    <a href="/" class="ob-dashboard-link">Go to Dashboard &rarr;</a>',
            '  </div>',
            '</div>',

            /* Navigation */
            '<div class="ob-nav">',
            '  <button id="ob-btn-back" class="ob-btn ob-btn-secondary" style="display:none" type="button">&#8592; Back</button>',
            '  <div class="ob-nav-right">',
            '    <button id="ob-btn-skip" class="ob-btn ob-btn-ghost" style="display:none" type="button">Skip</button>',
            '    <button id="ob-btn-next" class="ob-btn ob-btn-primary" type="button">Start for free</button>',
            '  </div>',
            '</div>'
        ].join('\n');
    };

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /**
     * Creates a singleton OnboardingWizard and attaches it to the global scope.
     * Called from a DOMContentLoaded listener in dashboard.html.
     */
    function initOnboarding(options) {
        var wizard = new OnboardingWizard(options);
        global.onboardingWizard = wizard;
        return wizard;
    }

    // Export
    global.OnboardingWizard = OnboardingWizard;
    global.initOnboarding = initOnboarding;

}(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : {})));
