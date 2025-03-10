import { useState } from 'react';
import { FileInfo } from '@/types';
import { convertToBase64, getFileBuffer } from '@/utils/fileUtils';

interface UseFileHandlerReturn {
  selectedFile: FileInfo | null;
  file: File | null;
  fileData: string | Buffer | null;
  setSelectedFile: (file: FileInfo | null) => void;
  handleFile: (file: File) => Promise<void>;
  clearFile: () => void;
}

export const useFileHandler = (): UseFileHandlerReturn => {
  const [selectedFile, setSelectedFile] = useState<FileInfo | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileData, setFileData] = useState<string | Buffer | null>(null);

  const handleFile = async (file: File) => {
    setFile(file);
    
    if (file.type.startsWith('image/')) {
      const base64Data = await convertToBase64(file);
      setFileData(base64Data);
    } else if (file.type.startsWith('audio/')) {
      const bufferData = await getFileBuffer(file);
      setFileData(bufferData);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    setFile(null);
    setFileData(null);
  };

  return {
    selectedFile,
    file,
    fileData,
    setSelectedFile,
    handleFile,
    clearFile,
  };
}; 