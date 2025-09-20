// src/components/ui/image-upload.tsx
"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, X } from "lucide-react";
import Image from "next/image";

interface ImageUploadProps {
  value: string | null; // Current image URL
  onChange: (file: File) => void; // Callback when a new file is selected
  isUploading: boolean;
}

export function ImageUpload({
  value,
  onChange,
  isUploading,
}: ImageUploadProps) {
  const [preview, setPreview] = useState<string | null>(value);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles[0]) {
        const file = acceptedFiles[0];
        setPreview(URL.createObjectURL(file));
        onChange(file);
      }
    },
    [onChange]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpeg", ".jpg", ".png", ".webp"] },
    maxFiles: 1,
  });

  const removePreview = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPreview(null);
    // You might want a callback here to remove the image from the backend too
  };

  return (
    <div
      {...getRootProps()}
      className={`relative w-full aspect-video border-2 border-dashed rounded-lg flex items-center justify-center text-center cursor-pointer transition-all ${
        isDragActive ? "border-primary bg-primary/10" : "border-border"
      }`}
    >
      <input {...getInputProps()} />
      {preview ? (
        <>
          <Image
            src={preview}
            alt="Event image preview"
            fill
            className="object-cover rounded-md"
          />
          <button
            onClick={removePreview}
            className="absolute top-2 right-2 bg-background/50 backdrop-blur-sm rounded-full p-1 text-foreground transition-all hover:scale-110"
          >
            <X className="h-4 w-4" />
          </button>
        </>
      ) : (
        <div className="flex flex-col items-center">
          <UploadCloud className="h-10 w-10 text-muted-foreground mb-2" />
          <p className="font-semibold">
            {isDragActive
              ? "Drop the image here"
              : "Drag & drop or click to upload"}
          </p>
          <p className="text-xs text-muted-foreground">PNG, JPG, WEBP</p>
        </div>
      )}
      {isUploading && (
        <div className="absolute inset-0 bg-background/80 flex items-center justify-center rounded-lg">
          <div className="text-center">
            <p className="font-semibold text-lg">Uploading...</p>
            <p className="text-sm text-muted-foreground">Please wait.</p>
          </div>
        </div>
      )}
    </div>
  );
}
