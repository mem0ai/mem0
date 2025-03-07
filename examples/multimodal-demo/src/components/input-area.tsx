import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import GlobalContext from "@/contexts/GlobalContext";
import { FileInfo } from "@/types";
import { Images, Send, X } from "lucide-react";
import { useContext, useRef, useState } from "react";

const InputArea = () => {
  const [inputValue, setInputValue] = useState("");
  const { handleSend, selectedFile, setSelectedFile, setFile } = useContext(GlobalContext);
  const [loading, setLoading] = useState(false);

  const ref = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setSelectedFile({
        name: file.name,
        type: file.type,
        size: file.size
      })
      setFile(file)
    }
  }

  const handleSendController = async () => {
    setLoading(true);
    setInputValue("");
    await handleSend(inputValue);
    setLoading(false);

    // focus on input
    setTimeout(() => {
      ref.current?.focus();
    }, 0);
  };

  const handleClosePopup = () => {
    setSelectedFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <>
      <div className="border-t p-4">
        <div className="flex items-center space-x-2">
          <div className="relative bottom-3 left-5">
          <div className="absolute">
          <Input
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            ref={fileInputRef}
            className="sr-only"
            id="file-upload"
          />
          <label
            htmlFor="file-upload"
            className="flex items-center justify-center w-6 h-6 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 cursor-pointer"
          >
            <Images className="h-4 w-4" />
          </label>
          {selectedFile && <FileInfoPopup file={selectedFile} onClose={handleClosePopup} />}
        </div>
          </div>
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSendController()}
            placeholder="Type a message..."
            className="flex-1 pl-10 rounded-3xl"
            disabled={loading}
            ref={ref}
          />
          <div className="relative right-14 bottom-5 flex">
          <Button className="absolute rounded-full w-10 h-10 bg-transparent hover:bg-transparent cursor-pointer z-20 text-primary" onClick={handleSendController} disabled={!inputValue.trim() || loading}>
            <Send className="h-8 w-8" size={50} />
          </Button>
          </div>
        </div>
      </div>
    </>
  );
};

const FileInfoPopup = ({ file, onClose }: { file: FileInfo, onClose: () => void }) => {
  return (
   <div className="relative bottom-36">
     <div className="absolute top-full left-0 mt-1 bg-white dark:bg-gray-800 p-2 rounded-md shadow-md border border-gray-200 dark:border-gray-700 z-10 w-48">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-sm truncate">{file.name}</h3>
        <Button variant="ghost" size="sm" onClick={onClose} className="h-5 w-5 p-0">
          <X className="h-3 w-3" />
        </Button>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">Type: {file.type}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400">Size: {(file.size / 1024).toFixed(2)} KB</p>
    </div>
   </div>
  )
}

export default InputArea;
