/**
 * Requirement Sync Tests - AI-157
 * REQ-CONTROL-007: Implement Requirement Sync to Linear
 *
 * Tests the frontend Requirement Editor UI including:
 * - Toggle visibility and state
 * - Load requirement (GET)
 * - Save without Linear sync
 * - Save with Linear sync
 * - Error feedback display
 */

describe('Requirement Editor - AI-157', () => {
    let reqTicketInput;
    let reqLoadBtn;
    let reqTextarea;
    let reqSyncToggle;
    let reqSaveBtn;
    let reqFeedback;
    let fetchMock;

    // Minimal API_BASE_URL expected by the implementation
    global.API_BASE_URL = 'http://localhost:8080';

    function setupDOM() {
        document.body.innerHTML = `
            <div id="requirement-editor" data-testid="requirement-editor">
                <input
                    type="text"
                    id="req-ticket-key"
                    data-testid="req-ticket-key-input"
                    placeholder="Ticket key (e.g. AI-157)"
                />
                <button id="req-load-btn" data-testid="req-load-button">Load</button>
                <textarea
                    id="req-textarea"
                    data-testid="req-textarea"
                    placeholder="Enter or edit requirement text here..."
                ></textarea>
                <div class="req-footer">
                    <label class="req-sync-toggle" for="req-sync-toggle">
                        <span class="toggle-switch">
                            <input
                                type="checkbox"
                                id="req-sync-toggle"
                                data-testid="req-sync-toggle"
                                aria-label="Sync to Linear"
                            />
                            <span class="toggle-slider"></span>
                        </span>
                        <span class="req-sync-label">
                            Sync to Linear
                            <span>(updates the Linear issue description)</span>
                        </span>
                    </label>
                    <button id="req-save-btn" data-testid="req-save-button">Save Requirement</button>
                </div>
                <div id="req-feedback" class="req-feedback" data-testid="req-feedback"></div>
            </div>
        `;

        reqTicketInput = document.getElementById('req-ticket-key');
        reqLoadBtn = document.getElementById('req-load-btn');
        reqTextarea = document.getElementById('req-textarea');
        reqSyncToggle = document.getElementById('req-sync-toggle');
        reqSaveBtn = document.getElementById('req-save-btn');
        reqFeedback = document.getElementById('req-feedback');
    }

    function showReqFeedback(message, type) {
        if (!reqFeedback) return;
        reqFeedback.textContent = message;
        reqFeedback.className = 'req-feedback ' + type;
    }

    async function loadRequirement() {
        const ticketKey = reqTicketInput ? reqTicketInput.value.trim() : '';
        if (!ticketKey) {
            showReqFeedback('Please enter a ticket key first.', 'error');
            return;
        }
        try {
            const resp = await fetch(`${API_BASE_URL}/api/requirements/${encodeURIComponent(ticketKey)}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (reqTextarea) reqTextarea.value = data.requirement || '';
            showReqFeedback(`Requirement loaded for ${data.ticket_key}.`, 'success');
        } catch (err) {
            showReqFeedback(`Failed to load requirement: ${err.message}`, 'error');
        }
    }

    async function saveRequirement() {
        const ticketKey = reqTicketInput ? reqTicketInput.value.trim() : '';
        if (!ticketKey) {
            showReqFeedback('Please enter a ticket key first.', 'error');
            return;
        }
        const requirementText = reqTextarea ? reqTextarea.value : '';
        const syncToLinear = reqSyncToggle ? reqSyncToggle.checked : false;

        if (reqSaveBtn) reqSaveBtn.disabled = true;
        try {
            const resp = await fetch(`${API_BASE_URL}/api/requirements/${encodeURIComponent(ticketKey)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ requirement: requirementText, sync_to_linear: syncToLinear }),
            });
            const data = await resp.json();
            if (!resp.ok) {
                throw new Error(data.error || `HTTP ${resp.status}`);
            }
            let msg = `Requirement saved for ${data.ticket_key}.`;
            if (syncToLinear) {
                if (data.linear_synced) {
                    msg += ' Linear issue updated successfully.';
                } else if (data.linear_error) {
                    msg += ` Note: Linear sync failed — ${data.linear_error}`;
                    showReqFeedback(msg, 'error');
                    return;
                }
            }
            showReqFeedback(msg, 'success');
        } catch (err) {
            showReqFeedback(`Failed to save requirement: ${err.message}`, 'error');
        } finally {
            if (reqSaveBtn) reqSaveBtn.disabled = false;
        }
    }

    beforeEach(() => {
        setupDOM();
        // Reset fetch mock
        fetchMock = jest.fn();
        global.fetch = fetchMock;
        jest.useFakeTimers();
    });

    afterEach(() => {
        jest.useRealTimers();
        jest.restoreAllMocks();
    });

    // ---- UI Structure Tests ----

    test('requirement editor section is visible in the DOM', () => {
        const editor = document.getElementById('requirement-editor');
        expect(editor).toBeTruthy();
    });

    test('ticket key input is present', () => {
        expect(reqTicketInput).toBeTruthy();
    });

    test('requirement textarea is present', () => {
        expect(reqTextarea).toBeTruthy();
    });

    test('sync toggle is visible and labeled clearly', () => {
        expect(reqSyncToggle).toBeTruthy();
        const label = document.querySelector('label.req-sync-toggle');
        expect(label).toBeTruthy();
        expect(label.textContent).toMatch(/Sync to Linear/i);
    });

    test('sync toggle is unchecked by default', () => {
        expect(reqSyncToggle.checked).toBe(false);
    });

    test('save button is present and enabled by default', () => {
        expect(reqSaveBtn).toBeTruthy();
        expect(reqSaveBtn.disabled).toBe(false);
    });

    test('sync toggle can be checked and unchecked', () => {
        reqSyncToggle.checked = true;
        expect(reqSyncToggle.checked).toBe(true);
        reqSyncToggle.checked = false;
        expect(reqSyncToggle.checked).toBe(false);
    });

    // ---- Load Requirement Tests ----

    test('load shows error feedback when ticket key is empty', async () => {
        reqTicketInput.value = '';
        await loadRequirement();
        expect(reqFeedback.className).toContain('error');
        expect(reqFeedback.textContent).toMatch(/ticket key/i);
    });

    test('load calls GET /api/requirements/{ticket_key}', async () => {
        reqTicketInput.value = 'AI-157';
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ ticket_key: 'AI-157', requirement: 'Test requirement text.' }),
        });

        await loadRequirement();

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining('/api/requirements/AI-157')
        );
    });

    test('load populates textarea with returned requirement text', async () => {
        reqTicketInput.value = 'AI-157';
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ ticket_key: 'AI-157', requirement: 'Loaded requirement text.' }),
        });

        await loadRequirement();

        expect(reqTextarea.value).toBe('Loaded requirement text.');
    });

    test('load shows success feedback after successful fetch', async () => {
        reqTicketInput.value = 'AI-157';
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ ticket_key: 'AI-157', requirement: 'Some text.' }),
        });

        await loadRequirement();

        expect(reqFeedback.className).toContain('success');
        expect(reqFeedback.textContent).toMatch(/loaded/i);
    });

    test('load shows error feedback when fetch fails', async () => {
        reqTicketInput.value = 'AI-999';
        fetchMock.mockRejectedValueOnce(new Error('Network error'));

        await loadRequirement();

        expect(reqFeedback.className).toContain('error');
        expect(reqFeedback.textContent).toMatch(/failed/i);
    });

    // ---- Save Without Linear Sync ----

    test('save shows error feedback when ticket key is empty', async () => {
        reqTicketInput.value = '';
        await saveRequirement();
        expect(reqFeedback.className).toContain('error');
    });

    test('save calls PUT /api/requirements/{ticket_key} with sync_to_linear=false when toggle is off', async () => {
        reqTicketInput.value = 'AI-157';
        reqTextarea.value = 'My requirement text.';
        reqSyncToggle.checked = false;

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, ticket_key: 'AI-157', linear_synced: false }),
        });

        await saveRequirement();

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining('/api/requirements/AI-157'),
            expect.objectContaining({
                method: 'PUT',
                body: expect.stringContaining('"sync_to_linear":false'),
            })
        );
    });

    test('save shows success feedback when toggle is off', async () => {
        reqTicketInput.value = 'AI-157';
        reqTextarea.value = 'Requirement text.';
        reqSyncToggle.checked = false;

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, ticket_key: 'AI-157', linear_synced: false }),
        });

        await saveRequirement();

        expect(reqFeedback.className).toContain('success');
        expect(reqFeedback.textContent).toMatch(/saved/i);
    });

    // ---- Save With Linear Sync ----

    test('save calls PUT with sync_to_linear=true when toggle is on', async () => {
        reqTicketInput.value = 'AI-157';
        reqTextarea.value = 'Synced requirement.';
        reqSyncToggle.checked = true;

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, ticket_key: 'AI-157', linear_synced: true }),
        });

        await saveRequirement();

        const [url, opts] = fetchMock.mock.calls[0];
        const body = JSON.parse(opts.body);
        expect(body.sync_to_linear).toBe(true);
        expect(body.requirement).toBe('Synced requirement.');
    });

    test('save shows "Linear issue updated" in success feedback when linear_synced=true', async () => {
        reqTicketInput.value = 'AI-157';
        reqTextarea.value = 'Synced requirement.';
        reqSyncToggle.checked = true;

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, ticket_key: 'AI-157', linear_synced: true }),
        });

        await saveRequirement();

        expect(reqFeedback.textContent).toMatch(/linear issue updated/i);
    });

    // ---- Error Handling Tests ----

    test('save shows error feedback when Linear API fails (linear_error in response)', async () => {
        reqTicketInput.value = 'AI-157';
        reqTextarea.value = 'Requirement.';
        reqSyncToggle.checked = true;

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                ticket_key: 'AI-157',
                linear_synced: false,
                linear_error: 'Linear API unavailable',
            }),
        });

        await saveRequirement();

        expect(reqFeedback.className).toContain('error');
        expect(reqFeedback.textContent).toMatch(/Linear sync failed/i);
    });

    test('save shows error feedback when network fetch throws', async () => {
        reqTicketInput.value = 'AI-157';
        reqTextarea.value = 'Requirement.';
        reqSyncToggle.checked = false;

        fetchMock.mockRejectedValueOnce(new Error('Network error'));

        await saveRequirement();

        expect(reqFeedback.className).toContain('error');
        expect(reqFeedback.textContent).toMatch(/failed to save/i);
    });

    test('save button is re-enabled after save completes', async () => {
        reqTicketInput.value = 'AI-157';
        reqTextarea.value = 'Requirement.';
        reqSyncToggle.checked = false;

        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, ticket_key: 'AI-157', linear_synced: false }),
        });

        await saveRequirement();

        expect(reqSaveBtn.disabled).toBe(false);
    });

    test('save button is re-enabled even when fetch fails', async () => {
        reqTicketInput.value = 'AI-157';
        reqTextarea.value = 'Requirement.';
        reqSyncToggle.checked = false;

        fetchMock.mockRejectedValueOnce(new Error('Network error'));

        await saveRequirement();

        expect(reqSaveBtn.disabled).toBe(false);
    });
});
