"""Manual screenshot capture script for AI-129 provider switching demo.

This script helps capture screenshots showing the provider switching and hot-swap functionality.
"""

import time
from pathlib import Path

def print_instructions():
    """Print instructions for manual screenshot capture."""

    screenshots_dir = Path(__file__).parent.parent.parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    print("\n" + "="*80)
    print("AI-129: Multi-Provider Switching - Manual Screenshot Capture")
    print("="*80)
    print()
    print("SETUP INSTRUCTIONS:")
    print("-" * 80)
    print("1. Start the REST API server:")
    print("   cd /Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-dashboard")
    print("   python dashboard/rest_api_server.py --port 8420")
    print()
    print("2. Open test_chat.html in a browser:")
    print("   Open: dashboard/test_chat.html")
    print("   Or use: file:///Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-dashboard/.worktrees/coding-0/dashboard/test_chat.html")
    print()
    print()
    print("SCREENSHOT CHECKLIST:")
    print("-" * 80)
    print()
    print("Screenshot 1: All 6 Providers in Selector")
    print("  - Click on the Provider dropdown")
    print("  - Verify all 6 providers are visible: Claude, ChatGPT, Gemini, Groq, KIMI, Windsurf")
    print("  - Capture: provider_selector_all_6.png")
    print()

    print("Screenshot 2: Provider Status Indicators")
    print("  - Show the provider badge with status indicator (green/yellow/red dot)")
    print("  - The dot should be visible next to the provider name")
    print("  - Capture: provider_status_indicator.png")
    print()

    print("Screenshot 3: Initial Conversation with Claude")
    print("  - Ensure Claude is selected")
    print("  - Send message: 'Hello, testing multi-provider chat!'")
    print("  - Wait for response")
    print("  - Capture: conversation_1_claude.png")
    print()

    print("Screenshot 4: Hot-Swap to Gemini (History Preserved)")
    print("  - Switch provider to Gemini using dropdown")
    print("  - Verify the previous message is still visible")
    print("  - Verify badge changed to 'Gemini'")
    print("  - Verify model selector updated to show Gemini models")
    print("  - Capture: conversation_2_gemini_hotswap.png")
    print()

    print("Screenshot 5: Continue Conversation with Gemini")
    print("  - Send message: 'What is 2+2?'")
    print("  - Wait for Gemini response")
    print("  - Verify both Claude and Gemini messages are visible")
    print("  - Capture: conversation_3_gemini_response.png")
    print()

    print("Screenshot 6: Hot-Swap to Groq (All History Preserved)")
    print("  - Switch provider to Groq")
    print("  - Verify all previous messages are still visible")
    print("  - Verify badge changed to 'Groq'")
    print("  - Verify model selector updated to show Groq models")
    print("  - Capture: conversation_4_groq_hotswap.png")
    print()

    print("Screenshot 7: Model Selector Sync")
    print("  - Open the Model dropdown")
    print("  - Verify it shows Groq-specific models (Llama 3.3 70B, Mixtral 8x7B)")
    print("  - Capture: model_selector_groq.png")
    print()

    print("Screenshot 8: Complete Conversation Thread")
    print("  - Send final message with Groq: 'Show me the conversation history'")
    print("  - Wait for response")
    print("  - Scroll to show entire conversation with all 3 providers")
    print("  - Capture: conversation_final_all_providers.png")
    print()

    print()
    print("SAVE SCREENSHOTS TO:")
    print("-" * 80)
    print(f"  {screenshots_dir.absolute()}")
    print()

    print()
    print("BROWSER DEVELOPER CONSOLE VERIFICATION:")
    print("-" * 80)
    print("  - Open browser DevTools (F12)")
    print("  - Check Console for log messages:")
    print("    - 'Provider hot-swapped from X to Y'")
    print("    - 'Conversation history preserved: N messages'")
    print("  - Check Application > Session Storage:")
    print("    - selectedAIProvider")
    print("    - selectedAIModel")
    print("    - chatMessages (should contain JSON array of messages)")
    print()

    print()
    print("SUCCESS CRITERIA:")
    print("-" * 80)
    print("  ✓ All 6 providers display in selector")
    print("  ✓ Provider status indicators show (green/yellow/red)")
    print("  ✓ Provider switching works without losing chat history")
    print("  ✓ Model selector updates when provider changes")
    print("  ✓ Hot-swap during conversation preserves all messages")
    print()
    print("="*80)
    print()

if __name__ == "__main__":
    print_instructions()
