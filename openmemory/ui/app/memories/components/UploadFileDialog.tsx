"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useCallback, useRef, useState } from "react";
import { Upload, FileText, X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { toast } from "sonner";

type UploadState = "idle" | "selected" | "uploading" | "success" | "error";

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

export function UploadFileDialog() {
  const { uploadMemoryFile, fetchMemories } = useMemoriesApi();
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<UploadState>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [memoriesCreated, setMemoriesCreated] = useState<number>(0);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setState("idle");
    setFile(null);
    setMemoriesCreated(0);
    setIsDragging(false);
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleClose = (isOpen: boolean) => {
    if (!isOpen) reset();
    setOpen(isOpen);
  };

  const selectFile = (f: File) => {
    if (!isAcceptedFile(f)) {
      toast.error("Unsupported file type. Please upload a PDF, TXT, or DOCX file.");
      return;
    }
    setFile(f);
    setState("selected");
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) selectFile(f);
  };

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) selectFile(f);
  }, []);

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleUpload = async () => {
    if (!file) return;
    setState("uploading");
    try {
      const result = await uploadMemoryFile(file);
      setMemoriesCreated(result.memories_created);
      setState("success");
      await fetchMemories();
    } catch {
      setState("error");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800"
        >
          <Upload className="w-4 h-4" />
          Upload File
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[480px] bg-zinc-900 border-zinc-800">
        <DialogHeader>
          <DialogTitle>Upload File</DialogTitle>
          <DialogDescription>
            Extract memories from a PDF, TXT, or DOCX file
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {/* Idle / Selected: drop zone */}
          {(state === "idle" || state === "selected") && (
            <>
              <div
                onClick={() => state !== "selected" && inputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                className={`
                  relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed
                  transition-colors cursor-pointer select-none
                  ${isDragging
                    ? "border-primary bg-primary/10"
                    : "border-zinc-700 bg-zinc-950 hover:border-zinc-500 hover:bg-zinc-900"
                  }
                  ${state === "selected" ? "cursor-default hover:border-zinc-700 hover:bg-zinc-950" : ""}
                  py-10 px-6
                `}
              >
                {state === "idle" ? (
                  <>
                    <div className="rounded-full bg-zinc-800 p-3">
                      <Upload className="w-6 h-6 text-zinc-400" />
                    </div>
                    <div className="text-center">
                      <p className="text-sm font-medium text-zinc-200">
                        Drop your file here, or{" "}
                        <span className="text-primary underline underline-offset-2">browse</span>
                      </p>
                      <p className="text-xs text-zinc-500 mt-1">PDF, TXT, DOCX supported</p>
                    </div>
                  </>
                ) : (
                  <div className="flex w-full items-start gap-3">
                    <div className="rounded-md bg-zinc-800 p-2 shrink-0">
                      <FileText className="w-5 h-5 text-zinc-300" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-zinc-200 truncate">{file?.name}</p>
                      <p className="text-xs text-zinc-500 mt-0.5">{file ? formatFileSize(file.size) : ""}</p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); reset(); }}
                      className="shrink-0 rounded p-1 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}
                <input
                  ref={inputRef}
                  type="file"
                  accept={ACCEPTED_EXTENSIONS.join(",")}
                  onChange={handleFileInput}
                  className="hidden"
                />
              </div>
              {state === "selected" && (
                <p
                  className="text-xs text-zinc-500 mt-2 text-center cursor-pointer hover:text-zinc-300 transition-colors"
                  onClick={() => inputRef.current?.click()}
                >
                  Choose a different file
                </p>
              )}
            </>
          )}

          {/* Uploading */}
          {state === "uploading" && (
            <div className="flex flex-col items-center gap-4 py-6">
              <Loader2 className="w-10 h-10 text-primary animate-spin" />
              <div className="text-center">
                <p className="text-sm font-medium text-zinc-200">Processing file…</p>
                <p className="text-xs text-zinc-500 mt-1">Extracting and storing memories</p>
              </div>
            </div>
          )}

          {/* Success */}
          {state === "success" && (
            <div className="flex flex-col items-center gap-4 py-6">
              <CheckCircle2 className="w-10 h-10 text-green-500" />
              <div className="text-center">
                <p className="text-sm font-medium text-zinc-200">Upload complete</p>
                <p className="text-xs text-zinc-500 mt-1">
                  {memoriesCreated} {memoriesCreated === 1 ? "memory" : "memories"} created from{" "}
                  <span className="text-zinc-300">{file?.name}</span>
                </p>
              </div>
            </div>
          )}

          {/* Error */}
          {state === "error" && (
            <div className="flex flex-col items-center gap-4 py-6">
              <AlertCircle className="w-10 h-10 text-red-500" />
              <div className="text-center">
                <p className="text-sm font-medium text-zinc-200">Upload failed</p>
                <p className="text-xs text-zinc-500 mt-1">
                  Something went wrong. Please try again.
                </p>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          {(state === "idle" || state === "selected" || state === "error") && (
            <Button variant="outline" onClick={() => handleClose(false)}>
              Cancel
            </Button>
          )}

          {(state === "idle" || state === "selected") && (
            <Button disabled={state !== "selected"} onClick={handleUpload}>
              Upload
            </Button>
          )}

          {state === "uploading" && (
            <Button disabled>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Uploading…
            </Button>
          )}

          {state === "success" && (
            <Button onClick={() => handleClose(false)}>Done</Button>
          )}

          {state === "error" && (
            <Button onClick={() => setState("selected")}>Try Again</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
