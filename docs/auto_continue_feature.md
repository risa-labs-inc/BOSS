# Auto-Continue Feature for Claude in Cursor

## Overview

When working with Claude in the Cursor IDE, you may encounter this message after a series of tool calls:

```
Note: we default stop the agent after 25 tool calls. You can resume the conversation.
```

The Auto-Continue feature automatically handles this situation by:
1. Waiting for 2 seconds after detecting the message
2. Automatically sending "continue" as a response
3. Allowing Claude to resume the conversation without manual intervention

## Installation

1. Run the setup script from the terminal:
   ```bash
   ./scripts/setup_auto_continue.sh
   ```

2. This script will:
   - Create the necessary extension files in the `.cursor/extensions` directory
   - Add documentation on how to use the feature
   - Make the extension executable

3. In Cursor, you need to load the extension:
   - Open Cursor's settings/preferences
   - Navigate to Extensions or Custom Scripts
   - Load the extension from `.cursor/extensions/auto_continue.js`

## How It Works

The extension uses a MutationObserver to monitor the chat for the specific "tool calls" message. When detected, it:
1. Waits for the configured time (default: 2 seconds)
2. Automatically enters "continue" in the input field
3. Submits the message

## Customization

If you want to change the wait time before auto-continuing, edit the `.cursor/extensions/auto_continue.js` file and modify the `WAIT_TIME_MS` constant (in milliseconds).

## Troubleshooting

If the auto-continue feature isn't working:

1. Check if the extension is properly loaded in Cursor
2. Look for console messages in the Cursor developer tools
3. Verify that the script has the correct permissions
4. If needed, manually run the setup script again

## Manual Override

If you prefer to manually respond in certain cases, you can:
1. Quickly type your response before the 2-second delay elapses
2. Disable the extension in Cursor's settings temporarily 