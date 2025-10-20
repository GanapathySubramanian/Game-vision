import { useState, useCallback } from 'react';
import { videoApi, UploadVideoResponse } from '../services/api';

export interface UseVideoUploadReturn {
  uploadVideo: (file: File) => Promise<UploadVideoResponse>;
  uploadProgress: number;
  isUploading: boolean;
  error: string | null;
  clearError: () => void;
}

export const useVideoUpload = (): UseVideoUploadReturn => {
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadVideo = useCallback(async (file: File): Promise<UploadVideoResponse> => {
    setIsUploading(true);
    setUploadProgress(0);
    setError(null);

    try {
      // Validate file
      if (!file) {
        throw new Error('No file selected');
      }

      // Check file type
      if (!file.type.startsWith('video/')) {
        throw new Error('Please select a valid video file');
      }

      // Check file size (limit to 200MB)
      const maxSize = 500 * 1024 * 1024; // 200MB
      if (file.size > maxSize) {
        throw new Error('File size must be less than 200MB');
      }

      // Step 1: Get presigned URL
      setUploadProgress(10);
      const uploadInfo = await videoApi.getUploadUrl(file.name, file.type);

      // Step 2: Upload to S3
      setUploadProgress(20);
      await videoApi.uploadToS3(uploadInfo.uploadUrl, file, (progress) => {
        // Map S3 upload progress to 20-90% of total progress
        const mappedProgress = 20 + (progress * 0.7);
        setUploadProgress(mappedProgress);
      });

      // Step 3: Complete
      setUploadProgress(100);
      
      return uploadInfo;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsUploading(false);
      // Reset progress after a delay
      setTimeout(() => {
        setUploadProgress(0);
      }, 2000);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    uploadVideo,
    uploadProgress,
    isUploading,
    error,
    clearError,
  };
};
