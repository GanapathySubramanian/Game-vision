import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Box,
  Typography,
  LinearProgress,
  Alert,
  Button,
  Paper,
} from '@mui/material';
import {
  CloudUpload,
  VideoFile,
  CheckCircle,
  Error,
  Analytics,
  PlayArrow,
} from '@mui/icons-material';

interface VideoUploadProps {
  onUpload: (file: File) => Promise<void>;
  onAnalyze?: (videoId: string) => Promise<void>;
  isUploading: boolean;
  uploadProgress: number;
  error?: string | null;
  onClearError?: () => void;
  uploadedVideo?: {
    videoId: string;
    fileName: string;
    s3Uri: string;
  } | null;
  analysisStatus?: 'ready' | 'analyzing' | 'complete' | 'error';
}

const VideoUpload: React.FC<VideoUploadProps> = ({
  onUpload,
  onAnalyze,
  isUploading,
  uploadProgress,
  error,
  onClearError,
  uploadedVideo,
  analysisStatus = 'ready',
}) => {

  const handleAnalyzeClick = async () => {
    if (uploadedVideo && onAnalyze) {
      try {
        await onAnalyze(uploadedVideo.videoId);
      } catch (err) {
        console.error('Analysis failed:', err);
      }
    }
  };
  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        try {
          await onUpload(file);
        } catch (err) {
          console.error('Upload failed:', err);
        }
      }
    },
    [onUpload]
  );

  const {
    getRootProps,
    getInputProps,
    isDragActive,
    isDragReject,
  } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
    },
    multiple: false,
    disabled: isUploading,
    maxSize: 500 * 1024 * 1024, // 200MB
  });

  const getDropzoneContent = () => {
    if (isUploading) {
      return (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <CloudUpload sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Uploading Video...
          </Typography>
          <Box sx={{ width: '100%', mt: 2 }}>
            <LinearProgress
              variant="determinate"
              value={uploadProgress}
              sx={{ height: 8, borderRadius: 4 }}
            />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {Math.round(uploadProgress)}% complete
            </Typography>
          </Box>
        </Box>
      );
    }

    if (uploadProgress === 100) {
      return (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <CheckCircle sx={{ fontSize: 48, color: 'success.main', mb: 2 }} />
          <Typography variant="h6" color="success.main">
            Upload Complete!
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Starting video analysis...
          </Typography>
        </Box>
      );
    }

    if (isDragReject) {
      return (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Error sx={{ fontSize: 48, color: 'error.main', mb: 2 }} />
          <Typography variant="h6" color="error.main">
            Invalid File Type
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Please upload a valid video file (MP4, MOV, AVI, MKV, WebM)
          </Typography>
        </Box>
      );
    }

    if (isDragActive) {
      return (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <CloudUpload sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
          <Typography variant="h6" color="primary.main">
            Drop your video here
          </Typography>
        </Box>
      );
    }

    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <VideoFile sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
        <Typography variant="h6" gutterBottom>
          Upload Gameplay Video
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Drag and drop your video here, or click to browse
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Supported formats: MP4, MOV, AVI, MKV, WebM (max 200MB)
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Button variant="outlined" component="span">
            Choose File
          </Button>
        </Box>
      </Box>
    );
  };

  return (
    <Box>
      {error && (
        <Alert
          severity="error"
          onClose={onClearError}
          sx={{ mb: 2 }}
        >
          {error}
        </Alert>
      )}
      
      <Paper
        {...getRootProps()}
        elevation={isDragActive ? 4 : 1}
        sx={{
          border: 2,
          borderStyle: 'dashed',
          borderColor: isDragActive
            ? 'primary.main'
            : isDragReject
            ? 'error.main'
            : (theme) => theme.palette.mode === 'dark' ? 'grey.700' : 'grey.300',
          borderRadius: 2,
          cursor: isUploading ? 'default' : 'pointer',
          transition: 'all 0.2s ease-in-out',
          bgcolor: isDragActive
            ? (theme) => theme.palette.mode === 'dark' ? 'primary.900' : 'primary.50'
            : isDragReject
            ? (theme) => theme.palette.mode === 'dark' ? 'error.900' : 'error.50'
            : 'background.paper',
          '&:hover': {
            borderColor: isUploading ? (theme) => theme.palette.mode === 'dark' ? 'grey.700' : 'grey.300' : 'primary.main',
            bgcolor: isUploading ? 'background.paper' : (theme) => theme.palette.mode === 'dark' ? 'primary.900' : 'primary.50',
          },
        }}
      >
        <input {...getInputProps()} />
        {getDropzoneContent()}
      </Paper>

      {/* Uploaded Video Status */}
      {uploadedVideo && (
        <Paper elevation={2} sx={{ mt: 2, p: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <PlayArrow sx={{ color: 'success.main', mr: 1 }} />
            <Typography variant="h6" color="success.main">
              Video Ready
            </Typography>
          </Box>
          
          <Typography variant="body1" sx={{ mb: 1, fontWeight: 500 }}>
            {uploadedVideo.fileName}
          </Typography>
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Video ID: {uploadedVideo.videoId}
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button
              variant="contained"
              startIcon={
                analysisStatus === 'analyzing' ? (
                  <Analytics sx={{ animation: 'pulse 1.5s infinite' }} />
                ) : (
                  <Analytics />
                )
              }
              onClick={handleAnalyzeClick}
              disabled={analysisStatus === 'analyzing'}
              sx={{
                bgcolor: analysisStatus === 'complete' ? 'success.main' : 'primary.main',
                '&:hover': {
                  bgcolor: analysisStatus === 'complete' ? 'success.dark' : 'primary.dark',
                },
              }}
            >
              {analysisStatus === 'analyzing' && 'Analyzing...'}
              {analysisStatus === 'ready' && 'Analyze Video'}
              {analysisStatus === 'complete' && 'Analysis Complete'}
              {analysisStatus === 'error' && 'Retry Analysis'}
            </Button>

            {analysisStatus === 'analyzing' && (
              <Box sx={{ flex: 1 }}>
                <LinearProgress sx={{ height: 6, borderRadius: 3 }} />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                  Processing video with Bedrock Data Automation...
                </Typography>
              </Box>
            )}

            {analysisStatus === 'complete' && (
              <Typography variant="body2" color="success.main" sx={{ fontWeight: 500 }}>
                ✓ Ready for questions
              </Typography>
            )}
          </Box>
        </Paper>
      )}
    </Box>
  );
};

export default VideoUpload;
