/**
 * Playwright E2E tests for Acceleration UI (AI-263)
 *
 * Tests cover:
 * - Modal open/close
 * - Slider interaction
 * - Enable/disable acceleration
 * - Status updates
 * - Error handling
 */

const { test, expect } = require('@playwright/test');

test.describe('Acceleration Feature UI', () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to dashboard
        await page.goto('http://localhost:8420');
        await page.waitForLoadState('networkidle');
    });

    test('should display Accelerate button in header', async ({ page }) => {
        const accelerateBtn = page.locator('#accelerate-btn');
        await expect(accelerateBtn).toBeVisible();
        await expect(accelerateBtn).toHaveText('Accelerate');
    });

    test('should open acceleration modal when button clicked', async ({ page }) => {
        await page.click('#accelerate-btn');

        const modal = page.locator('#acceleration-modal-overlay');
        await expect(modal).toHaveClass(/active/);

        const modalTitle = page.locator('.modal-title');
        await expect(modalTitle).toHaveText('Task Acceleration');
    });

    test('should close modal when X button clicked', async ({ page }) => {
        // Open modal
        await page.click('#accelerate-btn');
        await expect(page.locator('#acceleration-modal-overlay')).toHaveClass(/active/);

        // Close modal
        await page.click('#acceleration-modal-close');
        await expect(page.locator('#acceleration-modal-overlay')).not.toHaveClass(/active/);
    });

    test('should close modal when Cancel button clicked', async ({ page }) => {
        // Open modal
        await page.click('#accelerate-btn');

        // Click cancel
        await page.click('#acceleration-cancel');
        await expect(page.locator('#acceleration-modal-overlay')).not.toHaveClass(/active/);
    });

    test('should close modal when overlay clicked', async ({ page }) => {
        // Open modal
        await page.click('#accelerate-btn');

        // Click overlay background
        await page.click('#acceleration-modal-overlay', { position: { x: 10, y: 10 } });
        await expect(page.locator('#acceleration-modal-overlay')).not.toHaveClass(/active/);
    });

    test('should update slider value display when slider moved', async ({ page }) => {
        await page.click('#accelerate-btn');

        const slider = page.locator('#acceleration-slider');
        const valueDisplay = page.locator('#acceleration-value');

        // Set slider to 5.0
        await slider.fill('5.0');
        await expect(valueDisplay).toHaveText('5.0x');

        // Set slider to 10.0
        await slider.fill('10.0');
        await expect(valueDisplay).toHaveText('10.0x');
    });

    test('should display metrics in modal', async ({ page }) => {
        await page.click('#accelerate-btn');

        await expect(page.locator('#accel-active-tasks')).toBeVisible();
        await expect(page.locator('#accel-queue-size')).toBeVisible();
        await expect(page.locator('#accel-completed-tasks')).toBeVisible();
        await expect(page.locator('#accel-avg-duration')).toBeVisible();
    });

    test('should show Enable button initially', async ({ page }) => {
        await page.click('#accelerate-btn');

        const enableBtn = page.locator('#acceleration-enable');
        const disableBtn = page.locator('#acceleration-disable');

        await expect(enableBtn).toBeVisible();
        await expect(disableBtn).not.toBeVisible();
    });

    test('should enable acceleration when Enable clicked', async ({ page }) => {
        // Intercept API call
        await page.route('**/api/acceleration/enable', route => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    status: 'enabled',
                    factor: 2.0,
                    mode: 'enabled',
                    max_concurrent_tasks: 10,
                    timestamp: new Date().toISOString()
                })
            });
        });

        await page.click('#accelerate-btn');

        const slider = page.locator('#acceleration-slider');
        await slider.fill('2.0');

        await page.click('#acceleration-enable');

        // Modal should close
        await expect(page.locator('#acceleration-modal-overlay')).not.toHaveClass(/active/);

        // Button should show active state
        const accelerateBtn = page.locator('#accelerate-btn');
        await expect(accelerateBtn).toHaveClass(/active/);
        await expect(accelerateBtn).toContainText('2.0x');
    });

    test('should disable acceleration when Disable clicked', async ({ page }) => {
        // First enable acceleration
        await page.route('**/api/acceleration/enable', route => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    status: 'enabled',
                    factor: 3.0,
                    mode: 'enabled',
                    timestamp: new Date().toISOString()
                })
            });
        });

        await page.route('**/api/acceleration/disable', route => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    status: 'disabled',
                    timestamp: new Date().toISOString()
                })
            });
        });

        // Enable first
        await page.click('#accelerate-btn');
        await page.click('#acceleration-enable');

        // Open modal again
        await page.click('#accelerate-btn');

        // Disable button should now be visible
        await expect(page.locator('#acceleration-disable')).toBeVisible();

        await page.click('#acceleration-disable');

        // Button should no longer be active
        const accelerateBtn = page.locator('#accelerate-btn');
        await expect(accelerateBtn).not.toHaveClass(/active/);
        await expect(accelerateBtn).toHaveText('Accelerate');
    });

    test('should handle API error gracefully', async ({ page }) => {
        // Intercept API call with error
        await page.route('**/api/acceleration/enable', route => {
            route.fulfill({
                status: 500,
                contentType: 'application/json',
                body: JSON.stringify({
                    error: 'Internal server error'
                })
            });
        });

        // Listen for alert dialog
        page.on('dialog', dialog => dialog.accept());

        await page.click('#accelerate-btn');
        await page.click('#acceleration-enable');

        // Modal should still be open after error
        await expect(page.locator('#acceleration-modal-overlay')).toHaveClass(/active/);
    });

    test('should fetch and display acceleration status on load', async ({ page }) => {
        await page.route('**/api/acceleration/status', route => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    enabled: true,
                    acceleration_factor: 4.5,
                    mode: 'enabled',
                    max_concurrent_tasks: 22,
                    metrics: {
                        active_tasks: 3,
                        completed_tasks: 15,
                        failed_tasks: 0,
                        queue_size: 2,
                        avg_task_duration: 1.5,
                        total_tasks_processed: 15
                    },
                    timestamp: new Date().toISOString()
                })
            });
        });

        await page.reload();
        await page.waitForLoadState('networkidle');

        const accelerateBtn = page.locator('#accelerate-btn');
        await expect(accelerateBtn).toHaveClass(/active/);
        await expect(accelerateBtn).toContainText('4.5x');
    });

    test('should update metrics when modal is opened', async ({ page }) => {
        await page.route('**/api/acceleration/status', route => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    enabled: false,
                    acceleration_factor: 1.0,
                    mode: 'disabled',
                    max_concurrent_tasks: 5,
                    metrics: {
                        active_tasks: 2,
                        completed_tasks: 42,
                        failed_tasks: 1,
                        queue_size: 5,
                        avg_task_duration: 2.35,
                        total_tasks_processed: 43
                    },
                    timestamp: new Date().toISOString()
                })
            });
        });

        await page.click('#accelerate-btn');

        // Check that metrics are displayed
        await expect(page.locator('#accel-active-tasks')).toHaveText('0');
        await expect(page.locator('#accel-queue-size')).toHaveText('0');
        await expect(page.locator('#accel-completed-tasks')).toHaveText('0');
    });

    test('should allow slider range from 1.0 to 10.0', async ({ page }) => {
        await page.click('#accelerate-btn');

        const slider = page.locator('#acceleration-slider');

        // Test minimum
        await slider.fill('1.0');
        await expect(page.locator('#acceleration-value')).toHaveText('1.0x');

        // Test maximum
        await slider.fill('10.0');
        await expect(page.locator('#acceleration-value')).toHaveText('10.0x');

        // Test middle value
        await slider.fill('5.5');
        await expect(page.locator('#acceleration-value')).toHaveText('5.5x');
    });

    test('should display modal info text', async ({ page }) => {
        await page.click('#accelerate-btn');

        const infoText = page.locator('.modal-info');
        await expect(infoText).toBeVisible();
        await expect(infoText).toContainText('Acceleration enables parallel task processing');
    });

    test('should have accessible modal close button', async ({ page }) => {
        await page.click('#accelerate-btn');

        const closeBtn = page.locator('#acceleration-modal-close');
        await expect(closeBtn).toHaveAttribute('aria-label', 'Close modal');
    });
});
