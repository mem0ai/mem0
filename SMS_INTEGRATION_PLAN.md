# Project Plan: SMS Memory Integration

This document outlines the strategy and implementation plan for integrating a new SMS-based memory feature into the Jean Memory platform.

## 1. Vision & User Experience

The core vision is to provide an incredibly accessible way for users to interact with their memories. The user flow should be simple and intuitive:

1.  From the main dashboard, a Pro user clicks "Connect" on an "SMS" integration card.
2.  A modal appears, prompting for their phone number.
3.  They receive a verification code via text message.
4.  After entering the code, their phone is linked.
5.  They can immediately start sending text messages to add and search their memories (e.g., "Remember: My dog's name is Sparky" or "Search: what is my dog's name?").

This feature will be exclusive to **Pro and Enterprise** subscribers. Non-pro users will be prompted to upgrade when they attempt to connect.

## 2. Core Principles

*   **User Experience First**: The integration point must be prominent and easy to find on the main dashboard, not hidden in settings.
*   **Clear "Pro" Gating**: The UI must clearly indicate that this is a Pro feature and prevent non-pro users from starting the connection flow.
*   **Minimal Disruption**: The implementation must not interfere with the existing, critical infrastructure, especially the Cloudflare worker and the core MCP server logic.
*   **Security**: Phone numbers must be verified, and all API endpoints must be authenticated and authorized.

## 3. High-Level Architecture

The implementation will be divided into three main parts: the backend API, the database, and the frontend UI.

![Architecture Diagram](https://i.imgur.com/8Q6zZ9c.png)

### 3.1. Backend API

To maintain separation from the core MCP logic, we will create two new, isolated API routers:

*   **`profile.py`**: This router will handle user-facing profile management. It will expose endpoints for the frontend to:
    *   Fetch user profile data (including subscription tier and phone number status).
    *   Add/update a phone number and trigger the verification process.
    *   Submit a verification code.
*   **`webhooks.py`**: This router will contain a single endpoint (`/webhooks/twilio/sms`) dedicated to handling incoming SMS messages from Twilio. Its responsibilities include:
    *   Authenticating the request is from the user's verified phone number.
    *   Enforcing the Pro subscription requirement.
    *   Parsing the SMS content for commands (`remember:`, `search:`).
    *   Interacting with the `mem0` memory client.
    *   Sending a reply back to the user via SMS.

### 3.2. Database

The `User` model in `openmemory/api/app/models.py` will be extended to include two new fields:

*   `phone_number` (String, unique): To store the user's phone number.
*   `phone_verified` (Boolean): A flag to indicate whether the user has successfully completed the verification process.

A verification code will be temporarily stored in the user's `metadata_` JSON field during the verification flow.

### 3.3. Frontend UI

The user interface changes will be focused on the new dashboard:

*   **`dashboard-new/page.tsx`**:
    *   A new "SMS" entry will be added to the `availableApps` array to render an integration card, which will be visually marked as a "Pro" feature.
    *   The `handleConnectApp` function will be updated. When a user clicks the "SMS" card, it will first check their subscription tier.
        *   If the user is `PRO` or `ENTERPRISE`, it will launch the `SmsModal`.
        *   If the user is `FREE`, it will show a toast notification or a separate "Upgrade to Pro" modal instead of the connection modal.
*   **`components/dashboard/SmsModal.tsx`**: A new, self-contained modal component will be created to manage the entire connection flow (phone number input, verification code input, and success/error states).

## 4. Implementation Roadmap

### Phase 1: Backend Foundation

1.  **Modify Database Model**: Add `phone_number` and `phone_verified` to the `User` model.
2.  **Create SMS Utility**: Implement a `utils/sms.py` module to handle communication with the Twilio API.
3.  **Build Profile API**: Create the `routers/profile.py` file with all necessary endpoints for the frontend to manage phone numbers.
4.  **Build Webhook**: Create the `routers/webhooks.py` file to handle incoming SMS messages from Twilio.
5.  **Integrate Routers**: Add the new `profile` and `webhooks` routers to the main FastAPI application in `routers/__init__.py`.

### Phase 2: Frontend Integration

1.  **Create SMS Modal**: Build the `SmsModal.tsx` component.
2.  **Update Dashboard**: Add the "SMS" app to the `availableApps` list in `dashboard-new/page.tsx`.
3.  **Trigger Modal**: Update the `handleConnectApp` logic in `dashboard-new/page.tsx` to open the `SmsModal` only for Pro users.

This plan ensures a robust, secure, and user-friendly implementation while protecting the stability of the existing platform. 