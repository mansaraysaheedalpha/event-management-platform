// src/hooks/use-image-upload.ts
import { useState } from "react";
import axios from "axios"; // Using axios for easier form-data handling
import { useAuthStore } from "@/store/auth.store";
import { toast } from "sonner";

// Re-configure a base axios instance for REST calls
const apiClient = axios.create({
  baseURL:
    process.env.NEXT_PUBLIC_EVENT_SERVICE_URL || "http://localhost:8000/api/v1",
});

export function useImageUpload(orgId: string, eventId: string) {
  const [isUploading, setIsUploading] = useState(false);
  const token = useAuthStore((state) => state.token);

  const uploadImage = async (file: File) => {
    if (!token) {
      toast.error("Authentication error. Please log in again.");
      return null;
    }

    setIsUploading(true);
    const toastId = toast.loading("Preparing to upload image...");

    try {
      // Step 1: Request a pre-signed URL from our backend
      toast.info("Requesting upload permission...", { id: toastId });
      const { data: uploadData } = await apiClient.post(
        `/organizations/${orgId}/events/${eventId}/image-upload-request`,
        {
          content_type: file.type,
          filename: file.name,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Step 2: Upload the file directly to S3 using the pre-signed URL
      toast.info("Uploading image...", { id: toastId });
      const formData = new FormData();
      Object.entries(uploadData.fields).forEach(([key, value]) => {
        formData.append(key, value as string);
      });
      formData.append("file", file);

      await axios.post(uploadData.url, formData);

      // Step 3: Notify our backend that the upload is complete
      toast.info("Finalizing...", { id: toastId });
      const { data: updatedEvent } = await apiClient.post(
        `/organizations/${orgId}/events/${eventId}/image-upload-complete?s3_key=${uploadData.s3_key}`,
        {}, // Empty body
        { headers: { Authorization: `Bearer ${token}` } }
      );

      toast.success("Image uploaded successfully!", { id: toastId });
      return updatedEvent;
    } catch (error: any) {
      const errorMessage =
        error.response?.data?.detail ||
        error.message ||
        "An unknown error occurred.";
      toast.error(errorMessage, { id: toastId });
      return null;
    } finally {
      setIsUploading(false);
    }
  };

  return { isUploading, uploadImage };
}
