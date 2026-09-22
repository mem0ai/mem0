import { useState } from "react";

import { CheckIcon, CopyIcon } from "@radix-ui/react-icons";
import { CopyToClipboard } from "react-copy-to-clipboard";

interface CopyButtonProps {
  textToCopy: string;
}

const CopyButton: React.FC<CopyButtonProps> = ({ textToCopy }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    setCopied(true);
    setTimeout(() => {
      setCopied(false);
    }, 2000);
  };

  return (
    <CopyToClipboard text={textToCopy} onCopy={handleCopy}>
      <button
        type="button"
        className="absolute top-2 right-2 bg-white hover:bg-gray-100 p-2 text-black rounded-md"
      >
        {copied ? (
          <CheckIcon className="size-3" />
        ) : (
          <CopyIcon className="size-3" />
        )}
      </button>
    </CopyToClipboard>
  );
};

export default CopyButton;
