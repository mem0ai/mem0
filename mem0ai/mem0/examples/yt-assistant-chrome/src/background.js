// Background script to handle API calls to OpenAI and manage extension state

// Configuration (will be stored in sync storage eventually)
let config = {
  apiKey: "", // Will be set by user in options
  mem0ApiKey: "", // Will be set by user in options
  model: "gpt-4",
  maxTokens: 2000,
  temperature: 0.7,
  enabledSites: ["youtube.com"],
};

// Track if config is loaded
let isConfigLoaded = false;

// Initialize configuration from storage
chrome.storage.sync.get(
  ["apiKey", "mem0ApiKey", "model", "maxTokens", "temperature", "enabledSites"],
  (result) => {
    if (result.apiKey) config.apiKey = result.apiKey;
    if (result.mem0ApiKey) config.mem0ApiKey = result.mem0ApiKey;
    if (result.model) config.model = result.model;
    if (result.maxTokens) config.maxTokens = result.maxTokens;
    if (result.temperature) config.temperature = result.temperature;
    if (result.enabledSites) config.enabledSites = result.enabledSites;

    isConfigLoaded = true;
  }
);

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Handle different message types
  switch (request.action) {
    case "sendChatRequest":
      sendChatRequest(request.messages, request.model || config.model)
        .then((response) => sendResponse(response))
        .catch((error) => sendResponse({ error: error.message }));
      return true; // Required for async response

    case "saveConfig":
      saveConfig(request.config)
        .then(() => sendResponse({ success: true }))
        .catch((error) => sendResponse({ error: error.message }));
      return true;

    case "getConfig":
      // If config isn't loaded yet, load it first
      if (!isConfigLoaded) {
        chrome.storage.sync.get(
          [
            "apiKey",
            "mem0ApiKey",
            "model",
            "maxTokens",
            "temperature",
            "enabledSites",
          ],
          (result) => {
            if (result.apiKey) config.apiKey = result.apiKey;
            if (result.mem0ApiKey) config.mem0ApiKey = result.mem0ApiKey;
            if (result.model) config.model = result.model;
            if (result.maxTokens) config.maxTokens = result.maxTokens;
            if (result.temperature) config.temperature = result.temperature;
            if (result.enabledSites) config.enabledSites = result.enabledSites;
            isConfigLoaded = true;
            sendResponse({ config });
          }
        );
        return true;
      }
      sendResponse({ config });
      return false;

    case "openOptions":
      // Open options page
      chrome.runtime.openOptionsPage(() => {
        if (chrome.runtime.lastError) {
          console.error(
            "Error opening options page:",
            chrome.runtime.lastError
          );
          // Fallback: Try to open directly in a new tab
          chrome.tabs.create({ url: chrome.runtime.getURL("options.html") });
        }
        sendResponse({ success: true });
      });
      return true;

    case "toggleChat":
      // Forward the toggle request to the active tab
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
          chrome.tabs
            .sendMessage(tabs[0].id, { action: "toggleChat" })
            .then((response) => sendResponse(response))
            .catch((error) => sendResponse({ error: error.message }));
        } else {
          sendResponse({ error: "No active tab found" });
        }
      });
      return true;
  }
});

// Handle extension icon click - toggle chat visibility
chrome.action.onClicked.addListener((tab) => {
  chrome.tabs
    .sendMessage(tab.id, { action: "toggleChat" })
    .catch((error) => console.error("Error toggling chat:", error));
});

// Save configuration to sync storage
async function saveConfig(newConfig) {
  // Validate API key if provided
  if (newConfig.apiKey) {
    try {
      const isValid = await validateApiKey(newConfig.apiKey);
      if (!isValid) {
        throw new Error("Invalid API key");
      }
    } catch (error) {
      throw new Error(`API key validation failed: ${error.message}`);
    }
  }

  // Update local config
  config = { ...config, ...newConfig };

  // Save to sync storage
  return chrome.storage.sync.set(newConfig);
}

// Validate OpenAI API key with a simple request
async function validateApiKey(apiKey) {
  try {
    const response = await fetch("https://api.openai.com/v1/models", {
      method: "GET",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }

    return true;
  } catch (error) {
    console.error("API key validation error:", error);
    return false;
  }
}

// Send a chat request to OpenAI API
async function sendChatRequest(messages, model) {
  // Check if API key is set
  if (!config.apiKey) {
    return {
      error:
        "API key not configured. Please set your OpenAI API key in the extension options.",
    };
  }

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: model || config.model,
        messages: messages.map((msg) => ({
          role: msg.role,
          content: msg.content,
        })),
        max_tokens: config.maxTokens,
        temperature: config.temperature,
        stream: true, // Enable streaming
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(
        errorData.error?.message || `API returned ${response.status}`
      );
    }

    // Create a ReadableStream from the response
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    // Process the stream
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Decode the chunk and add to buffer
      buffer += decoder.decode(value, { stream: true });

      // Process complete lines
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // Keep the last incomplete line in the buffer

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            // Stream complete
            return { done: true };
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.choices[0].delta.content) {
              // Send the chunk to the content script
              chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                if (tabs[0]) {
                  chrome.tabs.sendMessage(tabs[0].id, {
                    action: "streamChunk",
                    chunk: parsed.choices[0].delta.content,
                  });
                }
              });
            }
          } catch (e) {
            console.error("Error parsing chunk:", e);
          }
        }
      }
    }

    return { done: true };
  } catch (error) {
    console.error("Error sending chat request:", error);
    return { error: error.message };
  }
}

// Future: Add mem0 integration functions here
// When ready, replace with actual implementation
function mem0Integration() {
  // Placeholder for future mem0 integration
  return {
    getUserMemories: async (userId) => {
      return { memories: [] };
    },
    saveMemory: async (userId, memory) => {
      return { success: true };
    },
  };
}
