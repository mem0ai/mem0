import { Buffer } from 'buffer';

export const convertToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = error => reject(error);
  });
};

export const getFileBuffer = async (file: File): Promise<Buffer> => {
  const response = await fetch(URL.createObjectURL(file));
  const arrayBuffer = await response.arrayBuffer();
  return Buffer.from(arrayBuffer);
}; 