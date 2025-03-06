// Auto-Continue Extension for Cursor
// Automatically responds with "continue" when Claude hits the tool call limit

(function() {
  // Configuration
  const WAIT_TIME_MS = 2000; // Wait 2 seconds before responding
  let isWaiting = false;

  // Function to monitor messages in the chat
  function monitorMessages() {
    const chatContainer = document.querySelector('.chat-container');
    if (!chatContainer) {
      console.log("Chat container not found, retrying in 1 second...");
      setTimeout(monitorMessages, 1000);
      return;
    }

    console.log("Auto-continue feature enabled - monitoring for tool call limit messages");

    // Create a MutationObserver to watch for new messages
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        // Check added nodes for the specific message
        if (mutation.addedNodes) {
          mutation.addedNodes.forEach(function(node) {
            if (node.textContent && 
                node.textContent.includes("Note: we default stop the agent after 25 tool calls. You can resume the conversation.") &&
                !isWaiting) {
              
              console.log("Tool call limit detected, will auto-continue in " + (WAIT_TIME_MS/1000) + " seconds");
              isWaiting = true;
              
              // Wait for specified time
              setTimeout(() => {
                // Find the input field and submit button
                const inputField = document.querySelector('.chat-input textarea');
                const submitButton = document.querySelector('.chat-input button[type="submit"]');
                
                if (inputField && submitButton) {
                  // Set the input field value
                  const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                  nativeTextAreaValueSetter.call(inputField, "continue");
                  
                  // Dispatch an input event to trigger any listeners
                  inputField.dispatchEvent(new Event('input', { bubbles: true }));
                  
                  // Click the submit button
                  submitButton.click();
                  
                  console.log("Auto-continued the conversation");
                } else {
                  console.error("Could not find input field or submit button");
                }
                
                isWaiting = false;
              }, WAIT_TIME_MS);
            }
          });
        }
      });
    });

    // Start observing the chat container for changes
    observer.observe(chatContainer, { childList: true, subtree: true });
  }

  // Start monitoring when the document is ready
  if (document.readyState === "complete" || document.readyState === "interactive") {
    setTimeout(monitorMessages, 1000);
  } else {
    document.addEventListener("DOMContentLoaded", function() {
      setTimeout(monitorMessages, 1000);
    });
  }
})();
