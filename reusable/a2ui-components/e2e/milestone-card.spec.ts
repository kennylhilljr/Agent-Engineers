import { test, expect } from '@playwright/test';

// Override base URL to use existing dev server on port 3010
test.use({ baseURL: 'http://localhost:3010' });

test.describe('MilestoneCard Component E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the A2UI demo page where MilestoneCard component is rendered
    await page.goto('/a2ui-demo');
    await page.waitForLoadState('networkidle');
  });

  test('multiple milestone cards display correctly', async ({ page }) => {
    // Look for multiple MilestoneCard components
    const milestoneCards = page.getByTestId('milestone-card');
    const count = await milestoneCards.count();
    expect(count).toBeGreaterThanOrEqual(4); // We have 4 examples
  });

  test('milestone card displays with green gradient background', async ({ page }) => {
    const milestoneCard = page.getByTestId('milestone-card').first();
    await expect(milestoneCard).toBeVisible();

    // Check for green-themed classes
    const classList = await milestoneCard.getAttribute('class');
    expect(classList).toContain('bg-gradient-to-br');
    expect(classList).toContain('border-green');
  });

  test('milestone card displays title and summary', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    const title = firstCard.getByTestId('milestone-title');
    await expect(title).toBeVisible();
    await expect(title).toContainText('A2UI Catalog Complete!');

    const summary = firstCard.getByTestId('milestone-summary');
    await expect(summary).toBeVisible();
    await expect(summary).toContainText('implemented all 9 A2UI components');
  });

  test('milestone card displays tasks counter and completion badge', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    const tasksCounter = firstCard.getByTestId('tasks-counter');
    await expect(tasksCounter).toBeVisible();

    const completionBadge = firstCard.getByTestId('completion-badge');
    await expect(completionBadge).toBeVisible();
    await expect(completionBadge).toContainText('9 / 9');
  });

  test('milestone card displays progress bar with correct percentage', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    const progressSection = firstCard.getByTestId('progress-section');
    await expect(progressSection).toBeVisible();

    const completionPercentage = firstCard.getByTestId('completion-percentage');
    await expect(completionPercentage).toBeVisible();
    await expect(completionPercentage).toContainText('100%');

    const progressBar = firstCard.getByTestId('progress-bar');
    await expect(progressBar).toBeVisible();
  });

  test('milestone card displays celebration message when provided', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    const celebrationMessage = firstCard.getByTestId('celebration-message');
    await expect(celebrationMessage).toBeVisible();
    await expect(celebrationMessage).toContainText('Incredible work!');
  });

  test('milestone card displays completion date when provided', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    const completionDate = firstCard.getByTestId('completion-date');
    await expect(completionDate).toBeVisible();
    await expect(completionDate).toContainText('February');
    await expect(completionDate).toContainText('2024');
  });

  test('milestone card displays next phase information when provided', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    const nextPhase = firstCard.getByTestId('next-phase');
    await expect(nextPhase).toBeVisible();
    await expect(nextPhase).toContainText('Up Next');
    await expect(nextPhase).toContainText('Production deployment');
  });

  test('milestone card displays check icon with animation elements', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    const checkIconContainer = firstCard.getByTestId('check-icon-container');
    await expect(checkIconContainer).toBeVisible();

    const checkIcon = firstCard.getByTestId('check-icon');
    await expect(checkIcon).toBeVisible();
  });

  test('milestone card with animations enabled shows sparkles and glow effects', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    // Check for animation elements
    const glowEffect = firstCard.getByTestId('glow-effect');
    await expect(glowEffect).toBeVisible();

    const sparkle1 = firstCard.getByTestId('sparkle-1');
    await expect(sparkle1).toBeVisible();

    const sparkle2 = firstCard.getByTestId('sparkle-2');
    await expect(sparkle2).toBeVisible();

    const sparkle3 = firstCard.getByTestId('sparkle-3');
    await expect(sparkle3).toBeVisible();

    const iconGlow = firstCard.getByTestId('icon-glow');
    await expect(iconGlow).toBeVisible();
  });

  test('milestone card without animations does not show sparkles', async ({ page }) => {
    // Find the card with celebrationAnimation: false (4th card)
    const cards = page.getByTestId('milestone-card');
    const cardWithoutAnimation = cards.nth(3); // 4th card (0-indexed)
    await expect(cardWithoutAnimation).toBeVisible();

    // Animation elements should not be present
    const glowEffect = cardWithoutAnimation.getByTestId('glow-effect');
    await expect(glowEffect).not.toBeVisible();

    const sparkle1 = cardWithoutAnimation.getByTestId('sparkle-1');
    await expect(sparkle1).not.toBeVisible();
  });

  test('partial completion milestone shows correct percentage', async ({ page }) => {
    // Second card has 15/20 tasks (75%)
    const cards = page.getByTestId('milestone-card');
    const partialCard = cards.nth(1);
    await expect(partialCard).toBeVisible();

    const completionBadge = partialCard.getByTestId('completion-badge');
    await expect(completionBadge).toContainText('15 / 20');

    const completionPercentage = partialCard.getByTestId('completion-percentage');
    await expect(completionPercentage).toContainText('75%');
  });

  test('milestone card without celebration message does not display message box', async ({ page }) => {
    // Second card does not have a celebration message
    const cards = page.getByTestId('milestone-card');
    const cardWithoutMessage = cards.nth(1);
    await expect(cardWithoutMessage).toBeVisible();

    const celebrationMessage = cardWithoutMessage.getByTestId('celebration-message');
    await expect(celebrationMessage).not.toBeVisible();
  });

  test('milestone card without next phase does not display next phase section', async ({ page }) => {
    // Third card does not have nextPhase
    const cards = page.getByTestId('milestone-card');
    const cardWithoutNextPhase = cards.nth(2);
    await expect(cardWithoutNextPhase).toBeVisible();

    const nextPhase = cardWithoutNextPhase.getByTestId('next-phase');
    await expect(nextPhase).not.toBeVisible();
  });

  test('milestone card without completion date does not display date', async ({ page }) => {
    // Third card does not have completionDate
    const cards = page.getByTestId('milestone-card');
    const cardWithoutDate = cards.nth(2);
    await expect(cardWithoutDate).toBeVisible();

    const completionDate = cardWithoutDate.getByTestId('completion-date');
    await expect(completionDate).not.toBeVisible();
  });

  test('animation transitions occur smoothly over time', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    // Wait for animations to complete (component has 100ms delay + transitions)
    await page.waitForTimeout(500);

    // Verify animation classes are applied after delay
    const glowEffect = firstCard.getByTestId('glow-effect');
    const classList = await glowEffect.getAttribute('class');
    expect(classList).toContain('opacity-100');
  });

  test('milestone cards have proper visual hierarchy and spacing', async ({ page }) => {
    const firstCard = page.getByTestId('milestone-card').first();
    await expect(firstCard).toBeVisible();

    // Check that title is larger than summary
    const title = firstCard.getByTestId('milestone-title');
    const titleClasses = await title.getAttribute('class');
    expect(titleClasses).toContain('text-2xl');

    const summary = firstCard.getByTestId('milestone-summary');
    const summaryClasses = await summary.getAttribute('class');
    expect(summaryClasses).toContain('text-sm');
  });

  test('all milestone cards are accessible and properly structured', async ({ page }) => {
    const cards = page.getByTestId('milestone-card');
    const count = await cards.count();

    for (let i = 0; i < count; i++) {
      const card = cards.nth(i);
      await expect(card).toBeVisible();

      // Each card should have essential elements
      const title = card.getByTestId('milestone-title');
      await expect(title).toBeVisible();

      const summary = card.getByTestId('milestone-summary');
      await expect(summary).toBeVisible();

      const tasksCounter = card.getByTestId('tasks-counter');
      await expect(tasksCounter).toBeVisible();

      const checkIcon = card.getByTestId('check-icon');
      await expect(checkIcon).toBeVisible();
    }
  });

  test('milestone card maintains green theme consistency', async ({ page }) => {
    const cards = page.getByTestId('milestone-card');
    const firstCard = cards.first();
    await expect(firstCard).toBeVisible();

    // Check for green color classes in various elements
    const completionBadge = firstCard.getByTestId('completion-badge');
    const badgeClasses = await completionBadge.getAttribute('class');
    expect(badgeClasses).toContain('text-green');

    const checkIcon = firstCard.getByTestId('check-icon');
    const iconClasses = await checkIcon.getAttribute('class');
    expect(iconClasses).toContain('text-green');
  });
});
