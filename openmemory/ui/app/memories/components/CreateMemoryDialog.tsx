"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useCallback, useRef, useState } from "react";
import { GoPlus } from "react-icons/go";
import {
  Paperclip,
  FileText,
  X,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { toast } from "sonner";

type InputMode = "text" | "file";
type Status = "idle" | "loading" | "success" | "error";

const ACCEPTED_EXTENSIONS = [".pdf", ".txt", ".docx"];
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "text/plain",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isAcceptedFile(file: File): boolean {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  return ACCEPTED_EXTENSIONS.includes(ext) || ACCEPTED_MIME_TYPES.includes(file.type);
}

export function CreateMemoryDialog() {
  const { createMemory, uploadMemoryFile, fetchMemories } = useMemoriesApi();

  const [open, setOpen] = useState(false);
  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [status, setStatus] = useState<Status>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [memoriesCreated, setMemoriesCreated] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  const textRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setInputMode("text");
    setStatus("idle");
    setFile(null);
    setMemoriesCreated(0);
    setIsDragging(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (textRef.current) textRef.current.value = "";
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) reset();
    setOpen(next);
  };

  const attachFile = (f: File) => {
    if (!isAcceptedFile(f)) {
      toast.error("Use PDF, TXT, or DOCX.");
      return;
    }
    setFile(f);
    setInputMode("file");
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) attachFile(f);
  }, []);

  const handleSubmit = async () => {
    setStatus("loading");
    try {
      if (inputMode === "text") {
        const text = textRef.current?.value?.trim() || "";
        if (!text) { setStatus("idle"); return; }
        await createMemory(text);
        setStatus("success");
        await fetchMemories();
      } else {
        if (!file) { setStatus("idle"); return; }
        const result = await uploadMemoryFile(file);
        setMemoriesCreated(result.memories_created);
        setStatus("success");
        await fetchMemories();
      }
    } catch {
      setStatus("error");
    }
  };

  const isLoading = status === "loading";
  const isDone = status === "success" || status === "error";

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="bg-primary hover:bg-primary/90 text-white border-0"
        onClick={() => setOpen(true)}
      >
        <GoPlus />
        Add Memory
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-[460px] bg-zinc-900 border-zinc-800 p-5 gap-4">
          <DialogHeader className="pb-0">
            <DialogTitle className="text-sm font-semibold text-zinc-100">
              Add Memory
            </DialogTitle>
          </DialogHeader>

          {/* Result states */}
          {status === "success" && (
            <div className="flex flex-col items-center gap-3 py-6">
              <CheckCircle2 className="w-8 h-8 text-emerald-500" />
              <p className="text-sm text-zinc-200 font-medium">
                {inputMode === "file"
                  ? `${memoriesCreated} ${memoriesCreated === 1 ? "memory" : "memories"} saved`
                  : "Memory saved"}
              </p>
              <Button size="sm" onClick={() => handleOpenChange(false)}>
                Done
              </Button>
            </div>
          )}

          {status === "error" && (
            <div className="flex flex-col items-center gap-3 py-6">
              <AlertCircle className="w-8 h-8 text-red-500" />
              <p className="text-sm text-zinc-200 font-medium">Something went wrong</p>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" className="text-zinc-400" onClick={() => handleOpenChange(false)}>
                  Cancel
                </Button>
                <Button size="sm" onClick={() => setStatus("idle")}>
                  Try Again
                </Button>
              </div>
            </div>
          )}

          {/* Input area */}
          {!isDone && (
            <>
              <div
                onDrop={handleDrop}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                className={[
                  "relative rounded-lg border transition-colors overflow-hidden",
                  isDragging ? "border-primary/60 bg-primary/5" : "border-zinc-800 bg-zinc-950",
                ].join(" ")}
              >
                {inputMode === "text" ? (
                  <>
                    <textarea
                      ref={textRef}
                      disabled={isLoading}
                      placeholder="e.g., Prefers concise explanations over lengthy ones…"
                      autoFocus
                      className="w-full bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 resize-none outline-none px-3 pt-3 pb-9 min-h-[130px] disabled:opacity-50"
                    />
                    {/* Attach file button — lives inside the input */}
                    <div className="absolute bottom-2.5 right-2.5 flex items-center gap-1.5">
                      <span className="text-xs text-zinc-700 select-none">
                        or drop a file
                      </span>
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => fileInputRef.current?.click()}
                        className="flex items-center justify-center w-6 h-6 rounded text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800 transition-colors disabled:pointer-events-none"
                        title="Attach PDF, TXT, or DOCX"
                      >
                        <Paperclip className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </>
                ) : (
                  /* File selected state */
                  <div className="flex items-center gap-3 p-3">
                    <div className="rounded-md bg-zinc-800 p-2 shrink-0">
                      <FileText className="w-4 h-4 text-zinc-300" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-zinc-200 truncate">{file?.name}</p>
                      <p className="text-xs text-zinc-500">
                        {file ? formatFileSize(file.size) : ""} · Memories will be extracted
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={isLoading}
                      onClick={() => { setFile(null); setInputMode("text"); if (fileInputRef.current) fileInputRef.current.value = ""; }}
                      className="shrink-0 p-1 rounded text-zinc-600 hover:text-zinc-200 hover:bg-zinc-800 transition-colors disabled:pointer-events-none"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_EXTENSIONS.join(",")}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) attachFile(f); }}
                className="hidden"
              />

              <div className="flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-zinc-400 hover:text-zinc-200"
                  disabled={isLoading}
                  onClick={() => handleOpenChange(false)}
                >
                  Cancel
                </Button>
                <Button size="sm" disabled={isLoading} onClick={handleSubmit}>
                  {isLoading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : inputMode === "file" ? (
                    "Extract Memories"
                  ) : (
                    "Save Memory"
                  )}
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
