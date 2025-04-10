// Options page functionality for AI Chat Assistant
import { MemoryClient } from "mem0ai";

// Default configuration
const defaultConfig = {
  model: "gpt-4o",
  maxTokens: 2000,
  temperature: 0.7,
  enabledSites: ["youtube.com"],
};

// Initialize Mem0AI client
let mem0client = null;

// Initialize when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", init);

// Initialize options page
async function init() {
  // Set up event listeners
  document
    .getElementById("save-options")
    .addEventListener("click", saveOptions);
  document
    .getElementById("reset-defaults")
    .addEventListener("click", resetToDefaults);
  document.getElementById("add-memory").addEventListener("click", addMemory);

  // Set up slider value display
  const temperatureSlider = document.getElementById("temperature");
  const temperatureValue = document.getElementById("temperature-value");

  temperatureSlider.addEventListener("input", () => {
    temperatureValue.textContent = temperatureSlider.value;
  });

  // Set up memories sidebar functionality
  document
    .getElementById("refresh-memories")
    .addEventListener("click", fetchMemories);
  document
    .getElementById("delete-all-memories")
    .addEventListener("click", deleteAllMemories);
  document
    .getElementById("close-edit-modal")
    .addEventListener("click", closeEditModal);
  document.getElementById("save-memory").addEventListener("click", saveMemory);
  document
    .getElementById("delete-memory")
    .addEventListener("click", deleteMemory);

  // Load current configuration
  await loadConfig();
  // Initialize Mem0AI and load memories
  await initializeMem0AI();
  await fetchMemories();
}

// Initialize Mem0AI with API key from storage
async function initializeMem0AI() {
  try {
    const response = await chrome.runtime.sendMessage({ action: "getConfig" });
    const mem0ApiKey = response.config.mem0ApiKey;

    if (!mem0ApiKey) {
      showMemoriesError("Please configure your Mem0 API key in the popup");
      return false;
    }

    mem0client = new MemoryClient({
      apiKey: mem0ApiKey,
      projectId: "youtube-assistant",
      isExtension: true,
    });

    return true;
  } catch (error) {
    console.error("Error initializing Mem0AI:", error);
    showMemoriesError("Failed to initialize Mem0AI");
    return false;
  }
}

// Load configuration from storage
async function loadConfig() {
  try {
    const response = await chrome.runtime.sendMessage({ action: "getConfig" });
    const config = response.config;

    // Update form fields with current values
    if (config.model) {
      document.getElementById("model").value = config.model;
    }

    if (config.maxTokens) {
      document.getElementById("max-tokens").value = config.maxTokens;
    }

    if (config.temperature !== undefined) {
      const temperatureSlider = document.getElementById("temperature");
      temperatureSlider.value = config.temperature;
      document.getElementById("temperature-value").textContent =
        config.temperature;
    }
  } catch (error) {
    showStatus(`Error loading configuration: ${error.message}`, "error");
  }
}

// Save options to storage
async function saveOptions() {
  // Get values from form
  const model = document.getElementById("model").value;
  const maxTokens = parseInt(document.getElementById("max-tokens").value);
  const temperature = parseFloat(document.getElementById("temperature").value);

  // Validate inputs
  if (maxTokens < 50 || maxTokens > 4000) {
    showStatus("Maximum tokens must be between 50 and 4000", "error");
    return;
  }

  if (temperature < 0 || temperature > 1) {
    showStatus("Temperature must be between 0 and 1", "error");
    return;
  }

  // Prepare config object
  const config = {
    model,
    maxTokens,
    temperature,
  };

  // Show loading status
  showStatus("Saving options...", "warning");

  try {
    // Send to background script for saving
    const response = await chrome.runtime.sendMessage({
      action: "saveConfig",
      config,
    });

    if (response.error) {
      showStatus(`Error: ${response.error}`, "error");
    } else {
      showStatus("Options saved successfully", "success");
      loadConfig(); // Refresh the UI with the latest saved values
    }
  } catch (error) {
    showStatus(`Error: ${error.message}`, "error");
  }
}

// Reset options to defaults
function resetToDefaults() {
  if (
    confirm(
      "Are you sure you want to reset all options to their default values?"
    )
  ) {
    // Set form fields to default values
    document.getElementById("model").value = defaultConfig.model;
    document.getElementById("max-tokens").value = defaultConfig.maxTokens;

    const temperatureSlider = document.getElementById("temperature");
    temperatureSlider.value = defaultConfig.temperature;
    document.getElementById("temperature-value").textContent =
      defaultConfig.temperature;

    showStatus("Restored default values. Click Save to apply.", "warning");
  }
}

// Memories functionality
let currentMemory = null;

async function fetchMemories() {
  try {
    if (!mem0client) {
      const initialized = await initializeMem0AI();
      if (!initialized) return;
    }

    const memories = await mem0client.getAll({
      user_id: "youtube-assistant-mem0",
      page: 1,
      page_size: 50,
    });
    displayMemories(memories.results);
  } catch (error) {
    console.error("Error fetching memories:", error);
    showMemoriesError("Failed to load memories");
  }
}

function displayMemories(memories) {
  const memoriesList = document.getElementById("memories-list");
  memoriesList.innerHTML = "";

  if (memories.length === 0) {
    memoriesList.innerHTML = `
      <div class="memory-item">
        <div class="memory-content">No memories found. Your memories will appear here.</div>
      </div>
    `;
    return;
  }

  memories.forEach((memory) => {
    const memoryElement = document.createElement("div");
    memoryElement.className = "memory-item";
    memoryElement.innerHTML = `
      <div class="memory-content">${memory.memory}</div>
      <div class="memory-meta">Last updated: ${new Date(
        memory.updated_at
      ).toLocaleString()}</div>
      <div class="memory-actions">
        <button class="memory-action-btn edit" data-id="${
          memory.id
        }">Edit</button>
        <button class="memory-action-btn delete" data-id="${
          memory.id
        }">Delete</button>
      </div>
    `;

    // Add event listeners
    memoryElement
      .querySelector(".edit")
      .addEventListener("click", () => editMemory(memory));
    memoryElement
      .querySelector(".delete")
      .addEventListener("click", () => deleteMemory(memory.id));

    memoriesList.appendChild(memoryElement);
  });
}

function showMemoriesError(message) {
  const memoriesList = document.getElementById("memories-list");
  memoriesList.innerHTML = `
    <div class="memory-item">
      <div class="memory-content">${message}</div>
    </div>
  `;
}

async function deleteAllMemories() {
  if (
    !confirm(
      "Are you sure you want to delete all memories? This action cannot be undone."
    )
  ) {
    return;
  }

  try {
    if (!mem0client) {
      const initialized = await initializeMem0AI();
      if (!initialized) return;
    }

    await mem0client.deleteAll({
      user_id: "youtube-assistant-mem0",
    });
    showStatus("All memories deleted successfully", "success");
    await fetchMemories();
  } catch (error) {
    console.error("Error deleting memories:", error);
    showStatus("Failed to delete memories", "error");
  }
}

function editMemory(memory) {
  currentMemory = memory;
  const modal = document.getElementById("edit-memory-modal");
  const textarea = document.getElementById("edit-memory-text");
  textarea.value = memory.memory;
  modal.classList.add("open");
}

function closeEditModal() {
  const modal = document.getElementById("edit-memory-modal");
  modal.classList.remove("open");
  currentMemory = null;
}

async function saveMemory() {
  if (!currentMemory) return;

  try {
    if (!mem0client) {
      const initialized = await initializeMem0AI();
      if (!initialized) return;
    }

    const textarea = document.getElementById("edit-memory-text");
    const updatedMemory = textarea.value.trim();

    if (!updatedMemory) {
      showStatus("Memory cannot be empty", "error");
      return;
    }

    await mem0client.update(currentMemory.id, updatedMemory);

    showStatus("Memory updated successfully", "success");
    closeEditModal();
    await fetchMemories();
  } catch (error) {
    console.error("Error updating memory:", error);
    showStatus("Failed to update memory", "error");
  }
}

async function deleteMemory(memoryId) {
  if (
    !confirm(
      "Are you sure you want to delete this memory? This action cannot be undone."
    )
  ) {
    return;
  }

  try {
    if (!mem0client) {
      const initialized = await initializeMem0AI();
      if (!initialized) return;
    }

    await mem0client.delete(memoryId);
    showStatus("Memory deleted successfully", "success");
    await fetchMemories();
  } catch (error) {
    console.error("Error deleting memory:", error);
    showStatus("Failed to delete memory", "error");
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

// Add memory to Mem0
async function addMemory() {
  const memoryInput = document.getElementById("memory-input");
  const addButton = document.getElementById("add-memory");
  const memoryResult = document.getElementById("memory-result");
  const buttonText = addButton.querySelector(".button-text");

  const content = memoryInput.value.trim();

  if (!content) {
    showMemoryResult(
      "Please enter some information to add as a memory",
      "error"
    );
    return;
  }

  // Show loading state
  addButton.disabled = true;
  buttonText.textContent = "Adding...";
  addButton.innerHTML =
    '<div class="loading-spinner"></div><span class="button-text">Adding...</span>';
  memoryResult.style.display = "none";

  try {
    if (!mem0client) {
      const initialized = await initializeMem0AI();
      if (!initialized) return;
    }

    const result = await mem0client.add(
      [
        {
          role: "user",
          content: content,
        },
      ],
      {
        user_id: "youtube-assistant-mem0",
      }
    );

    // Show success message with number of memories added
    showMemoryResult(
      `Added ${result.length || 0} new ${
        result.length === 1 ? "memory" : "memories"
      }`,
      "success"
    );

    // Clear the input
    memoryInput.value = "";

    // Refresh the memories list
    await fetchMemories();
  } catch (error) {
    showMemoryResult(`Error adding memory: ${error.message}`, "error");
  } finally {
    // Reset button state
    addButton.disabled = false;
    buttonText.textContent = "Add Memory";
    addButton.innerHTML = '<span class="button-text">Add Memory</span>';
  }
}

// Show memory result message
function showMemoryResult(message, type) {
  const memoryResult = document.getElementById("memory-result");
  memoryResult.textContent = message;
  memoryResult.className = `memory-result ${type}`;
  memoryResult.style.display = "block";

  // Auto-clear success messages after 3 seconds
  if (type === "success") {
    setTimeout(() => {
      memoryResult.style.opacity = "0";
      setTimeout(() => {
        memoryResult.style.display = "none";
        memoryResult.style.opacity = "1";
      }, 300);
    }, 3000);
  }
}
