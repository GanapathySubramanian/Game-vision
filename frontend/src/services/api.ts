import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    console.log(`API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export interface UploadVideoResponse {
  uploadUrl: string;
  s3Uri: string;
  videoId: string;
}

export interface VideoStatus {
  videoId: string;
  status: 'uploaded' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
}

export interface AnalysisResults {
  videoId: string;
  analysisStatus: string;
  standardOutput?: any;
  customOutput?: any;
  metadata?: any;
  processingTime?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  videoId?: string;
  relevantTimestamps?: Array<{
    timestamp: string;
    description: string;
    relevance: number;
  }>;
  relatedPlayers?: string[];
}

export interface BedrockAgentResponse {
  sessionId: string;
  output: {
    text: string;
  };
  citations?: any[];
  trace?: any;
}

// Video Management API
export const videoApi = {
  // Get presigned URL for video upload
  getUploadUrl: async (fileName: string, contentType: string = 'video/mp4'): Promise<UploadVideoResponse> => {
    const response = await api.post('/api/video/upload-url', {
      fileName,
      contentType,
    });
    return response.data;
  },

  // Upload video to S3 using presigned URL
  uploadToS3: async (uploadUrl: string, file: File, onProgress?: (progress: number) => void): Promise<void> => {
    await axios.put(uploadUrl, file, {
      headers: {
        'Content-Type': file.type,
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
  },

};


// Bedrock Agent API
export const agentApi = {
  // Start conversation with Bedrock Agent
  startConversation: async (videoId?: string): Promise<{ sessionId: string }> => {
    const response = await api.post('/api/agent/conversation/start', {
      videoId,
    });
    return response.data;
  },

  // Send message to Bedrock Agent
  sendMessage: async (
    sessionId: string,
    message: string,
    videoId?: string
  ): Promise<BedrockAgentResponse> => {
    const response = await api.post('/api/agent/conversation/message', {
      sessionId,
      message,
      videoId,
    });
    return response.data;
  },

  // End conversation
  endConversation: async (sessionId: string): Promise<void> => {
    await api.post('/api/agent/conversation/end', {
      sessionId,
    });
  },
};


export default api;
