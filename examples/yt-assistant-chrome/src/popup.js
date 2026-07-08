// Popup functionality for AI Chat Assistant

document.addEventListener("DOMContentLoaded", init);

// Initialize popup
async function init() {
  try {
    // Set up event listeners
    document
      .getElementById("toggle-chat")
      .addEventListener("click", toggleChat);
    document
      .getElementById("open-options")
      .addEventListener("click", openOptions);
    document
      .getElementById("save-api-key")
      .addEventListener("click", saveApiKey);
    document
      .getElementById("save-mem0-api-key")
      .addEventListener("click", saveMem0ApiKey);

    // Set up password toggle listeners
    document
      .getElementById("toggle-openai-key")
      .addEventListener("click", () => togglePasswordVisibility("api-key"));
    document
      .getElementById("toggle-mem0-key")
      .addEventListener("click", () =>
        togglePasswordVisibility("mem0-api-key")
      );

    // Load current configuration and wait for it to complete
    await loadConfig();
  } catch (error) {
    console.error("Initialization error:", error);
    showStatus("Error initializing popup", "error");
  }
}

// Toggle chat visibility in the active tab
function toggleChat() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      // First check if we can inject the content script
      chrome.scripting
        .executeScript({
          target: { tabId: tabs[0].id },
          files: ["dist/content.bundle.js"],
        })
        .then(() => {
          // Now try to toggle the chat
          chrome.tabs
            .sendMessage(tabs[0].id, { action: "toggleChat" })
            .then((response) => {
              if (response && response.error) {
                console.error("Error toggling chat:", response.error);
                showStatus(
                  "Chat interface not available on this page",
                  "warning"
                );
              } else {
                // Close the popup after successful toggle
                window.close();
              }
            })
            .catch((error) => {
              console.error("Error toggling chat:", error);
              showStatus(
                "Chat interface not available on this page",
                "warning"
              );
            });
        })
        .catch((error) => {
          console.error("Error injecting content script:", error);
          showStatus("Cannot inject chat interface on this page", "error");
        });
    }
  });
}

// Open options page
function openOptions() {
  // Send message to background script to handle opening options
  chrome.runtime.sendMessage({ action: "openOptions" }, (response) => {
    if (chrome.runtime.lastError) {
      console.error("Error opening options:", chrome.runtime.lastError);

      // Direct fallback if communication with background script fails
      try {
        chrome.tabs.create({ url: chrome.runtime.getURL("options.html") });
      } catch (err) {
        console.error("Fallback failed:", err);
        // Last resort
        window.open(chrome.runtime.getURL("options.html"), "_blank");
      }
    }
  });
}

// Toggle password visibility
function togglePasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  const type = input.type === "password" ? "text" : "password";
  input.type = type;

  // Update the eye icon
  const button = input.nextElementSibling;
  const icon = button.querySelector(".icon");
  if (type === "text") {
    icon.innerHTML =
      '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>';
  } else {
    icon.innerHTML =
      '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
  }
}

// Save API key to storage
async function saveApiKey() {
  const apiKeyInput = document.getElementById("api-key");
  const apiKey = apiKeyInput.value.trim();

  // Show loading status
  showStatus("Saving API key...", "warning");

  try {
    // Send to background script for validation and saving
    const response = await chrome.runtime.sendMessage({
      action: "saveConfig",
      config: { apiKey },
    });

    if (response.error) {
      showStatus(`Error: ${response.error}`, "error");
    } else {
      showStatus("API key saved successfully", "success");
      loadConfig(); // Refresh the UI
    }
  } catch (error) {
    showStatus(`Error: ${error.message}`, "error");
  }
}

// Save mem0 API key to storage
async function saveMem0ApiKey() {
  const apiKeyInput = document.getElementById("mem0-api-key");
  const apiKey = apiKeyInput.value.trim();

  // Show loading status
  showStatus("Saving Mem0 API key...", "warning");

  try {
    // Send to background script for saving
    const response = await chrome.runtime.sendMessage({
      action: "saveConfig",
      config: { mem0ApiKey: apiKey },
    });

    if (response.error) {
      showStatus(`Error: ${response.error}`, "error");
    } else {
      showStatus("Mem0 API key saved successfully", "success");
      loadConfig(); // Refresh the UI
    }
  } catch (error) {
    showStatus(`Error: ${error.message}`, "error");
  }
}

// Load configuration from storage
async function loadConfig() {
  try {
    // Add a small delay to ensure background script is ready
    await new Promise((resolve) => setTimeout(resolve, 100));

    const response = await chrome.runtime.sendMessage({ action: "getConfig" });
    const config = response.config || {};

    // Update OpenAI API key field
    const apiKeyInput = document.getElementById("api-key");
    if (config.apiKey) {
      apiKeyInput.value = config.apiKey;
      apiKeyInput.type = "password"; // Ensure it's hidden by default
      document.getElementById("api-key-section").style.display = "block";
    } else {
      apiKeyInput.value = "";
      document.getElementById("api-key-section").style.display = "block";
      showStatus("Please set your OpenAI API key", "warning");
    }

    // Update mem0 API key field
    const mem0ApiKeyInput = document.getElementById("mem0-api-key");
    if (config.mem0ApiKey) {
      mem0ApiKeyInput.value = config.mem0ApiKey;
      mem0ApiKeyInput.type = "password"; // Ensure it's hidden by default
      document.getElementById("mem0-api-key-section").style.display = "block";
      document.getElementById("mem0-status-text").textContent = "Connected";
      document.getElementById("mem0-status-text").style.color =
        "var(--success-color)";
    } else {
      mem0ApiKeyInput.value = "";
      document.getElementById("mem0-api-key-section").style.display = "block";
      document.getElementById("mem0-status-text").textContent =
        "Not configured";
      document.getElementById("mem0-status-text").style.color =
        "var(--warning-color)";
    }
  } catch (error) {
    console.error("Error loading configuration:", error);
    showStatus(`Error loading configuration: ${error.message}`, "error");
  }
}

// Show status message
function showStatus(message, type = "info") {
  const statusContainer = document.getElementById("status-container");

  // Clear previous status
  statusContainer.innerHTML = "";

  // Create status element
  const statusElement = document.createElement("div");
  statusElement.className = `status ${type}`;
  statusElement.textContent = message;

  // Add to container
  statusContainer.appendChild(statusElement);

  // Auto-clear success messages after 3 seconds
  if (type === "success") {
    setTimeout(() => {
      statusElement.style.opacity = "0";
      setTimeout(() => {
        if (statusContainer.contains(statusElement)) {
          statusContainer.removeChild(statusElement);
        }
      }, 300);
    }, 3000);
  }
}
