/**
 * AI-226: Onboarding Wizard Unit Tests
 *
 * Tests the OnboardingWizard class from onboarding.js covering:
 * - Initialization
 * - Step navigation (next, back, skip)
 * - First-run detection
 * - localStorage persistence
 * - Step rendering
 * - Demo simulation
 * - Settings restart button integration
 */

'use strict';

const path = require('path');
const fs = require('fs');

// Load the onboarding module into the jsdom environment
const onboardingPath = path.join(__dirname, '../onboarding.js');
const onboardingSource = fs.readFileSync(onboardingPath, 'utf-8');

// ---- helpers ----

function makeStorage() {
    const store = {};
    return {
        getItem: (k) => (k in store ? store[k] : null),
        setItem: (k, v) => { store[k] = String(v); },
        removeItem: (k) => { delete store[k]; },
        _store: store,
    };
}

function makeWizard(storageOverride) {
    // Evaluate the source in the current jsdom context
    const fn = new Function('window', 'global', 'localStorage', onboardingSource);
    // We need OnboardingWizard to be available – eval in the global scope
    eval(onboardingSource); // eslint-disable-line no-eval
    return new OnboardingWizard({ storage: storageOverride || makeStorage(), document: document });
}

// Re-eval the module so global variables are set
beforeEach(() => {
    // Reset document body before each test
    document.body.innerHTML = '';
    // Evaluate module to register globals
    eval(onboardingSource); // eslint-disable-line no-eval
});

// ============================================================
// 1. Initialization
// ============================================================

describe('OnboardingWizard - Initialization', () => {
    test('can be instantiated with no arguments', () => {
        const wizard = new OnboardingWizard();
        expect(wizard).toBeDefined();
    });

    test('uses provided storage object', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        expect(wizard._storage).toBe(storage);
    });

    test('uses provided document object', () => {
        const wizard = new OnboardingWizard({ document });
        expect(wizard._document).toBe(document);
    });

    test('defaults _demoTimer to null', () => {
        const wizard = new OnboardingWizard({ storage: makeStorage() });
        expect(wizard._demoTimer).toBeNull();
    });

    test('defaults _demoIndex to 0', () => {
        const wizard = new OnboardingWizard({ storage: makeStorage() });
        expect(wizard._demoIndex).toBe(0);
    });

    test('initOnboarding function sets global onboardingWizard', () => {
        const storage = makeStorage();
        // Prevent auto-show by pre-setting complete flag
        storage.setItem('onboarding_complete', 'true');
        const wizard = initOnboarding({ storage, document });
        expect(window.onboardingWizard).toBe(wizard);
    });
});

// ============================================================
// 2. First-run Detection
// ============================================================

describe('OnboardingWizard - First-run Detection', () => {
    test('shouldShow returns true when onboarding_complete is not set', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        expect(wizard.shouldShow()).toBe(true);
    });

    test('shouldShow returns false when onboarding_complete is "true"', () => {
        const storage = makeStorage();
        storage.setItem('onboarding_complete', 'true');
        const wizard = new OnboardingWizard({ storage });
        expect(wizard.shouldShow()).toBe(false);
    });

    test('isComplete returns false when storage has no complete key', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        expect(wizard.isComplete()).toBe(false);
    });

    test('isComplete returns true after markComplete is called', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.markComplete();
        expect(wizard.isComplete()).toBe(true);
    });

    test('init() calls show() when onboarding is not complete', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        const showSpy = jest.spyOn(wizard, 'show');
        wizard.init();
        expect(showSpy).toHaveBeenCalled();
    });

    test('init() does not call show() when onboarding is complete', () => {
        const storage = makeStorage();
        storage.setItem('onboarding_complete', 'true');
        const wizard = new OnboardingWizard({ storage, document });
        const showSpy = jest.spyOn(wizard, 'show');
        wizard.init();
        expect(showSpy).not.toHaveBeenCalled();
    });
});

// ============================================================
// 3. localStorage Persistence
// ============================================================

describe('OnboardingWizard - localStorage Persistence', () => {
    test('getCurrentStep returns 1 when no step stored', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        expect(wizard.getCurrentStep()).toBe(1);
    });

    test('setCurrentStep persists step to storage', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.setCurrentStep(3);
        expect(storage.getItem('onboarding_step')).toBe('3');
    });

    test('getCurrentStep reads back a previously stored step', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.setCurrentStep(4);
        expect(wizard.getCurrentStep()).toBe(4);
    });

    test('getCurrentStep returns 1 for out-of-range stored step', () => {
        const storage = makeStorage();
        storage.setItem('onboarding_step', '99');
        const wizard = new OnboardingWizard({ storage });
        expect(wizard.getCurrentStep()).toBe(1);
    });

    test('markComplete sets onboarding_complete to "true" in storage', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.markComplete();
        expect(storage.getItem('onboarding_complete')).toBe('true');
    });

    test('markComplete removes onboarding_step from storage', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.setCurrentStep(3);
        wizard.markComplete();
        expect(storage.getItem('onboarding_step')).toBeNull();
    });

    test('reset removes onboarding_complete from storage', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.markComplete();
        wizard.reset();
        expect(storage.getItem('onboarding_complete')).toBeNull();
    });

    test('reset removes onboarding_step from storage', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.setCurrentStep(2);
        wizard.reset();
        expect(storage.getItem('onboarding_step')).toBeNull();
    });

    test('saveData persists JSON to onboarding_data key', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.saveData({ plan: 'builder', repoUrl: 'https://github.com/test/repo' });
        const raw = storage.getItem('onboarding_data');
        expect(raw).not.toBeNull();
        const parsed = JSON.parse(raw);
        expect(parsed.plan).toBe('builder');
        expect(parsed.repoUrl).toBe('https://github.com/test/repo');
    });

    test('loadData returns empty object when nothing is stored', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        expect(wizard.loadData()).toEqual({});
    });

    test('loadData returns previously saved data', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.saveData({ plan: 'team' });
        expect(wizard.loadData().plan).toBe('team');
    });

    test('saveData merges new data with existing data', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage });
        wizard.saveData({ plan: 'explorer' });
        wizard.saveData({ repoUrl: 'https://github.com/org/repo' });
        const data = wizard.loadData();
        expect(data.plan).toBe('explorer');
        expect(data.repoUrl).toBe('https://github.com/org/repo');
    });
});

// ============================================================
// 4. Step Navigation
// ============================================================

describe('OnboardingWizard - Step Navigation', () => {
    function makeWizardWithDOM(storage) {
        const wizard = new OnboardingWizard({ storage: storage || makeStorage(), document });
        // Build the overlay so we have DOM to operate on
        wizard.show();
        return wizard;
    }

    test('nextStep increments step from 1 to 2', () => {
        const wizard = makeWizardWithDOM();
        expect(wizard.getCurrentStep()).toBe(1);
        wizard.nextStep();
        expect(wizard.getCurrentStep()).toBe(2);
    });

    test('nextStep increments step from 2 to 3', () => {
        const storage = makeStorage();
        storage.setItem('onboarding_step', '2');
        const wizard = makeWizardWithDOM(storage);
        wizard.nextStep();
        expect(wizard.getCurrentStep()).toBe(3);
    });

    test('prevStep decrements step from 3 to 2', () => {
        const storage = makeStorage();
        storage.setItem('onboarding_step', '3');
        const wizard = makeWizardWithDOM(storage);
        wizard.prevStep();
        expect(wizard.getCurrentStep()).toBe(2);
    });

    test('prevStep does not go below step 1', () => {
        const wizard = makeWizardWithDOM();
        wizard.prevStep();
        expect(wizard.getCurrentStep()).toBe(1);
    });

    test('skipStep increments step when not on last step', () => {
        const storage = makeStorage();
        storage.setItem('onboarding_step', '2');
        const wizard = makeWizardWithDOM(storage);
        wizard.skipStep();
        expect(wizard.getCurrentStep()).toBe(3);
    });

    test('skipStep on last step calls _finish', () => {
        const storage = makeStorage();
        storage.setItem('onboarding_step', '5');
        const wizard = makeWizardWithDOM(storage);
        const finishSpy = jest.spyOn(wizard, '_finish');
        wizard.skipStep();
        expect(finishSpy).toHaveBeenCalled();
    });

    test('nextStep on last step calls _finish', () => {
        const storage = makeStorage();
        storage.setItem('onboarding_step', '5');
        const wizard = makeWizardWithDOM(storage);
        const finishSpy = jest.spyOn(wizard, '_finish');
        wizard.nextStep();
        expect(finishSpy).toHaveBeenCalled();
    });

    test('_finish calls markComplete and hide', () => {
        const storage = makeStorage();
        const wizard = makeWizardWithDOM(storage);
        const markSpy = jest.spyOn(wizard, 'markComplete');
        const hideSpy = jest.spyOn(wizard, 'hide');
        wizard._finish();
        expect(markSpy).toHaveBeenCalled();
        expect(hideSpy).toHaveBeenCalled();
    });

    test('after _finish isComplete returns true', () => {
        const storage = makeStorage();
        const wizard = makeWizardWithDOM(storage);
        wizard._finish();
        expect(wizard.isComplete()).toBe(true);
    });
});

// ============================================================
// 5. DOM / Rendering
// ============================================================

describe('OnboardingWizard - DOM Rendering', () => {
    test('show() inserts onboarding-overlay into document body', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        const overlay = document.getElementById('onboarding-overlay');
        expect(overlay).not.toBeNull();
    });

    test('overlay has role="dialog"', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        const overlay = document.getElementById('onboarding-overlay');
        expect(overlay.getAttribute('role')).toBe('dialog');
    });

    test('show() displays overlay as flex', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        const overlay = document.getElementById('onboarding-overlay');
        expect(overlay.style.display).toBe('flex');
    });

    test('hide() sets overlay display to none', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        wizard.hide();
        const overlay = document.getElementById('onboarding-overlay');
        expect(overlay.style.display).toBe('none');
    });

    test('hide() sets aria-hidden to "true"', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        wizard.hide();
        const overlay = document.getElementById('onboarding-overlay');
        expect(overlay.getAttribute('aria-hidden')).toBe('true');
    });

    test('step 1 panel is visible by default', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        const step1 = document.getElementById('ob-step-1');
        expect(step1).not.toBeNull();
        expect(step1.style.display).not.toBe('none');
    });

    test('progress dots exist for all 5 steps', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        for (let i = 1; i <= 5; i++) {
            const dot = document.getElementById('ob-dot-' + i);
            expect(dot).not.toBeNull();
        }
    });

    test('first dot has ob-dot-active class on step 1', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        const dot1 = document.getElementById('ob-dot-1');
        expect(dot1.classList.contains('ob-dot-active')).toBe(true);
    });

    test('step 5 panel is not visible on step 1', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        const step5 = document.getElementById('ob-step-5');
        expect(step5).not.toBeNull();
        expect(step5.style.display).toBe('none');
    });

    test('next button exists and is labeled "Start for free" on step 1', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        const nextBtn = document.getElementById('ob-btn-next');
        expect(nextBtn).not.toBeNull();
        expect(nextBtn.textContent).toBe('Start for free');
    });

    test('back button is hidden on step 1', () => {
        const storage = makeStorage();
        const wizard = new OnboardingWizard({ storage, document });
        wizard.show();
        const backBtn = document.getElementById('ob-btn-back');
        expect(backBtn.style.display).toBe('none');
    });
});

// ============================================================
// 6. onboarding.js file existence
// ============================================================

describe('onboarding.js - file', () => {
    test('onboarding.js file exists in dashboard directory', () => {
        expect(fs.existsSync(onboardingPath)).toBe(true);
    });

    test('onboarding.js exports OnboardingWizard class', () => {
        expect(typeof OnboardingWizard).toBe('function');
    });

    test('onboarding.js exports initOnboarding function', () => {
        expect(typeof initOnboarding).toBe('function');
    });

    test('STORAGE_KEY constants are referenced in the file', () => {
        expect(onboardingSource).toContain('onboarding_step');
        expect(onboardingSource).toContain('onboarding_complete');
        expect(onboardingSource).toContain('onboarding_data');
    });

    test('file contains 5 step definitions', () => {
        expect(onboardingSource).toContain('ob-step-1');
        expect(onboardingSource).toContain('ob-step-2');
        expect(onboardingSource).toContain('ob-step-3');
        expect(onboardingSource).toContain('ob-step-4');
        expect(onboardingSource).toContain('ob-step-5');
    });
});
