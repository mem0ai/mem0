// Main content script that injects the AI chat into YouTube
import { YoutubeTranscript } from "youtube-transcript";
import { MemoryClient } from "mem0ai";

// Configuration
const config = {
  apiEndpoint: "https://api.openai.com/v1/chat/completions",
  model: "gpt-4o",
  chatPosition: "right", // Where to display the chat panel
  autoExtract: true, // Automatically extract video context
  mem0ApiKey: "", // Will be set through extension options
};

// Initialize Mem0AI - will be initialized properly when API key is available
let mem0client = null;
let mem0Initializing = false;

// Function to initialize Mem0AI with API key from storage
async function initializeMem0AI() {
  if (mem0Initializing) return; // Prevent multiple simultaneous initialization attempts
  mem0Initializing = true;

  try {
    // Get API key from storage
    const items = await chrome.storage.sync.get(["mem0ApiKey"]);
    if (items.mem0ApiKey) {
      try {
        // Create new client instance with v2.1.11 configuration
        mem0client = new MemoryClient({
          apiKey: items.mem0ApiKey,
          projectId: "youtube-assistant", // Add a project ID for organization
          isExtension: true,
        });

        // Set up custom instructions for the YouTube educational assistant
        await mem0client.updateProject({
          custom_instructions: `Your task: Create memories for a YouTube AI assistant. Focus on capturing:

1. User's Knowledge & Experience:
   - Direct statements about their skills, knowledge, or experience
   - Their level of expertise in specific areas
   - Technologies, frameworks, or tools they work with
   - Their learning journey or background

2. User's Interests & Goals:
   - What they're trying to learn or understand (user messages may include the video title)
   - Their specific questions or areas of confusion
   - Their learning objectives or career goals
   - Topics they want to explore further

3. Personal Context:
   - Their current role or position
   - Their learning style or preferences
   - Their experience level in the video's topic
   - Any challenges or difficulties they're facing

4. Video Engagement:
   - Their reactions to the content
   - Points they agree or disagree with
   - Areas they want to discuss further
   - Connections they make to other topics

For each message:
- Extract both explicit statements and implicit knowledge
- Capture both video-related and personal context
- Note any relationships between user's knowledge and video content

Remember: The goal is to build a comprehensive understanding of both the user's knowledge and their learning journey through YouTube.`,
        });
        return true;
      } catch (error) {
        console.error("Error initializing Mem0AI:", error);
        return false;
      }
    } else {
      console.log("No Mem0AI API key found in storage");
      return false;
    }
  } catch (error) {
    console.error("Error accessing storage:", error);
    return false;
  } finally {
    mem0Initializing = false;
  }
}

// Global state
let chatState = {
  messages: [],
  isVisible: false,
  isLoading: false,
  videoContext: null,
  transcript: null, // Add transcript to state
  userMemories: null, // Will store retrieved memories
  currentStreamingMessage: null, // Track the current streaming message
};

// Function to extract video ID from YouTube URL
function getYouTubeVideoId(url) {
  const urlObj = new URL(url);
  const searchParams = new URLSearchParams(urlObj.search);
  return searchParams.get("v");
}

// Function to fetch and log transcript
async function fetchAndLogTranscript() {
  try {
    // Check if we're on a YouTube video page
    if (
      window.location.hostname.includes("youtube.com") &&
      window.location.pathname.includes("/watch")
    ) {
      const videoId = getYouTubeVideoId(window.location.href);

      if (videoId) {
        // Fetch transcript using youtube-transcript package
        const transcript = await YoutubeTranscript.fetchTranscript(videoId);

        // Decode HTML entities in transcript text
        const decodedTranscript = transcript.map((entry) => ({
          ...entry,
          text: entry.text
            .replace(/&amp;#39;/g, "'")
            .replace(/&amp;quot;/g, '"')
            .replace(/&amp;lt;/g, "<")
            .replace(/&amp;gt;/g, ">")
            .replace(/&amp;amp;/g, "&"),
        }));

        // Store transcript in state
        chatState.transcript = decodedTranscript;
      } else {
        return;
      }
    }
  } catch (error) {
    console.error("Error fetching transcript:", error);
    chatState.transcript = null;
  }
}

// Initialize when the DOM is fully loaded
document.addEventListener("DOMContentLoaded", async () => {
  init();
  fetchAndLogTranscript();
  await initializeMem0AI(); // Initialize Mem0AI
});

// Also attempt to initialize on window load to handle YouTube's SPA behavior
window.addEventListener("load", async () => {
  init();
  fetchAndLogTranscript();
  await initializeMem0AI(); // Initialize Mem0AI
});

// Add another listener for YouTube's navigation events
window.addEventListener("yt-navigate-finish", () => {
  init();
  fetchAndLogTranscript();
});

// Main initialization function
function init() {
  // Check if we're on a YouTube page
  if (
    !window.location.hostname.includes("youtube.com") ||
    !window.location.pathname.includes("/watch")
  ) {
    return;
  }

  // Give YouTube's DOM a moment to settle
  setTimeout(() => {
    // Only inject if not already present
    if (!document.getElementById("ai-chat-assistant-container")) {
      injectChatInterface();
      setupEventListeners();
      extractVideoContext();
    }
  }, 1500);
}

// Extract context from the current YouTube video
function extractVideoContext() {
  if (!config.autoExtract) return;

  try {
    const videoTitle =
      document.querySelector(
        "h1.title.style-scope.ytd-video-primary-info-renderer"
      )?.textContent ||
      document.querySelector("h1.title")?.textContent ||
      "Unknown Video";
    const channelName =
      document.querySelector("ytd-channel-name yt-formatted-string")
        ?.textContent ||
      document.querySelector("ytd-channel-name")?.textContent ||
      "Unknown Channel";

    // Video ID from URL
    const videoId = new URLSearchParams(window.location.search).get("v");

    // Update state with basic video context first
    chatState.videoContext = {
      title: videoTitle,
      channel: channelName,
      videoId: videoId,
      url: window.location.href,
    };
  } catch (error) {
    console.error("Error extracting video context:", error);
    chatState.videoContext = {
      title: "Error extracting video information",
      url: window.location.href,
    };
  }
}

// Inject the chat interface into the YouTube page
function injectChatInterface() {
  // Create main container
  const container = document.createElement("div");
  container.id = "ai-chat-assistant-container";
  container.className = "ai-chat-container";

  // Set up basic HTML structure
  container.innerHTML = `
    <div class="ai-chat-header">
      <div class="ai-chat-tabs">
        <button class="ai-chat-tab active" data-tab="chat">Chat</button>
        <button class="ai-chat-tab" data-tab="memories">Memories</button>
      </div>
      <div class="ai-chat-controls">
        <button id="ai-chat-minimize" class="ai-chat-btn" title="Minimize">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
        </button>
        <button id="ai-chat-close" class="ai-chat-btn" title="Close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>
    <div class="ai-chat-body">
      <div id="ai-chat-content" class="ai-chat-content">
        <div id="ai-chat-messages" class="ai-chat-messages"></div>
        <div class="ai-chat-input-container">
          <textarea id="ai-chat-input" placeholder="Ask about this video..."></textarea>
          <button id="ai-chat-send" class="ai-chat-send-btn" title="Send message">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
      </div>
      <div id="ai-chat-memories" class="ai-chat-memories" style="display: none;">
        <div class="memories-header">
          <div class="memories-title">
            Manage memories <a href="#" id="manage-memories-link" title="Open options page">here <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
              <polyline points="15 3 21 3 21 9"></polyline>
              <line x1="10" y1="14" x2="21" y2="3"></line>
            </svg></a>
          </div>
          <button id="refresh-memories" class="ai-chat-btn" title="Refresh memories">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M23 4v6h-6"></path>
              <path d="M1 20v-6h6"></path>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
            </svg>
          </button>
        </div>
        <div id="memories-list" class="memories-list"></div>
      </div>
    </div>
  `;

  // Append to body
  document.body.appendChild(container);

  // Add welcome message
  addMessage(
    "assistant",
    "Hello! I can help answer questions about this video. What would you like to know?"
  );
}

// Set up event listeners for the chat interface
function setupEventListeners() {
  // Tab switching
  const tabs = document.querySelectorAll(".ai-chat-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      // Update active tab
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      // Show corresponding content
      const tabName = tab.dataset.tab;
      document.getElementById("ai-chat-content").style.display =
        tabName === "chat" ? "flex" : "none";
      document.getElementById("ai-chat-memories").style.display =
        tabName === "memories" ? "flex" : "none";

      // Load memories if switching to memories tab
      if (tabName === "memories") {
        loadMemories();
      }
    });
  });

  // Refresh memories button
  document
    .getElementById("refresh-memories")
    ?.addEventListener("click", loadMemories);

  // Toggle chat visibility
  document.getElementById("ai-chat-toggle")?.addEventListener("click", () => {
    const container = document.getElementById("ai-chat-assistant-container");
    chatState.isVisible = !chatState.isVisible;

    if (chatState.isVisible) {
      container.classList.add("visible");
    } else {
      container.classList.remove("visible");
    }
  });

  // Close button
  document.getElementById("ai-chat-close")?.addEventListener("click", () => {
    const container = document.getElementById("ai-chat-assistant-container");
    container.classList.remove("visible");
    chatState.isVisible = false;
  });

  // Minimize button
  document.getElementById("ai-chat-minimize")?.addEventListener("click", () => {
    const container = document.getElementById("ai-chat-assistant-container");
    container.classList.toggle("minimized");
  });

  // Send message on button click
  document
    .getElementById("ai-chat-send")
    ?.addEventListener("click", sendMessage);

  // Send message on Enter key (but allow Shift+Enter for new lines)
  document.getElementById("ai-chat-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Add click handler for manage memories link
  document
    .getElementById("manage-memories-link")
    .addEventListener("click", (e) => {
      e.preventDefault();
      chrome.runtime.sendMessage({ action: "openOptions" }, (response) => {
        if (chrome.runtime.lastError) {
          console.error("Error opening options:", chrome.runtime.lastError);
          // Fallback: Try to open directly in a new tab
          chrome.tabs.create({ url: chrome.runtime.getURL("options.html") });
        }
      });
    });
}

// Add a message to the chat
function addMessage(role, text, isStreaming = false) {
  const messagesContainer = document.getElementById("ai-chat-messages");
  if (!messagesContainer) return;

  const messageElement = document.createElement("div");
  messageElement.className = `ai-chat-message ${role}`;

  // Enhanced markdown-like formatting
  let formattedText = text
    // Code blocks
    .replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
    // Inline code
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    // Bold text
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    // Italic text
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    // Lists
    .replace(/^\s*[-*]\s+(.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>")
    // Line breaks
    .replace(/\n/g, "<br>");

  messageElement.innerHTML = formattedText;
  messagesContainer.appendChild(messageElement);

  // Scroll to bottom
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  // Add to messages array if not streaming
  if (!isStreaming) {
    chatState.messages.push({ role, content: text });
  }

  return messageElement;
}

// Format streaming text with markdown
function formatStreamingText(text) {
  return text
    // Code blocks
    .replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
    // Inline code
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    // Bold text
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    // Italic text
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    // Lists
    .replace(/^\s*[-*]\s+(.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>")
    // Line breaks
    .replace(/\n/g, "<br>");
}

// Send a message to the AI
async function sendMessage() {
  const inputElement = document.getElementById("ai-chat-input");
  if (!inputElement) return;

  const userMessage = inputElement.value.trim();
  if (!userMessage) return;

  // Clear input
  inputElement.value = "";

  // Add user message to chat
  addMessage("user", userMessage);

  // Show loading indicator
  chatState.isLoading = true;
  const loadingMessage = document.createElement("div");
  loadingMessage.className = "ai-chat-message assistant loading";
  loadingMessage.textContent = "Thinking...";
  document.getElementById("ai-chat-messages").appendChild(loadingMessage);

  try {
    // If mem0client is available, store the message as a memory and search for relevant memories
    if (mem0client) {
      try {
        // Store the message as a memory
        await mem0client.add(
          [
            {
              role: "user",
              content: `${userMessage}\n\nVideo title: ${chatState.videoContext?.title}`,
            },
          ],
          {
            user_id: "youtube-assistant-mem0", // Required parameter
            metadata: {
              videoId: chatState.videoContext?.videoId || "",
              videoTitle: chatState.videoContext?.title || "",
            },
          }
        );

        // Search for relevant memories
        const searchResults = await mem0client.search(userMessage, {
          user_id: "youtube-assistant-mem0", // Required parameter
          limit: 5,
        });

        // Store the retrieved memories
        chatState.userMemories = searchResults || null;
      } catch (memoryError) {
        console.error("Error with Mem0AI operations:", memoryError);
        // Continue with the chat process even if memory operations fail
      }
    }

    // Prepare messages with context (now includes memories if available)
    const contextualizedMessages = prepareMessagesWithContext();

    // Remove loading message
    document.getElementById("ai-chat-messages").removeChild(loadingMessage);

    // Create a new message element for streaming
    chatState.currentStreamingMessage = addMessage("assistant", "", true);

    // Send to background script to handle API call
    chrome.runtime.sendMessage(
      {
        action: "sendChatRequest",
        messages: contextualizedMessages,
        model: config.model,
      },
      (response) => {
        chatState.isLoading = false;

        if (response.error) {
          addMessage("system", `Error: ${response.error}`);
        }
      }
    );
  } catch (error) {
    // Remove loading indicator
    document.getElementById("ai-chat-messages").removeChild(loadingMessage);
    chatState.isLoading = false;

    // Show error
    addMessage("system", `Error: ${error.message}`);
  }
}

// Prepare messages with added context
function prepareMessagesWithContext() {
  const messages = [...chatState.messages];

  // If we have video context, add it as system message at the beginning
  if (chatState.videoContext) {
    let transcriptSection = "";

    // Add transcript if available
    if (chatState.transcript) {
      // Format transcript into a readable string
      const formattedTranscript = chatState.transcript
        .map((entry) => `${entry.text}`)
        .join("\n");

      transcriptSection = `\n\nTranscript:\n${formattedTranscript}`;
    }

    // Add user memories if available
    let userMemoriesSection = "";
    if (chatState.userMemories && chatState.userMemories.length > 0) {
      const formattedMemories = chatState.userMemories
        .map((memory) => `${memory.memory}`)
        .join("\n");

      userMemoriesSection = `\n\nUser Memories:\n${formattedMemories}\n\n`;
    }

    const systemContent = `You are an AI assistant helping with a YouTube video. Here's the context:
      Title: ${chatState.videoContext.title}
      Channel: ${chatState.videoContext.channel}
      URL: ${chatState.videoContext.url}
      
      ${
        userMemoriesSection
          ? `Use the user memories below to personalize your response based on their past interactions and interests. These memories represent relevant past conversations and information about the user.
      ${userMemoriesSection}
      `
          : ""
      }

      Please provide helpful, relevant information based on the video's content.
      ${
        transcriptSection
          ? `"Use the transcript below to provide accurate answers about the video. Ignore if the transcript doesn't make sense."
        ${transcriptSection}
        `
          : "Since the transcript is not available, focus on general questions about the topic and use the video title for context. If asked about specific parts of the video content, politely explain that the video doesn't have a transcript."
      }
      
      Be concise and helpful in your responses.
    `;

    messages.unshift({
      role: "system",
      content: systemContent,
    });
  }

  return messages;
}

// Listen for commands from the background script or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "toggleChat") {
    const container = document.getElementById("ai-chat-assistant-container");
    chatState.isVisible = !chatState.isVisible;

    if (chatState.isVisible) {
      container.classList.add("visible");
    } else {
      container.classList.remove("visible");
    }

    sendResponse({ success: true });
  } else if (message.action === "streamChunk") {
    // Handle streaming chunks
    if (chatState.currentStreamingMessage) {
      const currentContent = chatState.currentStreamingMessage.innerHTML;
      chatState.currentStreamingMessage.innerHTML = formatStreamingText(currentContent + message.chunk);
      
      // Scroll to bottom
      const messagesContainer = document.getElementById("ai-chat-messages");
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }
});

// Load memories from mem0
async function loadMemories() {
  try {
    const memoriesContainer = document.getElementById("memories-list");
    memoriesContainer.innerHTML =
      '<div class="loading">Loading memories...</div>';

    // If client isn't initialized, try to initialize it
    if (!mem0client) {
      const initialized = await initializeMem0AI();
      if (!initialized) {
        memoriesContainer.innerHTML =
          '<div class="error">Please set your Mem0 API key in the extension options.</div>';
        return;
      }
    }

    const response = await mem0client.getAll({
      user_id: "youtube-assistant-mem0",
      page: 1,
      page_size: 50,
    });

    if (response && response.results) {
      memoriesContainer.innerHTML = "";
      response.results.forEach((memory) => {
        const memoryElement = document.createElement("div");
        memoryElement.className = "memory-item";
        memoryElement.textContent = memory.memory;
        memoriesContainer.appendChild(memoryElement);
      });

      if (response.results.length === 0) {
        memoriesContainer.innerHTML =
          '<div class="no-memories">No memories found</div>';
      }
    } else {
      memoriesContainer.innerHTML =
        '<div class="no-memories">No memories found</div>';
    }
  } catch (error) {
    console.error("Error loading memories:", error);
    document.getElementById("memories-list").innerHTML =
      '<div class="error">Error loading memories. Please try again.</div>';
  }
}
