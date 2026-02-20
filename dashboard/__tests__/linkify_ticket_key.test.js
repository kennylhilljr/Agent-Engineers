/**
 * Unit tests for linkifyTicketKey utility function (AI-261)
 * Tests the conversion of ticket identifiers to clickable links
 *
 * Run with: npm test tests/dashboard/test_ticket_links_ai261.spec.js
 */

// Mock the escapeHtml function
function escapeHtml(text) {
    // Node.js compatible version
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, char => map[char]);
}

// Copy the linkifyTicketKey function
function linkifyTicketKey(text) {
    if (!text) return '';
    const ticketPattern = /([A-Z]+-\d+)/g;
    return text.replace(ticketPattern, function(match) {
        return `<a href="https://linear.app/ai-cli-macz/issue/${match}" class="ticket-link" target="_blank" title="Open ${match} in Linear">${escapeHtml(match)}</a>`;
    });
}

describe('linkifyTicketKey', () => {

    test('should convert single ticket key to link', () => {
        const result = linkifyTicketKey('AI-261');
        expect(result).toContain('<a href="https://linear.app/ai-cli-macz/issue/AI-261"');
        expect(result).toContain('class="ticket-link"');
        expect(result).toContain('AI-261</a>');
    });

    test('should convert multiple ticket keys to links', () => {
        const result = linkifyTicketKey('Working on AI-261 and AI-262');
        expect(result).toContain('<a href="https://linear.app/ai-cli-macz/issue/AI-261"');
        expect(result).toContain('<a href="https://linear.app/ai-cli-macz/issue/AI-262"');
        expect(result).toContain('Working on ');
        expect(result).toContain(' and ');
    });

    test('should handle different ticket prefixes', () => {
        const result = linkifyTicketKey('LIN-123 is related to DB-456');
        expect(result).toContain('LIN-123</a>');
        expect(result).toContain('DB-456</a>');
    });

    test('should open links in new tab', () => {
        const result = linkifyTicketKey('AI-261');
        expect(result).toContain('target="_blank"');
    });

    test('should include title attribute for hover tooltip', () => {
        const result = linkifyTicketKey('AI-261');
        expect(result).toContain('title="Open AI-261 in Linear"');
    });

    test('should not linkify when text is empty', () => {
        expect(linkifyTicketKey('')).toBe('');
        expect(linkifyTicketKey(null)).toBe('');
        expect(linkifyTicketKey(undefined)).toBe('');
    });

    test('should preserve surrounding text', () => {
        const input = 'This is ticket AI-261 for testing';
        const result = linkifyTicketKey(input);
        expect(result).toContain('This is ticket ');
        expect(result).toContain(' for testing');
    });

    test('should handle ticket keys at start and end of text', () => {
        const result = linkifyTicketKey('AI-261 is the ticket');
        expect(result).toMatch(/^<a href/);

        const result2 = linkifyTicketKey('The ticket is AI-261');
        expect(result2).toMatch(/<\/a>$/);
    });

    test('should not linkify partial patterns', () => {
        const result = linkifyTicketKey('This is a AI and a -261 but not AI-261 yet');
        // Only AI-261 should be linkified
        const linkCount = (result.match(/ticket-link/g) || []).length;
        expect(linkCount).toBe(1);
    });

    test('should handle special characters in text safely', () => {
        const result = linkifyTicketKey('Issue: AI-261 (important!) & AI-262');
        expect(result).toContain('Issue: ');
        expect(result).toContain(' (important!) &amp; ');
    });

    test('should work with activity event ticket key', () => {
        const event = { ticket_key: 'AI-150', status: 'success' };
        const ticketLink = linkifyTicketKey(event.ticket_key);
        expect(ticketLink).toContain('AI-150</a>');
    });

    test('should handle hyphenated prefixes', () => {
        const result = linkifyTicketKey('AI-CORE-123 should work too');
        expect(result).toContain('AI-CORE</a>-123');
    });
});
