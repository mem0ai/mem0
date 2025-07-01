# VCF Card Download Feature for SMS

## 1. Goal

To improve user experience after SMS verification, we will add a "Download Contact" button to the settings page. This button will allow users to easily save the Jean Memory SMS number to their phone's contacts. The contact card will include the name "Jean Memory", the phone number, and the company logo.

## 2. File to Modify

All changes will be made in the following file:
`openmemory/ui/app/settings/page.tsx`

## 3. Implementation Steps

### Step 1: Add New Imports

At the top of the file, add `Download` to the `lucide-react` import.

```tsx
// ... existing code ...
import { Key, Plus, Trash2, Copy, AlertTriangle, X, Check, Phone, Download } from 'lucide-react';
// ... existing code ...
```

### Step 2: Create the VCF Download Handler

Inside the `SettingsPage` component, add a new handler function `handleDownloadVCF`. This function will dynamically create the VCF file content and trigger a download.

**Note to Engineer:** The `PHOTO` field requires the image to be base64 encoded. The placeholder `[BASE64_ENCODED_IMAGE_DATA]` must be replaced with the actual base64 string of the image located at `/openmemory/ui/public/images/jean-white-theme-bug.png`.

```tsx
// Inside the SettingsPage component function

const twilioPhoneNumber = "+13648889368"; // The Jean Memory contact number

const handleDownloadVCF = () => {
  // TODO: Replace the placeholder below with the actual base64 encoded image string.
  const imageAsBase64 = "[BASE64_ENCODED_IMAGE_DATA]";
  
  const vcfContent = `BEGIN:VCARD
VERSION:3.0
FN:Jean Memory
TEL;TYPE=CELL:${twilioPhoneNumber}
PHOTO;TYPE=PNG;ENCODING=BASE64:${imageAsBase64}
END:VCARD`;

  const blob = new Blob([vcfContent], { type: "text/vcf;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", "JeanMemory.vcf");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  toast.success("Contact downloaded!", {
    description: "Check your downloads folder for JeanMemory.vcf.",
  });
};
```

### Step 3: Add the "Download Contact" Button

In the JSX, locate the section that displays the user's phone number status. We will add a new button that only appears if the phone number is verified.

Find this block:
```tsx
// ... existing code ...
<div className="flex items-center justify-between">
  {profile.phone_number ? (
    // ... existing code ...
  ) : (
    <Button onClick={() => setIsSmsModalOpen(true)}>
      <Phone className="mr-2 h-4 w-4" /> Connect Phone
    </Button>
  )}
</div>
// ... existing code ...
```

And modify it to look like this:
```tsx
// ... existing code ...
<div className="flex items-center justify-between">
  {profile.phone_number ? (
    <div className="flex items-center space-x-4">
      {/* ... icon and text div ... */}
    </div>
  ) : (
    <div>
      <p className="font-semibold">No phone number connected</p>
      <p className="text-sm text-gray-400">
        Verify your number to send and receive memories via SMS.
      </p>
    </div>
  )}
  {profile.phone_verified ? (
    <Button variant="outline" size="sm" onClick={handleDownloadVCF}>
      <Download className="mr-2 h-4 w-4" />
      Download Contact
    </Button>
  ) : (
    <Button onClick={() => setIsSmsModalOpen(true)}>
      <Phone className="mr-2 h-4 w-4" /> Connect Phone
    </Button>
  )}
</div>
// ... existing code ...
```
This change ensures the "Download Contact" button appears when the number is verified, replacing the "Connect Phone" button.

---

This completes the feature implementation. The result will be a much smoother onboarding experience for users who verify their phone number for SMS integration. 